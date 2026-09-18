"""Button platform — manual refresh for NPR Parkeren."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_AREA_MANAGER_DESC, DOCUMENTATION_URL, DOMAIN, MANUFACTURER, NAME
from .coordinator import NprParkerenCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NprParkerenCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NprRefreshButton(coordinator, entry)])


class NprRefreshButton(ButtonEntity):
    """Force a coordinator refresh."""

    _attr_has_entity_name = True
    _attr_name = "Refresh"
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: NprParkerenCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        place = entry.data.get(CONF_AREA_MANAGER_DESC, NAME)
        self._attr_unique_id = f"{DOMAIN}_refresh_{entry.entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{NAME} ({place})",
            manufacturer=MANUFACTURER,
            model="RDW open data / Officiële bekendmakingen",
            configuration_url=DOCUMENTATION_URL,
        )

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
