"""Expired fare parts are ignored. A zero amount is kept."""

from __future__ import annotations

from datetime import datetime

from custom_components.npr_parkeren.schedule import (
    fare_steps_from_parts,
    format_tariff,
    select_current_fare_parts,
)

TODAY = datetime(2026, 9, 18, 11, 0)

PARTS = [
    {
        "amountfarepart": "1.00000000",
        "stepsizefarepart": "60",
        "startdatefarepart": "20160402",
        "enddatefarepart": "20201116",
        "startdurationfarepart": "120",
        "enddurationfarepart": "999999",
    },
    {
        "amountfarepart": "0.00000000",
        "stepsizefarepart": "60",
        "startdatefarepart": "20201116",
        "enddatefarepart": "29991231",
        "startdurationfarepart": "0",
        "enddurationfarepart": "60",
    },
    {
        "amountfarepart": "0.02500000",
        "stepsizefarepart": "1",
        "startdatefarepart": "20201116",
        "enddatefarepart": "29991231",
        "startdurationfarepart": "60",
        "enddurationfarepart": "999999",
    },
]


def test_expired_tariff_ignored_and_zero_kept() -> None:
    current = select_current_fare_parts(PARTS, TODAY)
    assert len(current) == 2
    assert all(part["enddatefarepart"] != "20201116" for part in current)
    amounts = [float(part["amountfarepart"]) for part in current]
    assert 0.0 in amounts
    assert 1.0 not in amounts
    steps = fare_steps_from_parts(current)
    assert steps[0]["amount_eur"] == 0.0
    assert steps[0]["step_minutes"] == 60
    text = format_tariff(current)
    assert text is not None
    assert "€0.00" in text
    assert "€1.00" not in text
