"""Neighbour gazette items are dropped. Classification comes from the text."""

from __future__ import annotations

from custom_components.npr_parkeren.gazette import (
    build_gazette_query,
    classify_decision,
    filter_by_municipality,
)


def test_neighbor_item_dropped() -> None:
    items = [
        {
            "title": "gmb-2026-1 : Landgraaf",
            "description": "Verkeersbesluit in Landgraaf",
            "link": "https://zoek.officielebekendmakingen.nl/gmb-landgraaf.html",
            "pub_date": "Fri, 18 Sep 2026 00:00:00 +0200",
            "category": "Gemeenteblad",
        },
        {
            "title": "gmb-2026-2 : Kerkrade",
            "description": "Parkeerverbod Nieuwstraat in Kerkrade",
            "link": "https://zoek.officielebekendmakingen.nl/gmb-kerkrade.html",
            "pub_date": "Fri, 18 Sep 2026 00:00:00 +0200",
            "category": "Gemeenteblad",
        },
    ]
    kept = filter_by_municipality(items, "Kerkrade")
    assert len(kept) == 1
    assert "Landgraaf" not in kept[0]["title"]
    assert "Kerkrade" in kept[0]["title"]


def test_classify_from_text_without_invented_dates() -> None:
    assert (
        classify_decision("Besluit", "Parkeerverbod op de Nieuwstraat") == "parking_ban"
    )
    assert (
        classify_decision("Besluit", "Wegafsluiting wegens werkzaamheden")
        == "road_closure"
    )
    assert (
        classify_decision("Besluit", "Verkeersbesluit Kerkraadseweg")
        == "traffic_decision"
    )


def test_query_substitutes_municipality_and_keyword() -> None:
    query = build_gazette_query("Kerkrade", "verkeersbesluit")
    assert 'cql.textAndIndexes=="Kerkrade"' in query
    assert 'cql.textAndIndexes=="verkeersbesluit"' in query
    assert 'w.publicatienaam=="Gemeenteblad"' in query
    assert 'c.product-area=="officielepublicaties"' in query
