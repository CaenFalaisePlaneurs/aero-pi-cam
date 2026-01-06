"""EXIF metadata embedding for JPEG images.

Handles standard EXIF tags (GPS, ImageDescription, Copyright) and custom
aeronautical metadata (METAR, TAF, ICAO code, sunrise/sunset).
Also embeds XMP metadata with custom schema.
"""

import json
from datetime import datetime
from io import BytesIO

import piexif
from PIL import Image

from ..core.config import Config


def convert_gps_coordinates(latitude: float, longitude: float) -> dict:
    """Convert decimal degrees to EXIF GPS format (degrees/minutes/seconds).

    Args:
        latitude: Latitude in decimal degrees (-90 to 90)
        longitude: Longitude in decimal degrees (-180 to 180)

    Returns:
        Dictionary with GPS EXIF tags: GPSLatitude, GPSLatitudeRef,
        GPSLongitude, GPSLongitudeRef
    """
    # Convert latitude
    lat_abs = abs(latitude)
    lat_deg = int(lat_abs)
    lat_min = int((lat_abs - lat_deg) * 60)
    lat_sec = (lat_abs - lat_deg - lat_min / 60) * 3600

    # Convert to EXIF rational format: (numerator, denominator)
    # For seconds, use 100 as denominator for 2 decimal places precision
    lat_sec_numerator = int(lat_sec * 100)
    lat_sec_denominator = 100

    gps_latitude = (
        (lat_deg, 1),
        (lat_min, 1),
        (lat_sec_numerator, lat_sec_denominator),
    )
    gps_latitude_ref = "N" if latitude >= 0 else "S"

    # Convert longitude
    lon_abs = abs(longitude)
    lon_deg = int(lon_abs)
    lon_min = int((lon_abs - lon_deg) * 60)
    lon_sec = (lon_abs - lon_deg - lon_min / 60) * 3600

    # Convert to EXIF rational format
    lon_sec_numerator = int(lon_sec * 100)
    lon_sec_denominator = 100

    gps_longitude = (
        (lon_deg, 1),
        (lon_min, 1),
        (lon_sec_numerator, lon_sec_denominator),
    )
    gps_longitude_ref = "E" if longitude >= 0 else "W"

    return {
        "GPSLatitude": gps_latitude,
        "GPSLatitudeRef": gps_latitude_ref,
        "GPSLongitude": gps_longitude,
        "GPSLongitudeRef": gps_longitude_ref,
    }


def build_exif_dict(
    config: Config,
    sunrise_time: datetime,
    sunset_time: datetime,
    raw_metar: str | None = None,
    raw_taf: str | None = None,
) -> dict:
    """Build EXIF dictionary with standard and custom metadata.

    Args:
        config: Configuration object containing camera, location, and overlay settings
        sunrise_time: Sunrise time in UTC
        sunset_time: Sunset time in UTC
        raw_metar: Optional raw METAR text
        raw_taf: Optional raw TAF text

    Returns:
        Dictionary suitable for piexif.dump() containing EXIF data
    """
    # Start with empty EXIF structure
    exif_dict: dict[str, dict[int, object]] = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    # Standard EXIF tags
    # ImageDescription (0x010E) - Camera name
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = config.overlay.camera_name

    # Copyright (0x8298) - Provider name + License
    copyright_text = f"{config.overlay.provider_name}\n{config.metadata.license_mark}"
    exif_dict["0th"][piexif.ImageIFD.Copyright] = copyright_text

    # GPS coordinates
    gps_data = convert_gps_coordinates(config.location.latitude, config.location.longitude)
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = gps_data["GPSLatitude"]
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = gps_data["GPSLatitudeRef"]
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = gps_data["GPSLongitude"]
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = gps_data["GPSLongitudeRef"]

    # Custom aeronautical metadata in UserComment (0x9286)
    # Format as structured JSON for machine-readable key-value pairs
    metadata_dict: dict[str, str] = {}

    # Always include camera and provider info
    metadata_dict["camera_name"] = config.overlay.camera_name
    metadata_dict["provider_name"] = config.overlay.provider_name
    metadata_dict["latitude"] = str(config.location.latitude)
    metadata_dict["longitude"] = str(config.location.longitude)
    metadata_dict["github_repo"] = config.metadata.github_repo
    metadata_dict["webcam_url"] = config.metadata.webcam_url
    metadata_dict["license"] = config.metadata.license
    metadata_dict["license_url"] = config.metadata.license_url
    metadata_dict["license_mark"] = config.metadata.license_mark
    metadata_dict["camera_heading"] = config.location.camera_heading

    # Airfield ICAO code (from location config, not METAR station)
    metadata_dict["airfield_icao"] = config.location.name

    # Optional aeronautical data
    if raw_metar:
        metadata_dict["metar"] = raw_metar

    if raw_taf:
        metadata_dict["taf"] = raw_taf

    # Sunrise and sunset times (ISO 8601 UTC format)
    sunrise_str = sunrise_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    sunset_str = sunset_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    metadata_dict["sunrise"] = sunrise_str
    metadata_dict["sunset"] = sunset_str

    # Convert to JSON string for structured format
    user_comment_json = json.dumps(metadata_dict, ensure_ascii=False)
    # piexif expects UserComment as bytes with encoding prefix
    # Format: [encoding_byte, ...text_bytes, 0x00]
    user_comment_bytes = b"\x00" + user_comment_json.encode("utf-8") + b"\x00"
    exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment_bytes

    return exif_dict


