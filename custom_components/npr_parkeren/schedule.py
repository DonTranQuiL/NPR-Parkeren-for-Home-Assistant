"""NPR date windows, weekday timeframes, and tariff steps.

Timeframe dates look like ``20160601000000``. Area and fare dates are often
``YYYYMMDD`` or an ISO timestamp such as ``2018-12-20T00:00:00.000``.
``starttimetimeframe`` / ``endtimetimeframe`` are HHMM integers: ``900`` is
09:00 and ``2400`` is the end of the day. ``daytimeframe`` is a Dutch weekday
name such as ``DINSDAG``, sometimes qualified (``ZATERDAG DECEMBER``) or a
special-day name (``FEESTDAG``).

A fare step whose ``amountfarepart`` is 0 is free for that duration. That is
real data (the first hour free) and must not be treated as missing.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

DUTCH_WEEKDAYS = {
    0: "MAANDAG",
    1: "DINSDAG",
    2: "WOENSDAG",
    3: "DONDERDAG",
    4: "VRIJDAG",
    5: "ZATERDAG",
    6: "ZONDAG",
}
WEEKDAY_NAMES = set(DUTCH_WEEKDAYS.values())
WEEKDAY_ALIASES = {
    "MA": "MAANDAG",
    "DI": "DINSDAG",
    "WO": "WOENSDAG",
    "DO": "DONDERDAG",
    "VR": "VRIJDAG",
    "ZA": "ZATERDAG",
    "ZO": "ZONDAG",
}
DUTCH_MONTHS = {
    1: "JANUARI",
    2: "FEBRUARI",
    3: "MAART",
    4: "APRIL",
    5: "MEI",
    6: "JUNI",
    7: "JULI",
    8: "AUGUSTUS",
    9: "SEPTEMBER",
    10: "OKTOBER",
    11: "NOVEMBER",
    12: "DECEMBER",
}
_MISSING = {"", "NULL", "NONE"}


def _blank(value: Any) -> bool:
    if value is None:
        return True
    return str(value).strip().upper() in _MISSING


def parse_npr_date(value: Any) -> date | None:
    """Parse an NPR date field to a calendar date. Time of day is ignored."""
    if _blank(value):
        return None
    text = str(value).strip()
    if "T" in text or (len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-"):
        head = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(head).date()
        except ValueError:
            pass
    digits = re.sub(r"\D", "", text)
    if len(digits) < 8:
        return None
    try:
        return date(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def period_contains_date(start: Any, end: Any, day: date) -> bool:
    """Inclusive date window. Missing bounds are open. Invalid bounds are ignored."""
    start_day = parse_npr_date(start)
    end_day = parse_npr_date(end)
    started = start_day is None or day >= start_day
    ended = end_day is None or day <= end_day
    return started and ended


def as_float(value: Any) -> float | None:
    """Parse a number. ``0`` is a real value. Empty and ``NULL`` are missing."""
    if _blank(value) or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    number = as_float(value)
    if number is None:
        return None
    return int(number)


def hhmm_to_minutes(value: Any) -> int | None:
    """Convert an NPR HHMM value to minutes from midnight.

    ``900`` is 09:00. ``0`` is 00:00. ``2400`` is 24:00. ``09:00`` is accepted.
    """
    if _blank(value) or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        text = str(int(value)) if float(value) == int(value) else str(value)
    else:
        text = str(value).strip()
    if ":" in text:
        hour_text, minute_text = text.split(":", 1)
        try:
            return int(hour_text) * 60 + int(minute_text)
        except ValueError:
            return None
    if not re.fullmatch(r"\d{1,4}", text):
        return None
    number = int(text)
    if len(text) <= 2:
        return number * 60
    return (number // 100) * 60 + (number % 100)


def time_in_window(start: Any, end: Any, moment: datetime) -> bool:
    """Return True when ``moment`` is inside an HHMM window (end exclusive)."""
    start_min = hhmm_to_minutes(start)
    end_min = hhmm_to_minutes(end)
    if start_min is None or end_min is None:
        return False
    if end_min >= 24 * 60:
        end_min = 24 * 60
    now = moment.hour * 60 + moment.minute
    if start_min == end_min:
        return False
    if start_min < end_min:
        return start_min <= now < end_min
    return now >= start_min or now < end_min


def _tokens(name: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", name.upper())


def timeframe_matches_day(
    daytimeframe: Any, moment: datetime, specials: set[str] | None = None
) -> bool:
    """Match a Dutch weekday, a month-qualified weekday, or a special-day name."""
    name = str(daytimeframe or "").strip().upper()
    if not name:
        return False
    special_names = {item.strip().upper() for item in (specials or set()) if item}
    if name in special_names:
        return True
    weekday = DUTCH_WEEKDAYS[moment.weekday()]
    if name == weekday:
        return True
    tokens = _tokens(name)
    month = DUTCH_MONTHS[moment.month]
    if month not in tokens:
        return False
    if weekday in tokens:
        return True
    return any(WEEKDAY_ALIASES.get(token) == weekday for token in tokens)


def timeframe_active(
    row: dict[str, Any], moment: datetime, specials: set[str] | None = None
) -> bool:
    """Date window, weekday (or special day), and HHMM clock, all must match."""
    if not period_contains_date(
        row.get("startdatetimeframe"), row.get("enddatetimeframe"), moment.date()
    ):
        return False
    if not timeframe_matches_day(row.get("daytimeframe"), moment, specials):
        return False
    return time_in_window(
        row.get("starttimetimeframe"), row.get("endtimetimeframe"), moment
    )


def pick_timeframe(
    frames: list[dict[str, Any]],
    moment: datetime,
    specials: set[str] | None = None,
) -> dict[str, Any] | None:
    """Prefer a special-day window over a month window over a plain weekday."""
    special_names = {item.strip().upper() for item in (specials or set()) if item}
    active = [row for row in frames if timeframe_active(row, moment, special_names)]
    if not active:
        return None

    def rank(row: dict[str, Any]) -> int:
        name = str(row.get("daytimeframe") or "").strip().upper()
        if name in special_names:
            return 0
        if name in WEEKDAY_NAMES:
            return 2
        return 1

    active.sort(key=rank)
    return active[0]


def _start_key(row: dict[str, Any], field: str) -> date:
    return parse_npr_date(row.get(field)) or date.min


def select_latest_window(
    rows: list[dict[str, Any]], start_field: str, end_field: str, moment: datetime
) -> list[dict[str, Any]]:
    """Rows whose date window contains today, narrowed to the latest start."""
    day = moment.date()
    valid = [
        row
        for row in rows
        if period_contains_date(row.get(start_field), row.get(end_field), day)
    ]
    if not valid:
        return []
    latest = max(_start_key(row, start_field) for row in valid)
    return [row for row in valid if _start_key(row, start_field) == latest]


def select_current_row(
    rows: list[dict[str, Any]], start_field: str, end_field: str, moment: datetime
) -> dict[str, Any] | None:
    chosen = select_latest_window(rows, start_field, end_field, moment)
    return chosen[-1] if chosen else None


def select_current_fare_parts(
    parts: list[dict[str, Any]], moment: datetime
) -> list[dict[str, Any]]:
    """Tariff steps in force today. Expired windows are dropped, zeroes kept."""
    chosen = select_latest_window(parts, "startdatefarepart", "enddatefarepart", moment)

    def duration_key(row: dict[str, Any]) -> int:
        return as_int(row.get("startdurationfarepart")) or 0

    chosen.sort(key=duration_key)
    return chosen


def max_stay_minutes(value: Any) -> int | None:
    """Minutes of maximum stay. ``0`` in the feed means no maximum, not zero minutes."""
    minutes = as_int(value)
    if minutes is None or minutes <= 0:
        return None
    return minutes


def fare_steps_from_parts(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Whitelist step records. An amount of 0 is included."""
    steps: list[dict[str, Any]] = []
    for part in parts:
        amount = as_float(part.get("amountfarepart"))
        if amount is None:
            continue
        step_minutes = as_int(part.get("stepsizefarepart"))
        steps.append(
            {
                "amount_eur": amount,
                "step_minutes": step_minutes,
                "start_minute": as_int(part.get("startdurationfarepart")) or 0,
                "end_minute": as_int(part.get("enddurationfarepart")),
            }
        )
    return steps


def format_eur(amount: float) -> str:
    """Format euros. Zero is ``€0.00``, not an empty string."""
    if amount == 0:
        return "€0.00"
    text = f"{round(amount, 4):.4f}".rstrip("0").rstrip(".")
    if "." not in text:
        text = f"{text}.00"
    elif len(text.split(".", 1)[1]) == 1:
        text = f"{text}0"
    return f"€{text}"


def format_tariff(parts: list[dict[str, Any]]) -> str | None:
    """Human tariff from current steps, including free steps."""
    bits: list[str] = []
    for step in fare_steps_from_parts(parts):
        label = format_eur(float(step["amount_eur"]))
        minutes = step.get("step_minutes")
        if minutes:
            bits.append(f"{label} / {minutes} min")
        else:
            bits.append(label)
    if not bits:
        return None
    return ", ".join(bits)


def special_names_on(rows: list[dict[str, Any]], day: date) -> set[str]:
    """Special-day names whose ``datespecialday`` is ``day``."""
    names: set[str] = set()
    for row in rows:
        if parse_npr_date(row.get("datespecialday")) != day:
            continue
        name = str(row.get("namespecialday") or "").strip().upper()
        if name and name not in _MISSING:
            names.add(name)
    return names
