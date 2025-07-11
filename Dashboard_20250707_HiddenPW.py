#!/usr/bin/env python3
"""
Configurable Web Server for Thermostat Dashboard
Easily adaptable for different controllers and EnteliCloud servers
"""

import os

# ============================================================================
# CLIENT CONFIGURATION - MODIFY THESE SETTINGS FOR EACH DEPLOYMENT
# ============================================================================

# EnteliCloud Server Connection
SERVER = "stasisenergy.entelicloud.com"       # Your EnteliCloud server URL (no https://)
SITE = "UnivRedlands"                         # Site name in EnteliCloud
DEVICE = "4145549"                            # Device ID number

# Authentication Credentials
USER = "stasis_api"                           # API username
PASSWORD = os.environ.get('PASSWORD', 'your_password_here')  # API password

# BACnet Object Mapping - Update these for your specific controller
OBJECTS = {
    # Temperature readings
    'temperature': 'analog-input,201001',      # Current zone temperature sensor (for display)
    'trend_temperature': 'analog-value,1',     # Temperature for trend log (AV1)
    
    # Setpoint controls (configure based on your system type)
    'zone_setpoint': 'analog-value,1',         # Single zone setpoint (if using single setpoint)
    'heating_setpoint': 'analog-value,3',      # Heating setpoint (if using dual setpoint)
    'cooling_setpoint': 'analog-value,2',      # Cooling setpoint (if using dual setpoint)
    
    # System status indicators
    'system_mode': 'multi-state-value,2',      # System mode (heating/cooling/deadband)
    'peak_savings': 'binary-value,16',         # Peak demand savings mode
    'fan_status': 'binary-output,1105',        # Supply fan on/off status
    
    # Device information
    'device_name': 'device,{DEVICE}/object-name',  # Controller device name
    'trend_log': 'trend-log,27',               # Temperature trend log (TL27)
}

# Dashboard Display Settings
DISPLAY_CONFIG = {
    'use_dual_setpoints': False,               # True = dual setpoint, False = single setpoint
    'site_display_name': SITE,                # How site appears on dashboard
    'company_name': 'Stasis Energy Group',     # Your company name
    'logo_url': 'https://raw.githubusercontent.com/stasisluke/stasis-dashboard/main/stasis-logo.png',
    'dashboard_title': 'Thermal Energy Storage Dashboard',  # Subtitle text
}

# Server Settings
PORT = 8000                                   # Web server port
DEBUG_MODE = False                            # Set to True for development

# ============================================================================
# END CLIENT CONFIGURATION
# ============================================================================

from flask import Flask, request, jsonify, send_from_directory
import requests
import base64
from datetime import datetime

app = Flask(__name__)

# Basic auth header
auth_header = {
    "Authorization": f"Basic {base64.b64encode(f'{USER}:{PASSWORD}'.encode()).decode()}",
    "Accept": "application/json"
}

