"""RTSP URL wildcard expansion and scan-with-cache for DHCP cameras."""

from urllib.parse import urlparse, urlunparse

from .capture import CaptureResult, capture_frame


def expand_rtsp_url_candidates(rtsp_url: str, max_attempts: int) -> list[str]:
    """Expand a wildcard RTSP URL into a list of concrete candidate URLs.

    If the hostname contains exactly one '*', it is replaced with digits 0 through
    max_attempts-1 (e.g. 192.168.0.10* with max_attempts=5 -> 100, 101, 102, 103, 104).
    If there is no '*' or more than one '*', returns [rtsp_url] unchanged.

    Args:
        rtsp_url: RTSP URL, optionally with a single '*' in the hostname
        max_attempts: Maximum number of candidate URLs to generate

    Returns:
        List of RTSP URLs to try in order
    """
    parsed = urlparse(rtsp_url)
    hostname = parsed.hostname or ""

    if hostname.count("*") == 0:
        return [rtsp_url]
    if hostname.count("*") != 1:
        return [rtsp_url]

    auth = ""
    if parsed.username is not None and parsed.password is not None:
        auth = f"{parsed.username}:{parsed.password}@"

    candidates: list[str] = []
    for d in range(max_attempts):
        new_host = hostname.replace("*", str(d), 1)
        new_netloc = auth + new_host + (f":{parsed.port}" if parsed.port else "")
        new_url = urlunparse(
            (
                parsed.scheme,
                new_netloc,
                parsed.path or "",
                parsed.params or "",
                parsed.query or "",
                parsed.fragment or "",
            )
        )
        candidates.append(new_url)

    return candidates


def _build_url_with_hostname(template_url: str, hostname: str) -> str:
    """Build a full RTSP URL from a template (with optional *) by setting the hostname."""
    parsed = urlparse(template_url)
    auth = ""
    if parsed.username is not None and parsed.password is not None:
        auth = f"{parsed.username}:{parsed.password}@"
    new_netloc = auth + hostname + (f":{parsed.port}" if parsed.port else "")
    return urlunparse(
        (
            parsed.scheme,
            new_netloc,
            parsed.path or "",
            parsed.params or "",
            parsed.query or "",
            parsed.fragment or "",
        )
    )


def capture_frame_with_scan(
    rtsp_url: str,
    rtsp_user: str | None = None,
    rtsp_password: str | None = None,
    max_attempts: int = 5,
    scan_timeout_seconds: int = 10,
    last_camera_ip_ref: dict[str, str | None] | None = None,
) -> CaptureResult:
    """Capture a frame, trying cached IP first then scanning candidates if URL has wildcard.

    For static URLs (no '*' in hostname), calls capture_frame once with default timeout.
    For wildcard URLs, tries last_camera_ip_ref first if set; on failure, scans all
    candidates except the stale cached IP, then updates the cache on success.

    Args:
        rtsp_url: RTSP URL (may contain one '*' in hostname for DHCP scan)
        rtsp_user: Optional username
        rtsp_password: Optional password
        max_attempts: Max candidate URLs when expanding wildcard
        scan_timeout_seconds: Per-attempt timeout when scanning
        last_camera_ip_ref: Mutable ref to store last successful hostname (key "value")

    Returns:
        CaptureResult with image on success
    """
    ref = last_camera_ip_ref if last_camera_ip_ref is not None else {}
    candidates = expand_rtsp_url_candidates(rtsp_url, max_attempts)

    if len(candidates) == 1:
        return capture_frame(
            candidates[0],
            rtsp_user=rtsp_user,
            rtsp_password=rtsp_password,
            timeout_seconds=30,
        )

    # Try cached IP first
    cached_host = ref.get("value")
    if cached_host:
        cached_url = _build_url_with_hostname(rtsp_url, cached_host)
        result = capture_frame(
            cached_url,
            rtsp_user=rtsp_user,
            rtsp_password=rtsp_password,
            timeout_seconds=scan_timeout_seconds,
        )
        if result.success:
            return result
        # Cached IP failed; fall back to scan, excluding the stale one
        candidates_to_try = [c for c in candidates if urlparse(c).hostname != cached_host]
    else:
        candidates_to_try = candidates

    last_error: str | None = None
    for candidate_url in candidates_to_try:
        result = capture_frame(
            candidate_url,
            rtsp_user=rtsp_user,
            rtsp_password=rtsp_password,
            timeout_seconds=scan_timeout_seconds,
        )
        if result.success:
            hostname = urlparse(candidate_url).hostname
            if hostname:
                ref["value"] = hostname
                print(f"Camera found at {hostname} (DHCP scan)")
            return result
        last_error = result.error

    return CaptureResult(success=False, error=last_error or "No successful candidate")
