"""Config and options flow for NPR Parkeren."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NprApi, NprApiError
from .const import (
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
    MIN_SCAN_INTERVAL,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


class NprParkerenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """One config entry per Dutch municipality."""

    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}
        self._managers: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        hass_lat = self.hass.config.latitude
        hass_lon = self.hass.config.longitude

        if user_input is not None:
            municipality = str(user_input.get(CONF_MUNICIPALITY) or "").strip()
            self._user_input = {
                CONF_MUNICIPALITY: municipality,
                CONF_LATITUDE: float(user_input[CONF_LATITUDE]),
                CONF_LONGITUDE: float(user_input[CONF_LONGITUDE]),
                CONF_RADIUS_KM: float(
                    user_input.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)
                ),
            }
            try:
                session = async_get_clientsession(self.hass)
                self._managers = await NprApi(session).lookup_managers(municipality)
            except NprApiError as err:
                _LOGGER.debug("Area manager lookup failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not self._managers:
                    errors["base"] = "municipality_not_found"
                else:
                    exact = [
                        row
                        for row in self._managers
                        if str(row.get("areamanagerdesc") or "").casefold()
                        == municipality.casefold()
                    ]
                    chosen = exact[0] if len(exact) == 1 else None
                    if chosen is None and len(self._managers) == 1:
                        chosen = self._managers[0]
                    if chosen is not None:
                        return await self._async_create(chosen)
                    return await self.async_step_select_manager()

        schema = vol.Schema(
            {
                vol.Required(CONF_MUNICIPALITY): str,
                vol.Required(CONF_LATITUDE, default=hass_lat): cv.latitude,
                vol.Required(CONF_LONGITUDE, default=hass_lon): cv.longitude,
                vol.Optional(CONF_RADIUS_KM, default=DEFAULT_RADIUS_KM): vol.All(
                    vol.Coerce(float), vol.Range(min=0.1, max=50.0)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_select_manager(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            selected = str(user_input.get(CONF_AREA_MANAGER_ID) or "")
            for row in self._managers:
                if str(row.get("areamanagerid")) == selected:
                    return await self._async_create(row)
            return self.async_abort(reason="municipality_not_found")

        options = [
            {
                "value": str(row.get("areamanagerid")),
                "label": (f"{row.get('areamanagerdesc')} ({row.get('areamanagerid')})"),
            }
            for row in self._managers
            if row.get("areamanagerid")
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_AREA_MANAGER_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="select_manager", data_schema=schema)

    async def _async_create(self, manager: dict[str, Any]) -> FlowResult:
        manager_id = str(manager.get("areamanagerid") or "").strip()
        manager_desc = str(manager.get("areamanagerdesc") or "").strip()
        await self.async_set_unique_id(manager_id)
        self._abort_if_unique_id_configured()
        data = {
            CONF_MUNICIPALITY: self._user_input[CONF_MUNICIPALITY],
            CONF_AREA_MANAGER_ID: manager_id,
            CONF_AREA_MANAGER_DESC: manager_desc,
            CONF_LATITUDE: self._user_input[CONF_LATITUDE],
            CONF_LONGITUDE: self._user_input[CONF_LONGITUDE],
            CONF_RADIUS_KM: self._user_input[CONF_RADIUS_KM],
        }
        options = {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_RADIUS_KM: self._user_input[CONF_RADIUS_KM],
            CONF_MAX_MAP_MARKERS: DEFAULT_MAX_MAP_MARKERS,
            CONF_KEYWORD: DEFAULT_KEYWORD,
            CONF_ENABLE_MARKERS: DEFAULT_ENABLE_MARKERS,
        }
        title = manager_desc or self._user_input[CONF_MUNICIPALITY]
        return self.async_create_entry(
            title=f"{NAME} ({title})", data=data, options=options
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return NprParkerenOptionsFlow()


class NprParkerenOptionsFlow(config_entries.OptionsFlow):
    """Scan interval, radius, marker cap, keyword, and map markers."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            scan = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            user_input[CONF_SCAN_INTERVAL] = max(scan, MIN_SCAN_INTERVAL)
            keyword = str(user_input.get(CONF_KEYWORD) or "").strip()
            user_input[CONF_KEYWORD] = keyword or DEFAULT_KEYWORD
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        data = self.config_entry.data
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=86400,
                        step=60,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Optional(
                    CONF_RADIUS_KM,
                    default=opts.get(
                        CONF_RADIUS_KM, data.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=50,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="km",
                    )
                ),
                vol.Optional(
                    CONF_MAX_MAP_MARKERS,
                    default=opts.get(CONF_MAX_MAP_MARKERS, DEFAULT_MAX_MAP_MARKERS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=80,
                        step=1,
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_KEYWORD,
                    default=opts.get(CONF_KEYWORD, DEFAULT_KEYWORD),
                ): str,
                vol.Optional(
                    CONF_ENABLE_MARKERS,
                    default=opts.get(CONF_ENABLE_MARKERS, DEFAULT_ENABLE_MARKERS),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
