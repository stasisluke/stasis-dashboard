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
SERVER = "https://stasisenergy.entelicloud.com/"  # Your EnteliCloud server URL
SITE = "UnivRedlands"                   # Site name in EnteliCloud
DEVICE = "4145549"                              # Device ID number

# Authentication Credentials
USER = "stasis_api"                           # API username
PASSWORD = os.environ.get('PASSWORD', 'your_password_here')  # API password

# BACnet Object Mapping - Update these for your specific controller
OBJECTS = {
    # Temperature readings
    'temperature': 'analog-input,201001',      # Current zone temperature sensor
    
    # Setpoint controls (configure based on your system type)
    'zone_setpoint': 'analog-value,1',         # Single zone setpoint (if using single setpoint)
    'heating_setpoint': 'analog-value,3',      # Heating setpoint (if using dual setpoint)
    'cooling_setpoint': 'analog-value,2',      # Cooling setpoint (if using dual setpoint)
    
    # System status indicators
    'system_mode': 'multi-state-value,2',      # System mode (heating/cooling/deadband)
    'peak_savings': 'binary-value,16',       # Peak demand savings mode
    'fan_status': 'binary-output,1105',           # Supply fan on/off status
    
    # Device information
    'device_name': 'device,{DEVICE}/object-name',  # Controller device name
}

# Dashboard Display Settings
DISPLAY_CONFIG = {
    'use_dual_setpoints': False,                # True = dual setpoint, False = single setpoint
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
        
        <div class="config-info">
            <h4>Controller Configuration:</h4>
            <strong>Server:</strong> {SERVER} | <strong>Site:</strong> {SITE} | <strong>Device:</strong> {DEVICE} | 
            <strong>Mode:</strong> {"Dual Setpoint" if DISPLAY_CONFIG['use_dual_setpoints'] else "Single Setpoint"}

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
            <h3>Temperature History</h3>
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
                        tension: 0.4,
                        fill: true
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{ y: {{ beginAtZero: false }} }}
                }}
            }});
        }}
        
        // Fetch data from our Python API
        async function fetchData() {{
            try {{
                const response = await fetch('/api/thermostat');
                const data = await response.json();
                
                if (data.error) {{
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
            
            // Add to chart
            if (data.temperature) {{
                const now = new Date().toLocaleTimeString();
                chart.data.labels.push(now);
                chart.data.datasets[0].data.push(data.temperature);
                
                // Keep only last 20 points
                if (chart.data.labels.length > 20) {{
                    chart.data.labels.shift();
                    chart.data.datasets[0].data.shift();
                }}
                
                chart.update();
            }}
        }}
        
        // Toggle auto-refresh
        function toggleAutoRefresh() {{
            autoRefresh = !autoRefresh;
            if (autoRefresh) {{
                refreshInterval = setInterval(fetchData, 5000);
                alert('Auto-refresh enabled (every 5 seconds)');
            }} else {{
                clearInterval(refreshInterval);
                alert('Auto-refresh disabled');
            }}
        }}
        
        // Initialize on page load
        window.onload = function() {{
            initChart();
            fetchData(); // Initial data fetch
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
            try:
                response = requests.get(url, headers=auth_header, timeout=10)
                if response.ok:
                    return response.json().get('value')
                else:
                    print(f"Failed to fetch {object_id}: HTTP {response.status_code}")
                    return None
            except Exception as e:
                print(f"Error fetching {object_id}: {e}")
                return None
        
        # Fetch temperature
        temp_value = fetch_object_value(OBJECTS['temperature'])
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
            'raw_values': {}
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
    print(f"Setpoint Mode: {'Dual' if DISPLAY_CONFIG['use_dual_setpoints'] else 'Single'}")
    print(f"Company: {DISPLAY_CONFIG['company_name']}")
    print("-" * 60)
    print(f"Dashboard URL: http://localhost:{PORT}")
    print(f"Debug URL: http://localhost:{PORT}/api/debug")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG_MODE)
