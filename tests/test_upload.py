"""Tests for upload module."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import ApiConfig
from src.upload import upload_image


@pytest.mark.asyncio
async def test_upload_success() -> None:
    """Test successful upload with 201 response."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    response_body = {
        "id": "test-uuid",
        "received_at": "2026-01-02T15:30:05Z",
        "size_bytes": 245000,
    }

    mock_response = AsyncMock()
    mock_response.status_code = 201
    mock_response.json = lambda: response_body

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, api_config)

    assert result.success is True
    assert result.status_code == 201
    assert result.response_body == response_body


@pytest.mark.asyncio
async def test_upload_sends_correct_headers() -> None:
    """Test that upload sends correct headers."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response = AsyncMock()
    mock_response.status_code = 201
    mock_response.json = lambda: {"id": "test", "received_at": "", "size_bytes": 0}

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        await upload_image(b"fake-jpeg-data", metadata, api_config)

        call_kwargs = mock_client.put.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-api-key"
        assert call_kwargs["headers"]["Content-Type"] == "image/jpeg"
        assert call_kwargs["headers"]["X-Capture-Timestamp"] == "2026-01-02T15:30:00Z"
        assert call_kwargs["headers"]["X-Location"] == "LFAS"
        assert call_kwargs["headers"]["X-Is-Day"] == "true"


@pytest.mark.asyncio
async def test_upload_4xx_no_retry() -> None:
    """Test that 4xx errors don't trigger retry."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response = AsyncMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, api_config)

    assert result.success is False
    assert result.status_code == 400
    assert "HTTP 400" in result.error


@pytest.mark.asyncio
async def test_upload_retry_on_5xx() -> None:
    """Test retry on 5xx response."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response_500 = AsyncMock()
    mock_response_500.status_code = 500
    mock_response_500.text = "Internal Server Error"

    mock_response_201 = AsyncMock()
    mock_response_201.status_code = 201
    mock_response_201.json = lambda: {"id": "test", "received_at": "", "size_bytes": 0}

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=[mock_response_500, mock_response_201])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, api_config)

    assert result.success is True


@pytest.mark.asyncio
async def test_upload_retry_on_429() -> None:
    """Test retry on 429 response."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response_429 = AsyncMock()
    mock_response_429.status_code = 429
    mock_response_429.text = "Too Many Requests"

    mock_response_201 = AsyncMock()
    mock_response_201.status_code = 201
    mock_response_201.json = lambda: {"id": "test", "received_at": "", "size_bytes": 0}

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=[mock_response_429, mock_response_201])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, api_config)

    assert result.success is True


@pytest.mark.asyncio
async def test_upload_fails_after_max_retries() -> None:
    """Test that upload fails after max retries."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, api_config)

    assert result.success is False
    assert "All 3 upload attempts failed" in result.error


@pytest.mark.asyncio
async def test_upload_timeout() -> None:
    """Test upload timeout handling."""
    import httpx

    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, api_config)

    assert result.success is False
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_upload_cancelled_during_request() -> None:
    """Test upload cancellation during request."""
    import asyncio

    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=asyncio.CancelledError())
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, api_config)

    assert result.success is False
    assert "cancelled" in result.error.lower()


@pytest.mark.asyncio
async def test_upload_cancelled_during_backoff() -> None:
    """Test upload cancellation during backoff sleep."""
    import asyncio

    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("httpx.AsyncClient", return_value=mock_client),
        patch("asyncio.sleep", side_effect=asyncio.CancelledError()),
    ):
        result = await upload_image(b"fake-jpeg-data", metadata, api_config)

    assert result.success is False
    assert "cancelled" in result.error.lower()


@pytest.mark.asyncio
async def test_upload_request_error() -> None:
    """Test upload handles RequestError."""
    import httpx

    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=httpx.RequestError("Connection error"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, api_config)

    assert result.success is False
    assert "Connection error" in result.error
