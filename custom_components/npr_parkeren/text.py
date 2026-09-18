"""Text entity: comma-separated streets that should raise a bus event."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_AREA_MANAGER_DESC, DOCUMENTATION_URL, DOMAIN, MANUFACTURER, NAME
from .coordinator import NprParkerenCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NprParkerenCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NprStreetWatchlist(coordinator, entry)])


class NprStreetWatchlist(RestoreEntity, TextEntity):
    """Comma-separated street names. A new decision that mentions one fires an event."""

    _attr_has_entity_name = True
    _attr_name = "Street watchlist"
    _attr_translation_key = "watchlist"
    _attr_icon = "mdi:road-variant"
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 255
    _attr_native_value = ""

    def __init__(self, coordinator: NprParkerenCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        place = entry.data.get(CONF_AREA_MANAGER_DESC, NAME)
        self._attr_unique_id = f"{DOMAIN}_watchlist_{entry.entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{NAME} ({place})",
            manufacturer=MANUFACTURER,
            model="RDW open data / Officiële bekendmakingen",
            configuration_url=DOCUMENTATION_URL,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        value = state.state[:255]
        self._attr_native_value = value
        self.coordinator.set_watchlist(value)

    async def async_set_value(self, value: str) -> None:
        clipped = (value or "")[:255]
        self._attr_native_value = clipped
        self.coordinator.set_watchlist(clipped)
        self.async_write_ha_state()
