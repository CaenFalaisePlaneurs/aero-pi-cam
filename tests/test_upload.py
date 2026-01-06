"""Tests for upload factory function."""

import pytest

from aero_pi_cam.config import ApiConfig, Config, SftpConfig
from aero_pi_cam.upload import ApiUploader, SftpUploader, create_uploader

from .conftest import _create_test_config


# Tests for factory function
def test_create_uploader_api() -> None:
    """Test factory creates ApiUploader for API method."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="API", api_config=api_config)

    uploader = create_uploader(config)
    assert isinstance(uploader, ApiUploader)
    assert uploader.api_config == api_config


def test_create_uploader_sftp() -> None:
    """Test factory creates SftpUploader for SFTP method."""
    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)

    uploader = create_uploader(config)
    assert isinstance(uploader, SftpUploader)
    assert uploader.sftp_config == sftp_config


def test_create_uploader_invalid_method() -> None:
    """Test factory raises error for invalid upload method."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="API", api_config=api_config)
    # Use model_construct to bypass validation and set invalid upload_method
    config_dict = config.model_dump()
    config_dict["upload_method"] = "INVALID"  # type: ignore[assignment]
    config = Config.model_construct(**config_dict)

    with pytest.raises(ValueError, match="Unknown upload method"):
        create_uploader(config)


def test_create_uploader_missing_api_config() -> None:
    """Test factory raises error when API config is missing."""
    # Create config with API method but no api config
    # Use model_construct to bypass validation
    base_config = _create_test_config(
        upload_method="API",
        api_config=ApiConfig(
            url="https://api.example.com/api/webcam/image",
            key="test-api-key",
            timeout_seconds=30,
        ),
    )
    config_dict = base_config.model_dump()
    config_dict["api"] = None
    config = Config.model_construct(**config_dict)

    with pytest.raises(ValueError, match="api configuration is required"):
        create_uploader(config)


def test_create_uploader_missing_sftp_config() -> None:
    """Test factory raises error when SFTP config is missing."""
    # Create config with SFTP method but no sftp config
    # Use model_construct to bypass validation
    base_config = _create_test_config(
        upload_method="SFTP",
        sftp_config=SftpConfig(
            host="test.example.com",
            port=22,
            user="testuser",
            password="testpass",
            remote_path="/test/path",
            timeout_seconds=30,
        ),
    )
    config_dict = base_config.model_dump()
    config_dict["sftp"] = None
    config = Config.model_construct(**config_dict)

    with pytest.raises(ValueError, match="sftp configuration is required"):
        create_uploader(config)
