"""Persistent Store cache for one municipality's NPR catalog."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import CATALOG_REFRESH_SECONDS, DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


class CatalogCache:
    """Store-backed NPR tables for a single area manager. 12 hour cadence."""

    def __init__(self, hass: HomeAssistant, manager_id: str) -> None:
        self.manager_id = manager_id
        key = f"{DOMAIN}.catalog.{manager_id}"
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, key)
        self.payload: dict[str, Any] | None = None
        self.fetched_at: float = 0.0
        self._loaded = False

    @property
    def is_stale(self) -> bool:
        if not self.payload:
            return True
        return (time.time() - self.fetched_at) >= CATALOG_REFRESH_SECONDS

    async def async_load(self) -> None:
        """Load the catalog from disk once per process."""
        if self._loaded:
            return
        data = await self._store.async_load()
        self._loaded = True
        if not isinstance(data, dict):
            return
        payload = data.get("payload")
        if isinstance(payload, dict) and payload.get("areamanagerid"):
            self.payload = payload
        self.fetched_at = float(data.get("fetched_at") or 0.0)
        _LOGGER.debug(
            "NPR catalog cache loaded for %s (areas=%s)",
            self.manager_id,
            len((self.payload or {}).get("areas") or []),
        )

    async def async_save(self, payload: dict[str, Any]) -> None:
        """Replace the cached catalog. Callers must not pass an empty failure."""
        self.payload = payload
        self.fetched_at = time.time()
        self._loaded = True
        await self._store.async_save(
            {
                "version": VERSION,
                "fetched_at": self.fetched_at,
                "payload": payload,
            }
        )
        _LOGGER.debug("NPR catalog cache saved for %s", self.manager_id)
