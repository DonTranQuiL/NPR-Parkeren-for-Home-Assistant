"""Point-in-polygon for POLYGON, POLYGON Z, and MULTIPOLYGON."""

from __future__ import annotations

from custom_components.npr_parkeren.geo import point_in_wkt, simplify_ring

SQUARE = "POLYGON ((0 0, 4 0, 4 4, 0 4, 0 0))"
SQUARE_Z = "POLYGON Z ((0 0 12, 4 0 12, 4 4 8.5, 0 4 8.5, 0 0 12))"
MULTI = (
    "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 1, 0 0)), ((10 10, 12 10, 12 12, 10 12, 10 10)))"
)


def test_point_inside_polygon() -> None:
    assert point_in_wkt(SQUARE, 2.0, 2.0) is True
    assert point_in_wkt(SQUARE, 5.0, 2.0) is False
    assert point_in_wkt(SQUARE, 2.0, -0.1) is False


def test_polygon_z_ignores_height() -> None:
    assert point_in_wkt(SQUARE_Z, 1.0, 1.0) is True
    assert point_in_wkt(SQUARE_Z, 6.0, 6.0) is False


def test_multipolygon_second_ring() -> None:
    assert point_in_wkt(MULTI, 0.5, 0.5) is True
    assert point_in_wkt(MULTI, 11.0, 11.0) is True
    assert point_in_wkt(MULTI, 5.0, 5.0) is False


def test_hole_is_not_inside() -> None:
    holed = "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0), (4 4, 6 4, 6 6, 4 6, 4 4))"
    assert point_in_wkt(holed, 1.0, 1.0) is True
    assert point_in_wkt(holed, 5.0, 5.0) is False


def test_simplify_ring_caps_at_twelve() -> None:
    ring = [(float(i), 0.0) for i in range(30)]
    ring.append(ring[0])
    sampled = simplify_ring(ring, 12)
    assert len(sampled) <= 12
    assert sampled[0] == sampled[-1]
