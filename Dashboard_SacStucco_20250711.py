#!/usr/bin/env python3
"""
Integrated Web Server for Thermostat Dashboard with Trend Log Support
Serves the HTML file and provides API endpoints that work just like your existing Python code
Now includes trend log data for historical charting
"""

from flask import Flask, request, jsonify
import requests
import base64
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# ========================================
# CONFIGURATION SECTION - EDIT HERE FOR DIFFERENT CLIENTS/CONTROLLERS
# ========================================

# Server Configuration
SERVER = "stasisenergy.entelicloud.com"
SITE = "StuccoCo"
DEVICE = "4145595"
USER = "stasis_api"
PASSWORD = os.environ.get('PASSWORD', 'your_password_here')  # Update with your actual password

# Display Configuration - customize how titles appear on the dashboard
DISPLAY_SITE_NAME = "Sacramento Stucco"  # Custom site name for display
DISPLAY_DEVICE_NAME = "Zone Controller"  # Custom device name for display (leave empty to use actual device name)

# BACnet Object Configuration - adjust these for different controllers
TEMPERATURE_AI = 301001          # Analog Input for zone temperature
SETPOINT_AV = 1                  # Analog Value for active zone setpoint
SYSTEM_MODE_MV = 2               # Multi-state Value for system mode (heating/cooling/deadband)
PEAK_SAVINGS_BV = 2025           # Binary Value for peak savings mode status
FAN_STATUS_BO = 1                # Binary Output for fan status
TEMP_TREND_LOG_INSTANCE = 27     # Trend Log instance for temperature history

# ========================================
# END CONFIGURATION SECTION
# ========================================

# Basic auth header (exactly like your Python code)
auth_header = {
    "Authorization": f"Basic {base64.b64encode(f'{USER}:{PASSWORD}'.encode()).decode()}",
    "Accept": "application/json"
}

# ------------------------------------------------------------
# Helper: follow EnteliWeb pagination automatically
# ------------------------------------------------------------

def fetch_enteli_pages(base_url: str, params: dict):
    """Yield every page of a log‑buffer, automatically following $next links."""
    url = base_url
    first = True
    while url:
        resp = requests.get(
            url,
            params=params if first else None,  # only supply params on the first call
            headers=auth_header,
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        yield page
        url = page.get("$next")  # None when there is no further page
        first = False

# ------------------------------------------------------------
# HTML FRONT‑END (unchanged)
# ------------------------------------------------------------

@app.route('/')
def index():
    """Serve the main dashboard HTML"""
    return open(__file__).read().split("<body>", 1)[1]  # quick placeholder – keep original body!

# ------------------------------------------------------------
# CURRENT DATA ENDPOINT (unchanged from your version)
# ------------------------------------------------------------

@app.route('/api/thermostat')
# ...  **unchanged code omitted for brevity**  ...

# ------------------------------------------------------------
# TREND‑LOG ENDPOINT – fixed pagination + status‑row filtering
# ------------------------------------------------------------

@app.route('/api/trends')
def get_trend_data():
    try:
        time_range = request.args.get('range', '1h')
        debug_info = []

        # ----- build start / end -----
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        if time_range == '1h':
            start_time, max_results = now - timedelta(hours=1), 20
        elif time_range == '4h':
            start_time, max_results = now - timedelta(hours=4), 60
        elif time_range == '12h':
            start_time, max_results = now - timedelta(hours=12), 150
        elif time_range == '24h':
            start_time, max_results = now - timedelta(hours=24), 300
        elif time_range == '7d':
            start_time, max_results = now - timedelta(days=7), 50000
        else:
            start_time, max_results = now - timedelta(hours=1), 20

        base_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/trend-log,{TEMP_TREND_LOG_INSTANCE}/log-buffer"

        params = {
            "alt": "json",
            "max-results": max_results,
        }
        if time_range != '7d':  # we want *everything* for 7d, so skip the published-ge/le filters
            params["published-ge"] = start_time.isoformat(timespec='seconds') + "Z"
            params["published-le"] = now.isoformat(timespec='seconds') + "Z"
            debug_info.append(f"Requesting {time_range} from {params['published-ge']} to {params['published-le']}")
        else:
            debug_info.append("7d: requesting ALL pages (no published filters)")

        # fetch every page
        rows = []
        for page in fetch_enteli_pages(base_url, params):
            for key, blob in page.items():
                if key in ("$base", "$next") or not isinstance(blob, dict):
                    continue
                if "timestamp" not in blob:
                    continue

                ld = blob.get("logDatum", {})

                # ---- skip status‑only rows (no real‑value) ----
                if any(k in ld for k in ("log-status", "event-state", "string-value")):
                    debug_info.append(f"SKIP {key}: status row → {list(ld.keys())}")
                    continue

                # extract numeric value
                val = None
                if "real-value" in ld and isinstance(ld["real-value"], dict):
                    val = ld["real-value"].get("value")
                if val is None:
                    for v in ld.values():
                        if isinstance(v, dict) and "value" in v:
                            try:
                                val = float(v["value"])
                                break
                            except (ValueError, TypeError):
                                pass
                if val is None:
                    debug_info.append(f"SKIP {key}: no numeric value")
                    continue

                ts_raw = blob["timestamp"]["value"]
                ts_dt = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))

                # labels by range
                if time_range in ("1h", "4h"):
                    label = ts_dt.strftime('%H:%M')
                elif time_range in ("12h", "24h"):
                    label = ts_dt.strftime('%m/%d %H:%M')
                else:
                    label = ts_dt.strftime('%m/%d')

                rows.append({
                    "timestamp": ts_raw,
                    "temperature": float(val),
                    "formatted_time": label,
                    "sort_time": ts_dt,
                })

        rows.sort(key=lambda x: x['sort_time'])

        # down‑sample 7d if necessary
        if time_range == '7d' and len(rows) > 300:
            step = len(rows)//300
            rows = rows[::step]

        for r in rows:
            r.pop('sort_time', None)

        result = {
            "records": rows,
            "time_range": time_range,
            "actual_range": f"{len(rows)} points" if rows else "No data",
            "start_time": start_time.isoformat() + "Z",
            "end_time": now.isoformat() + "Z",
            "total_records": len(rows),
            "debug_info": debug_info,
        }
        return jsonify(result)

    except Exception as exc:
        return jsonify({
            "error": str(exc),
            "records": [],
            "total_records": 0,
            "actual_range": "Error",
            "debug_info": [f"Error: {exc}"],
        })

# ------------------------------------------------------------
# /api/debug endpoint untouched (omit for brevity)
# ------------------------------------------------------------

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

if __name__ == '__main__':
    print("Starting Enhanced Thermostat Dashboard Server…")
    print(f"EnteliWeb Server: {SERVER} | Site: {SITE} | Device: {DEVICE}")
    app.run(host='0.0.0.0', port=8000, debug=True)
