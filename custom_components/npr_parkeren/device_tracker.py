"""Map markers for parking zones inside the radius and the marker cap.

A zone that falls out of the radius or the cap is removed from the entity
registry immediately. entity_category stays unset so Home Assistant does not
hide the pins as diagnostics, and entity_picture is a local PNG so the map
does not draw name initials.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_AREA_MANAGER_DESC,
    DOMAIN,
    MANUFACTURER,
    MARKER_FILES,
    NAME,
    USAGE_OTHER,
)
from .coordinator import NprParkerenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NprParkerenCoordinator = hass.data[DOMAIN][entry.entry_id]
    active: dict[str, NprZoneTracker] = {}

    def _area_from_unique_id(unique_id: str) -> str | None:
        prefix = f"{DOMAIN}_zone_"
        suffix = f"_{entry.entry_id}"
        if not unique_id.startswith(prefix) or not unique_id.endswith(suffix):
            return None
        area_id = unique_id[len(prefix) : -len(suffix)]
        return area_id or None

    def _purge_registry(keep: set[str]) -> None:
        registry = er.async_get(hass)
        for reg in list(er.async_entries_for_config_entry(registry, entry.entry_id)):
            if reg.domain != "device_tracker":
                continue
            area_id = _area_from_unique_id(reg.unique_id)
            if area_id is None or area_id in keep:
                continue
            registry.async_remove(reg.entity_id)
            _LOGGER.debug("Removed dropped zone marker %s", area_id)

    def _force_remove(area_ids: list[str]) -> None:
        registry = er.async_get(hass)
        for area_id in area_ids:
            entity = active.pop(area_id, None)
            if entity is None:
                continue
            entity_id = entity.entity_id
            hass.async_create_task(entity.async_remove(force_remove=True))
            if entity_id and registry.async_get(entity_id):
                registry.async_remove(entity_id)
            _LOGGER.debug("Removed zone marker %s", area_id)

    @callback
    def _update() -> None:
        data = coordinator.data or {}
        tracked = data.get("tracked") or []
        current: set[str] = set()
        new_entities: list[NprZoneTracker] = []
        for item in tracked:
            area_id = item.get("areaid")
            if not area_id:
                continue
            current.add(area_id)
            if area_id not in active:
                tracker = NprZoneTracker(coordinator, entry, area_id)
                active[area_id] = tracker
                new_entities.append(tracker)
        if new_entities:
            async_add_entities(new_entities)
        dropped = [area_id for area_id in list(active) if area_id not in current]
        if dropped:
            _force_remove(dropped)
        _purge_registry(current)

    entry.async_on_unload(coordinator.async_add_listener(_update))
    _update()


class NprZoneTracker(CoordinatorEntity[NprParkerenCoordinator], TrackerEntity):
    """GPS pin for one parking zone, keyed by area id."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_entity_category = None
    _attr_icon = "mdi:parking"

    def __init__(
        self,
        coordinator: NprParkerenCoordinator,
        entry: ConfigEntry,
        area_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._area_id = area_id
        place = entry.data.get(CONF_AREA_MANAGER_DESC, NAME)
        self._attr_unique_id = f"{DOMAIN}_zone_{area_id}_{entry.entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{NAME} ({place})",
            manufacturer=MANUFACTURER,
            model="RDW open data / Officiële bekendmakingen",
        )

    def _item(self) -> dict[str, Any] | None:
        data = self.coordinator.data or {}
        for collection in ("tracked", "zones"):
            for item in data.get(collection) or []:
                if item.get("areaid") == self._area_id:
                    return item
        return None

    @property
    def name(self) -> str:
        item = self._item()
        if item and item.get("name"):
            return str(item["name"])
        return self._area_id

    @property
    def latitude(self) -> float | None:
        item = self._item()
        if not item or item.get("latitude") is None:
            return None
        return float(item["latitude"])

    @property
    def longitude(self) -> float | None:
        item = self._item()
        if not item or item.get("longitude") is None:
            return None
        return float(item["longitude"])

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def entity_picture(self) -> str:
        item = self._item() or {}
        kind = str(item.get("usage_kind") or USAGE_OTHER)
        filename = MARKER_FILES.get(kind, MARKER_FILES[USAGE_OTHER])
        return f"/{DOMAIN}_assets/{filename}"

    @property
    def location_name(self) -> str | None:
        item = self._item()
        if not item:
            return None
        return str(item.get("usage_kind") or USAGE_OTHER)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = self._item()
        if not item:
            return {"areaid": self._area_id}
        return {
            "areaid": self._area_id,
            "usage": item.get("usage"),
            "usage_kind": item.get("usage_kind"),
            "in_force": item.get("in_force"),
            "inside": item.get("inside"),
            "tariff": item.get("tariff"),
            "max_stay_minutes": item.get("max_stay_minutes"),
            "distance_km": item.get("distance_km"),
        }
