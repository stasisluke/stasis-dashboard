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
    """Yield every page of a log‑buffer, automatically following next links."""
    url = base_url
    first = True
    page_count = 0

    # Prepare params for first and subsequent requests
    params_first = params.copy()  # alt=json, max-results=…
    params_next = {"alt": "json"}  # only alt=json

    while url and page_count < 50:  # Safety limit
        print(f"DEBUG: Fetching page {page_count + 1}: {url[:100]}...")

        resp = requests.get(
            url,
            params=params_first if first else params_next,
            headers=auth_header,
            timeout=30,
        )
        resp.raise_for_status()

        # Check content type to make sure we got JSON
        if "application/json" not in resp.headers.get("Content-Type", ""):
            print(f"ERROR: Page {page_count + 1} returned {resp.headers.get('Content-Type')}")
            print(f"Response text: {resp.text[:200]}")
            break

        page = resp.json()

        # Count actual data records (skip $base and next)
        data_keys = [k for k in page.keys() if k not in ('$base', 'next')]
        print(f"DEBUG: Page {page_count + 1} has {len(data_keys)} data records")

        yield page

        # Get next URL
        url = page.get("next")
        print(f"DEBUG: Next URL exists: {bool(url)}")

        first = False
        page_count += 1

    print(f"DEBUG: Pagination complete after {page_count} pages")

# -----------------------------------------------------------------------------
# Route: / (dashboard HTML) – UNCHANGED BELOW THIS POINT UNTIL get_trend_data()
# -----------------------------------------------------------------------------
