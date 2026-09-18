<div align="center">

# NPR Parkeren

**One Home Assistant config entry per Dutch municipality: regulated parking zones, the tariff and maximum stay in force right now, and municipal traffic decisions.**

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA](https://img.shields.io/badge/Home%20Assistant-2025.1.0+-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/DonTranQuiL/NPR-Parkeren-for-Home-Assistant)](https://github.com/DonTranQuiL/NPR-Parkeren-for-Home-Assistant/releases)
[![Issues](https://img.shields.io/github/issues/DonTranQuiL/NPR-Parkeren-for-Home-Assistant)](https://github.com/DonTranQuiL/NPR-Parkeren-for-Home-Assistant/issues)
[![hassfest](https://img.shields.io/github/actions/workflow/status/DonTranQuiL/NPR-Parkeren-for-Home-Assistant/hassfest.yaml?label=hassfest&style=for-the-badge)](https://github.com/DonTranQuiL/NPR-Parkeren-for-Home-Assistant/actions/workflows/hassfest.yaml)
[![HACS Validation](https://img.shields.io/github/actions/workflow/status/DonTranQuiL/NPR-Parkeren-for-Home-Assistant/hacs.yaml?style=for-the-badge&label=HACS%20VALIDATION&color=5dbb0f)](https://github.com/DonTranQuiL/NPR-Parkeren-for-Home-Assistant/actions)
[![Tests](https://img.shields.io/github/actions/workflow/status/DonTranQuiL/NPR-Parkeren-for-Home-Assistant/pytest.yml?style=for-the-badge&label=TESTS&color=5dbb0f)](https://github.com/DonTranQuiL/NPR-Parkeren-for-Home-Assistant/actions)
[![Code Checks](https://img.shields.io/github/actions/workflow/status/DonTranQuiL/NPR-Parkeren-for-Home-Assistant/codechecker.yml?style=for-the-badge&label=CODE%20CHECKS&color=5dbb0f)](https://github.com/DonTranQuiL/NPR-Parkeren-for-Home-Assistant/actions)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000?style=for-the-badge)](https://github.com/astral-sh/ruff)
[![Maintainer](https://img.shields.io/badge/maintainer-%40DonTranQuiL-007ec6?style=for-the-badge)](https://github.com/DonTranQuiL)

</div>

## What it does

NPR Parkeren reads the Nationaal Parkeer Register on RDW open data for a single municipality and the official gazette (Gemeenteblad). It shows paid parking, permit zones, blue zones, garages and lots; the tariff and maximum stay that apply at the current weekday and time; whether your coordinates are inside a zone; and recent traffic decisions. Full polygons stay in the coordinator cache. Entities publish a centroid and at most twelve ring points.

## Install (HACS custom repository)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. URL: `https://github.com/DonTranQuiL/NPR-Parkeren-for-Home-Assistant`
3. Category: **Integration**
4. Download **NPR Parkeren**
5. **Restart Home Assistant**
6. Settings → Devices & services → Add Integration → **NPR Parkeren**
7. Enter the municipality name, the latitude and longitude to test, and a radius. The area manager is looked up during setup. The same municipality cannot be added twice.

## Lovelace card

Copy the card into your Home Assistant config www folder:

```bash
cp npr_parkeren-card.js /config/www/npr_parkeren-card.js
```

Add a Lovelace resource:

- URL: `/local/npr_parkeren-card.js`
- Type: JavaScript Module

```yaml
type: custom:npr_parkeren-card
entity: sensor.npr_parkeren_kerkrade_overview
title: Parking near home
```

Adjust the entity id to the overview sensor of your config entry.

## Recorder tip

The overview sensor carries the zone list, decisions and history. Exclude it from the recorder:

```yaml
recorder:
  exclude:
    entities:
      - sensor.npr_parkeren_kerkrade_overview
```

(Adjust the entity id to match your municipality.)

## Options

| Option | Default | Notes |
|--------|---------|-------|
| `scan_interval` | 900 s | Minimum 300. Gazette is fetched every poll. |
| `radius_km` | 2.0 | Centre is the latitude and longitude from setup. |
| `max_map_markers` | 25 | Pins outside the cap are removed immediately. |
| `keyword` | verkeersbesluit | Second term in the gazette query. |
| `enable_markers` | true | Device-tracker pins, colored by usage. |

NPR tables are filtered to the area manager of the entry and cached for 12 hours. A failed poll keeps the last good payload.

## Entities

| Entity | Role |
|--------|------|
| `sensor.*_overview` | Zones in radius, plus the attributes the card reads |
| `sensor.*_zones_in_radius` | Count |
| `sensor.*_regulated_here` | The location answer: inside a zone, tariff, maximum stay |
| `sensor.*_latest_decision` | Newest gazette item that names this municipality |
| `sensor.*_decision_count` | Count |
| `sensor.*_consecutive_errors` | Diagnostic |
| `sensor.*_last_update_status` | Diagnostic |
| `sensor.*_last_update_time` | Diagnostic timestamp |
| `text.*_watchlist` | Comma-separated streets |
| `device_tracker.*` | Map pins (optional) |
| `button.*_refresh` | Manual refresh |

A new decision that mentions a watched street fires `npr_parkeren_decision` on the event bus. Publication dates come from the feed. The integration does not invent start or end dates.

Service `npr_parkeren.refresh` refreshes every configured municipality.

## Disclaimer

RDW publishes the Nationaal Parkeer Register as open data on [opendata.rdw.nl](https://opendata.rdw.nl). Official publications come from [zoek.officielebekendmakingen.nl](https://zoek.officielebekendmakingen.nl). Use of both sources is subject to the upstream terms of use of RDW open data and overheid.nl / Officiële bekendmakingen. This integration is unofficial and is not affiliated with RDW, a municipality, or the Dutch government. The gazette index is loose: a neighbouring municipality can appear in the raw feed, so items are kept only when the title or description contains the configured municipality. Tariffs and decisions can be delayed or incomplete. Check the sign and the official publication before you rely on them.

**Credit:** RDW open data (NPR) and Officiële bekendmakingen.

## Built by AI

This integration was created entirely by AI and is maintained by AI.

## License

MIT © DonTranQuiL