@app.route('/')
def index():
    """Serve the main dashboard HTML"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{DISPLAY_CONFIG['company_name']} - {DISPLAY_CONFIG['site_display_name']} Device {DEVICE}</title>
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
            text-align: center;
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
        .chart-container {{ position: relative; height: 300px; margin-top: 20px; }}
        .last-updated {{ font-size: 0.9em; color: #666; text-align: center; margin-top: 10px; }}
        .btn {{ padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 1em; background: #2196F3; color: white; margin: 5px; }}
        .btn:hover {{ background: #1976D2; }}
        .chart-controls {{
            margin-bottom: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .chart-controls label {{
            font-weight: 600;
            color: #333;
        }}
        .chart-controls input {{
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .chart-controls span {{
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="stasis-logo">
                <img src="{DISPLAY_CONFIG['logo_url']}" alt="{DISPLAY_CONFIG['company_name']}" onerror="this.style.display='none'">
            </div>
            <div class="header-text">
                <h1>{DISPLAY_CONFIG['company_name']}</h1>
                <h2 id="deviceTitle">{DISPLAY_CONFIG['site_display_name']} - Device {DEVICE}</h2>
                <p class="powered-by">{DISPLAY_CONFIG['dashboard_title']}</p>
            </div>
        </div>
        
        <div class="card">
            <h3>Current Temperature</h3>
            <div class="temperature-circle" id="tempCircle">
                <div class="temperature-value" id="currentTemp">--</div>
                <div class="temperature-unit">°F</div>
                <div class="setpoint-text" id="setpointText">{"Comfort Range: --°F - --°F" if DISPLAY_CONFIG['use_dual_setpoints'] else "Setpoint: --°F"}</div>
                <div class="mode-text" id="modeText">--</div>
            </div>
            <div class="last-updated" id="lastUpdated">Never updated</div>
        </div>
        
        <div class="card">
            <h3>Temperature History (Last 7 Days)</h3>
            <div class="chart-controls">
                <label for="dateRange">Select Date Range:</label>
                <input type="datetime-local" id="startDate" />
                <span> to </span>
                <input type="datetime-local" id="endDate" />
                <button class="btn" onclick="updateChartRange()">Update Chart</button>
                <button class="btn" onclick="setQuickRange('24h')">Last 24h</button>
                <button class="btn" onclick="setQuickRange('3d')">Last 3 Days</button>
                <button class="btn" onclick="setQuickRange('7d')">Last 7 Days</button>
            </div>
            <div class="chart-container">
                <canvas id="temperatureChart"></canvas>
            </div>
        </div>
        
        <div class="card">
            <button class="btn" onclick="fetchData()">Refresh Data</button>
            <button class="btn" onclick="toggleAutoRefresh()">Toggle Auto-Refresh</button>
            <button class="btn" onclick="window.open('/api/debug', '_blank')">Debug Info</button>
        </div>
    </div>

    <script>
        let chart;
        let autoRefresh = false;
        let refreshInterval;
        let trendData = []; // Store all trend log data
        const useDualSetpoints = {str(DISPLAY_CONFIG['use_dual_setpoints']).lower()};
        
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
                        tension: 0.1,
                        fill: true,
                        pointRadius: 1,
                        pointHoverRadius: 4
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
                            // Use linear scale initially, will convert to time scale when data loads
                            type: 'linear',
                            display: true
                        }},
                        y: {{
                            beginAtZero: false,
                            title: {{
                                display: true,
                                text: 'Temperature (°F)'
                            }}
                        }}
                    }},
                    plugins: {{
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    return `Temperature: ${{context.parsed.y ? context.parsed.y.toFixed(1) : '--'}}°F`;
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        // Set quick date ranges
        function setQuickRange(range) {{
            const now = new Date();
            const start = new Date();
            
            switch(range) {{
                case '24h':
                    start.setHours(now.getHours() - 24);
                    break;
                case '3d':
                    start.setDate(now.getDate() - 3);
                    break;
                case '7d':
                    start.setDate(now.getDate() - 7);
                    break;
            }}
            
            document.getElementById('startDate').value = start.toISOString().slice(0, 16);
            document.getElementById('endDate').value = now.toISOString().slice(0, 16);
            updateChartRange();
        }}
        
        // Update chart with selected date range
        function updateChartRange() {{
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            
            if (!startDate || !endDate) {{
                alert('Please select both start and end dates');
                return;
            }}
            
            const start = new Date(startDate);
            const end = new Date(endDate);
            
            // Filter trend data to selected range
            const filteredData = trendData.filter(point => {{
                const pointDate = new Date(point.timestamp);
                return pointDate >= start && pointDate <= end;
            }});
            
            updateChartData(filteredData);
        }}
        
        // Update chart with filtered data
        function updateChartData(data) {{
            // Convert timestamps to readable labels for now (we'll improve this later)
            const labels = data.map(point => {{
                const date = new Date(point.timestamp);
                return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}});
            }});
            
            chart.data.labels = labels;
            chart.data.datasets[0].data = data.map(point => point.value);
            chart.update();
        }}
        
        // Fetch trend log data
        async function fetchTrendData() {{
            try {{
                const response = await fetch('/api/trend');
                const data = await response.json();
                
                if (data.error) {{
                    console.error('Trend data error:', data.error);
                    return;
                }}
                
                trendData = data.trend_data || [];
                
                // Set default to last 24 hours
                setQuickRange('24h');
                
            }} catch (error) {{
                console.error('Error fetching trend data:', error);
            }}
        }}
        
        // Fetch current data from our Python API
        async function fetchData() {{
            console.log('Starting fetchData...');
            try {{
                console.log('Making request to /api/thermostat');
                const response = await fetch('/api/thermostat');
                console.log('Response status:', response.status);
                
                if (!response.ok) {{
                    console.error('Response not OK:', response.status, response.statusText);
                    alert('Error: HTTP ' + response.status);
                    return;
                }}
                
                const data = await response.json();
                console.log('Response data:', data);
                
                if (data.error) {{
                    console.error('API error:', data.error);
                    alert('Error: ' + data.error);
                    return;
                }}
                
                updateDisplay(data);
            }} catch (error) {{
                console.error('Error fetching data:', error);
                alert('Failed to fetch data: ' + error.message);
            }}
        }}
        
        // Update display with new data
        function updateDisplay(data) {{
            // Update temperature circle
            const tempValue = data.temperature ? data.temperature.toFixed(1) : '--';
            document.getElementById('currentTemp').textContent = tempValue;
            
            // Update setpoint display based on configuration
            if (useDualSetpoints) {{
                const heatingSetpoint = data.heating_setpoint ? data.heating_setpoint.toFixed(0) : '--';
                const coolingSetpoint = data.cooling_setpoint ? data.cooling_setpoint.toFixed(0) : '--';
                document.getElementById('setpointText').textContent = `Comfort Range: ${{heatingSetpoint}}°F - ${{coolingSetpoint}}°F`;
            }} else {{
                const setpointValue = data.zone_setpoint ? data.zone_setpoint.toFixed(1) : '--';
                document.getElementById('setpointText').textContent = `Setpoint: ${{setpointValue}}°F`;
            }}
            
            // Determine mode and circle styling
            const circle = document.getElementById('tempCircle');
            const modeText = document.getElementById('modeText');
            
            // Clear all mode classes
            circle.className = 'temperature-circle';
            modeText.className = 'mode-text';
            
            if (data.peak_savings) {{
                circle.classList.add('peak-savings');
                modeText.classList.add('peak-savings');
                modeText.textContent = 'PEAK SAVINGS MODE';
            }} else if (data.system_mode === 'Cooling') {{
                circle.classList.add('cooling');
                modeText.classList.add('cooling');
                modeText.textContent = 'COOLING';
            }} else if (data.system_mode === 'Heating') {{
                circle.classList.add('heating');
                modeText.classList.add('heating');
                modeText.textContent = 'HEATING';
            }} else {{
                circle.classList.add('deadband');
                modeText.classList.add('deadband');
                modeText.textContent = 'MAINTAINING';
            }}
            
            // Update device title
            if (data.device_name && data.device_name !== 'Device {DEVICE}') {{
                document.getElementById('deviceTitle').textContent = `{DISPLAY_CONFIG['site_display_name']} : ${{data.device_name}}`;
            }}
            
            document.getElementById('lastUpdated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
        }}
        
        // Toggle auto-refresh
        function toggleAutoRefresh() {{
            autoRefresh = !autoRefresh;
            if (autoRefresh) {{
                refreshInterval = setInterval(fetchData, 30000); // Every 30 seconds for current temp
                alert('Auto-refresh enabled (every 30 seconds)');
            }} else {{
                clearInterval(refreshInterval);
                alert('Auto-refresh disabled');
            }}
        }}
        
        // Initialize on page load
        window.onload = function() {{
            initChart();
            fetchData(); // Get current temperature
            fetchTrendData(); // Get historical data
        }};
    </script>
</body>
</html>'''

@app.route('/api/thermostat')
def get_thermostat_data():
    """
    API endpoint that fetches thermostat data using configurable object mapping
    """
    try:
        data = {}
        
        # Helper function to fetch BACnet object value
        def fetch_object_value(object_id):
            url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/{object_id}/present-value?alt=json"
            print(f"Fetching {object_id} from: {url}")
            try:
                response = requests.get(url, headers=auth_header, timeout=10)
                print(f"Response for {object_id}: HTTP {response.status_code}")
                if response.ok:
                    response_data = response.json()
                    print(f"Response data for {object_id}: {response_data}")
                    # Handle different response formats
                    if isinstance(response_data, dict):
                        if 'value' in response_data:
                            print(f"Found value for {object_id}: {response_data['value']}")
                            return response_data['value']
                        elif '$base' in response_data and 'value' in response_data:
                            print(f"Found $base value for {object_id}: {response_data['value']}")
                            return response_data['value']
                    print(f"Returning raw data for {object_id}: {response_data}")
                    return response_data
                else:
                    print(f"Failed to fetch {object_id}: HTTP {response.status_code}")
                    print(f"Response text: {response.text}")
                    return None
            except Exception as e:
                print(f"Error fetching {object_id}: {e}")
                return None
        
        # Fetch temperature
        temp_value = fetch_object_value(OBJECTS['temperature'])
        print(f"Temperature fetch result: {temp_value} (type: {type(temp_value)})")
        if temp_value is not None:
            data['temperature'] = float(temp_value)
        
        # Fetch setpoints based on configuration
        if DISPLAY_CONFIG['use_dual_setpoints']:
            # Dual setpoint system
            heating_sp = fetch_object_value(OBJECTS['heating_setpoint'])
            cooling_sp = fetch_object_value(OBJECTS['cooling_setpoint'])
            if heating_sp is not None:
                data['heating_setpoint'] = float(heating_sp)
            if cooling_sp is not None:
                data['cooling_setpoint'] = float(cooling_sp)
        else:
            # Single setpoint system
            zone_sp = fetch_object_value(OBJECTS['zone_setpoint'])
            if zone_sp is not None:
                data['zone_setpoint'] = float(zone_sp)
        
        # Fetch system mode (handle complex formats)
        mode_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/{OBJECTS['system_mode']}/present-value?alt=json"
        response = requests.get(mode_url, headers=auth_header, timeout=10)
        if response.ok:
            mode_data = response.json()
            
            # Handle different mode value formats
            mode_value = mode_data.get('value', '3')
            if isinstance(mode_value, dict) and 'enumerated' in mode_value:
                # Handle Choice object format
                mode_value = mode_value['enumerated'].get('value', '3')
            
            try:
                mode_number = int(str(mode_value))
                mode_map = {1: 'Heating', 2: 'Cooling', 3: 'Deadband'}
                data['system_mode'] = mode_map.get(mode_number, 'Deadband')
            except:
                data['system_mode'] = 'Unknown'
        
        # Fetch peak savings status
        peak_value = fetch_object_value(OBJECTS['peak_savings'])
        if peak_value is not None:
            data['peak_savings'] = str(peak_value).lower() in ['active', 'on', 'true', '1']
        
        # Fetch fan status
        fan_value = fetch_object_value(OBJECTS['fan_status'])
        if fan_value is not None:
            data['fan_status'] = str(fan_value).lower() in ['active', 'on', 'true', '1']
        
        # Fetch device name
        device_name_obj = OBJECTS['device_name'].format(DEVICE=DEVICE)
        device_name_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/{device_name_obj}?alt=json"
        response = requests.get(device_name_url, headers=auth_header, timeout=10)
        if response.ok:
            device_data = response.json()
            data['device_name'] = device_data.get('value', f'Device {DEVICE}')
        else:
            data['device_name'] = f'Device {DEVICE}'
        
        data['timestamp'] = datetime.now().isoformat()
        return jsonify(data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trend')
def get_trend_data():
    """
    API endpoint that fetches trend log data for historical temperature chart
    """
    try:
        from datetime import datetime, timedelta
        
        # First try to get recent data (last 7 days)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)
        
        # Format dates for API (yyyy-mm-ddThh:mm:ss)
        start_str = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        end_str = end_time.strftime('%Y-%m-%dT%H:%M:%S')
        
        # Try with date range first
        trend_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/{OBJECTS['trend_log']}/log-buffer?published-ge={start_str}&published-le={end_str}&alt=json"
        
        print(f"Trying with date range: {trend_url}")
        response = requests.get(trend_url, headers=auth_header, timeout=30)
        
        # If date range fails, try without date filter to get any available data
        if not response.ok:
            print(f"Date range failed (HTTP {response.status_code}), trying without date filter...")
            trend_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/{OBJECTS['trend_log']}/log-buffer?alt=json"
            response = requests.get(trend_url, headers=auth_header, timeout=30)
        
        # If still failing, try with max-results parameter
        if not response.ok:
            print(f"Basic call failed (HTTP {response.status_code}), trying with max-results...")
            trend_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/{OBJECTS['trend_log']}/log-buffer?max-results=100&alt=json"
            response = requests.get(trend_url, headers=auth_header, timeout=30)
        
        if not response.ok:
            print(f"All attempts failed. HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Try to check if the trend log object exists at all
            tl_check_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/{OBJECTS['trend_log']}?alt=json"
            check_response = requests.get(tl_check_url, headers=auth_header, timeout=10)
            
            if check_response.ok:
                return jsonify({
                    'error': f'Trend log exists but log-buffer access failed: HTTP {response.status_code}',
                    'trend_log_properties': check_response.json()
                }), 500
            else:
                return jsonify({
                    'error': f'Trend log TL27 does not exist: HTTP {check_response.status_code}',
                    'suggestion': 'Check /api/debug to see which trend logs are available'
                }), 500
        
        trend_raw = response.json()
        print(f"Successfully got response, type: {type(trend_raw)}")
        
        trend_data = []
        
        # Parse trend log entries according to EnteliCloud format
        if isinstance(trend_raw, dict):
            # Filter out metadata keys
            sequence_numbers = [key for key in trend_raw.keys() if key != "$base" and key.isdigit()]
            print(f"Found {len(sequence_numbers)} sequence entries")
            
            # Debug: show first few keys
            if len(sequence_numbers) > 0:
                sample_keys = sorted(sequence_numbers, key=int)[:3]
                print(f"Sample sequence numbers: {sample_keys}")
                
                for seq_num in sample_keys:
                    print(f"Sample entry {seq_num}: {trend_raw[seq_num]}")
            
            for seq_num in sequence_numbers:
                try:
                    entry = trend_raw[seq_num]
                    
                    if not isinstance(entry, dict):
                        continue
                    
                    # Extract timestamp
                    timestamp_obj = entry.get('timestamp', {})
                    timestamp_str = None
                    if isinstance(timestamp_obj, dict) and 'value' in timestamp_obj:
                        timestamp_str = timestamp_obj['value']
                    elif isinstance(timestamp_obj, str):
                        timestamp_str = timestamp_obj
                    
                    if not timestamp_str:
                        print(f"No timestamp found in entry {seq_num}")
                        continue
                    
                    # Extract value from logDatum
                    log_datum = entry.get('logDatum', {})
                    value = None
                    
                    if isinstance(log_datum, dict):
                        # Try different value types
                        for value_type in ['real-value', 'unsigned-value', 'signed-value']:
                            if value_type in log_datum:
                                value_obj = log_datum[value_type]
                                if isinstance(value_obj, dict) and 'value' in value_obj:
                                    value = float(value_obj['value'])
                                    break
                                elif isinstance(value_obj, (int, float)):
                                    value = float(value_obj)
                                    break
                    
                    if value is not None and timestamp_str:
                        # Parse timestamp (format: 2014-06-04T12:00:57.67)
                        try:
                            # Remove sub-seconds if present and parse
                            if '.' in timestamp_str:
                                timestamp_str = timestamp_str.split('.')[0]
                            dt = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S')
                            
                            trend_data.append({
                                'timestamp': dt.isoformat(),
                                'value': value,
                                'sequence': seq_num
                            })
                            
                        except ValueError as e:
                            print(f"Error parsing timestamp '{timestamp_str}': {e}")
                            continue
                    else:
                        print(f"Missing data in entry {seq_num}: timestamp={timestamp_str}, value={value}")
                    
                except Exception as e:
                    print(f"Error processing sequence {seq_num}: {e}")
                    continue
        
        print(f"Successfully parsed {len(trend_data)} data points")
        
        if not trend_data:
            return jsonify({
                'error': 'No valid data points found in trend log',
                'debug_info': {
                    'url_used': trend_url,
                    'response_keys': list(trend_raw.keys()) if isinstance(trend_raw, dict) else 'not_dict',
                    'raw_response_sample': str(trend_raw)[:1000] if trend_raw else 'empty'
                }
            }), 500
        
        # Sort by timestamp
        trend_data.sort(key=lambda x: x['timestamp'])
        
        print(f"Returning {len(trend_data)} trend data points")
        if trend_data:
            print(f"Date range: {trend_data[0]['timestamp']} to {trend_data[-1]['timestamp']}")
        
        return jsonify({
            'trend_data': trend_data,
            'total_points': len(trend_data),
            'date_range': {
                'start': trend_data[0]['timestamp'] if trend_data else None,
                'end': trend_data[-1]['timestamp'] if trend_data else None
            }
        })
        
    except Exception as e:
        print(f"Trend data error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug')
def debug_values():
    """Debug endpoint to see all configured objects and their raw values"""
    try:
        debug_data = {
            'configuration': {
                'server': SERVER,
                'site': SITE,
                'device': DEVICE,
                'objects': OBJECTS,
                'display_config': DISPLAY_CONFIG
            },
            'raw_values': {},
            'trend_log_check': {}
        }
        
        # Fetch all configured objects
        for obj_name, obj_id in OBJECTS.items():
            if obj_name == 'device_name':
                continue  # Skip device name as it needs special handling
                
            url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/{obj_id}/present-value?alt=json"
            try:
                response = requests.get(url, headers=auth_header, timeout=10)
                if response.ok:
                    debug_data['raw_values'][obj_name] = response.json()
                else:
                    debug_data['raw_values'][obj_name] = f"HTTP {response.status_code}"
            except Exception as e:
                debug_data['raw_values'][obj_name] = f"Error: {str(e)}"
        
        # Check for trend logs - try different numbers
        for tl_num in [27, 1, 2, 3, 4, 5, 10, 20, 25, 26, 28, 29, 30]:
            tl_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/trend-log,{tl_num}/present-value?alt=json"
            try:
                response = requests.get(tl_url, headers=auth_header, timeout=10)
                if response.ok:
                    debug_data['trend_log_check'][f'TL{tl_num}'] = 'EXISTS'
                else:
                    debug_data['trend_log_check'][f'TL{tl_num}'] = f"HTTP {response.status_code}"
            except Exception as e:
                debug_data['trend_log_check'][f'TL{tl_num}'] = f"Error: {str(e)}"
        
        # Also try to list all objects on the device
        device_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/present-value?alt=json"
        try:
            response = requests.get(device_url, headers=auth_header, timeout=10)
            if response.ok:
                device_data = response.json()
                debug_data['device_objects'] = device_data
            else:
                debug_data['device_objects'] = f"HTTP {response.status_code}"
        except Exception as e:
            debug_data['device_objects'] = f"Error: {str(e)}"
        
        return jsonify(debug_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("CONFIGURABLE THERMOSTAT DASHBOARD")
    print("=" * 60)
    print(f"Server: {SERVER}")
    print(f"Site: {SITE}")
    print(f"Device: {DEVICE}")
    print(f"Username: {USER}")
    print(f"Password: {'SET' if PASSWORD != 'your_password_here' else 'NOT SET - USING DEFAULT'}")
    print(f"Setpoint Mode: {'Dual' if DISPLAY_CONFIG['use_dual_setpoints'] else 'Single'}")
    print(f"Company: {DISPLAY_CONFIG['company_name']}")
    print("-" * 60)
    print(f"Dashboard URL: http://localhost:{PORT}")
    print(f"Debug URL: http://localhost:{PORT}/api/debug")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG_MODE)
