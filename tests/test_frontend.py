"""The bundled card is served and registered exactly once."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.npr_parkeren import (
    ASSETS_URL,
    CARD_FILE,
    CARD_VERSION,
    _async_register_frontend,
)


def test_card_is_bundled():
    www = Path(__file__).parent.parent / "custom_components" / "npr_parkeren" / "www"
    assert (www / CARD_FILE).is_file()
    assert not (Path(__file__).parent.parent / CARD_FILE).exists()


@pytest.mark.asyncio
async def test_frontend_registered_once():
    hass = MagicMock()
    hass.data = {}
    hass.http.async_register_static_paths = AsyncMock()
    with patch("homeassistant.components.frontend.add_extra_js_url") as add_js:
        await _async_register_frontend(hass)
        await _async_register_frontend(hass)
    hass.http.async_register_static_paths.assert_awaited_once()
    add_js.assert_called_once_with(hass, f"{ASSETS_URL}/{CARD_FILE}?v={CARD_VERSION}")
