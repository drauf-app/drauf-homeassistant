"""Minimal async client for the drauf server API.

Only the read endpoints the integration needs: /api/version (public),
/api/plan/slots and /api/plan/entries (require a token with plan:read).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import aiohttp

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class DraufError(Exception):
    """Base error talking to a drauf server."""


class DraufConnectionError(DraufError):
    """The server could not be reached or answered garbage."""


class DraufAuthError(DraufError):
    """The token was rejected (missing, invalid, or lacking plan:read)."""


class DraufApiClient:
    """Thin wrapper over the drauf HTTP API."""

    def __init__(
        self, session: aiohttp.ClientSession, base_url: str, token: str | None = None
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._token = token

    @property
    def base_url(self) -> str:
        """The normalized instance URL."""
        return self._base_url

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        headers: dict[str, str] = {}
        if self._token is not None:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with self._session.get(
                f"{self._base_url}{path}",
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status in (401, 403):
                    raise DraufAuthError(f"{path} returned {response.status}")
                if response.status >= 400:
                    raise DraufError(f"{path} returned {response.status}")
                try:
                    return await response.json()
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise DraufConnectionError(f"{path} returned a non-JSON body") from err
        except TimeoutError as err:
            raise DraufConnectionError(f"timeout requesting {path}") from err
        except aiohttp.ClientError as err:
            raise DraufConnectionError(f"error requesting {path}: {err}") from err

    async def async_get_version(self) -> dict[str, Any]:
        """Fetch server version info; also proves the URL is a drauf server."""
        data = await self._get("/api/version")
        if not isinstance(data, dict) or "version" not in data:
            raise DraufConnectionError("URL does not look like a drauf server")
        return data

    async def async_get_slots(self) -> list[dict[str, Any]]:
        """Fetch the household's meal slots (labels)."""
        data = await self._get("/api/plan/slots")
        if not isinstance(data, list):
            raise DraufConnectionError("unexpected /api/plan/slots response")
        return data

    async def async_get_entries(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch plan entries in [start, end] (server caps the span at 92 days)."""
        data = await self._get(
            "/api/plan/entries",
            params={"from": start.isoformat(), "to": end.isoformat()},
        )
        if not isinstance(data, list):
            raise DraufConnectionError("unexpected /api/plan/entries response")
        return data
