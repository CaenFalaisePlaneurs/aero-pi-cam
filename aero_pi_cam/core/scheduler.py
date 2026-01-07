"""Scheduling logic for capture jobs."""

import logging
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.date import DateTrigger  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from ..weather.day_night import get_day_night_mode
from ..weather.sun import get_sun_times
from .config import Config
from .debug import debug_print


class MisfireWarningFilter(logging.Filter):
    """Filter to suppress APScheduler misfire warnings."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out misfire warnings from APScheduler."""
        # Suppress warnings about missed job runs (expected when service restarts)
        if "was missed by" in record.getMessage():
            return False
        return True


def _configure_scheduler_logger() -> None:
    """Configure APScheduler logger to suppress misfire warnings."""
    apscheduler_logger = logging.getLogger("apscheduler")
    # Add filter to suppress misfire warnings
    # Apply filter to logger and all its handlers
    apscheduler_logger.addFilter(MisfireWarningFilter())
    for handler in apscheduler_logger.handlers:
        handler.addFilter(MisfireWarningFilter())
    # Also apply to root logger handlers (APScheduler may propagate)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(MisfireWarningFilter())


def get_next_transition_time(now: datetime, config: Config | None) -> datetime | None:
    """Get the next day/night transition time.

    Args:
        now: Current UTC datetime
        config: Configuration object

    Returns:
        Next transition time (UTC datetime) or None if debug mode or config is None
        Returns sunrise if currently night, sunset if currently day
    """
    if config is None:
        return None

    # Skip transition checking in debug mode
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"
    if debug_enabled:
        return None

    # Determine if currently day or night
    is_day_time = get_day_night_mode(now, config)

    # Get sun times for today
    sun_times = get_sun_times(now, config.location)
    sunrise = sun_times["sunrise"]
    sunset = sun_times["sunset"]

    # Get next transition: sunrise if night, sunset if day
    if is_day_time:
        # Currently day, next transition is sunset
        next_transition = sunset
        # If sunset already passed today, get tomorrow's sunset
        if sunset <= now:
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            sun_times_tomorrow = get_sun_times(tomorrow, config.location)
            next_transition = sun_times_tomorrow["sunset"]
    else:
        # Currently night, next transition is sunrise
        next_transition = sunrise
        # If sunrise already passed today, get tomorrow's sunrise
        if sunrise <= now:
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            sun_times_tomorrow = get_sun_times(tomorrow, config.location)
            next_transition = sun_times_tomorrow["sunrise"]

    return next_transition


async def log_countdown(scheduler: AsyncIOScheduler | None, config: Config | None) -> None:
    """Log countdown until next capture in debug mode.

    Args:
        scheduler: APScheduler instance
        config: Configuration object
    """
    if scheduler is None:
        return

    # Double-check debug mode is enabled (safety check)
    if config is None:
        return
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"
    if not debug_enabled:
        return

    try:
        job = scheduler.get_job("capture_job")
        if not job:
            return

        if not job.next_run_time:
            # Job exists but next run time not set yet
            print("Next capture in: scheduling...", end="\r", flush=True)
            return

        now = datetime.now(UTC)
        # Ensure next_run_time is timezone-aware
        next_run = job.next_run_time
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=UTC)
        elif next_run.tzinfo != UTC:
            next_run = next_run.astimezone(UTC)

        remaining = (next_run - now).total_seconds()
        # Add small buffer to account for timing precision
        if remaining > 0.5:
            remaining_int = int(remaining)
            hours = remaining_int // 3600
            minutes = (remaining_int % 3600) // 60
            seconds = remaining_int % 60
            countdown_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            print(f"Next capture in: {countdown_str}", end="\r", flush=True)
        else:
            # Job is executing or about to execute
            print("Next capture in: executing...", end="\r", flush=True)
    except Exception:
        # Silently ignore errors (job might not exist yet)
        pass


