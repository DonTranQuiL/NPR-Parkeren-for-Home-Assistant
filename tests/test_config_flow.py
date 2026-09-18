"""Config flow happy path. The area manager lookup is mocked; no live network."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.npr_parkeren.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MUNICIPALITY,
    CONF_RADIUS_KM,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return None


async def test_config_flow_happy_path(hass) -> None:
    managers = [{"areamanagerid": "928", "areamanagerdesc": "Kerkrade"}]
    with patch(
        "custom_components.npr_parkeren.config_flow.NprApi.lookup_managers",
        new=AsyncMock(return_value=managers),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_MUNICIPALITY: "Kerkrade",
                CONF_LATITUDE: 50.865,
                CONF_LONGITUDE: 6.062,
                CONF_RADIUS_KM: 2.0,
            },
        )
    assert result["type"] == "create_entry"
    assert result["result"].unique_id == "928"
    assert result["data"]["areamanagerid"] == "928"
    assert result["data"]["areamanagerdesc"] == "Kerkrade"
    assert result["data"]["municipality"] == "Kerkrade"


async def test_same_municipality_cannot_be_added_twice(hass) -> None:
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="928",
        data={"areamanagerid": "928", "municipality": "Kerkrade"},
    ).add_to_hass(hass)
    managers = [{"areamanagerid": "928", "areamanagerdesc": "Kerkrade"}]
    with patch(
        "custom_components.npr_parkeren.config_flow.NprApi.lookup_managers",
        new=AsyncMock(return_value=managers),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_MUNICIPALITY: "Kerkrade",
                CONF_LATITUDE: 50.865,
                CONF_LONGITUDE: 6.062,
                CONF_RADIUS_KM: 1.0,
            },
        )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
