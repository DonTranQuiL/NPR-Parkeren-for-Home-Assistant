"""Snapshot drops full polygons, ignores expired tariffs, and keeps a free step."""

from __future__ import annotations

from datetime import datetime

from custom_components.npr_parkeren.snapshot import build_snapshot

TUESDAY = datetime(2026, 9, 15, 10, 0)

CATALOG = {
    "areas": [
        {
            "areaid": "A1",
            "areadesc": "Centre",
            "startdatearea": "20160101",
            "enddatearea": "29991231",
        }
    ],
    "geometries": [
        {
            "areaid": "A1",
            "areageometryastext": "POLYGON ((0 0, 4 0, 4 4, 0 4, 0 0))",
            "startdatearea": "20160101",
        }
    ],
    "links": [{"areaid": "A1", "usageid": "BETAALDP", "areaname": "Centre"}],
    "usages": [
        {
            "usageid": "BETAALDP",
            "usageiddesc": "Betaald Parkeren",
            "startdateusageid": "20160101",
            "enddateusageid": "29991231",
        }
    ],
    "area_regulations": [
        {
            "areaid": "A1",
            "regulationid": "R1",
            "usageid": "BETAALDP",
            "startdatearearegulation": "20160101000000",
            "enddatearearegulation": "29991231235959",
        }
    ],
    "regulations": [
        {
            "regulationid": "R1",
            "regulationdesc": "week",
            "startdateregulation": "20160101",
            "enddateregulation": "29991231",
        }
    ],
    "timeframes": [
        {
            "regulationid": "R1",
            "daytimeframe": "DINSDAG",
            "starttimetimeframe": "900",
            "endtimetimeframe": "1800",
            "startdatetimeframe": "20160601000000",
            "enddatetimeframe": "29991231235959",
            "farecalculationcode": "F1",
            "maxdurationright": "120",
        }
    ],
    "fares": [
        {
            "farecalculationcode": "F1",
            "farecalculationdesc": "first hour free",
            "startdatefare": "20201116",
            "enddatefare": "29991231",
        }
    ],
    "fare_parts": [
        {
            "farecalculationcode": "F1",
            "amountfarepart": "9.00000000",
            "stepsizefarepart": "60",
            "startdatefarepart": "20100101",
            "enddatefarepart": "20200101",
            "startdurationfarepart": "0",
        },
        {
            "farecalculationcode": "F1",
            "amountfarepart": "0.00000000",
            "stepsizefarepart": "60",
            "startdatefarepart": "20201116",
            "enddatefarepart": "29991231",
            "startdurationfarepart": "0",
        },
    ],
    "special_days": [],
    "specs": [
        {
            "areaid": "A1",
            "capacity": "12",
            "chargingpointcapacity": "1",
            "maximumvehicleheight": "200",
            "startdatespecifications": "20200101",
        }
    ],
}


def test_snapshot_inside_zone_keeps_free_step_and_hides_wkt() -> None:
    payload = build_snapshot(
        CATALOG,
        latitude=2.0,
        longitude=2.0,
        radius_km=1.0,
        moment=TUESDAY,
        decisions=[
            {
                "title": "Kept",
                "description": "Verkeersbesluit",
                "link": "https://example.test/kept",
                "pub_date": "Tue, 15 Sep 2026 00:00:00 +0200",
                "category": "Gemeenteblad",
                "classification": "traffic_decision",
            }
        ],
        max_markers=5,
        municipality="Example",
        manager_id="1",
        manager_desc="Example",
    )
    assert len(payload["zones"]) == 1
    zone = payload["zones"][0]
    assert zone["areaid"] == "A1"
    assert zone["inside"] is True
    assert zone["in_force"] is True
    assert zone["max_stay_minutes"] == 120
    assert zone["fare_steps"][0]["amount_eur"] == 0.0
    assert "€0.00" in zone["tariff"]
    assert "€9.00" not in (zone["tariff"] or "")
    assert "areageometryastext" not in zone
    assert len(zone["ring"]) <= 12
    assert "start" not in payload["decisions"][0]
    assert "end" not in payload["decisions"][0]
    blob = str(payload)
    assert "POLYGON" not in blob
