"""Shared fixtures. Home Assistant is optional: pure tests do not import it."""

from __future__ import annotations

import importlib.util

if importlib.util.find_spec("pytest_homeassistant_custom_component"):
    pytest_plugins = ["pytest_homeassistant_custom_component"]
