"""Async client for RDW NPR tables and the official gazette RSS feed.

Every request goes through the Home Assistant aiohttp session. Tables are
always filtered by area manager id. This client never downloads a national
dump.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import aiohttp

from .const import (
    CLIENT_TIMEOUT_CONNECT,
    CLIENT_TIMEOUT_READ,
    CLIENT_TIMEOUT_TOTAL,
    DATASET_AREA_REGULATION,
    DATASET_AREAS,
    DATASET_FARE,
    DATASET_FARE_PART,
    DATASET_GEOMETRY,
    DATASET_LINKS,
    DATASET_MANAGERS,
    DATASET_REGULATION,
    DATASET_SPECIAL,
    DATASET_SPECS,
    DATASET_TIMEFRAME,
    DATASET_USAGE,
    PAGE_CAP,
    PAGE_SIZE,
    SODA_BASE,
    USER_AGENT,
)
from .gazette import build_gazette_url

_LOGGER = logging.getLogger(__name__)

_MANAGER_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")


class NprApiError(Exception):
    """The upstream API did not return a usable payload."""


class NprApi:
    """Thin aiohttp wrapper. One session, explicit timeouts, one User-Agent."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._timeout = aiohttp.ClientTimeout(
            total=CLIENT_TIMEOUT_TOTAL,
            connect=CLIENT_TIMEOUT_CONNECT,
            sock_read=CLIENT_TIMEOUT_READ,
        )

    def _headers(self, accept: str) -> dict[str, str]:
        return {"User-Agent": USER_AGENT, "Accept": accept}

    async def _request(
        self, url: str, params: dict[str, str] | None, accept: str
    ) -> tuple[int, str]:
        try:
            async with self._session.get(
                url,
                params=params,
                headers=self._headers(accept),
                timeout=self._timeout,
            ) as response:
                text = await response.text()
                return response.status, text
        except aiohttp.ClientError as err:
            raise NprApiError(str(err)) from err
        except TimeoutError as err:
            raise NprApiError("timeout") from err

    async def _get_json(
        self, url: str, params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        status, text = await self._request(url, params, "application/json")
        if status != 200:
            raise NprApiError(f"HTTP {status} from {url}")
        try:
            payload = json.loads(text)
        except ValueError as err:
            raise NprApiError("response was not JSON") from err
        if not isinstance(payload, list):
            raise NprApiError("unexpected JSON payload")
        return [row for row in payload if isinstance(row, dict)]

    async def _get_pages(self, dataset: str, where: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        url = f"{SODA_BASE}/{dataset}.json"
        while offset < PAGE_CAP:
            batch = await self._get_json(
                url,
                {
                    "$where": where,
                    "$limit": str(PAGE_SIZE),
                    "$offset": str(offset),
                },
            )
            rows.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        _LOGGER.debug("Loaded %s rows from %s", len(rows), dataset)
        return rows

    async def lookup_managers(self, name: str) -> list[dict[str, Any]]:
        """Resolve an area manager by description. The id is never hardcoded."""
        cleaned = re.sub(r"[%_'\"]", " ", name or "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) < 2:
            return []
        pattern = cleaned.upper().replace("'", "''")
        where = f"upper(areamanagerdesc) like '%{pattern}%'"
        return await self._get_json(
            f"{SODA_BASE}/{DATASET_MANAGERS}.json",
            {
                "$select": "areamanagerid,areamanagerdesc",
                "$where": where,
                "$limit": "25",
            },
        )

    async def fetch_catalog(self, manager_id: str) -> dict[str, Any]:
        """Load NPR tables for one area manager only."""
        if not _MANAGER_ID.fullmatch(manager_id or ""):
            raise NprApiError("invalid area manager id")
        where = f"areamanagerid='{manager_id}'"
        areas = await self._get_pages(DATASET_AREAS, where)
        links = await self._get_pages(DATASET_LINKS, where)
        usages = await self._get_pages(DATASET_USAGE, where)
        geometries = await self._get_pages(DATASET_GEOMETRY, where)
        area_regulations = await self._get_pages(DATASET_AREA_REGULATION, where)
        regulations = await self._get_pages(DATASET_REGULATION, where)
        timeframes = await self._get_pages(DATASET_TIMEFRAME, where)
        fares = await self._get_pages(DATASET_FARE, where)
        fare_parts = await self._get_pages(DATASET_FARE_PART, where)
        special_days = await self._get_pages(DATASET_SPECIAL, where)
        specs = await self._get_pages(DATASET_SPECS, where)
        return {
            "areamanagerid": manager_id,
            "areas": areas,
            "links": links,
            "usages": usages,
            "geometries": geometries,
            "area_regulations": area_regulations,
            "regulations": regulations,
            "timeframes": timeframes,
            "fares": fares,
            "fare_parts": fare_parts,
            "special_days": special_days,
            "specs": specs,
        }

    async def fetch_gazette_xml(self, municipality: str, keyword: str) -> str:
        """One RSS document for this poll. The HTML article is not fetched."""
        url = build_gazette_url(municipality, keyword)
        status, text = await self._request(
            url, None, "application/rss+xml, application/xml, text/xml"
        )
        if status != 200:
            raise NprApiError(f"HTTP {status} from gazette")
        return text
