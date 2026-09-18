"""DataUpdateCoordinator for NPR Parkeren.

The coordinator is the only place that talks to the API. Sensors and map
markers render ``coordinator.data``. NPR tables are loaded once per area
manager, stored, and refreshed on a 12 hour cadence. The gazette RSS is
fetched once per poll.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NprApi, NprApiError
from .cache import CatalogCache
from .const import (
    ATTRIBUTION,
    CONF_AREA_MANAGER_DESC,
    CONF_AREA_MANAGER_ID,
    CONF_ENABLE_MARKERS,
    CONF_KEYWORD,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MAX_MAP_MARKERS,
    CONF_MUNICIPALITY,
    CONF_RADIUS_KM,
    CONF_SCAN_INTERVAL,
    DEFAULT_ENABLE_MARKERS,
    DEFAULT_KEYWORD,
    DEFAULT_MAX_MAP_MARKERS,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_DECISION,
    GAZETTE_DETAIL_MAX,
    HISTORY_MAX,
    MIN_SCAN_INTERVAL,
)
from .gazette import (
    classify_decision,
    extract_publication,
    filter_by_municipality,
    matching_streets,
    parse_rss,
    publication_xml_url,
    sort_decisions,
    watched_streets,
)
from .snapshot import build_snapshot

_LOGGER = logging.getLogger(__name__)


def _option(entry: ConfigEntry, key: str, default: Any) -> Any:
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


class NprParkerenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """One municipality: cached NPR tables plus one RSS fetch per poll."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.consecutive_errors = 0
        self.last_good_data: dict[str, Any] | None = None
        self.last_update_status = "never"
        self.last_update_success_timestamp = None
        self.watchlist = ""
        self._history: list[dict[str, Any]] = []
        self._last_decisions: list[dict[str, Any]] = []
        self._seen_links: set[str] = set()
        self._seen_ready = False

        scan = int(_option(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        scan = max(scan, MIN_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=scan),
            config_entry=entry,
        )
        self.api = NprApi(async_get_clientsession(hass))
        manager_id = str(entry.data.get(CONF_AREA_MANAGER_ID) or "")
        self.catalog_cache = CatalogCache(hass, manager_id)

    @property
    def manager_id(self) -> str:
        return str(self.entry.data.get(CONF_AREA_MANAGER_ID) or "")

    @property
    def municipality(self) -> str:
        official = str(self.entry.data.get(CONF_AREA_MANAGER_DESC) or "").strip()
        typed = str(self.entry.data.get(CONF_MUNICIPALITY) or "").strip()
        return official or typed

    def set_watchlist(self, value: str) -> None:
        self.watchlist = (value or "")[:255]

    def _centre(self) -> tuple[float, float, float]:
        latitude = float(
            _option(self.entry, CONF_LATITUDE, self.hass.config.latitude or 52.09)
        )
        longitude = float(
            _option(self.entry, CONF_LONGITUDE, self.hass.config.longitude or 5.12)
        )
        radius = float(_option(self.entry, CONF_RADIUS_KM, DEFAULT_RADIUS_KM))
        return latitude, longitude, radius

    async def async_background_refresh(self, _now: datetime | None = None) -> None:
        """Refresh the stored NPR catalog outside the entity path."""
        try:
            await self._refresh_catalog(force=True)
        except NprApiError as err:
            _LOGGER.warning("Background NPR catalog refresh failed: %s", err)
            return
        await self.async_request_refresh()

    async def _refresh_catalog(self, *, force: bool = False) -> None:
        await self.catalog_cache.async_load()
        if not force and not self.catalog_cache.is_stale:
            return
        payload = await self.api.fetch_catalog(self.manager_id)
        await self.catalog_cache.async_save(payload)

    async def _load_decisions(self) -> tuple[list[dict[str, Any]], str | None]:
        keyword = str(_option(self.entry, CONF_KEYWORD, DEFAULT_KEYWORD))
        try:
            xml_text = await self.api.fetch_gazette_xml(self.municipality, keyword)
            items = sort_decisions(
                filter_by_municipality(parse_rss(xml_text), self.municipality)
            )
        except (NprApiError, Exception) as err:
            _LOGGER.warning("Gazette RSS failed, keeping last decisions: %s", err)
            return list(self._last_decisions), str(err)
        enriched: list[dict[str, Any]] = []
        for item in items[:GAZETTE_DETAIL_MAX]:
            url = publication_xml_url(str(item.get("link") or ""))
            if not url:
                enriched.append(item)
                continue
            try:
                detail = extract_publication(await self.api.fetch_publication_xml(url))
            except NprApiError as err:
                _LOGGER.debug("Publication XML skipped for %s: %s", url, err)
                enriched.append(item)
                continue
            merged = dict(item)
            merged.update({key: value for key, value in detail.items() if value})
            merged["classification"] = classify_decision(
                str(detail.get("decision_title") or item.get("title") or ""),
                f"{item.get('description') or ''} {detail.get('excerpt') or ''}",
            )
            enriched.append(merged)
        enriched.extend(items[GAZETTE_DETAIL_MAX:])
        return enriched, None

    def _local_now(self) -> datetime:
        current = dt_util.now()
        if current.tzinfo is not None:
            return current.replace(tzinfo=None)
        return current

    def _record_history(self, payload: dict[str, Any], status: str) -> None:
        counts = payload.get("counts") or {}
        self._history.append(
            {
                "at": dt_util.utcnow().isoformat(),
                "status": status,
                "zones_in_radius": counts.get("zones_in_radius", 0),
                "inside": bool((payload.get("regulated_here") or {}).get("inside")),
                "decisions": counts.get("decisions", 0),
            }
        )
        if len(self._history) > HISTORY_MAX:
            self._history = self._history[-HISTORY_MAX:]

    def _fire_new_decisions(self, decisions: list[dict[str, Any]]) -> None:
        streets = watched_streets(self.watchlist)
        current_keys = {
            str(item.get("link") or item.get("title") or "") for item in decisions
        }
        if not self._seen_ready:
            self._seen_links = {key for key in current_keys if key}
            self._seen_ready = True
            return
        for item in decisions:
            key = str(item.get("link") or item.get("title") or "")
            if not key or key in self._seen_links:
                continue
            self._seen_links.add(key)
            matched = matching_streets(item, streets)
            if not matched:
                continue
            self.hass.bus.async_fire(
                EVENT_DECISION,
                {
                    "entry_id": self.entry.entry_id,
                    "municipality": self.municipality,
                    "street": matched[0],
                    "streets": matched,
                    "title": item.get("title") or "",
                    "link": item.get("link") or "",
                    "description": item.get("description") or "",
                    "pub_date": item.get("pub_date") or "",
                    "category": item.get("category") or "",
                    "classification": item.get("classification") or "",
                },
            )
        if len(self._seen_links) > 500:
            self._seen_links = {key for key in current_keys if key}

    def _fail(self, err: Exception) -> dict[str, Any]:
        self.consecutive_errors += 1
        self.last_update_status = "error"
        if self.last_good_data is not None:
            _LOGGER.warning("NPR update failed, keeping last payload: %s", err)
            return self.last_good_data
        raise UpdateFailed("NPR Parkeren has no data to show") from err

    async def _async_update_data(self) -> dict[str, Any]:
        catalog_error: Exception | None = None
        try:
            await self._refresh_catalog()
        except Exception as err:
            catalog_error = err
            _LOGGER.warning(
                "NPR catalog refresh failed, keeping cached tables: %s", err
            )

        decisions, rss_error = await self._load_decisions()
        if self.catalog_cache.payload is None and not decisions:
            return self._fail(catalog_error or NprApiError(rss_error or "no data"))

        latitude, longitude, radius = self._centre()
        markers = int(
            _option(self.entry, CONF_MAX_MAP_MARKERS, DEFAULT_MAX_MAP_MARKERS)
        )
        if not bool(_option(self.entry, CONF_ENABLE_MARKERS, DEFAULT_ENABLE_MARKERS)):
            markers = 0
        try:
            payload = await self.hass.async_add_executor_job(
                lambda: build_snapshot(
                    self.catalog_cache.payload,
                    latitude=latitude,
                    longitude=longitude,
                    radius_km=radius,
                    moment=self._local_now(),
                    decisions=decisions,
                    max_markers=markers,
                    municipality=self.municipality,
                    manager_id=self.manager_id,
                    manager_desc=str(self.entry.data.get(CONF_AREA_MANAGER_DESC) or ""),
                )
            )
        except Exception as err:
            return self._fail(err)

        status = "ok"
        if catalog_error or rss_error:
            self.consecutive_errors += 1
            status = "partial"
            self.last_update_status = "partial"
        else:
            self.consecutive_errors = 0
            self.last_update_status = "ok"
            self.last_update_success_timestamp = dt_util.utcnow()

        self._last_decisions = decisions
        self._fire_new_decisions(decisions)
        self._record_history(payload, status)
        payload["history"] = list(self._history)
        payload["attribution"] = ATTRIBUTION
        payload["last_update_status"] = self.last_update_status
        payload["consecutive_errors"] = self.consecutive_errors
        self.last_good_data = payload
        return payload