def build_xmp_xml(
    config: Config,
    sunrise_time: datetime,
    sunset_time: datetime,
    raw_metar: str | None = None,
    raw_taf: str | None = None,
) -> str:
    """Build XMP XML with custom aeronautical schema.

    Args:
        config: Configuration object containing camera, location, and overlay settings
        sunrise_time: Sunrise time in UTC
        sunset_time: Sunset time in UTC
        raw_metar: Optional raw METAR text
        raw_taf: Optional raw TAF text

    Returns:
        XMP XML string with custom schema
    """
    # Custom namespace for aeronautical metadata
    namespace_uri = "http://aero-pi-cam.org/xmp/1.0/"
    namespace_prefix = "aero"

    # Build XML structure
    sunrise_str = sunrise_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    sunset_str = sunset_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Escape XML special characters
    def escape_xml(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    xml_parts = [
        '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>',
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.6.0">',
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">',
        f'<rdf:Description rdf:about="" xmlns:{namespace_prefix}="{namespace_uri}">',
        f"<{namespace_prefix}:camera_name>{escape_xml(config.overlay.camera_name)}</{namespace_prefix}:camera_name>",
        f"<{namespace_prefix}:provider_name>{escape_xml(config.overlay.provider_name)}</{namespace_prefix}:provider_name>",
        f"<{namespace_prefix}:latitude>{config.location.latitude}</{namespace_prefix}:latitude>",
        f"<{namespace_prefix}:longitude>{config.location.longitude}</{namespace_prefix}:longitude>",
        f"<{namespace_prefix}:github_repo>{escape_xml(config.metadata.github_repo)}</{namespace_prefix}:github_repo>",
        f"<{namespace_prefix}:webcam_url>{escape_xml(config.metadata.webcam_url)}</{namespace_prefix}:webcam_url>",
        f"<{namespace_prefix}:license>{escape_xml(config.metadata.license)}</{namespace_prefix}:license>",
        f"<{namespace_prefix}:license_url>{escape_xml(config.metadata.license_url)}</{namespace_prefix}:license_url>",
        f"<{namespace_prefix}:license_mark>{escape_xml(config.metadata.license_mark)}</{namespace_prefix}:license_mark>",
        f"<{namespace_prefix}:camera_heading>{escape_xml(config.location.camera_heading)}</{namespace_prefix}:camera_heading>",
        f"<{namespace_prefix}:airfield_icao>{escape_xml(config.location.name)}</{namespace_prefix}:airfield_icao>",
    ]

    if raw_metar:
        xml_parts.append(
            f"<{namespace_prefix}:metar>{escape_xml(raw_metar)}</{namespace_prefix}:metar>"
        )

    if raw_taf:
        xml_parts.append(f"<{namespace_prefix}:taf>{escape_xml(raw_taf)}</{namespace_prefix}:taf>")

    xml_parts.extend(
        [
            f"<{namespace_prefix}:sunrise>{sunrise_str}</{namespace_prefix}:sunrise>",
            f"<{namespace_prefix}:sunset>{sunset_str}</{namespace_prefix}:sunset>",
            "</rdf:Description>",
            "</rdf:RDF>",
            "</x:xmpmeta>",
        ]
    )

    # Add padding to reach 4KB boundary (XMP standard)
    xml_content = "\n".join(xml_parts)
    # Calculate padding needed (XMP packets should be multiples of 4KB)
    padding_size = (4096 - (len(xml_content.encode("utf-8")) % 4096)) % 4096
    if padding_size > 0:
        xml_content += "\n" + " " * (padding_size - 1)
    xml_content += '\n<?xpacket end="w"?>'

    return xml_content


def embed_xmp_in_jpeg(jpeg_bytes: bytes, xmp_xml: str) -> bytes:
    """Embed XMP metadata into JPEG image bytes.

    Args:
        jpeg_bytes: JPEG image as bytes
        xmp_xml: XMP XML string from build_xmp_xml()

    Returns:
        JPEG bytes with embedded XMP metadata

    Raises:
        Exception: If XMP embedding fails
    """
    # XMP is stored in JPEG APP1 segment with identifier "http://ns.adobe.com/xap/1.0/\x00"
    xmp_identifier = b"http://ns.adobe.com/xap/1.0/\x00"
    xmp_data = xmp_xml.encode("utf-8")

    # JPEG file structure: SOI (0xFFD8) followed by segments
    # Each segment: 0xFF + marker + 2-byte length + data
    # APP1 marker is 0xE1
    app1_marker = b"\xff\xe1"
    # Length includes 2 bytes for length field + identifier + data
    segment_length = 2 + len(xmp_identifier) + len(xmp_data)
    length_bytes = segment_length.to_bytes(2, byteorder="big")

    # Build XMP segment
    xmp_segment = app1_marker + length_bytes + xmp_identifier + xmp_data

    # Find insertion point: after SOI (0xFFD8) but before other APP segments
    # We'll insert after any existing APP0 (JFIF) segment
    jpeg_list = bytearray(jpeg_bytes)
    insert_pos = 2  # After SOI

    # Skip JFIF segment if present (APP0, marker 0xFFE0)
    if len(jpeg_list) > 4 and jpeg_list[0:2] == b"\xff\xd8":
        pos = 2
        while pos < len(jpeg_list) - 1:
            if jpeg_list[pos] == 0xFF:
                marker = jpeg_list[pos + 1]
                # APP0 (0xE0) or APP1 (0xE1) - skip them
                if marker == 0xE0 or marker == 0xE1:
                    # Get segment length
                    if pos + 3 < len(jpeg_list):
                        seg_len = int.from_bytes(jpeg_list[pos + 2 : pos + 4], byteorder="big")
                        pos += 2 + seg_len
                        insert_pos = pos
                        continue
                # If not APP segment, stop looking
                break
            pos += 1

    # Insert XMP segment
    jpeg_list[insert_pos:insert_pos] = xmp_segment

    return bytes(jpeg_list)


def embed_exif_in_jpeg(
    jpeg_bytes: bytes,
    exif_dict: dict,
    xmp_xml: str | None = None,
) -> bytes:
    """Embed EXIF and XMP metadata into JPEG image bytes.

    Args:
        jpeg_bytes: JPEG image as bytes
        exif_dict: EXIF dictionary from build_exif_dict()
        xmp_xml: Optional XMP XML string from build_xmp_xml()

    Returns:
        JPEG bytes with embedded EXIF and XMP metadata

    Raises:
        Exception: If EXIF embedding fails (caller should handle gracefully)
    """
    # Load image to verify it's valid
    img = Image.open(BytesIO(jpeg_bytes))

    # Convert EXIF dictionary to bytes using piexif
    exif_bytes = piexif.dump(exif_dict)

    # Save image with EXIF data
    output = BytesIO()
    img.save(output, format="JPEG", quality=90, exif=exif_bytes)
    result_bytes = output.getvalue()

    # Embed XMP metadata if provided
    if xmp_xml:
        try:
            result_bytes = embed_xmp_in_jpeg(result_bytes, xmp_xml)
        except Exception as e:
            # Log warning but continue without XMP
            print(f"WARNING: Failed to embed XMP metadata: {e}")

    return result_bytes
