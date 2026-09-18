"""Build the public snapshot from one cached municipality catalog.

The catalog may hold full WKT. The snapshot never does: a centroid and at
most 12 ring points are published for the card.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .const import (
    DECISION_MAX,
    DESCRIPTION_MAX,
    KIND_RANK,
    RING_POINT_MAX,
    USAGE_LABELS,
    USAGE_OTHER,
)
from .gazette import public_decision, sort_decisions
from .geo import centroid, haversine_km, parse_wkt, point_in_polygons, public_ring
from .schedule import (
    as_float,
    as_int,
    fare_steps_from_parts,
    format_tariff,
    max_stay_minutes,
    period_contains_date,
    pick_timeframe,
    select_current_fare_parts,
    select_current_row,
    special_names_on,
)


def _rows(catalog: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = catalog.get(key) or []
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _index(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ident = str(row.get(key) or "").strip()
        if not ident:
            continue
        grouped.setdefault(ident, []).append(row)
    return grouped


def _usage_kind(usage_id: str | None) -> str:
    code = (usage_id or "").upper()
    if code == "BETAALDP":
        return "paid"
    if code == "BLAUWEZ":
        return "blue"
    if "VERGUN" in code:
        return "permit"
    if code == "GARAGEP":
        return "garage"
    if code == "TERREINP":
        return "lot"
    return USAGE_OTHER


def _usage_label(
    usages: dict[str, list[dict[str, Any]]], usage_id: str, moment: datetime
) -> str:
    current = select_current_row(
        usages.get(usage_id, []), "startdateusageid", "enddateusageid", moment
    )
    if current and current.get("usageiddesc"):
        return str(current["usageiddesc"])
    return USAGE_LABELS.get(usage_id, usage_id)


def _best_row(
    rows: list[dict[str, Any]],
    start_field: str,
    end_field: str,
    moment: datetime,
) -> dict[str, Any] | None:
    day = moment.date()
    current = [
        row
        for row in rows
        if period_contains_date(row.get(start_field), row.get(end_field), day)
    ]
    pool = current or rows
    if not pool:
        return None
    return select_current_row(pool, start_field, end_field, moment) or pool[-1]


def _regulation_choice(
    links: list[dict[str, Any]],
    area_regs: list[dict[str, Any]],
    regulations: dict[str, list[dict[str, Any]]],
    timeframes: dict[str, list[dict[str, Any]]],
    fares: dict[str, list[dict[str, Any]]],
    fare_parts: dict[str, list[dict[str, Any]]],
    usages: dict[str, list[dict[str, Any]]],
    moment: datetime,
    specials: set[str],
) -> dict[str, Any]:
    day = moment.date()
    candidates: list[dict[str, Any]] = []
    for link in area_regs:
        if not period_contains_date(
            link.get("startdatearearegulation"),
            link.get("enddatearearegulation"),
            day,
        ):
            continue
        regulation_id = str(link.get("regulationid") or "")
        frame = pick_timeframe(timeframes.get(regulation_id, []), moment, specials)
        if frame is None:
            continue
        usage_id = str(link.get("usageid") or "")
        regulation = select_current_row(
            regulations.get(regulation_id, []),
            "startdateregulation",
            "enddateregulation",
            moment,
        )
        code = str(frame.get("farecalculationcode") or "").strip()
        if code.upper() == "NULL":
            code = ""
        parts = (
            select_current_fare_parts(fare_parts.get(code, []), moment) if code else []
        )
        fare = (
            select_current_row(
                fares.get(code, []), "startdatefare", "enddatefare", moment
            )
            if code
            else None
        )
        candidates.append(
            {
                "usage_id": usage_id,
                "usage": _usage_label(usages, usage_id, moment) if usage_id else "",
                "usage_kind": _usage_kind(usage_id),
                "in_force": True,
                "regulation_id": regulation_id,
                "regulation": (regulation or {}).get("regulationdesc") or "",
                "maximum_day_charge": as_float(
                    (regulation or {}).get("maximumdaycharge")
                ),
                "tariff": format_tariff(parts),
                "tariff_description": (fare or {}).get("farecalculationdesc") or "",
                "fare_steps": fare_steps_from_parts(parts),
                "max_stay_minutes": max_stay_minutes(frame.get("maxdurationright")),
            }
        )

    if candidates:
        candidates.sort(key=lambda item: KIND_RANK.get(item["usage_kind"], 9))
        chosen = dict(candidates[0])
        chosen["also"] = [
            item["usage_id"] for item in candidates[1:] if item.get("usage_id")
        ][:6]
        return chosen

    usage_id = ""
    for link in area_regs:
        if period_contains_date(
            link.get("startdatearearegulation"),
            link.get("enddatearearegulation"),
            day,
        ):
            usage_id = str(link.get("usageid") or "")
            if usage_id:
                break
    if not usage_id:
        for link in links:
            usage_id = str(link.get("usageid") or "")
            if usage_id:
                break
    return {
        "usage_id": usage_id,
        "usage": _usage_label(usages, usage_id, moment) if usage_id else "",
        "usage_kind": _usage_kind(usage_id) if usage_id else USAGE_OTHER,
        "in_force": False,
        "regulation_id": "",
        "regulation": "",
        "maximum_day_charge": None,
        "tariff": None,
        "tariff_description": "",
        "fare_steps": [],
        "max_stay_minutes": None,
        "also": [],
    }


def build_snapshot(
    catalog: dict[str, Any] | None,
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
    moment: datetime,
    decisions: list[dict[str, Any]] | None,
    max_markers: int,
    municipality: str,
    manager_id: str,
    manager_desc: str,
) -> dict[str, Any]:
    """Return the coordinator payload. Full polygons are not included."""
    catalog = catalog or {}
    areas = _rows(catalog, "areas")
    links = _index(_rows(catalog, "links"), "areaid")
    usages = _index(_rows(catalog, "usages"), "usageid")
    geometries = _index(_rows(catalog, "geometries"), "areaid")
    area_regs = _index(_rows(catalog, "area_regulations"), "areaid")
    regulations = _index(_rows(catalog, "regulations"), "regulationid")
    timeframes = _index(_rows(catalog, "timeframes"), "regulationid")
    fares = _index(_rows(catalog, "fares"), "farecalculationcode")
    fare_parts = _index(_rows(catalog, "fare_parts"), "farecalculationcode")
    specs = _index(_rows(catalog, "specs"), "areaid")
    specials = special_names_on(_rows(catalog, "special_days"), moment.date())

    day = moment.date()
    zones: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    area_count = 0

    for area in areas:
        if not period_contains_date(
            area.get("startdatearea"), area.get("enddatearea"), day
        ):
            continue
        area_id = str(area.get("areaid") or "").strip()
        if not area_id:
            continue
        area_count += 1
        name = str(area.get("areadesc") or "").strip()
        link_rows = links.get(area_id, [])
        if not name and link_rows:
            name = str(link_rows[0].get("areaname") or "").strip()
        choice = _regulation_choice(
            link_rows,
            area_regs.get(area_id, []),
            regulations,
            timeframes,
            fares,
            fare_parts,
            usages,
            moment,
            specials,
        )
        spec = _best_row(
            specs.get(area_id, []),
            "startdatespecifications",
            "enddatespecifications",
            moment,
        )
        geometry = _best_row(
            geometries.get(area_id, []), "startdatearea", "enddatearea", moment
        )
        wkt = (geometry or {}).get("areageometryastext")
        polygons = parse_wkt(str(wkt)) if wkt else []
        outer = polygons[0][0] if polygons and polygons[0] else []
        centre = centroid(outer) if outer else None
        inside = point_in_polygons(longitude, latitude, polygons) if polygons else False
        distance = None
        zone_lat = None
        zone_lon = None
        if centre is not None:
            zone_lon, zone_lat = centre
            distance = round(haversine_km(latitude, longitude, zone_lat, zone_lon), 3)
        in_radius = inside or (distance is not None and distance <= float(radius_km))
        zone = {
            "areaid": area_id,
            "name": name or area_id,
            "usage_id": choice["usage_id"],
            "usage": choice["usage"],
            "usage_kind": choice["usage_kind"],
            "latitude": round(zone_lat, 6) if zone_lat is not None else None,
            "longitude": round(zone_lon, 6) if zone_lon is not None else None,
            "distance_km": distance,
            "inside": inside,
            "in_force": choice["in_force"],
            "tariff": choice["tariff"],
            "tariff_description": choice["tariff_description"],
            "fare_steps": choice["fare_steps"],
            "max_stay_minutes": choice["max_stay_minutes"],
            "maximum_day_charge": choice["maximum_day_charge"],
            "regulation": choice["regulation"],
            "capacity": as_int((spec or {}).get("capacity")),
            "charging_point_capacity": as_int(
                (spec or {}).get("chargingpointcapacity")
            ),
            "maximum_vehicle_height": as_int((spec or {}).get("maximumvehicleheight")),
            "ring": public_ring(outer, RING_POINT_MAX) if in_radius else [],
        }
        if polygons and in_radius:
            zones.append(zone)
        elif not polygons:
            unmapped.append(
                {
                    "areaid": zone["areaid"],
                    "name": zone["name"],
                    "usage_id": zone["usage_id"],
                    "usage": zone["usage"],
                    "usage_kind": zone["usage_kind"],
                    "in_force": zone["in_force"],
                    "tariff": zone["tariff"],
                    "max_stay_minutes": zone["max_stay_minutes"],
                }
            )

    zones.sort(
        key=lambda item: (
            item["distance_km"] is None,
            item["distance_km"] if item["distance_km"] is not None else 0,
            item["areaid"],
        )
    )
    inside_zones = [zone for zone in zones if zone["inside"]]
    inside_zones.sort(
        key=lambda item: (
            0 if item["in_force"] else 1,
            KIND_RANK.get(item["usage_kind"], 9),
            item["distance_km"] if item["distance_km"] is not None else 9999,
        )
    )
    if inside_zones:
        primary = inside_zones[0]
        regulated = {
            "inside": True,
            "in_force": primary["in_force"],
            "areaid": primary["areaid"],
            "name": primary["name"],
            "usage_id": primary["usage_id"],
            "usage": primary["usage"],
            "usage_kind": primary["usage_kind"],
            "tariff": primary["tariff"],
            "tariff_description": primary["tariff_description"],
            "fare_steps": primary["fare_steps"],
            "max_stay_minutes": primary["max_stay_minutes"],
            "distance_km": primary["distance_km"],
        }
    else:
        regulated = {
            "inside": False,
            "in_force": False,
            "areaid": None,
            "name": None,
            "usage_id": None,
            "usage": None,
            "usage_kind": None,
            "tariff": None,
            "tariff_description": "",
            "fare_steps": [],
            "max_stay_minutes": None,
            "distance_km": None,
        }

    published_decisions = [
        public_decision(item, DESCRIPTION_MAX)
        for item in sort_decisions(list(decisions or []))[:DECISION_MAX]
    ]
    tracked = [
        {
            "areaid": zone["areaid"],
            "name": zone["name"],
            "usage_kind": zone["usage_kind"],
            "usage": zone["usage"],
            "latitude": zone["latitude"],
            "longitude": zone["longitude"],
            "in_force": zone["in_force"],
            "inside": zone["inside"],
            "tariff": zone["tariff"],
            "max_stay_minutes": zone["max_stay_minutes"],
            "distance_km": zone["distance_km"],
        }
        for zone in zones
        if zone["latitude"] is not None and zone["longitude"] is not None
    ][: max(int(max_markers), 0)]

    return {
        "municipality": municipality,
        "areamanager_id": manager_id,
        "areamanager_desc": manager_desc,
        "latitude": latitude,
        "longitude": longitude,
        "radius_km": radius_km,
        "zones": zones,
        "unmapped_zones": unmapped[:100],
        "unmapped_total": len(unmapped),
        "regulated_here": regulated,
        "decisions": published_decisions,
        "latest_decision": published_decisions[0] if published_decisions else None,
        "tracked": tracked,
        "counts": {
            "areas": area_count,
            "zones_in_radius": len(zones),
            "in_force": sum(1 for zone in zones if zone["in_force"]),
            "inside": 1 if regulated["inside"] else 0,
            "decisions": len(published_decisions),
            "unmapped": len(unmapped),
        },
    }
