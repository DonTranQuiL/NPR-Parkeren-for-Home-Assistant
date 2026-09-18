"""WKT polygons and point-in-polygon for NPR area geometry.

RDW field ``areageometryastext`` is WKT in WGS84. Coordinate order is
longitude, latitude. A third (Z) value is ignored. POLYGON and MULTIPOLYGON
are both accepted.
"""

from __future__ import annotations

import math
import re

_NUM = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_COORD = re.compile(rf"({_NUM})\s+({_NUM})(?:\s+{_NUM})?")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two WGS84 points."""
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(min(1.0, a)))


def _unwrap(blob: str) -> str:
    """Strip one matched outer pair of parentheses."""
    text = blob.strip()
    if not (text.startswith("(") and text.endswith(")")):
        return text
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(text) - 1:
                return text
    return text[1:-1].strip()


def _split_top(blob: str) -> list[str]:
    """Split on commas that sit at parenthesis depth zero."""
    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(blob):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            piece = blob[start:index].strip()
            if piece:
                parts.append(piece)
            start = index + 1
    tail = blob[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _coords(text: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for match in _COORD.finditer(text):
        points.append((float(match.group(1)), float(match.group(2))))
    return points


def parse_wkt(text: str | None) -> list[list[list[tuple[float, float]]]]:
    """Parse POLYGON or MULTIPOLYGON WKT into polygons of rings of (lon, lat)."""
    raw = (text or "").strip()
    if "(" not in raw:
        return []
    head = raw.split("(", 1)[0].strip().upper()
    body = raw[raw.find("(") :].strip()
    polygons_in = _split_top(_unwrap(body)) if head.startswith("MULTI") else [body]
    polygons: list[list[list[tuple[float, float]]]] = []
    for blob in polygons_in:
        rings: list[list[tuple[float, float]]] = []
        for ring_blob in _split_top(_unwrap(blob)):
            content = ring_blob.strip()
            if content.startswith("("):
                content = _unwrap(content)
            ring = _coords(content)
            if len(ring) >= 3:
                rings.append(ring)
        if rings:
            polygons.append(rings)
    return polygons


def point_in_ring(
    longitude: float, latitude: float, ring: list[tuple[float, float]]
) -> bool:
    """Ray-cast a WGS84 point against one ring (lon, lat pairs)."""
    inside = False
    count = len(ring)
    if count < 3:
        return False
    previous = count - 1
    for index in range(count):
        xi, yi = ring[index]
        xj, yj = ring[previous]
        if (yi > latitude) != (yj > latitude):
            # Horizontal edges never enter this branch, so the divisor is not zero.
            slope = (xj - xi) * (latitude - yi) / (yj - yi) + xi
            if longitude < slope:
                inside = not inside
        previous = index
    return inside


def point_in_polygons(
    longitude: float,
    latitude: float,
    polygons: list[list[list[tuple[float, float]]]],
) -> bool:
    """Return True when the point is inside any polygon (holes use even-odd)."""
    for rings in polygons:
        inside = False
        for ring in rings:
            if point_in_ring(longitude, latitude, ring):
                inside = not inside
        if inside:
            return True
    return False


def point_in_wkt(text: str | None, longitude: float, latitude: float) -> bool:
    """Return True when longitude/latitude lies inside the WKT geometry."""
    return point_in_polygons(longitude, latitude, parse_wkt(text))


def centroid(ring: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Average vertex of a ring, ignoring the repeated closing point."""
    if not ring:
        return None
    points = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    if not points:
        return None
    lon = sum(point[0] for point in points) / len(points)
    lat = sum(point[1] for point in points) / len(points)
    return lon, lat


def simplify_ring(
    ring: list[tuple[float, float]], limit: int = 12
) -> list[tuple[float, float]]:
    """Evenly sample a ring down to ``limit`` points, keeping it closed."""
    if not ring or limit < 2 or len(ring) <= limit:
        return [(float(lon), float(lat)) for lon, lat in ring]
    closed = ring[0] == ring[-1] and len(ring) > 1
    core = list(ring[:-1] if closed else ring)
    keep = max(limit - 1, 2) if closed else limit
    if len(core) <= keep:
        sampled = core
    else:
        last = len(core) - 1
        indexes: list[int] = []
        for step in range(keep):
            indexes.append(round(step * last / (keep - 1)))
        unique: list[int] = []
        for index in indexes:
            if not unique or unique[-1] != index:
                unique.append(index)
        sampled = [core[index] for index in unique]
    if closed and sampled:
        sampled = [*sampled, sampled[0]]
    return [(float(lon), float(lat)) for lon, lat in sampled]


def public_ring(
    ring: list[tuple[float, float]], limit: int = 12
) -> list[dict[str, float]]:
    """Return at most ``limit`` ``{latitude, longitude}`` points for the card."""
    points: list[dict[str, float]] = []
    for lon, lat in simplify_ring(ring, limit):
        points.append({"latitude": round(lat, 6), "longitude": round(lon, 6)})
    return points
