from __future__ import annotations

import logging
import time
import random

import httpx

from tubescrape._innertube import InnerTube
from tubescrape.exceptions import RateLimitError, RequestError

logger = logging.getLogger('tubescrape.http')


class HTTPClient:
    """HTTP transport layer with retry, proxy support, and cookie management.

    Supports both synchronous and asynchronous operations via httpx.

    Args:
        proxy: Single proxy URL (e.g. 'http://user:pass@host:port').
        proxies: List of proxy URLs for rotation.
        timeout: Request timeout in seconds.
        max_retries: Maximum retry attempts on transient failures.
        cookies: Additional cookies to include in requests.
    """

    RETRYABLE_STATUS_CODES: tuple[int, ...] = (429, 500, 502, 503, 504)

    def __init__(
        self,
        proxy: str | None = None,
        proxies: list[str] | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        cookies: dict[str, str] | None = None,
    ):
        self._proxy = proxy
        self._proxies = proxies or []
        self._proxy_index = 0
        self._timeout = timeout
        self._max_retries = max_retries
        self._cookies = {**InnerTube.VISITOR_COOKIES, **(cookies or {})}

        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    @property
    def _current_proxy(self) -> str | None:
        if self._proxy:
            return self._proxy
        if self._proxies:
            proxy = self._proxies[self._proxy_index % len(self._proxies)]
            self._proxy_index += 1
            return proxy
        return None

    def _get_sync_client(self) -> httpx.Client:
        if self._sync_client is None or self._sync_client.is_closed:
            proxy = self._current_proxy
            self._sync_client = httpx.Client(
                headers=InnerTube.DEFAULT_HEADERS,
                cookies=self._cookies,
                timeout=self._timeout,
                proxy=proxy,
                follow_redirects=True,
            )
        return self._sync_client

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            proxy = self._current_proxy
            self._async_client = httpx.AsyncClient(
                headers=InnerTube.DEFAULT_HEADERS,
                cookies=self._cookies,
                timeout=self._timeout,
                proxy=proxy,
                follow_redirects=True,
            )
        return self._async_client

    def _handle_response(self, response: httpx.Response) -> httpx.Response:
        """Check response status and raise appropriate exceptions."""
        if response.status_code == 429:
            raise RateLimitError()
        if response.status_code >= 400:
            raise RequestError(
                'HTTP %d: %s' % (response.status_code, response.text[:200]),
                status_code=response.status_code,
            )
        return response

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        """Exponential backoff with jitter."""
        base = min(2 ** attempt, 30)
        jitter = random.uniform(0, base * 0.5)
        return base + jitter

    def post(self, url: str, json: dict, **kwargs) -> httpx.Response:
        """Send a POST request with retry logic.

        Args:
            url: Full URL to POST to.
            json: JSON payload.
            **kwargs: Additional arguments passed to httpx.Client.post.
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                client = self._get_sync_client()
                response = client.post(url, json=json, **kwargs)
                return self._handle_response(response)
            except RateLimitError:
                last_error = RateLimitError()
                if attempt < self._max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        'Rate limited (attempt %d/%d), retrying in %.1fs',
                        attempt + 1, self._max_retries + 1, delay,
                    )
                    time.sleep(delay)
                    self._rotate_proxy()
            except RequestError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        'Request failed (attempt %d/%d): %s, retrying in %.1fs',
                        attempt + 1, self._max_retries + 1, exc, delay,
                    )
                    time.sleep(delay)
                    self._rotate_proxy()

        raise RequestError(
            'Request failed after %d attempts: %s' % (self._max_retries + 1, last_error)
        )

    def get(self, url: str, **kwargs) -> httpx.Response:
        """Send a GET request with retry logic."""
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                client = self._get_sync_client()
                response = client.get(url, **kwargs)
                return self._handle_response(response)
            except RateLimitError:
                last_error = RateLimitError()
                if attempt < self._max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        'Rate limited (attempt %d/%d), retrying in %.1fs',
                        attempt + 1, self._max_retries + 1, delay,
                    )
                    time.sleep(delay)
                    self._rotate_proxy()
            except RequestError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        'Request failed (attempt %d/%d): %s, retrying in %.1fs',
                        attempt + 1, self._max_retries + 1, exc, delay,
                    )
                    time.sleep(delay)
                    self._rotate_proxy()

        raise RequestError(
            'Request failed after %d attempts: %s' % (self._max_retries + 1, last_error)
        )

    async def apost(self, url: str, json: dict, **kwargs) -> httpx.Response:
        """Async POST request with retry logic."""
        import asyncio

        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                client = self._get_async_client()
                response = await client.post(url, json=json, **kwargs)
                return self._handle_response(response)
            except RateLimitError:
                last_error = RateLimitError()
                if attempt < self._max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        'Rate limited (attempt %d/%d), retrying in %.1fs',
                        attempt + 1, self._max_retries + 1, delay,
                    )
                    await asyncio.sleep(delay)
                    self._rotate_proxy()
            except RequestError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        'Request failed (attempt %d/%d): %s, retrying in %.1fs',
                        attempt + 1, self._max_retries + 1, exc, delay,
                    )
                    await asyncio.sleep(delay)
                    self._rotate_proxy()

        raise RequestError(
            'Request failed after %d attempts: %s' % (self._max_retries + 1, last_error)
        )

    async def aget(self, url: str, **kwargs) -> httpx.Response:
        """Async GET request with retry logic."""
        import asyncio

        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                client = self._get_async_client()
                response = await client.get(url, **kwargs)
                return self._handle_response(response)
            except RateLimitError:
                last_error = RateLimitError()
                if attempt < self._max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        'Rate limited (attempt %d/%d), retrying in %.1fs',
                        attempt + 1, self._max_retries + 1, delay,
                    )
                    await asyncio.sleep(delay)
                    self._rotate_proxy()
            except RequestError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        'Request failed (attempt %d/%d): %s, retrying in %.1fs',
                        attempt + 1, self._max_retries + 1, exc, delay,
                    )
                    await asyncio.sleep(delay)
                    self._rotate_proxy()

        raise RequestError(
            'Request failed after %d attempts: %s' % (self._max_retries + 1, last_error)
        )

    def _rotate_proxy(self) -> None:
        """Close current client to force a new proxy on next request."""
        if self._proxies:
            self.close_sync()

    def close_sync(self) -> None:
        """Close the synchronous HTTP client."""
        if self._sync_client and not self._sync_client.is_closed:
            self._sync_client.close()
            self._sync_client = None

    async def close_async(self) -> None:
        """Close the asynchronous HTTP client."""
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None

    def close(self) -> None:
        """Close all HTTP clients."""
        self.close_sync()

    async def aclose(self) -> None:
        """Close all async HTTP clients."""
        await self.close_async()

    def __enter__(self) -> HTTPClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    async def __aenter__(self) -> HTTPClient:
        return self

    async def __aexit__(self, *args) -> None:
        await self.aclose()
