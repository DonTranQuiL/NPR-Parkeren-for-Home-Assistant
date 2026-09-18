/**
 * NPR Parkeren Lovelace card.
 * Custom element: npr_parkeren-card
 * Reads the overview sensor attributes. No extra fetches.
 */
class NprParkerenCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._expanded = new Set();
    this._filter = "all";
    this._fingerprint = "";
    this._onClick = this._onClick.bind(this);
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Please define an entity (NPR Parkeren overview sensor).");
    }
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    const entityId = this.config.entity;
    const stateObj = hass.states[entityId];
    if (!stateObj) {
      this.shadowRoot.innerHTML =
        `<ha-card style="padding:16px;color:var(--error-color);">Entity not found: ${this._esc(entityId)}</ha-card>`;
      return;
    }
    const attrs = stateObj.attributes || {};
    const dark = this._isDark(hass);
    const fingerprint = JSON.stringify({
      s: stateObj.state,
      f: this._filter,
      e: [...this._expanded],
      d: dark,
      z: attrs.zones || [],
      r: attrs.regulated_here || {},
      n: attrs.decisions || [],
      c: attrs.counts || {},
    });
    if (fingerprint === this._fingerprint) {
      return;
    }
    this._fingerprint = fingerprint;
    this._render(stateObj, attrs, dark);
  }

  getCardSize() {
    return 5;
  }

  _isDark(hass) {
    try {
      return !!(hass && hass.themes && hass.themes.darkMode);
    } catch (_err) {
      return false;
    }
  }

  _esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  _kindColor(kind) {
    switch (kind) {
      case "paid":
        return "var(--success-color, #2ea043)";
      case "blue":
        return "var(--info-color, #1976d2)";
      case "permit":
        return "var(--warning-color, #f5a623)";
      default:
        return "var(--secondary-text-color, #757575)";
    }
  }

  _zones(attrs) {
    const zones = (attrs.zones || []).slice();
    const filter = this._filter;
    if (filter === "decisions" || filter === "all") {
      return filter === "decisions" ? [] : zones;
    }
    if (filter === "in_force") {
      return zones.filter((zone) => zone.in_force);
    }
    return zones.filter((zone) => zone.usage_kind === filter);
  }

  _money(zone) {
    if (zone.tariff) {
      return zone.tariff;
    }
    if (zone.in_force) {
      return "In force";
    }
    return "Not in force";
  }

  _stay(zone) {
    if (!zone.in_force) {
      return "";
    }
    if (zone.max_stay_minutes == null) {
      return "No maximum stay";
    }
    return `Max ${zone.max_stay_minutes} min`;
  }

  _svg(ring) {
    if (!ring || ring.length < 2) {
      return "";
    }
    const lats = ring.map((point) => point.latitude);
    const lons = ring.map((point) => point.longitude);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    const height = Math.max(maxLat - minLat, 0.00001);
    const width = Math.max(maxLon - minLon, 0.00001);
    const points = ring
      .map((point) => {
        const x = ((point.longitude - minLon) / width) * 100;
        const y = (1 - (point.latitude - minLat) / height) * 60;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
    return `<svg viewBox="0 0 100 60" class="ring" aria-hidden="true"><polygon points="${points}"></polygon></svg>`;
  }

  _steps(zone) {
    const steps = zone.fare_steps || [];
    if (!steps.length) {
      return "<p class='muted'>No tariff steps in force.</p>";
    }
    return `<ul class="steps">${steps
      .map((step) => {
        const amount = Number(step.amount_eur);
        const label = amount === 0 ? "€0.00" : `€${amount}`;
        const minutes = step.step_minutes ? ` / ${step.step_minutes} min` : "";
        const from = step.start_minute != null ? `from ${step.start_minute} min` : "";
        return `<li>${this._esc(label)}${this._esc(minutes)} <span class="muted">${this._esc(from)}</span></li>`;
      })
      .join("")}</ul>`;
  }

  _onClick(event) {
    const filter = event.target.closest("[data-filter]");
    if (filter) {
      this._filter = filter.getAttribute("data-filter");
      this._fingerprint = "";
      if (this._hass) {
        this.hass = this._hass;
      }
      return;
    }
    const row = event.target.closest("[data-area]");
    if (!row) {
      return;
    }
    const area = row.getAttribute("data-area");
    if (this._expanded.has(area)) {
      this._expanded.delete(area);
    } else {
      this._expanded.add(area);
    }
    this._fingerprint = "";
    if (this._hass) {
      this.hass = this._hass;
    }
  }

  _render(stateObj, attrs, dark) {
    const title = this.config.title || "NPR Parkeren";
    const place = attrs.areamanager_desc || attrs.municipality || "";
    const counts = attrs.counts || {};
    const regulated = attrs.regulated_here || {};
    const decisions = this._filter === "decisions" || this._filter === "all"
      ? attrs.decisions || []
      : [];
    const zones = this._zones(attrs);
    const filters = [
      ["all", "All"],
      ["paid", "Paid"],
      ["blue", "Blue zone"],
      ["permit", "Permit"],
      ["garage", "Garage"],
      ["lot", "Lot"],
      ["in_force", "In force"],
      ["decisions", "Decisions"],
    ];
    const filterHtml = filters
      .map(
        ([id, label]) =>
          `<button type="button" data-filter="${id}" class="${this._filter === id ? "on" : ""}">${label}</button>`
      )
      .join("");

    const rows = zones
      .map((zone) => {
        const open = this._expanded.has(zone.areaid);
        const inside = zone.inside ? "<span class='pill inside'>Here</span>" : "";
        const force = zone.in_force
          ? "<span class='pill onforce'>In force</span>"
          : "<span class='pill'>Outside hours</span>";
        const details = open
          ? `<div class="details">
              <p>${this._esc(zone.tariff_description || "")}</p>
              <p>${this._esc(zone.regulation || "")}</p>
              ${this._steps(zone)}
              <p class="muted">Capacity ${this._esc(zone.capacity == null ? "—" : zone.capacity)} · charging points ${this._esc(zone.charging_point_capacity == null ? "—" : zone.charging_point_capacity)} · height ${this._esc(zone.maximum_vehicle_height == null ? "—" : zone.maximum_vehicle_height)}</p>
              ${this._svg(zone.ring)}
            </div>`
          : "";
        return `<article class="row" data-area="${this._esc(zone.areaid)}">
          <div class="row-main">
            <span class="dot" style="background:${this._kindColor(zone.usage_kind)}"></span>
            <div class="grow">
              <strong>${this._esc(zone.name)}</strong>
              <div class="muted">${this._esc(zone.usage || zone.usage_kind || "")} · ${zone.distance_km == null ? "" : `${this._esc(zone.distance_km)} km`}</div>
            </div>
            <div class="meta">
              ${inside}${force}
              <div>${this._esc(this._money(zone))}</div>
              <div class="muted">${this._esc(this._stay(zone))}</div>
            </div>
          </div>
          ${details}
        </article>`;
      })
      .join("");

    const decisionHtml = (this._filter === "decisions" || this._filter === "all" ? attrs.decisions || [] : [])
      .slice(0, 12)
      .map((item) => {
        const klass = item.classification || "traffic_decision";
        return `<a class="decision" href="${this._esc(item.link || "#")}" target="_blank" rel="noopener">
          <span class="pill ${this._esc(klass)}">${this._esc(klass)}</span>
          <strong>${this._esc(item.title || "Decision")}</strong>
          <span class="muted">${this._esc(item.pub_date || "")}</span>
          <p>${this._esc(item.description || "")}</p>
        </a>`;
      })
      .join("");

    const here = regulated.inside
      ? `${this._esc(regulated.name || "Inside a zone")} · ${this._esc(regulated.tariff || (regulated.in_force ? "In force" : "Not in force"))}`
      : "Not inside a regulated zone";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          background: var(--card-background-color, var(--ha-card-background, #fff));
          color: var(--primary-text-color, #212121);
          padding: 16px;
        }
        :host(.dark) ha-card { color: var(--primary-text-color, #e3e3e3); }
        h2 { margin: 0; font-size: 1.15rem; font-weight: 600; }
        .sub { color: var(--secondary-text-color); margin-top: 2px; }
        .stats { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
        .stat {
          background: var(--secondary-background-color, rgba(0,0,0,.04));
          border-radius: 10px;
          padding: 8px 10px;
          min-width: 88px;
        }
        .stat b { display: block; font-size: 1.05rem; }
        .stat span { color: var(--secondary-text-color); font-size: .78rem; }
        .filters { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
        button {
          border: 1px solid var(--divider-color, rgba(0,0,0,.12));
          background: transparent;
          color: var(--primary-text-color);
          border-radius: 999px;
          padding: 4px 10px;
          cursor: pointer;
        }
        button.on {
          background: var(--primary-color, #03a9f4);
          color: var(--text-primary-color, #fff);
          border-color: transparent;
        }
        .layout {
          display: grid;
          grid-template-columns: minmax(0, 1.6fr) minmax(240px, .9fr);
          gap: 14px;
        }
        .row {
          border-top: 1px solid var(--divider-color, rgba(0,0,0,.12));
          padding: 10px 0;
          cursor: pointer;
        }
        .row-main { display: flex; gap: 10px; align-items: flex-start; }
        .grow { flex: 1; min-width: 0; }
        .dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 6px; flex: none; }
        .meta { text-align: right; font-size: .86rem; }
        .muted { color: var(--secondary-text-color); font-size: .8rem; }
        .pill {
          display: inline-block;
          border-radius: 999px;
          padding: 1px 7px;
          margin-left: 4px;
          font-size: .72rem;
          background: var(--secondary-background-color, rgba(0,0,0,.06));
        }
        .pill.inside { background: var(--success-color, #2ea043); color: #fff; }
        .pill.onforce { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
        .pill.parking_ban { background: var(--error-color, #c62828); color: #fff; }
        .pill.road_closure { background: var(--warning-color, #ef6c00); color: #fff; }
        .details { margin: 8px 0 0 20px; }
        .steps { margin: 6px 0; padding-left: 18px; }
        .ring { width: 160px; height: 96px; }
        .ring polygon {
          fill: color-mix(in srgb, var(--primary-color, #03a9f4) 25%, transparent);
          stroke: var(--primary-color, #03a9f4);
          stroke-width: 1.5;
        }
        .decision {
          display: block;
          text-decoration: none;
          color: inherit;
          padding: 8px 0;
          border-top: 1px solid var(--divider-color, rgba(0,0,0,.12));
        }
        .decision p { margin: 4px 0 0; color: var(--secondary-text-color); font-size: .84rem; }
        .here {
          background: var(--secondary-background-color, rgba(0,0,0,.04));
          border-radius: 10px;
          padding: 10px;
          margin-bottom: 10px;
        }
        @media (max-width: 1000px) {
          .layout { grid-template-columns: 1fr; }
          .meta { text-align: left; }
          .row-main { flex-wrap: wrap; }
        }
      </style>
      <ha-card class="${dark ? "dark" : ""}">
        <h2>${this._esc(title)}</h2>
        <div class="sub">${this._esc(place)} · state ${this._esc(stateObj.state)}</div>
        <div class="stats">
          <div class="stat"><b>${this._esc(counts.zones_in_radius || 0)}</b><span>in radius</span></div>
          <div class="stat"><b>${this._esc(counts.in_force || 0)}</b><span>in force</span></div>
          <div class="stat"><b>${regulated.inside ? "yes" : "no"}</b><span>regulated here</span></div>
          <div class="stat"><b>${this._esc(counts.decisions || 0)}</b><span>decisions</span></div>
        </div>
        <div class="filters">${filterHtml}</div>
        <div class="layout">
          <section>${rows || "<p class='muted'>No zones for this filter.</p>"}</section>
          <aside>
            <div class="here"><strong>Regulated here</strong><div>${here}</div></div>
            <strong>Decisions</strong>
            ${decisionHtml || "<p class='muted'>No decisions.</p>"}
          </aside>
        </div>
      </ha-card>`;
    this.shadowRoot.querySelector("ha-card").addEventListener("click", this._onClick);
    if (dark) {
      this.classList.add("dark");
    } else {
      this.classList.remove("dark");
    }
  }
}

customElements.define("npr_parkeren-card", NprParkerenCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "npr_parkeren-card",
  name: "NPR Parkeren",
  description: "Regulated parking zones, the tariff in force, and municipal traffic decisions.",
  preview: true,
});
