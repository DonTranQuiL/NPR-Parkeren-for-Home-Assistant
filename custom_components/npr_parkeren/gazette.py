"""Official gazette RSS: query, parse, municipality filter, classification.

The search index is loose. A municipality query can return a neighbouring
municipality first. Keep an item only when the title or description contains
the municipality name. Do not invent start or end dates; ``pubDate`` is the
publication date from the feed.
"""

from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree

from .const import GAZETTE_RSS, GAZETTE_TYPE

# The stored default keyword names the rubriek. It is not a second index term.
_RUBRIC_KEYWORDS = frozenset({"verkeersbesluit", GAZETTE_TYPE.casefold()})

_PARKING_BAN = (
    "parkeerverbod",
    "parkeerverboden",
    "verbod te parkeren",
    "verbod tot parkeren",
    "parkeren verboden",
    "niet te parkeren",
)
_ROAD_CLOSURE = (
    "wegafsluiting",
    "afsluiting",
    "afgesloten",
    "stremming",
    "gesloten voor het verkeer",
    "gesloten voor verkeer",
    "weg gesloten",
)


def build_gazette_query(municipality: str, keyword: str | None = None) -> str:
    """Build the CQL query for the traffic-decision rubriek.

    The place is one text index term. An extra keyword is added only when
    the user typed something other than the rubriek name. The stored default
    ``verkeersbesluit`` selects the whole rubriek and is not ANDed in.
    """
    place = _clean_term(municipality)
    parts = [
        '(c.product-area=="officielepublicaties")',
        f'(dt.type=="{GAZETTE_TYPE}")',
        '(w.publicatienaam=="Gemeenteblad")',
        f'(cql.textAndIndexes=="{place}")',
    ]
    term = _clean_term(keyword)
    if term and term.casefold() not in _RUBRIC_KEYWORDS:
        parts.append(f'(cql.textAndIndexes=="{term}")')
    return "and".join(parts)


def build_gazette_url(municipality: str, keyword: str | None = None) -> str:
    """RSS URL for one municipality and keyword."""
    query = build_gazette_query(municipality, keyword)
    return f"{GAZETTE_RSS}?{urlencode({'q': query})}"


def publication_xml_url(link: str | None) -> str | None:
    """The decision text lives at the same id, with .html swapped for .xml."""
    value = (link or "").strip()
    if not value.endswith(".html"):
        return None
    return value[:-5] + ".xml"


def extract_publication(xml_text: str | None) -> dict[str, Any]:
    """Pull the decision title and body from an official-publication XML document.

    Publication date stays the RSS pubDate. A start or end date is not
    invented from the regulation text.
    """
    raw = (xml_text or "").lstrip("\ufeff").strip()
    if not raw:
        return {}
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return {}

    def local(tag: str) -> str:
        return tag.split("}")[-1]

    titles = [
        (element.text or "").strip()
        for element in root.iter()
        if local(element.tag) == "titel" and (element.text or "").strip()
    ]
    decision_title = next(
        (title for title in titles if title.casefold() != "gemeenteblad"),
        "",
    )
    paragraphs = [
        re.sub(r"\s+", " ", (element.text or "").strip())
        for element in root.iter()
        if local(element.tag) == "al" and (element.text or "").strip()
    ]
    excerpt = clip(" ".join(paragraphs), 800)
    result: dict[str, Any] = {}
    if decision_title:
        result["decision_title"] = decision_title
    if excerpt:
        result["excerpt"] = excerpt
    return result


def _clean_term(value: str | None) -> str:
    text = (value or "").replace('"', " ").replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:80]


def strip_html(value: str | None) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clip(value: str | None, limit: int = 400) -> str:
    text = value or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def classify_decision(title: str | None, description: str | None) -> str:
    """Classify from text: parking_ban, road_closure, or traffic_decision."""
    blob = f"{title or ''} {description or ''}".casefold()
    if any(term in blob for term in _PARKING_BAN):
        return "parking_ban"
    if any(term in blob for term in _ROAD_CLOSURE):
        return "road_closure"
    return "traffic_decision"


def parse_rss(xml_text: str | None) -> list[dict[str, Any]]:
    """Parse RSS items. HTML articles are not fetched."""
    raw = (xml_text or "").lstrip("\ufeff").strip()
    if not raw:
        return []
    root = ElementTree.fromstring(raw)
    items: list[dict[str, Any]] = []
    for node in root.findall(".//item"):
        categories = [
            (child.text or "").strip()
            for child in node.findall("category")
            if (child.text or "").strip()
        ]
        title = (node.findtext("title") or "").strip()
        description = strip_html(node.findtext("description"))
        item: dict[str, Any] = {
            "title": title,
            "link": (node.findtext("link") or "").strip(),
            "description": description,
            "pub_date": (node.findtext("pubDate") or "").strip(),
            "category": categories[0] if len(categories) == 1 else categories,
            "classification": classify_decision(title, description),
        }
        items.append(item)
    return items


def filter_by_municipality(
    items: list[dict[str, Any]], municipality: str
) -> list[dict[str, Any]]:
    """Drop items whose title and description do not name the municipality."""
    needle = (municipality or "").casefold().strip()
    if not needle:
        return []
    kept: list[dict[str, Any]] = []
    for item in items:
        blob = (
        f"{item.get('title') or ''} {item.get('decision_title') or ''} "
        f"{item.get('description') or ''} {item.get('excerpt') or ''}"
    ).casefold()
        if needle in blob:
            kept.append(item)
    return kept


def parse_pub_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None


def sort_decisions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Newest publication first. Unparseable dates keep their relative order."""

    def key(item: dict[str, Any]) -> tuple[int, float]:
        parsed = parse_pub_date(str(item.get("pub_date") or ""))
        if parsed is None:
            return (1, 0.0)
        return (0, -parsed.timestamp())

    return sorted(items, key=key)


def public_decision(
    item: dict[str, Any], description_limit: int = 400
) -> dict[str, Any]:
    """Whitelist one decision. No start or end date is added."""
    category = item.get("category")
    payload: dict[str, Any] = {
        "title": item.get("title") or "",
        "link": item.get("link") or "",
        "description": clip(str(item.get("description") or ""), description_limit),
        "pub_date": item.get("pub_date") or "",
        "category": category if category is not None else "",
        "classification": item.get("classification")
        or classify_decision(item.get("title"), item.get("description")),
    }
    decision_title = str(item.get("decision_title") or "").strip()
    excerpt = clip(str(item.get("excerpt") or ""), description_limit)
    if decision_title:
        payload["decision_title"] = decision_title
    if excerpt:
        payload["excerpt"] = excerpt
    return payload


def watched_streets(value: str | None) -> list[str]:
    """Comma-separated street names, blanks dropped."""
    streets: list[str] = []
    seen: set[str] = set()
    for part in (value or "").split(","):
        street = part.strip()
        key = street.casefold()
        if len(street) < 2 or key in seen:
            continue
        seen.add(key)
        streets.append(street)
    return streets


def matching_streets(item: dict[str, Any], streets: list[str]) -> list[str]:
    """Streets mentioned in the title or description, case-insensitive."""
    blob = f"{item.get('title') or ''} {item.get('description') or ''}".casefold()
    return [street for street in streets if street.casefold() in blob]
