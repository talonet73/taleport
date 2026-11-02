"""Shared HTTP client: timeouts, retries with exponential backoff, per-host pacing."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import httpx

from taleport import __version__
from taleport.collectors.base import CollectorError

log = logging.getLogger(__name__)

USER_AGENT = f"TALeport/{__version__} (Windows desktop app; trend research)"
MAX_RETRY_WAIT = 60.0


class HttpClient:
    def __init__(
        self,
        *,
        timeout: float = 15.0,
        max_attempts: int = 3,
        backoff: float = 1.5,
        min_interval: dict[str, float] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            transport=transport,
        )
        self._max_attempts = max_attempts
        self._backoff = backoff
        self._min_interval = min_interval or {}
        self._sleep = sleep
        self._host_locks: dict[str, threading.Lock] = {}
        self._last_request: dict[str, float] = {}
        self._not_before: dict[str, float] = {}
        self._registry_lock = threading.Lock()

    def close(self) -> None:
        self._client.close()

    def _pace(self, host: str) -> threading.Lock:
        with self._registry_lock:
            return self._host_locks.setdefault(host, threading.Lock())

    def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET with retries on network errors, 429 and 5xx. 4xx responses are returned as-is."""
        host = urlsplit(url).hostname or ""
        interval = self._min_interval.get(host, 0.0)
        for attempt in range(1, self._max_attempts + 1):
            with self._pace(host):
                now = time.monotonic()
                ready_at = max(
                    self._last_request.get(host, 0.0) + interval, self._not_before.get(host, 0.0)
                )
                if ready_at > now:
                    self._sleep(ready_at - now)
                self._last_request[host] = time.monotonic()
                try:
                    response = self._client.get(url, params=params)
                except httpx.TransportError as exc:
                    log.info("Network error on %s (attempt %d): %s", host, attempt, exc)
                    if attempt == self._max_attempts:
                        raise CollectorError("source.network", host=host) from exc
                    self._sleep(self._backoff * 2 ** (attempt - 1))
                    continue
                self._respect_rate_limit_headers(host, response)

            if response.status_code == 429 or response.status_code >= 500:
                retry_after = (
                    _retry_after(response)
                    or _ratelimit_reset(response)
                    or self._backoff * 2 ** (attempt - 1)
                )
                log.info("HTTP %d from %s (attempt %d)", response.status_code, host, attempt)
                if attempt == self._max_attempts or retry_after > MAX_RETRY_WAIT:
                    if response.status_code == 429:
                        raise CollectorError("source.rate_limited", host=host)
                    raise CollectorError("source.http", host=host, status=response.status_code)
                self._sleep(retry_after)
                continue
            return response
        raise AssertionError("unreachable")

    def _respect_rate_limit_headers(self, host: str, response: httpx.Response) -> None:
        """When a server says the budget is used up (X-Ratelimit-Remaining: 0, as Reddit
        does), hold further requests to that host until its window resets."""
        remaining = _float_header(response, "X-Ratelimit-Remaining")
        reset = _ratelimit_reset(response)
        if remaining is not None and remaining < 1 and reset is not None:
            self._not_before[host] = time.monotonic() + min(reset, MAX_RETRY_WAIT)


def _float_header(response: httpx.Response, name: str) -> float | None:
    try:
        return float(response.headers.get(name, ""))
    except ValueError:
        return None


def _retry_after(response: httpx.Response) -> float | None:
    return _float_header(response, "Retry-After")


def _ratelimit_reset(response: httpx.Response) -> float | None:
    return _float_header(response, "X-Ratelimit-Reset")


def ensure_ok(response: httpx.Response) -> httpx.Response:
    if response.status_code >= 400:
        host = response.request.url.host
        raise CollectorError("source.http", host=host, status=response.status_code)
    return response
