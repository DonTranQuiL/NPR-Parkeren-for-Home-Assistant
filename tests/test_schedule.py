"""Weekday name plus HHMM window."""

from __future__ import annotations

from datetime import datetime

from custom_components.npr_parkeren.schedule import (
    hhmm_to_minutes,
    parse_npr_date,
    timeframe_active,
)

# 15 September 2026 is a Tuesday. 18 September 2026 is a Friday.
TUESDAY_MORNING = datetime(2026, 9, 15, 10, 0)
TUESDAY_EARLY = datetime(2026, 9, 15, 8, 30)
TUESDAY_OPEN = datetime(2026, 9, 15, 9, 0)
TUESDAY_CLOSE = datetime(2026, 9, 15, 18, 0)
WEDNESDAY = datetime(2026, 9, 16, 10, 0)

WINDOW = {
    "daytimeframe": "DINSDAG",
    "starttimetimeframe": "900",
    "endtimetimeframe": "1800",
    "startdatetimeframe": "20160601000000",
    "enddatetimeframe": "29991231235959",
}


def test_hhmm_900_is_nine() -> None:
    assert hhmm_to_minutes("900") == 9 * 60
    assert hhmm_to_minutes(1800) == 18 * 60
    assert hhmm_to_minutes("0") == 0
    assert hhmm_to_minutes("2400") == 24 * 60


def test_weekday_and_hhmm_window() -> None:
    assert timeframe_active(WINDOW, TUESDAY_MORNING) is True
    assert timeframe_active(WINDOW, TUESDAY_OPEN) is True
    assert timeframe_active(WINDOW, TUESDAY_EARLY) is False
    assert timeframe_active(WINDOW, TUESDAY_CLOSE) is False
    assert timeframe_active(WINDOW, WEDNESDAY) is False


def test_iso_area_date_parses() -> None:
    assert parse_npr_date("2018-12-20T00:00:00.000") is not None
    assert parse_npr_date("2018-12-20T00:00:00.000").isoformat() == "2018-12-20"
    assert parse_npr_date("20160601000000").isoformat() == "2016-06-01"
