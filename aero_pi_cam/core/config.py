"""Configuration loading and validation using Pydantic."""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


class CameraConfig(BaseModel):
    """Camera configuration."""

    rtsp_url: str = Field(
        ..., description="RTSP URL for camera stream (with or without credentials)"
    )
    rtsp_user: str | None = Field(None, description="RTSP username (alternative to URL-embedded)")
    rtsp_password: str | None = Field(
        None, description="RTSP password (alternative to URL-embedded)"
    )

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, v: str) -> str:
        """Validate RTSP URL format."""
        if not v.startswith("rtsp://"):
            raise ValueError("RTSP URL must start with rtsp://")
        return v


class LocationConfig(BaseModel):
    """Location configuration for sun calculation.

    Note: All times in this application are in UTC (Coordinated Universal Time)
    for aeronautical compliance. No timezone conversions or daylight saving time
    adjustments are applied.
    """

    name: str = Field(..., min_length=1, description="Location identifier")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees")
    camera_heading: str = Field(
        ...,
        min_length=1,
        description="Camera heading/direction (e.g., '060° RWY 06')",
    )


class ScheduleConfig(BaseModel):
    """Schedule configuration."""

    day_interval_seconds: int = Field(
        ..., ge=1, le=86400, description="Capture interval during day (seconds)"
    )
    night_interval_seconds: int = Field(
        ..., ge=1, le=86400, description="Capture interval during night (seconds)"
    )


class DebugConfig(BaseModel):
    """Debug configuration for development/testing.

    Note: Debug mode is enabled via DEBUG_MODE environment variable.
    This config only provides interval settings when debug mode is active.
    """

    day_interval_seconds: int = Field(
        10, ge=1, le=3600, description="Capture interval during day (seconds)"
    )
    night_interval_seconds: int = Field(
        30, ge=1, le=3600, description="Capture interval during night (seconds)"
    )


class ApiConfig(BaseModel):
    """API upload configuration."""

    url: str | None = Field(
        None, description="API endpoint URL (optional, uses dummy server if not set)"
    )
    key: str = Field(..., min_length=1, description="API key for authentication")
    timeout_seconds: int = Field(..., ge=1, le=300, description="Request timeout in seconds")


class SftpConfig(BaseModel):
    """SFTP upload configuration."""

    host: str = Field(..., min_length=1, description="SFTP server hostname")
    port: int = Field(..., ge=1, le=65535, description="SFTP server port")
    user: str = Field(..., min_length=1, description="SFTP username")
    password: str = Field(..., min_length=1, description="SFTP password")
    remote_path: str = Field(..., min_length=1, description="Remote directory path for uploads")
    timeout_seconds: int = Field(..., ge=1, le=300, description="Connection timeout in seconds")
    image_base_url: str | None = Field(
        None,
        description="Primary image server domain for image URLs in JSON metadata (e.g., http://caenfal.cluster121.hosting.ovh.net/). If not set, image URLs will be relative paths.",
    )


class UploadConfig(BaseModel):
    """Upload configuration grouping method, API, and SFTP settings."""

    method: Literal["API", "SFTP"] = Field("API", description="Upload method to use")
    api: ApiConfig | None = Field(
        None, description="API upload configuration (required when method is API)"
    )
    sftp: SftpConfig | None = Field(
        None, description="SFTP upload configuration (required when method is SFTP)"
    )

    @model_validator(mode="after")
    def validate_upload_config(self) -> "UploadConfig":
        """Validate that the correct upload config is provided based on method."""
        if self.method == "API" and self.api is None:
            raise ValueError("api configuration is required when upload method is 'API'")
        if self.method == "SFTP" and self.sftp is None:
            raise ValueError("sftp configuration is required when upload method is 'SFTP'")
        return self


class OverlayConfig(BaseModel):
    """Overlay configuration for comprehensive image overlay.

    Overlay covers the full image surface (0,0 to image width, image height).
    Elements are positioned as follows:
    - Logo + provider name + ICAO code: top-left
    - Camera name + UTC timestamp: below logo, aligned left
    - Sunrise + sunset times: below camera info, aligned left
    - Raw METAR: bottom-left, aligned left
    """

    provider_name: str = Field(..., min_length=1, description="Image provider name")
    provider_logo: str = Field(
        ...,
        min_length=1,
        description="Path to provider logo file (PNG or SVG format). Supports absolute paths and ~ expansion (e.g., ~/images/logo.png).",
    )
    logo_size: int = Field(72, ge=1, description="Logo size in pixels")
    camera_name: str = Field(..., min_length=1, description="Camera identifier")
    font_color: str = Field("white", min_length=1, description="Color for overlay text")
    font_size: int = Field(16, ge=1, description="Font size in pixels")
    font_path: str | None = Field(
        None,
        description="Path to custom font file (e.g., ~/fonts/Poppins-Medium.ttf). If not set, uses system font.",
    )
    sun_icon_size: int = Field(24, ge=1, description="Sunrise/sunset icon size in pixels")
    line_spacing: int = Field(
        4, ge=0, description="Line spacing in pixels between overlay elements"
    )
    padding: int = Field(15, ge=0, description="Padding in pixels from image borders")
    background_color: str = Field("rgba(0,0,0,0.6)", min_length=1, description="Background color")
    shadow_enabled: bool = Field(True, description="Enable drop shadow behind text")
    shadow_offset_x: int = Field(2, description="Shadow horizontal offset in pixels")
    shadow_offset_y: int = Field(2, description="Shadow vertical offset in pixels")
    shadow_color: str = Field("black", min_length=1, description="Shadow color")


