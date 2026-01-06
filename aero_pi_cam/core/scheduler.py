"""Scheduling logic for capture jobs."""

import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..weather.day_night import get_day_night_mode
from .config import Config
from .debug import debug_print


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

        # Update or create scheduler
        if scheduler is None:
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
            misfire_grace_time=600,  # Ignore missed runs if more than 10 minutes late
        )

        # Re-evaluate schedule every 5 minutes for day/night transitions
        if schedule_func:
            scheduler.add_job(
                schedule_func,
                trigger=IntervalTrigger(minutes=5),
                id="schedule_check",
                coalesce=True,  # Run at most once if multiple runs are missed
                misfire_grace_time=300,  # Ignore missed runs if more than 5 minutes late
            )

    return scheduler
