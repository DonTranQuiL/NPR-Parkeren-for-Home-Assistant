"""Neighbour gazette items are dropped. Classification comes from the text."""

from __future__ import annotations

from custom_components.npr_parkeren.gazette import (
    build_gazette_query,
    classify_decision,
    extract_publication,
    filter_by_municipality,
    publication_xml_url,
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


def test_query_uses_rubriek_not_a_second_keyword() -> None:
    query = build_gazette_query("Maastricht", "verkeersbesluit")
    assert 'cql.textAndIndexes=="Maastricht"' in query
    assert 'dt.type=="verkeersbesluit of -mededeling"' in query
    assert 'cql.textAndIndexes=="verkeersbesluit"' not in query
    assert 'w.publicatienaam=="Gemeenteblad"' in query


def test_extra_keyword_is_added() -> None:
    query = build_gazette_query("Maastricht", "parkeerverbod")
    assert 'cql.textAndIndexes=="parkeerverbod"' in query


def test_publication_xml_and_title() -> None:
    link = "https://zoek.officielebekendmakingen.nl/gmb-2026-405510.html"
    assert publication_xml_url(link) == (
        "https://zoek.officielebekendmakingen.nl/gmb-2026-405510.xml"
    )
    xml = (
        "<officiele-publicatie><titel>GEMEENTEBLAD</titel>"
        "<titel>Verkeersmaatregel Academieplein</titel>"
        "<al>Parkeerverbod op het Academieplein.</al>"
        "</officiele-publicatie>"
    )
    parsed = extract_publication(xml)
    assert parsed["decision_title"] == "Verkeersmaatregel Academieplein"
    assert "Parkeerverbod" in parsed["excerpt"]