class MetarConfig(BaseModel):
    """METAR overlay configuration."""

    enabled: bool = Field(False, description="Enable METAR overlay")
    icao_code: str = Field(..., min_length=4, max_length=4, description="Airport ICAO code")
    api_url: str = Field(
        "https://aviationweather.gov/api/data/metar",
        description="METAR API base URL",
    )
    raw_metar_enabled: bool = Field(True, description="Show raw METAR text block")

    @field_validator("icao_code")
    @classmethod
    def uppercase_icao_code(cls, v: str) -> str:
        """Convert ICAO code to uppercase."""
        return v.upper()


class MetadataConfig(BaseModel):
    """Metadata configuration for EXIF and XMP embedding."""

    github_repo: str = Field(
        ...,
        min_length=1,
        description="GitHub repository URL for the project",
    )
    webcam_url: str = Field(
        ...,
        min_length=1,
        description="Web page URL for viewing webcam images (advertising/promotional URL, not the image server domain)",
    )
    license: str = Field(
        "CC BY-SA 4.0",
        description="License identifier (e.g., 'CC BY-SA 4.0')",
    )
    license_url: str = Field(
        "https://creativecommons.org/licenses/by-sa/4.0/",
        description="URL to the license text",
    )
    license_mark: str = Field(
        "This work is licensed under CC BY-SA 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by-sa/4.0/",
        description="Short license attribution mark",
    )


class Config(BaseModel):
    """Root configuration model."""

    camera: CameraConfig
    location: LocationConfig
    schedule: ScheduleConfig
    upload: UploadConfig
    overlay: OverlayConfig
    metar: MetarConfig
    metadata: MetadataConfig
    debug: DebugConfig | None = Field(None, description="Optional debug configuration")

    @property
    def upload_method(self) -> Literal["API", "SFTP"]:
        """Backward compatibility property for upload_method."""
        return self.upload.method

    @property
    def api(self) -> ApiConfig | None:
        """Backward compatibility property for api."""
        return self.upload.api

    @property
    def sftp(self) -> SftpConfig | None:
        """Backward compatibility property for sftp."""
        return self.upload.sftp


def format_validation_errors(error: ValidationError) -> str:
    """Format Pydantic validation errors into user-friendly messages.

    Args:
        error: Pydantic ValidationError instance

    Returns:
        Formatted error message string
    """
    lines = ["Configuration validation failed:"]
    for err in error.errors():
        field_path = " -> ".join(str(loc) for loc in err["loc"])
        error_msg = err.get("msg", "")

        # Format the error message
        if field_path:
            lines.append(f"  • {field_path}: {error_msg}")
        else:
            lines.append(f"  • {error_msg}")

        # Add context if available
        if "ctx" in err:
            ctx = err["ctx"]
            if "expected" in ctx:
                lines.append(f"    Expected: {ctx['expected']}")
            if "actual" in ctx:
                lines.append(f"    Actual: {ctx['actual']}")

    # Add helpful message pointing to documentation
    lines.append("")
    lines.append("For help configuring your config.yaml file:")
    lines.append("  • See config.example.yaml for a complete example configuration")
    lines.append("  • See README.md 'Configuration' section for detailed documentation")

    return "\n".join(lines)


def load_config(config_path: str | None = None) -> Config:
    """Load and validate configuration from YAML file.

    Args:
        config_path: Path to configuration file. If None, uses CONFIG_PATH env var or default.

    Returns:
        Validated Config instance

    Raises:
        FileNotFoundError: If config file does not exist
        ValidationError: If config validation fails (formatted error message is printed)
    """
    if config_path is None:
        config_path = os.getenv("CONFIG_PATH", "config.yaml")

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    print("Validating configuration...")

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        config_obj = Config.model_validate(data)
        print("Configuration validated successfully")
        return config_obj
    except ValidationError as e:
        error_msg = format_validation_errors(e)
        print(error_msg)
        raise


def validate_config(config: dict) -> Config:
    """Validate configuration dictionary."""
    return Config.model_validate(config)
