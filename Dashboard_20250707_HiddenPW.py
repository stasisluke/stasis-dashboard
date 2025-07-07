#!/usr/bin/env python3
"""
Integrated Web Server for Thermostat Dashboard
Serves the HTML file and provides API endpoints that work just like your existing Python code
"""

from flask import Flask, request, jsonify, send_from_directory
import requests
import base64
import os
from datetime import datetime

app = Flask(__name__)

# Configuration - update these with your settings
SERVER = "stasisenergygroup.entelicloud.com"
SITE = "Rancho Family YMCA"
DEVICE = "10500"
USER = "stasis_api"
PASSWORD = os.environ.get('PASSWORD', 'your_password_here')  # Update with your actual password

# Basic auth header (exactly like your Python code)
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
        .schedule-status {{
            display: flex;
            flex-direction: column;
            gap: 15px;
            padding: 10px 0;
        }}
        
        .occupancy-info, .peak-period-info, .tess-explanation {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px;
            border-radius: 8px;
            background: rgba(0, 0, 0, 0.03);
        }}
        
        .occupancy-info.occupied {{
            background: rgba(76, 175, 80, 0.1);
            border-left: 4px solid #4CAF50;
        }}
        
        .occupancy-info.unoccupied {{
            background: rgba(158, 158, 158, 0.1);
            border-left: 4px solid #9E9E9E;
        }}
        
        .peak-period-info.active {{
            background: rgba(255, 152, 0, 0.1);
            border-left: 4px solid #FF9800;
        }}
        
        .peak-period-info.inactive {{
            background: rgba(33, 150, 243, 0.1);
            border-left: 4px solid #2196F3;
        }}
        
        .tess-explanation {{
            background: rgba(103, 58, 183, 0.1);
            border-left: 4px solid #673AB7;
        }}
        
        .occupancy-icon, .peak-icon, .info-icon {{
            font-size: 1.2em;
            min-width: 24px;
        }}
        
        .occupancy-text, .peak-text, .explanation-text {{
            font-size: 0.95em;
            font-weight: 500;
            color: #333;
        }}
        .last-updated {{ font-size: 0.9em; color: #666; text-align: center; margin-top: 10px; }}
        .btn {{ padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 1em; background: #2196F3; color: white; margin: 5px; }}
        .btn:hover {{ background: #1976D2; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="stasis-logo">
                <img src="https://raw.githubusercontent.com/stasisluke/stasis-dashboard/main/stasis-logo.png" alt="Stasis Energy Group" onerror="this.style.display='none'">
            </div>
            <div class="header-text">
                <h1>Stasis Energy Group</h1>
                <h2 id="deviceTitle">{SITE} - Device {DEVICE}</h2>
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
            <h3>Building Schedule & Energy Status</h3>
            <div class="schedule-status" id="scheduleStatus">
                <div class="occupancy-info" id="occupancyInfo">
                    <span class="occupancy-icon">👥</span>
                    <span class="occupancy-text" id="occupancyText">Loading schedule...</span>
                </div>
                <div class="peak-period-info" id="peakPeriodInfo">
                    <span class="peak-icon">🕐</span>
                    <span class="peak-text" id="peakText">Peak Hours: 4:00 PM - 9:00 PM</span>
                </div>
                <div class="tess-explanation" id="tessExplanation">
                    <span class="info-icon">💡</span>
                    <span class="explanation-text" id="explanationText">Loading system status...</span>
                </div>
            </div>
        </div>
        
        <div class="card">
            <button class="btn" onclick="fetchData()">Refresh Data</button>
            <button class="btn" onclick="toggleAutoRefresh()">Toggle Auto-Refresh</button>
        </div>
    </div>

    <script>
        let chart;
        let autoRefresh = false;
        let refreshInterval;
        
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
                modeText.textContent = 'PEAK SAVINGS ACTIVE';
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
                modeText.textContent = 'STANDBY';
            }}
            
            // Update schedule and TESS information
            updateScheduleDisplay(data.peak_savings, data.schedule_value);
            
            // Update device title
            if (data.device_name && data.device_name !== 'Device {DEVICE}') {{
                document.getElementById('deviceTitle').textContent = `{SITE} : ${{data.device_name}}`;
            }} else {{
                document.getElementById('deviceTitle').textContent = `{SITE} : Device {DEVICE}`;
            }}
            
            document.getElementById('lastUpdated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
        }}
        
        // Update schedule display based on current time, peak savings status, and actual schedule
        function updateScheduleDisplay(isPeakSavingsActive, scheduleValue) {{
            const now = new Date();
            const currentHour = now.getHours();
            
            // Determine occupancy from SCH1 value
            // Common schedule values: "Occupied", "Unoccupied", "Holiday", etc.
            // You may need to adjust this logic based on your actual schedule values
            const isOccupied = scheduleValue === 'Occupied' || scheduleValue === 1 || scheduleValue === true;
            
            // Define peak period (4 PM - 9 PM)
            const peakStart = 16;  // 4 PM  
            const peakEnd = 21;    // 9 PM
            const isPeakPeriod = currentHour >= peakStart && currentHour < peakEnd;
            
            // Update occupancy display
            const occupancyInfo = document.getElementById('occupancyInfo');
            const occupancyText = document.getElementById('occupancyText');
            
            if (isOccupied) {{
                occupancyInfo.className = 'occupancy-info occupied';
                occupancyText.textContent = `OCCUPIED - Schedule: ${{scheduleValue || 'Active'}}`;
                document.querySelector('.occupancy-icon').textContent = '👥';
            }} else {{
                occupancyInfo.className = 'occupancy-info unoccupied';
                occupancyText.textContent = `UNOCCUPIED - Schedule: ${{scheduleValue || 'Inactive'}}`;
                document.querySelector('.occupancy-icon').textContent = '🌙';
            }}
            
            // Update peak period display
            const peakPeriodInfo = document.getElementById('peakPeriodInfo');
            const peakText = document.getElementById('peakText');
            
            if (isPeakPeriod) {{
                peakPeriodInfo.className = 'peak-period-info active';
                peakText.textContent = 'PEAK HOURS ACTIVE: 4:00 PM - 9:00 PM';
            }} else {{
                peakPeriodInfo.className = 'peak-period-info inactive';
                peakText.textContent = 'Peak Hours: 4:00 PM - 9:00 PM';
            }}
            
            // Update TESS explanation based on current state
            const explanationText = document.getElementById('explanationText');
            
            if (isPeakPeriod && isOccupied) {{
                explanationText.textContent = 'Comfort maintained using stored thermal energy - reducing demand charges during business hours';
            }} else if (isPeakPeriod && !isOccupied) {{
                explanationText.textContent = 'Building unoccupied - maximum peak demand savings from thermal storage';
            }} else if (!isPeakPeriod && isOccupied) {{
                explanationText.textContent = 'Building occupied - thermal mass storing energy for this afternoon\\'s peak period';
            }} else {{
                explanationText.textContent = 'Thermal mass charging naturally with off-peak energy for tomorrow\\'s savings';
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
    API endpoint that mimics your Python code functionality
    Returns current thermostat data from EnteliWeb
    """
    try:
        data = {}
        
        # Fetch temperature (AI201001 - IP_ZONE_Temperature)
        temp_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/analog-input,201001/present-value?alt=json"
        response = requests.get(temp_url, headers=auth_header, timeout=10)
        if response.ok:
            temp_data = response.json()
            data['temperature'] = float(temp_data.get('value', 0))
        
        # Fetch zone setpoint (AV1 - CTRL_ActiveZoneSetpoint)
        setpoint_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/analog-value,1/present-value?alt=json"
        response = requests.get(setpoint_url, headers=auth_header, timeout=10)
        if response.ok:
            setpoint_data = response.json()
            data['setpoint'] = float(setpoint_data.get('value', 0))
        
        # Fetch system mode (MV2 - multi-state-value,2)
        mode_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/multi-state-value,2/present-value?alt=json"
        response = requests.get(mode_url, headers=auth_header, timeout=10)
        if response.ok:
            mode_data = response.json()
            mode_value = mode_data.get('value', '3')
            
            # Debug print
            print(f"DEBUG: mode_value = {mode_value}, type = {type(mode_value)}")
            
            # Convert string to integer
            try:
                mode_number = int(mode_value)
                print(f"DEBUG: mode_number = {mode_number}")
            except:
                mode_number = 3
                print(f"DEBUG: Failed to convert, using default 3")
            
            # Map numeric values to text
            mode_map = {
                1: 'Heating',
                2: 'Cooling', 
                3: 'Deadband'
            }
            
            mode_text = mode_map.get(mode_number, 'Deadband')
            print(f"DEBUG: mode_text = {mode_text}")
            data['system_mode'] = mode_text
            
            # Set heating and cooling based on mode
            data['heating'] = mode_number == 1
            data['cooling'] = mode_number == 2
        else:
            print(f"DEBUG: Failed to get MV2 data")
            data['system_mode'] = 'Error'
        
        # Fetch peak savings mode status (BV2025)
        peak_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/binary-value,2025/present-value?alt=json"
        response = requests.get(peak_url, headers=auth_header, timeout=10)
        if response.ok:
            peak_data = response.json()
            peak_value = peak_data.get('value')
            data['peak_savings'] = peak_value == 'active' or peak_value == 'Active' or peak_value == 'On' or peak_value == True or peak_value == 1
        fan_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/binary-output,1/present-value?alt=json"
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

@app.route('/api/debug')
def debug_values():
    """Debug endpoint to see raw values from BACnet objects"""
    try:
        debug_data = {}
        
        # Debug MV2 - get both present-value and state-text
        mv2_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/multi-state-value,2/present-value?alt=json"
        response = requests.get(mv2_url, headers=auth_header, timeout=10)
        if response.ok:
            debug_data['mv2_present_value'] = response.json()
        
        # Try to get state text for MV2
        mv2_text_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/multi-state-value,2/state-text?alt=json"
        response = requests.get(mv2_text_url, headers=auth_header, timeout=10)
        if response.ok:
            debug_data['mv2_state_text'] = response.json()
        
        # Debug BO1 - fan status
        fan_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/binary-output,1/present-value?alt=json"
        response = requests.get(fan_url, headers=auth_header, timeout=10)
        if response.ok:
            debug_data['bo1_present_value'] = response.json()
        
        # Debug SCH1 - building schedule
        schedule_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/schedule,1/present-value?alt=json"
        response = requests.get(schedule_url, headers=auth_header, timeout=10)
        if response.ok:
            debug_data['sch1_present_value'] = response.json()
        
        return jsonify(debug_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print(f"Starting Thermostat Dashboard Server...")
    print(f"EnteliWeb Server: {SERVER}")
    print(f"Site: {SITE}")
    print(f"Device: {DEVICE}")
    print(f"Dashboard URL: http://localhost:8000")
    print(f"API Test: http://localhost:8000/api/thermostat")
    print("\nMake sure to update the PASSWORD variable with your actual password!")
    
    app.run(host='0.0.0.0', port=8000, debug=True)
