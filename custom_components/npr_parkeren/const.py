"""Constants for the NPR Parkeren integration."""

from __future__ import annotations

DOMAIN = "npr_parkeren"
NAME = "NPR Parkeren"
MANUFACTURER = "DonTranQuiL"
VERSION = "0.1.1"
ATTRIBUTION = (
    "Data © RDW Nationaal Parkeer Register (open data) and Officiële bekendmakingen"
)
DOCUMENTATION_URL = "https://github.com/DonTranQuiL/NPR-Parkeren-for-Home-Assistant"

PLATFORMS = (
    "sensor",
    "device_tracker",
    "button",
    "text",
)

SODA_BASE = "https://opendata.rdw.nl/resource"
GAZETTE_RSS = "https://zoek.officielebekendmakingen.nl/rss"
GAZETTE_TYPE = "verkeersbesluit of -mededeling"
GAZETTE_DETAIL_MAX = 8

DATASET_MANAGERS = "2uc2-nnv3"
DATASET_AREAS = "adw6-9hsg"
DATASET_LINKS = "mz4f-59fw"
DATASET_USAGE = "qidm-7mkf"
DATASET_GEOMETRY = "nsk3-v9n7"
DATASET_AREA_REGULATION = "qtex-qwd8"
DATASET_REGULATION = "yefi-qfiq"
DATASET_TIMEFRAME = "ixf8-gtwq"
DATASET_FARE = "nfzq-8g7y"
DATASET_FARE_PART = "534e-5vdg"
DATASET_SPECIAL = "hpi4-mynq"
DATASET_SPECS = "b3us-f26s"

USER_AGENT = f"HomeAssistant-NPR-Parkeren/{VERSION}"
CLIENT_TIMEOUT_TOTAL = 30
CLIENT_TIMEOUT_CONNECT = 10
CLIENT_TIMEOUT_READ = 20

CONF_MUNICIPALITY = "municipality"
CONF_AREA_MANAGER_ID = "areamanagerid"
CONF_AREA_MANAGER_DESC = "areamanagerdesc"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_RADIUS_KM = "radius_km"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MAX_MAP_MARKERS = "max_map_markers"
CONF_KEYWORD = "keyword"
CONF_ENABLE_MARKERS = "enable_markers"

DEFAULT_RADIUS_KM = 2.0
DEFAULT_SCAN_INTERVAL = 900
MIN_SCAN_INTERVAL = 300
DEFAULT_MAX_MAP_MARKERS = 25
DEFAULT_KEYWORD = "verkeersbesluit"
DEFAULT_ENABLE_MARKERS = True

CATALOG_REFRESH_SECONDS = 12 * 3600
HISTORY_MAX = 50
DECISION_MAX = 50
RING_POINT_MAX = 12
PAGE_SIZE = 1000
PAGE_CAP = 8000
DESCRIPTION_MAX = 400

EVENT_DECISION = f"{DOMAIN}_decision"

USAGE_PAID = "paid"
USAGE_BLUE = "blue"
USAGE_PERMIT = "permit"
USAGE_GARAGE = "garage"
USAGE_LOT = "lot"
USAGE_OTHER = "other"

# Labels observed on qidm-7mkf for a live municipality. Used only when the
# usage table itself did not return a current description.
USAGE_LABELS = {
    "BETAALDP": "Betaald Parkeren",
    "BLAUWEZ": "Blauwe Zone",
    "GARAGEP": "Garage Parkeren",
    "TERREINP": "Terrein Parkeren",
    "VERGUNP": "Vergunning Parkeren",
    "PARKEREN": "Parkeren",
    "PARKRIDE": "Park & Ride",
}

MARKER_FILES = {
    USAGE_PAID: "marker-paid.png",
    USAGE_BLUE: "marker-blue.png",
    USAGE_PERMIT: "marker-permit.png",
    USAGE_GARAGE: "marker-other.png",
    USAGE_LOT: "marker-other.png",
    USAGE_OTHER: "marker-other.png",
}

KIND_RANK = {
    USAGE_PAID: 0,
    USAGE_PERMIT: 1,
    USAGE_BLUE: 2,
    USAGE_GARAGE: 3,
    USAGE_LOT: 4,
    USAGE_OTHER: 5,
}