async def schedule_next_capture(
    scheduler: AsyncIOScheduler | None,
    config: Config | None,
    capture_and_upload_func: Callable[[], Awaitable[None]],
    schedule_func: Callable[[], Awaitable[None]] | None = None,
) -> AsyncIOScheduler:
    """Schedule captures with dynamic interval based on day/night.

    Args:
        scheduler: APScheduler instance (will be created if None)
        config: Configuration object
        capture_and_upload_func: Function to call for capture and upload
        schedule_func: Optional function to call for schedule re-evaluation (for recursive scheduling)

    Returns:
        APScheduler instance (created or updated)
    """
    if config is None:
        return

    now = datetime.now(UTC)
    time_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Re-evaluating schedule at {time_str}")
    is_day_time = get_day_night_mode(now, config)
    mode_str = "day" if is_day_time else "night"

    # Check if debug mode override is active
    debug_override = os.getenv("DEBUG_DAY_NIGHT_MODE", "").lower()
    if debug_override in ("day", "night"):
        mode_str += f" (forced via DEBUG_DAY_NIGHT_MODE={debug_override})"

    # Check if debug mode is enabled (via env var)
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"

    # Use debug intervals if enabled, otherwise use normal intervals
    if debug_enabled:
        # Get debug intervals from config if available, otherwise use defaults
        if config.debug:
            interval_seconds = (
                config.debug.day_interval_seconds
                if is_day_time
                else config.debug.night_interval_seconds
            )
        else:
            # Default debug intervals if config not provided
            interval_seconds = 10 if is_day_time else 30

        # Format timer as h:m:s
        hours = interval_seconds // 3600
        minutes = (interval_seconds % 3600) // 60
        seconds = interval_seconds % 60
        timer_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        debug_print(f"Schedule mode: {mode_str} (DEBUG), capture timer: {timer_str}")

        # Update or create scheduler
        if scheduler is None:
            _configure_scheduler_logger()
            scheduler = AsyncIOScheduler()
            scheduler.start()
        else:
            # Remove existing jobs if they exist
            try:
                scheduler.remove_job("capture_job")
            except Exception:
                pass
            try:
                scheduler.remove_job("schedule_check")
            except Exception:
                pass
            try:
                scheduler.remove_job("countdown_log")
            except Exception:
                pass

        scheduler.add_job(
            capture_and_upload_func,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id="capture_job",
            max_instances=1,  # Prevent concurrent executions
            coalesce=True,  # Run at most once if multiple runs are missed
            misfire_grace_time=60,  # Ignore missed runs if more than 60 seconds late
        )

        # Re-evaluate schedule every 30 seconds for day/night transitions in debug mode
        if schedule_func:
            scheduler.add_job(
                schedule_func,
                trigger=IntervalTrigger(seconds=30),
                id="schedule_check",
                coalesce=True,  # Run at most once if multiple runs are missed
                misfire_grace_time=30,  # Ignore missed runs if more than 30 seconds late
            )

        # Log countdown every second in debug mode (with coalesce and misfire_grace_time to avoid missed run warnings)
        async def _log_countdown_wrapper() -> None:
            await log_countdown(scheduler, config)

        scheduler.add_job(
            _log_countdown_wrapper,
            trigger=IntervalTrigger(seconds=1),
            id="countdown_log",
            coalesce=True,  # Run at most once if multiple runs are missed
            misfire_grace_time=5,  # Ignore missed runs if more than 5 seconds late
            max_instances=1,
        )
    else:
        # Use the already-calculated is_day_time to select interval
        interval_seconds = (
            config.schedule.day_interval_seconds
            if is_day_time
            else config.schedule.night_interval_seconds
        )
        # Format timer as h:m:s
        hours = interval_seconds // 3600
        minutes = (interval_seconds % 3600) // 60
        seconds = interval_seconds % 60
        timer_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        debug_print(f"Schedule mode: {mode_str}, capture timer: {timer_str}")

        # Calculate next capture time using current interval
        next_capture_time = now + timedelta(seconds=interval_seconds)

        # Get next transition time (returns None in debug mode or if config is None)
        next_transition_time = get_next_transition_time(now, config)

        # Determine which is sooner: transition time or interval-based time
        use_transition = False
        if next_transition_time is not None and next_transition_time < next_capture_time:
            # Only use transition if it's in the future (not a past time)
            if next_transition_time > now:
                use_transition = True
                next_capture_time = next_transition_time

        # Update or create scheduler
        if scheduler is None:
            _configure_scheduler_logger()
            scheduler = AsyncIOScheduler()
            scheduler.start()

            # Schedule capture job
            if use_transition:
                # Create wrapper that calls capture_and_upload_func then schedule_func
                async def _transition_capture_wrapper() -> None:
                    await capture_and_upload_func()
                    if schedule_func:
                        await schedule_func()

                scheduler.add_job(
                    _transition_capture_wrapper,
                    trigger=DateTrigger(run_date=next_capture_time),
                    id="capture_job",
                    max_instances=1,  # Prevent concurrent executions
                    misfire_grace_time=600,  # Ignore missed runs if more than 10 minutes late
                )
            else:
                scheduler.add_job(
                    capture_and_upload_func,
                    trigger=IntervalTrigger(seconds=interval_seconds),
                    id="capture_job",
                    max_instances=1,  # Prevent concurrent executions
                    coalesce=True,  # Run at most once if multiple runs are missed
                    misfire_grace_time=600,  # Ignore missed runs if more than 10 minutes late
                )

            # Add schedule_check job on first run
            if schedule_func:
                scheduler.add_job(
                    schedule_func,
                    trigger=IntervalTrigger(minutes=5),
                    id="schedule_check",
                    coalesce=True,  # Run at most once if multiple runs are missed
                    misfire_grace_time=300,  # Ignore missed runs if more than 5 minutes late
                )
        else:
            # Check if we need to reschedule the capture job
            existing_job = scheduler.get_job("capture_job")
            needs_reschedule = False

            if existing_job is None:
                # No existing job, need to create one
                needs_reschedule = True
            elif use_transition:
                # Need to use DateTrigger - check if current job is already using DateTrigger
                if not isinstance(existing_job.trigger, DateTrigger):
                    needs_reschedule = True
                # If already using DateTrigger, check if the run_date is different
                elif existing_job.trigger.run_date != next_capture_time:
                    needs_reschedule = True
            else:
                # Need to use IntervalTrigger - check if current job is using IntervalTrigger with same interval
                if not isinstance(existing_job.trigger, IntervalTrigger):
                    needs_reschedule = True
                elif existing_job.trigger.interval.total_seconds() != interval_seconds:
                    needs_reschedule = True

            if needs_reschedule:
                # Remove existing capture job only (keep schedule_check running)
                try:
                    scheduler.remove_job("capture_job")
                except Exception:
                    pass

                # Schedule capture job with new settings
                if use_transition:
                    # Create wrapper that calls capture_and_upload_func then schedule_func
                    async def _transition_capture_wrapper() -> None:
                        await capture_and_upload_func()
                        if schedule_func:
                            await schedule_func()

                    scheduler.add_job(
                        _transition_capture_wrapper,
                        trigger=DateTrigger(run_date=next_capture_time),
                        id="capture_job",
                        max_instances=1,  # Prevent concurrent executions
                        misfire_grace_time=600,  # Ignore missed runs if more than 10 minutes late
                    )
                else:
                    scheduler.add_job(
                        capture_and_upload_func,
                        trigger=IntervalTrigger(seconds=interval_seconds),
                        id="capture_job",
                        max_instances=1,  # Prevent concurrent executions
                        coalesce=True,  # Run at most once if multiple runs are missed
                        misfire_grace_time=600,  # Ignore missed runs if more than 10 minutes late
                    )

            # Ensure schedule_check job exists (in case it was removed somehow)
            if schedule_func:
                schedule_check_job = scheduler.get_job("schedule_check")
                if schedule_check_job is None:
                    scheduler.add_job(
                        schedule_func,
                        trigger=IntervalTrigger(minutes=5),
                        id="schedule_check",
                        coalesce=True,  # Run at most once if multiple runs are missed
                        misfire_grace_time=300,  # Ignore missed runs if more than 5 minutes late
                    )

    return scheduler
