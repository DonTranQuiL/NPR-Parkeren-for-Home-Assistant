"""Sensor platform for NPR Parkeren.

Sensors only render coordinator data. Diagnostic category is reserved for
consecutive errors, last update status, and last update time.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_AREA_MANAGER_DESC,
    DOCUMENTATION_URL,
    DOMAIN,
    MANUFACTURER,
    NAME,
)
from .coordinator import NprParkerenCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NprParkerenCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NprOverviewSensor(coordinator, entry),
            NprZonesInRadiusSensor(coordinator, entry),
            NprRegulatedHereSensor(coordinator, entry),
            NprLatestDecisionSensor(coordinator, entry),
            NprDecisionCountSensor(coordinator, entry),
            NprConsecutiveErrorsSensor(coordinator, entry),
            NprLastUpdateStatusSensor(coordinator, entry),
            NprLastUpdateTimeSensor(coordinator, entry),
        ]
    )


class NprBaseSensor(CoordinatorEntity[NprParkerenCoordinator], SensorEntity):
    """Shared base. One device per config entry."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: NprParkerenCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        place = entry.data.get(CONF_AREA_MANAGER_DESC, NAME)
        self._attr_unique_id = f"{DOMAIN}_{key}_{entry.entry_id}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{NAME} ({place})",
            manufacturer=MANUFACTURER,
            model="RDW open data / Officiële bekendmakingen",
            configuration_url=DOCUMENTATION_URL,
        )

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data or {}


class NprOverviewSensor(NprBaseSensor):
    """Fat attributes for the Lovelace card. State is the zones-in-radius count."""

    def __init__(self, coordinator: NprParkerenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "overview")
        self._attr_name = "Overview"
        self._attr_icon = "mdi:parking"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        return int((self._data.get("counts") or {}).get("zones_in_radius") or 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._data
        return {
            "municipality": data.get("municipality"),
            "areamanager_id": data.get("areamanager_id"),
            "areamanager_desc": data.get("areamanager_desc"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "radius_km": data.get("radius_km"),
            "zones": data.get("zones") or [],
            "unmapped_zones": data.get("unmapped_zones") or [],
            "unmapped_total": data.get("unmapped_total", 0),
            "regulated_here": data.get("regulated_here") or {},
            "decisions": data.get("decisions") or [],
            "latest_decision": data.get("latest_decision"),
            "counts": data.get("counts") or {},
            "history": data.get("history") or [],
            "attribution": ATTRIBUTION,
        }


class NprZonesInRadiusSensor(NprBaseSensor):
    def __init__(self, coordinator: NprParkerenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "zones_in_radius")
        self._attr_name = "Zones in radius"
        self._attr_icon = "mdi:map-marker-radius"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        return int((self._data.get("counts") or {}).get("zones_in_radius") or 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        zones = self._data.get("zones") or []
        return {
            "area_ids": [zone.get("areaid") for zone in zones if zone.get("areaid")]
        }


class NprRegulatedHereSensor(NprBaseSensor):
    """Whether the configured coordinates are inside a regulated zone right now."""

    def __init__(self, coordinator: NprParkerenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "regulated_here")
        self._attr_name = "Regulated here"
        self._attr_icon = "mdi:map-marker-check"

    @property
    def native_value(self) -> str:
        regulated = self._data.get("regulated_here") or {}
        if not regulated.get("inside"):
            return "not_regulated"
        name = str(regulated.get("name") or "regulated")
        return name[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        regulated = self._data.get("regulated_here") or {}
        return {
            "inside": bool(regulated.get("inside")),
            "in_force": bool(regulated.get("in_force")),
            "areaid": regulated.get("areaid"),
            "usage": regulated.get("usage"),
            "usage_kind": regulated.get("usage_kind"),
            "tariff": regulated.get("tariff"),
            "tariff_description": regulated.get("tariff_description"),
            "fare_steps": regulated.get("fare_steps") or [],
            "max_stay_minutes": regulated.get("max_stay_minutes"),
            "distance_km": regulated.get("distance_km"),
        }


class NprLatestDecisionSensor(NprBaseSensor):
    def __init__(self, coordinator: NprParkerenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "latest_decision")
        self._attr_name = "Latest decision"
        self._attr_icon = "mdi:newspaper-variant-outline"

    @property
    def native_value(self) -> str | None:
        latest = self._data.get("latest_decision")
        if not latest:
            return None
        title = str(latest.get("decision_title") or latest.get("title") or "").strip()
        return title[:255] or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        latest = self._data.get("latest_decision") or {}
        if not latest:
            return {}
        attributes = {
            "link": latest.get("link"),
            "description": latest.get("description"),
            "pub_date": latest.get("pub_date"),
            "category": latest.get("category"),
            "classification": latest.get("classification"),
        }
        if latest.get("decision_title"):
            attributes["decision_title"] = latest["decision_title"]
        if latest.get("excerpt"):
            attributes["excerpt"] = latest["excerpt"]
        return {
            key: value for key, value in attributes.items() if value not in (None, "")
        }


class NprDecisionCountSensor(NprBaseSensor):
    def __init__(self, coordinator: NprParkerenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "decision_count")
        self._attr_name = "Decision count"
        self._attr_icon = "mdi:counter"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        return int((self._data.get("counts") or {}).get("decisions") or 0)


class NprConsecutiveErrorsSensor(NprBaseSensor):
    def __init__(self, coordinator: NprParkerenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "consecutive_errors")
        self._attr_name = "Consecutive errors"
        self._attr_icon = "mdi:alert-circle"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        return int(self.coordinator.consecutive_errors)


class NprLastUpdateStatusSensor(NprBaseSensor):
    def __init__(self, coordinator: NprParkerenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "last_update_status")
        self._attr_name = "Last update status"
        self._attr_icon = "mdi:cloud-sync"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        return str(self.coordinator.last_update_status)


class NprLastUpdateTimeSensor(NprBaseSensor):
    def __init__(self, coordinator: NprParkerenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "last_update_time")
        self._attr_name = "Last update time"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:clock-check"

    @property
    def native_value(self):
        return self.coordinator.last_update_success_timestamp
