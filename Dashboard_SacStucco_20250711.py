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

@app.route('/')
def index():
    """Serve the main dashboard HTML"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stasis Energy Group - {SITE} Device {DEVICE}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; color: #333;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; color: white; position: relative; min-height: 120px; }}
        .header-text {{ text-align: center; }}
        .header-text h1 {{ font-size: 2.5em; margin-bottom: 5px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }}
        .header-text h2 {{ font-size: 1.5em; margin-bottom: 10px; color: #f0f0f0; font-weight: normal; }}
        .stasis-logo {{
            position: absolute;
            left: 20px;
            top: 50%;
            transform: translateY(-50%);
            width: 200px;
            height: 120px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .stasis-logo img {{
            max-width: 200px;
            max-height: 120px;
            object-fit: contain;
            opacity: 1;
        }}
        .powered-by {{
            font-size: 0.9em;
            color: rgba(255, 255, 255, 0.7);
            margin-top: 5px;
            font-weight: 300;
        }}
        .card {{
            background: rgba(255, 255, 255, 0.95); border-radius: 15px; padding: 25px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); margin-bottom: 20px;
        }}
        .temperature-circle {{
            position: relative;
            width: 250px;
            height: 250px;
            border-radius: 50%;
            margin: 20px auto;
            background: #f8f9fa;
            border: 8px solid #dee2e6;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            transition: border-color 0.5s ease;
        }}
        .temperature-circle.cooling {{
            border-color: #2196F3;
            box-shadow: 0 0 20px rgba(33, 150, 243, 0.3);
        }}
        .temperature-circle.heating {{
            border-color: #FF9800;
            box-shadow: 0 0 20px rgba(255, 152, 0, 0.3);
        }}
        .temperature-circle.peak-savings {{
            border-color: #4CAF50;
            box-shadow: 0 0 20px rgba(76, 175, 80, 0.4);
            animation: pulse-green 2s infinite;
        }}
        .temperature-circle.deadband {{
            border-color: #9E9E9E;
        }}
        @keyframes pulse-green {{
            0% {{ box-shadow: 0 0 20px rgba(76, 175, 80, 0.4); }}
            50% {{ box-shadow: 0 0 30px rgba(76, 175, 80, 0.7); }}
            100% {{ box-shadow: 0 0 20px rgba(76, 175, 80, 0.4); }}
        }}
        .temperature-value {{
            font-size: 3.5em;
            font-weight: bold;
            color: #333;
            line-height: 1;
        }}
        .temperature-unit {{
            font-size: 1.2em;
            color: #666;
            margin-top: -10px;
        }}
        .setpoint-text {{
            font-size: 1em;
            color: #666;
            margin-top: 10px;
        }}
        .mode-text {{
            font-size: 1.1em;
            font-weight: 600;
            margin-top: 5px;
            text-transform: uppercase;
        }}
        .mode-text.cooling {{ color: #2196F3; }}
        .mode-text.heating {{ color: #FF9800; }}
        .mode-text.peak-savings {{ color: #4CAF50; }}
        .mode-text.deadband {{ color: #9E9E9E; }}
        .status-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 20px; }}
        .status-item {{ text-align: center; padding: 15px; background: rgba(0, 0, 0, 0.05); border-radius: 10px; }}
        .status-value {{ font-size: 1.5em; font-weight: bold; color: #2196F3; }}
        .status-label {{ font-size: 0.9em; color: #666; margin-top: 5px; }}
        .chart-container {{ position: relative; height: 300px; margin-top: 20px; }}
        .chart-controls {{
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .time-range-btn {{
            padding: 8px 16px;
            border: 2px solid #2196F3;
            background: white;
            color: #2196F3;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.3s ease;
        }}
        .time-range-btn:hover {{
            background: #2196F3;
            color: white;
        }}
        .time-range-btn.active {{
            background: #2196F3;
            color: white;
        }}
        .last-updated {{ font-size: 0.9em; color: #666; text-align: center; margin-top: 10px; }}
        .btn {{ padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 1em; background: #2196F3; color: white; margin: 5px; }}
        .btn:hover {{ background: #1976D2; }}
        .loading {{ text-align: center; color: #666; font-style: italic; }}
        .error {{ color: #f44336; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="stasis-logo">
                <img src="https://raw.githubusercontent.com/stasisluke/stasis-dashboard/main/stasis-logo.png" alt="Stasis Energy Group" onerror="this.style.display='none'">
            </div>
            <div class="header-text">
                <h1>{DISPLAY_SITE_NAME}</h1>
                <h2 id="deviceTitle">{DISPLAY_DEVICE_NAME if DISPLAY_DEVICE_NAME else 'Device ' + DEVICE}</h2>
                <p class="powered-by">Thermal Energy Storage Dashboard</p>
            </div>
        </div>
        
        <div class="card">
            <h3>Current Temperature</h3>
            <div class="temperature-circle" id="tempCircle">
                <div class="temperature-value" id="currentTemp">--</div>
                <div class="temperature-unit">°F</div>
                <div class="setpoint-text" id="setpointText">Setpoint: --°F</div>
                <div class="mode-text" id="modeText">--</div>
            </div>
            <div class="last-updated" id="lastUpdated">Never updated</div>
        </div>
        
        <div class="card">
            <h3>Temperature History</h3>
            <div class="chart-controls">
                <button class="time-range-btn active" onclick="loadTrendData('1h')">Last Hour</button>
                <button class="time-range-btn" onclick="loadTrendData('4h')">Last 4 Hours</button>
                <button class="time-range-btn" onclick="loadTrendData('12h')">Last 12 Hours</button>
                <button class="time-range-btn" onclick="loadTrendData('24h')">Last 24 Hours</button>
                <button class="time-range-btn" onclick="loadTrendData('7d')">Last 7 Days</button>
            </div>
            <div class="chart-container">
                <canvas id="temperatureChart"></canvas>
            </div>
            <div id="chartStatus" class="loading">Loading chart data...</div>
        </div>
        
        <div class="card">
            <button class="btn" onclick="fetchData()">Refresh Data</button>
            <button class="btn" onclick="toggleAutoRefresh()">Toggle Auto-Refresh</button>
            <button class="btn" onclick="refreshChart()">Refresh Chart</button>
        </div>
    </div>

    <script>
        let chart;
        let autoRefresh = false;
        let refreshInterval;
        let currentTimeRange = '1h';
        
        // Initialize chart
        function initChart() {{
            const ctx = document.getElementById('temperatureChart').getContext('2d');
            chart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: [],
                    datasets: [{{
                        label: 'Temperature (°F)',
                        data: [],
                        borderColor: '#2196F3',
                        backgroundColor: 'rgba(33, 150, 243, 0.1)',
                        tension: 0.4,
                        fill: false,
                        pointRadius: 2,
                        pointHoverRadius: 5
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        intersect: false,
                        mode: 'index'
                    }},
                    scales: {{
                        x: {{
                            display: true,
                            title: {{
                                display: true,
                                text: 'Time'
                            }}
                        }},
                        y: {{
                            display: true,
                            title: {{
                                display: true,
                                text: 'Temperature (°F)'
                            }},
                            beginAtZero: false
                        }}
                    }},
                    plugins: {{
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    return `Temperature: ${{context.parsed.y.toFixed(1)}}°F`;
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        // Fetch current thermostat data (keeping all original functionality)
        async function fetchData() {{
            try {{
                const response = await fetch('/api/thermostat');
                const data = await response.json();
                
                if (data.error) {{
                    alert('Error: ' + data.error);
                    return;
                }}
                
                updateCurrentDisplay(data);
            }} catch (error) {{
                console.error('Error fetching data:', error);
                alert('Failed to fetch data: ' + error.message);
            }}
        }}
        
        // Keep the exact same display update logic as original
        function updateCurrentDisplay(data) {{
            // Update temperature circle
            const tempValue = data.temperature ? data.temperature.toFixed(1) : '--';
            const setpointValue = data.setpoint ? data.setpoint.toFixed(1) : '--';
            
            document.getElementById('currentTemp').textContent = tempValue;
            document.getElementById('setpointText').textContent = `Setpoint: ${{setpointValue}}°F`;
            
            // Determine mode and circle styling
            const circle = document.getElementById('tempCircle');
            const modeText = document.getElementById('modeText');
            
            // Clear all mode classes
            circle.className = 'temperature-circle';
            modeText.className = 'mode-text';
            
            if (data.peak_savings) {{
                circle.classList.add('peak-savings');
                modeText.classList.add('peak-savings');
                modeText.textContent = 'Peak Savings Mode';
            }} else if (data.system_mode === 'Cooling') {{
                circle.classList.add('cooling');
                modeText.classList.add('cooling');
                modeText.textContent = 'Cooling';
            }} else if (data.system_mode === 'Heating') {{
                circle.classList.add('heating');
                modeText.classList.add('heating');
                modeText.textContent = 'Heating';
            }} else {{
                circle.classList.add('deadband');
                modeText.classList.add('deadband');
                modeText.textContent = 'Standby';
            }}
            
            // Update device title - use custom display name or actual device name
            if ('{DISPLAY_DEVICE_NAME}') {{
                // Use the custom display name from configuration
                document.getElementById('deviceTitle').textContent = '{DISPLAY_DEVICE_NAME}';
            }} else if (data.device_name && data.device_name !== 'Device {DEVICE}') {{
                // Use actual device name from BACnet if no custom name set
                document.getElementById('deviceTitle').textContent = data.device_name;
            }} else {{
                // Fallback to Device + number
                document.getElementById('deviceTitle').textContent = `Device {DEVICE}`;
            }}
            
            document.getElementById('lastUpdated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
        }}
        
        // NEW: Load trend data for chart
        async function loadTrendData(timeRange) {{
            try {{
                document.getElementById('chartStatus').textContent = 'Loading trend data...';
                document.getElementById('chartStatus').className = 'loading';
                
                // Update active button - more precise matching
                document.querySelectorAll('.time-range-btn').forEach(btn => {{
                    btn.classList.remove('active');
                }});
                
                // Find and activate the correct button based on timeRange
                const buttonMap = {{
                    '1h': 'Last Hour',
                    '4h': 'Last 4 Hours', 
                    '12h': 'Last 12 Hours',
                    '24h': 'Last 24 Hours',
                    '7d': 'Last 7 Days'
                }};
                
                document.querySelectorAll('.time-range-btn').forEach(btn => {{
                    if (btn.textContent === buttonMap[timeRange]) {{
                        btn.classList.add('active');
                    }}
                }});
                
                currentTimeRange = timeRange;
                
                const response = await fetch(`/api/trends?range=${{timeRange}}`);
                const data = await response.json();
                
                if (data.error) {{
                    document.getElementById('chartStatus').textContent = 'Error loading trend data: ' + data.error;
                    document.getElementById('chartStatus').className = 'error';
                    return;
                }}
                
                updateChart(data);
                document.getElementById('chartStatus').textContent = `Loaded ${{data.records.length}} data points for ${{data.actual_range}}`;
                document.getElementById('chartStatus').className = 'last-updated';
                
            }} catch (error) {{
                console.error('Error fetching trend data:', error);
                document.getElementById('chartStatus').textContent = 'Failed to load trend data: ' + error.message;
                document.getElementById('chartStatus').className = 'error';
            }}
        }}
        
        // NEW: Update chart with trend data
        function updateChart(trendData) {{
            if (!trendData.records || trendData.records.length === 0) {{
                chart.data.labels = [];
                chart.data.datasets[0].data = [];
                chart.update();
                return;
            }}
            
            const labels = [];
            const temperatures = [];
            
            trendData.records.forEach(record => {{
                labels.push(record.formatted_time);
                temperatures.push(record.temperature);
            }});
            
            chart.data.labels = labels;
            chart.data.datasets[0].data = temperatures;
            chart.update();
        }}
        
        // NEW: Refresh chart with current time range
        function refreshChart() {{
            loadTrendData(currentTimeRange);
        }}
        
        // Toggle auto-refresh for current data (keeping original functionality)
        function toggleAutoRefresh() {{
            autoRefresh = !autoRefresh;
            if (autoRefresh) {{
                refreshInterval = setInterval(fetchData, 5000); // Original 5 second interval
                alert('Auto-refresh enabled (every 5 seconds)');
            }} else {{
                clearInterval(refreshInterval);
                alert('Auto-refresh disabled');
            }}
        }}
        
        // Initialize on page load
        window.onload = function() {{
            initChart();
            fetchData(); // Get current data (original function)
            loadTrendData('1h'); // Load initial trend data for chart
        }};
    </script>
</body>
</html>'''

@app.route('/api/thermostat')
def get_thermostat_data():
    """
    API endpoint that mimics your Python code functionality
    Returns current thermostat data from EnteliWeb
    """
    try:
        data = {}
        
        # Fetch temperature
        temp_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/analog-input,{TEMPERATURE_AI}/present-value?alt=json"
        response = requests.get(temp_url, headers=auth_header, timeout=10)
        if response.ok:
            temp_data = response.json()
            data['temperature'] = float(temp_data.get('value', 0))
        
        # Fetch zone setpoint
        setpoint_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/analog-value,{SETPOINT_AV}/present-value?alt=json"
        response = requests.get(setpoint_url, headers=auth_header, timeout=10)
        if response.ok:
            setpoint_data = response.json()
            data['setpoint'] = float(setpoint_data.get('value', 0))
        
        # Fetch system mode
        mode_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/multi-state-value,{SYSTEM_MODE_MV}/present-value?alt=json"
        response = requests.get(mode_url, headers=auth_header, timeout=10)
        if response.ok:
            mode_data = response.json()
            mode_value = mode_data.get('value', '3')
            
            # Convert string to integer
            try:
                mode_number = int(mode_value)
            except:
                mode_number = 3
            
            # Map numeric values to text
            mode_map = {
                1: 'Heating',
                2: 'Cooling', 
                3: 'Deadband'
            }
            
            mode_text = mode_map.get(mode_number, 'Deadband')
            data['system_mode'] = mode_text
            
            # Set heating and cooling based on mode
            data['heating'] = mode_number == 1
            data['cooling'] = mode_number == 2
        else:
            data['system_mode'] = 'Error'
        
        # Fetch peak savings mode status
        peak_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/binary-value,{PEAK_SAVINGS_BV}/present-value?alt=json"
        response = requests.get(peak_url, headers=auth_header, timeout=10)
        if response.ok:
            peak_data = response.json()
            peak_value = peak_data.get('value')
            data['peak_savings'] = peak_value == 'active' or peak_value == 'Active' or peak_value == 'On' or peak_value == True or peak_value == 1
        
        # Fetch fan status
        fan_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/binary-output,{FAN_STATUS_BO}/present-value?alt=json"
        response = requests.get(fan_url, headers=auth_header, timeout=10)
        if response.ok:
            fan_data = response.json()
            fan_value = fan_data.get('value')
            data['fan'] = fan_value == 'active' or fan_value == 'Active' or fan_value == 'On' or fan_value == True or fan_value == 1
        
        # Fetch device name from DEV object
        device_name_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/device,{DEVICE}/object-name?alt=json"
        response = requests.get(device_name_url, headers=auth_header, timeout=10)
        if response.ok:
            device_name_data = response.json()
            data['device_name'] = device_name_data.get('value', f'Device {DEVICE}')
        else:
            # Try device-name property as backup
            device_name_url2 = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/device,{DEVICE}/device-name?alt=json"
            response2 = requests.get(device_name_url2, headers=auth_header, timeout=10)
            if response2.ok:
                device_name_data2 = response2.json()
                data['device_name'] = device_name_data2.get('value', f'Device {DEVICE}')
            else:
                data['device_name'] = f'Device {DEVICE}'
        return jsonify(data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

        # Use pagination to fetch all pages
        rows = []
        for page in fetch_enteli_pages(base_url, params):
            for key, v in page.items():
                if key in ('$base', 'next') or not isinstance(v, dict) or "timestamp" not in v:
                    continue
                    
                ld = v.get("logDatum", {})
                
                # ---- skip status‑only rows (no real‑value) ----
                if any(k in ld for k in ("log-status", "event-state", "string-value")):
                    debug_info.append(f"SKIP {key}: status row → {list(ld.keys())}")
                    continue

                # extract numeric value
                val = None
                if "real-value" in ld and isinstance(ld["real-value"], dict):
                    val = ld["real-value"].get("value")
                if val is None:
                    for w in ld.values():
                        if isinstance(w, dict) and "value" in w:
                            try:
                                val = float(w["value"])
                                break
                            except (ValueError, TypeError):
                                pass
                if val is None:
                    debug_info.append(f"SKIP {key}: no numeric value")
                    continue

                ts_raw = v["timestamp"]["value"]
                # Simple timestamp parsing
                if ts_raw.endswith('Z'):
                    ts_dt = datetime.fromisoformat(ts_raw[:-1]).replace(tzinfo=timezone.utc)
                else:
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

@app.route('/test-pagination')
def test_pagination():
    url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/trend-log,{TEMP_TREND_LOG_INSTANCE}/log-buffer"
    params = {"alt": "json", "max-results": 5}
    
    results = []
    page_num = 0
    
    while url and page_num < 3:  # Just test 3 pages
        page_num += 1
        try:
            resp = requests.get(url, params=params if page_num == 1 else {"alt": "json"}, headers=auth_header, timeout=30)
            results.append(f"Page {page_num}: HTTP {resp.status_code}")
            
            if resp.status_code != 200:
                results.append(f"Error: {resp.text[:200]}")
                break
                
            data = resp.json()
            record_count = len([k for k in data.keys() if k not in ('$base', 'next')])
            results.append(f"Page {page_num}: {record_count} records")
            
            url = data.get('next')
            results.append(f"Next URL exists: {url is not None}")
            
            if not url:
                results.append("No more pages")
                break
                
        except requests.exceptions.JSONDecodeError as e:
            results.append(f"Page {page_num}: JSON decode error")
            results.append(f"Response text: {resp.text[:200]}")
            break
        except Exception as e:
            results.append(f"Page {page_num}: Error - {str(e)}")
            break
    
    return {"results": results}

@app.route('/api/debug')
def debug_values():
    """Debug endpoint to see raw values from BACnet objects"""
    try:
        debug_data = {}
        
        # Debug system mode
        mv_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/multi-state-value,{SYSTEM_MODE_MV}/present-value?alt=json"
        response = requests.get(mv_url, headers=auth_header, timeout=10)
        if response.ok:
            debug_data['system_mode_present_value'] = response.json()
        
        # Try to get state text for system mode
        mv_text_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/multi-state-value,{SYSTEM_MODE_MV}/state-text?alt=json"
        response = requests.get(mv_text_url, headers=auth_header, timeout=10)
        if response.ok:
            debug_data['system_mode_state_text'] = response.json()
        
        # Debug fan status
        fan_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/binary-output,{FAN_STATUS_BO}/present-value?alt=json"
        response = requests.get(fan_url, headers=auth_header, timeout=10)
        if response.ok:
            debug_data['fan_status_present_value'] = response.json()
        
        # Debug trend log info
        trend_info_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/trend-log,{TEMP_TREND_LOG_INSTANCE}/object-name?alt=json"
        response = requests.get(trend_info_url, headers=auth_header, timeout=10)
        if response.ok:
            debug_data['trend_log_name'] = response.json()
        else:
            debug_data['trend_log_name_error'] = f"HTTP {response.status_code}: {response.text[:200]}"
        
        # Test trend log with no time filter (get last 10 records)
        trend_test_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/trend-log,{TEMP_TREND_LOG_INSTANCE}/log-buffer?max-results=10&alt=json"
        response = requests.get(trend_test_url, headers=auth_header, timeout=10)
        if response.ok:
            trend_test_data = response.json()
            debug_data['trend_log_test'] = {
                'total_keys': len(trend_test_data),
                'sample_keys': list(trend_test_data.keys())[:10],
                'sample_records': []
            }
            # Get a few sample records with timestamps
            count = 0
            for key, value in trend_test_data.items():
                if key != '$base' and count < 3:
                    if isinstance(value, dict) and 'timestamp' in value:
                        debug_data['trend_log_test']['sample_records'].append({
                            'key': key,
                            'timestamp': value.get('timestamp', {}),
                            'logDatum': value.get('logDatum', {})
                        })
                        count += 1
        else:
            debug_data['trend_log_test_error'] = f"HTTP {response.status_code}: {response.text[:200]}"
        
        # Add current time for comparison
        debug_data['current_server_time'] = datetime.now().isoformat()
        debug_data['current_utc_time'] = datetime.utcnow().isoformat()
        
        return jsonify(debug_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print(f"Starting Enhanced Thermostat Dashboard Server...")
    print(f"EnteliWeb Server: {SERVER}")
    print(f"Site: {SITE}")
    print(f"Device: {DEVICE}")
    print(f"Temperature Trend Log Instance: {TEMP_TREND_LOG_INSTANCE}")
    print(f"Dashboard URL: http://localhost:8000")
    print(f"API Test: http://localhost:8000/api/thermostat")
    print(f"Trend API Test: http://localhost:8000/api/trends?range=1h")
    print(f"Debug API: http://localhost:8000/api/debug")
    print("\nMake sure to update the PASSWORD variable and TEMP_TREND_LOG_INSTANCE!")
    
    app.run(host='0.0.0.0', port=8000, debug=True)
