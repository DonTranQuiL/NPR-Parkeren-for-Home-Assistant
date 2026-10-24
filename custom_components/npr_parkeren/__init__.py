"""NPR Parkeren Home Assistant integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

from .const import DOMAIN, PLATFORMS

try:
    from homeassistant.helpers import config_validation as cv

    CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
except ImportError:  # unit tests that import pure helpers before HA is installed
    CONFIG_SCHEMA = None


_LOGGER = logging.getLogger(__name__)

ASSETS_URL = f"/{DOMAIN}_assets"
CARD_FILE = "npr_parkeren-card.js"
CARD_VERSION = "0.2.0"
DATA_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"


async def _async_register_frontend(hass) -> None:
    """Serve the bundled assets and load the card once, for all entries."""
    if hass.data.get(DATA_FRONTEND_REGISTERED):
        return
    hass.data[DATA_FRONTEND_REGISTERED] = True
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(ASSETS_URL, str(Path(__file__).parent / "www"), True)]
        )
        add_extra_js_url(hass, f"{ASSETS_URL}/{CARD_FILE}?v={CARD_VERSION}")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not register the NPR Parkeren card: %s", err)


def _platforms():
    from homeassistant.const import Platform

    return [Platform(name) for name in PLATFORMS]


async def async_setup(hass, config) -> bool:
    """Set up the NPR Parkeren component (YAML is not used)."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend(hass)
    return True


async def async_setup_entry(hass, entry) -> bool:
    """Set up NPR Parkeren from a config entry."""
    from homeassistant.helpers.event import async_track_time_interval

    from .coordinator import NprParkerenCoordinator

    coordinator = NprParkerenCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            coordinator.async_background_refresh,
            timedelta(hours=12),
        )
    )

    async def handle_refresh(_call) -> None:
        for coord in hass.data.get(DOMAIN, {}).values():
            await coord.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "refresh"):
        hass.services.async_register(DOMAIN, "refresh", handle_refresh)

    await hass.config_entries.async_forward_entry_setups(entry, _platforms())
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass, entry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _platforms())
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "refresh")
    return unload_ok
