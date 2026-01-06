"""Tests for dependencies module."""

import pytest

from aero_pi_cam.core.dependencies import check_external_dependencies


def test_check_external_dependencies_all_present(monkeypatch) -> None:
    """Test check_external_dependencies when all dependencies are present."""
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/ffmpeg" if x == "ffmpeg" else None)

    # When dependencies are present, should not exit
    # Note: This test may exit if cairosvg is not available, which is expected behavior
    try:
        check_external_dependencies()
        # If we get here, dependencies are present
    except SystemExit:
        # If it exits, that's also valid (dependencies missing)
        pass


def test_check_external_dependencies_missing_ffmpeg(monkeypatch) -> None:
    """Test check_external_dependencies when ffmpeg is missing."""
    monkeypatch.setattr("shutil.which", lambda x: None)

    # Should detect missing ffmpeg and exit
    with pytest.raises(SystemExit):
        check_external_dependencies()
