"""UpdateFailed does not wipe a previously stored catalog."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.npr_parkeren.api import NprApiError
from custom_components.npr_parkeren.const import DOMAIN
from custom_components.npr_parkeren.coordinator import NprParkerenCoordinator


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry1",
        unique_id="1",
        data={
            "municipality": "Kerkrade",
            "areamanagerid": "1",
            "areamanagerdesc": "Kerkrade",
            "latitude": 50.86,
            "longitude": 6.06,
            "radius_km": 2.0,
        },
        options={
            "scan_interval": 900,
            "radius_km": 2.0,
            "max_map_markers": 10,
            "keyword": "verkeersbesluit",
            "enable_markers": True,
        },
    )


async def test_update_failed_keeps_cache(hass) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    coordinator = NprParkerenCoordinator(hass, entry)
    sentinel = {
        "areamanagerid": "1",
        "areas": [{"areaid": "KEEP", "areadesc": "Keep"}],
        "sentinel": "keep",
    }
    coordinator.catalog_cache.payload = sentinel
    coordinator.catalog_cache._loaded = True
    coordinator.last_good_data = None
    coordinator.api.fetch_catalog = AsyncMock(side_effect=NprApiError("down"))
    coordinator.api.fetch_gazette_xml = AsyncMock(side_effect=NprApiError("rss"))

    with (
        patch_build(),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()

    assert coordinator.catalog_cache.payload is sentinel
    assert coordinator.catalog_cache.payload["sentinel"] == "keep"


def patch_build():
    from unittest.mock import patch

    return patch(
        "custom_components.npr_parkeren.coordinator.build_snapshot",
        side_effect=RuntimeError("cannot build"),
    )
