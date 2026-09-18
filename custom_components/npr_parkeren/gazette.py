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

from .const import DEFAULT_KEYWORD, GAZETTE_RSS

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
    """Build the CQL query, substituting municipality and keyword."""
    place = _clean_term(municipality)
    term = _clean_term(keyword or DEFAULT_KEYWORD) or DEFAULT_KEYWORD
    return (
        '(c.product-area=="officielepublicaties")and'
        '(w.publicatienaam=="Gemeenteblad")and'
        f'(cql.textAndIndexes=="{place}")and'
        f'(cql.textAndIndexes=="{term}")'
    )


def build_gazette_url(municipality: str, keyword: str | None = None) -> str:
    """RSS URL for one municipality and keyword."""
    query = build_gazette_query(municipality, keyword)
    return f"{GAZETTE_RSS}?{urlencode({'q': query})}"


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
        blob = f"{item.get('title') or ''} {item.get('description') or ''}".casefold()
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
    return {
        "title": item.get("title") or "",
        "link": item.get("link") or "",
        "description": clip(str(item.get("description") or ""), description_limit),
        "pub_date": item.get("pub_date") or "",
        "category": category if category is not None else "",
        "classification": item.get("classification")
        or classify_decision(item.get("title"), item.get("description")),
    }


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
