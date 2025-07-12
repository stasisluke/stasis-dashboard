#!/usr/bin/env python3
"""
Integrated Web Server for Thermostat Dashboard with Trend‑Log Support
Adds robust pagination so 7‑day (and longer) queries pull every page of the
log‑buffer instead of just the first one.  This solves the “Loaded 1 data
points” issue that appeared whenever the first page happened to contain only a
single numeric entry surrounded by Log‑Interrupted records.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import base64
import os
from typing import Dict, Any, List

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# ────────────────────────────
# CONFIGURATION  ─ edit freely
# ────────────────────────────
SERVER = "stasisenergy.entelicloud.com"
SITE = "StuccoCo"
DEVICE = "4145595"
USER = "stasis_api"
PASSWORD = os.environ.get("PASSWORD", "your_password_here")  # ⚠️  update in prod!

DISPLAY_SITE_NAME = "Sacramento Stucco"
DISPLAY_DEVICE_NAME = "Zone Controller"  # leave "" to show actual BACnet name

TEMPERATURE_AI = 301001      # AI – zone temp
SETPOINT_AV = 1              # AV – active set‑point
SYSTEM_MODE_MV = 2           # MV – 1=Heat,2=Cool,3=Deadband
PEAK_SAVINGS_BV = 2025       # BV – demand response enable
FAN_STATUS_BO = 1            # BO – fan on/off
TEMP_TREND_LOG_INSTANCE = 27 # Trend‑Log – historical zone temp

# ────────────────────────────
# helpers / auth header
# ────────────────────────────
AUTH_HEADER = {
    "Authorization": f"Basic {base64.b64encode(f'{USER}:{PASSWORD}'.encode()).decode()}",
    "Accept": "application/json",
}

# -----------------------------------------------------------------------------
#  UTILITIES
# -----------------------------------------------------------------------------

def _get_json(url: str, *, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Wrapper around requests.get with sane defaults & debug printing."""
    r = requests.get(url, headers=AUTH_HEADER, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

# -----------------------------------------------------------------------------
#  NEW ‣ trend‑log fetch with pagination
# -----------------------------------------------------------------------------

def _fetch_trend_pages(first_url: str) -> List[Dict[str, Any]]:
    """Follow `next` links until there are no more – collect pages in a list."""
    pages: list[dict[str, Any]] = []
    url = first_url
    safety_counter = 0

    while url and safety_counter < 50:  # hard‑stop after 50 pages
        page = _get_json(url)
        pages.append(page)
        safety_counter += 1

        next_rel = page.get("next")
        if not next_rel:
            break
        # next_rel can be relative (starts with '/') or absolute – normalise:
        url = next_rel if next_rel.startswith("http") else f"https://{SERVER}{next_rel}"
    return pages

# -----------------------------------------------------------------------------
#  /api/trends endpoint (refactored with correct URL building & pagination)
# -----------------------------------------------------------------------------

@app.route("/api/trends")
def api_trends() -> Any:
    rng = request.args.get("range", "1h")
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    ranges = {
        "1h": (now - timedelta(hours=1), 20),
        "4h": (now - timedelta(hours=4), 60),
        "12h": (now - timedelta(hours=12), 150),
        "24h": (now - timedelta(hours=24), 300),
        "7d": (now - timedelta(days=7), 50_000),
    }
    start_time, max_results = ranges.get(rng, ranges["1h"])

    base_url = (
        f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/"
        f"trend-log,{TEMP_TREND_LOG_INSTANCE}/log-buffer"
    )

    params: dict[str, Any] = {"alt": "json", "max-results": max_results}
    if rng != "7d":  # 7‑day pulls *everything* and we page through it
        params["published-ge"] = start_time.isoformat(timespec="seconds") + "Z"
        params["published-le"] = now.isoformat(timespec="seconds") + "Z"

    # Properly encode parameters so the first request is valid
    first_page_url = f"{base_url}?{urlencode(params)}"

    pages = _fetch_trend_pages(first_page_url)

    # ───── extract numeric rows ─────
    rows: list[dict[str, Any]] = []
    for data in pages:
        for key, rec in data.items():
            if key in {"$base", "next"} or not isinstance(rec, dict):
                continue
            ts_raw = rec.get("timestamp", {}).get("value")
            if not ts_raw:
                continue
            ld = rec.get("logDatum", {})
            # try every leaf that looks like a numeric value
            val = None
            for v in ld.values():
                try:
                    val = float(v["value"]) if isinstance(v, dict) and "value" in v else None
                except (ValueError, TypeError):
                    val = None
                if val is not None:
                    break
            if val is None:
                continue
            # timestamp parsing (keep tz‑aware)
            ts = (
                datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if "Z" in ts_raw or "+" in ts_raw
                else datetime.fromisoformat(ts_raw).replace(tzinfo=timezone.utc)
            )
            fmt = "%H:%M" if rng in {"1h", "4h"} else "%m/%d %H:%M" if rng in {"12h", "24h"} else "%m/%d"
            rows.append({
                "timestamp": ts_raw,
                "temperature": val,
                "formatted_time": ts.strftime(fmt),
                "sort_time": ts,
            })

    rows.sort(key=lambda r: r["sort_time"])

    # quick interpolation of obvious 5‑minute gaps (unchanged from before)
    from datetime import timedelta as _td
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        out.append(row)
        if idx == len(rows) - 1:
            break
        gap = rows[idx + 1]["sort_time"] - row["sort_time"]
        if gap > _td(minutes=10):
            steps = int(gap.total_seconds() // 300)  # 5‑min slices
            for j in range(1, min(steps, 48)):
                interp_t = row["sort_time"] + _td(minutes=5 * j)
                ratio = j / steps
                interp_val = row["temperature"] + (
                    rows[idx + 1]["temperature"] - row["temperature"]
                ) * ratio
                fmt = "%H:%M" if rng in {"1h", "4h"} else "%m/%d %H:%M" if rng in {"12h", "24h"} else "%m/%d"
                out.append({
                    "timestamp": interp_t.isoformat(),
                    "temperature": round(interp_val, 2),
                    "formatted_time": interp_t.strftime(fmt),
                    "interpolated": True,
                    "sort_time": interp_t,
                })
    # drop helper key
    for r in out:
        r.pop("sort_time", None)

    # down‑sample 7‑day view for perf
    if rng == "7d" and len(out) > 300:
        step = len(out) // 300
        out = out[::step]

    return jsonify({
        "records": out,
        "time_range": rng,
        "actual_range": f"{len(out)} points",
        "start_time": start_time.isoformat() + "Z",
        "end_time": now.isoformat() + "Z",
        "total_records": len(out),
    })

# -----------------------------------------------------------------------------
#  (All other endpoints – thermostat, debug, HTML – are unchanged)
# -----------------------------------------------------------------------------

# … KEEP THE REST OF YOUR ORIGINAL FILE UNTOUCHED BELOW THIS LINE …
