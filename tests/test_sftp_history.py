"""Tests for SFTP history filename utilities."""

from datetime import UTC, datetime, timedelta

from aero_pi_cam.upload.sftp_history import (
    build_timestamped_filename,
    collect_history_images,
    find_expired_images,
    parse_timestamp_from_filename,
)

BASE = "LFAS-Hangar_CFP_2-clean.jpg"
TS = datetime(2026, 3, 10, 17, 16, 32, tzinfo=UTC)


class TestBuildTimestampedFilename:
    """Tests for build_timestamped_filename."""

    def test_basic(self) -> None:
        """Test standard filename with extension."""
        result = build_timestamped_filename(BASE, TS)
        assert result == "LFAS-Hangar_CFP_2-clean.20260310T171632Z.jpg"

    def test_no_extension(self) -> None:
        """Test filename without extension."""
        result = build_timestamped_filename("camera", TS)
        assert result == "camera.20260310T171632Z"

    def test_different_timestamp(self) -> None:
        """Test with a different timestamp."""
        ts2 = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        result = build_timestamped_filename("img.jpg", ts2)
        assert result == "img.20260102T030405Z.jpg"


class TestParseTimestampFromFilename:
    """Tests for parse_timestamp_from_filename."""

    def test_valid_match(self) -> None:
        """Test parsing a valid timestamped filename."""
        result = parse_timestamp_from_filename(BASE, "LFAS-Hangar_CFP_2-clean.20260310T171632Z.jpg")
        assert result == TS

    def test_wrong_stem(self) -> None:
        """Test that different stem doesn't match."""
        result = parse_timestamp_from_filename(BASE, "OTHER-camera.20260310T171632Z.jpg")
        assert result is None

    def test_wrong_extension(self) -> None:
        """Test that different extension doesn't match."""
        result = parse_timestamp_from_filename(BASE, "LFAS-Hangar_CFP_2-clean.20260310T171632Z.png")
        assert result is None

    def test_base_filename_no_timestamp(self) -> None:
        """Test that the base filename itself doesn't match."""
        result = parse_timestamp_from_filename(BASE, BASE)
        assert result is None

    def test_garbage_input(self) -> None:
        """Test that garbage input returns None."""
        result = parse_timestamp_from_filename(BASE, "not-a-file")
        assert result is None

    def test_malformed_timestamp(self) -> None:
        """Test that a malformed timestamp portion returns None."""
        result = parse_timestamp_from_filename(BASE, "LFAS-Hangar_CFP_2-clean.20261332T999999Z.jpg")
        assert result is None


class TestCollectHistoryImages:
    """Tests for collect_history_images."""

    def test_collects_matching_files(self) -> None:
        """Test collecting timestamped files from a directory listing."""
        ts1 = datetime(2026, 3, 10, 17, 11, 0, tzinfo=UTC)
        ts2 = datetime(2026, 3, 10, 17, 16, 0, tzinfo=UTC)
        files = [
            BASE,
            "LFAS-Hangar_CFP_2-clean.20260310T171100Z.jpg",
            "LFAS-Hangar_CFP_2-clean.20260310T171600Z.jpg",
            "cam.json",
            "LFAS-Hangar_CFP_2.jpg",
        ]
        result = collect_history_images(files, BASE)
        assert len(result) == 2
        assert result[ts2] == "LFAS-Hangar_CFP_2-clean.20260310T171600Z.jpg"
        assert result[ts1] == "LFAS-Hangar_CFP_2-clean.20260310T171100Z.jpg"

    def test_sorted_most_recent_first(self) -> None:
        """Test that results are sorted most recent first."""
        files = [
            "img.20260101T010000Z.jpg",
            "img.20260103T010000Z.jpg",
            "img.20260102T010000Z.jpg",
        ]
        result = collect_history_images(files, "img.jpg")
        timestamps = list(result.keys())
        assert timestamps[0] > timestamps[1] > timestamps[2]

    def test_empty_list(self) -> None:
        """Test with no files."""
        result = collect_history_images([], BASE)
        assert result == {}

    def test_no_matches(self) -> None:
        """Test with files that don't match the pattern."""
        result = collect_history_images(["cam.json", "other.jpg"], BASE)
        assert result == {}


class TestFindExpiredImages:
    """Tests for find_expired_images."""

    def test_deletes_old_images(self) -> None:
        """Test that images beyond the retention period are returned."""
        now = datetime(2026, 3, 10, 18, 0, 0, tzinfo=UTC)
        keep = timedelta(hours=1)
        history = {
            datetime(2026, 3, 10, 17, 30, 0, tzinfo=UTC): "img.20260310T173000Z.jpg",
            datetime(2026, 3, 10, 17, 5, 0, tzinfo=UTC): "img.20260310T170500Z.jpg",
            datetime(2026, 3, 10, 16, 0, 0, tzinfo=UTC): "img.20260310T160000Z.jpg",
        }
        expired = find_expired_images(history, keep, now)
        assert len(expired) == 1
        assert "img.20260310T160000Z.jpg" in expired

    def test_keeps_all_within_duration(self) -> None:
        """Test that no images are deleted when all are within retention."""
        now = datetime(2026, 3, 10, 17, 30, 0, tzinfo=UTC)
        keep = timedelta(hours=2)
        history = {
            datetime(2026, 3, 10, 17, 0, 0, tzinfo=UTC): "a.jpg",
            datetime(2026, 3, 10, 16, 0, 0, tzinfo=UTC): "b.jpg",
        }
        expired = find_expired_images(history, keep, now)
        assert expired == []

    def test_empty_history(self) -> None:
        """Test with empty history."""
        now = datetime(2026, 3, 10, 18, 0, 0, tzinfo=UTC)
        expired = find_expired_images({}, timedelta(hours=1), now)
        assert expired == []
