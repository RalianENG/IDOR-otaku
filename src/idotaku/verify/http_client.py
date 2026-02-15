"""HTTP client for sending verification requests."""

from __future__ import annotations

import time
from typing import Optional

import httpx

from .models import RequestData, ResponseData

DEFAULT_TIMEOUT = 30.0
MAX_RESPONSE_BODY = 10240  # 10KB


class VerifyHttpClient:
    """HTTP client wrapper for IDOR verification.

    Wraps httpx to provide a simple interface for sending
    verification requests. Designed to be mockable for testing.
    """

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        verify_ssl: bool = True,
        proxy: Optional[str] = None,
    ) -> None:
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._proxy = proxy

    def send(self, request: RequestData) -> ResponseData:
        """Send an HTTP request and return the response.

        Args:
            request: The request to send

        Returns:
            ResponseData with status, headers, body, timing

        Raises:
            httpx.RequestError: On connection/timeout errors
        """
        start = time.monotonic()

        with httpx.Client(
            timeout=self._timeout,
            verify=self._verify_ssl,
            proxy=self._proxy,
            follow_redirects=False,
        ) as client:
            response = client.request(
                method=request.method,
                url=request.url,
                headers=request.headers,
                content=request.body if request.body else None,
            )

        elapsed = (time.monotonic() - start) * 1000  # ms

        return ResponseData(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.text[:MAX_RESPONSE_BODY],
            content_length=len(response.content),
            elapsed_ms=elapsed,
        )
