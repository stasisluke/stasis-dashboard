#!/usr/bin/env python3
"""
Ecobee-Inspired Thermostat Dashboard with AV1 Setpoint Control and Thermostat Lockout
Serves the HTML file and provides API endpoints for thermostat data and setpoint control
"""

import sys
from flask import Flask, request, jsonify
import requests
import base64
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# Force stdout to flush immediately
sys.stdout.reconfigure(line_buffering=True)

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
SETPOINT_AV = 1                  # Analog Value for active zone setpoint (THIS IS WHAT WE CONTROL)
SETPOINT_MAX_AV = 10             # Analog Value for maximum setpoint limit
SETPOINT_MIN_AV = 11             # Analog Value for minimum setpoint limit
SYSTEM_MODE_MV = 2               # Multi-state Value for system mode (heating/cooling/deadband)
PEAK_SAVINGS_BV = 2025           # Binary Value for peak savings mode status
FAN_STATUS_BO = 1                # Binary Output for fan status
TEMP_TREND_LOG_INSTANCE = 27     # Trend Log instance for temperature history

# ========================================
# END CONFIGURATION SECTION
# ========================================

# Basic auth header
auth_header = {
    "Authorization": f"Basic {base64.b64encode(f'{USER}:{PASSWORD}'.encode()).decode()}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

@app.route('/')
def index():
    """Serve the main dashboard HTML with setpoint controls and thermostat lockout"""
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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f5f5;
            min-height: 100vh; 
            color: #333;
        }}
        .container {{ 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px;
        }}
        .header {{ 
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            display: flex;
            align-items: center;
            justify-content: space-between;
            min-height: 100px;
        }}
        .header-left {{
            display: flex;
            align-items: center;
            gap: 20px;
        }}
        .stasis-logo {{
            width: 160px;
            height: 80px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .stasis-logo img {{
            max-width: 160px;
            max-height: 80px;
            object-fit: contain;
        }}
        .header-text {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .header-text h1 {{ 
            font-size: 2.2em; 
            font-weight: 300;
            color: #2c3e50;
            margin: 0;
        }}
        .header-text h2 {{ 
            font-size: 1.2em; 
            font-weight: 400;
            color: #7f8c8d;
            margin: 0;
        }}
        .powered-by {{
            font-size: 0.9em;
            color: #95a5a6;
            font-weight: 300;
        }}
        .card {{
            background: white;
            border-radius: 12px;
            padding: 32px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 24px;
            border: 1px solid #e8e8e8;
        }}
        .card h3 {{
            font-size: 1.3em;
            font-weight: 500;
            color: #2c3e50;
            margin-bottom: 24px;
            text-align: center;
        }}
        .temperature-display {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 40px;
            margin: 32px 0;
        }}
        .temperature-circle {{
            position: relative;
            width: 280px;
            height: 280px;
            border-radius: 50%;
            background: #fafafa;
            border: 3px solid #e8e8e8;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            transition: all 0.3s ease;
        }}
        .temperature-circle.cooling {{
            border-color: #3498db;
            background: #f8fcff;
        }}
        .temperature-circle.heating {{
            border-color: #e67e22;
            background: #fffaf8;
        }}
        .temperature-circle.peak-savings {{
            border-color: #27ae60;
            background: #f8fff8;
            animation: pulse-savings 3s infinite;
        }}
        .temperature-circle.deadband {{
            border-color: #bdc3c7;
            background: #fafafa;
        }}
        @keyframes pulse-savings {{
            0% {{ box-shadow: 0 0 0 0 rgba(39, 174, 96, 0.3); }}
            50% {{ box-shadow: 0 0 0 8px rgba(39, 174, 96, 0.1); }}
            100% {{ box-shadow: 0 0 0 0 rgba(39, 174, 96, 0.3); }}
        }}
        .temperature-value {{
            font-size: 4.5em;
            font-weight: 200;
            color: #2c3e50;
            line-height: 1;
            margin-bottom: 8px;
        }}
        .temperature-unit {{
            font-size: 1.4em;
            color: #95a5a6;
            font-weight: 300;
            margin-top: -20px;
        }}
        .status-panel {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 16px;
            min-width: 200px;
        }}
        .setpoint-display {{
            text-align: center;
            padding: 16px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e9ecef;
            width: 100%;
        }}
        .setpoint-label {{
            font-size: 0.9em;
            color: #6c757d;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .setpoint-value {{
            font-size: 1.8em;
            font-weight: 500;
            color: #2c3e50;
        }}
        
        /* Setpoint Control Styles */
        .setpoint-controls {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-top: 16px;
            padding: 16px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e9ecef;
        }}
        .setpoint-btn {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 2px solid #3498db;
            background: white;
            color: #3498db;
            font-size: 1.5em;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            user-select: none;
        }}
        .setpoint-btn:hover {{
            background: #3498db;
            color: white;
            transform: scale(1.05);
        }}
        .setpoint-btn:active {{
            transform: scale(0.95);
        }}
        .setpoint-btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }}
        .setpoint-input-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
        }}
        .setpoint-input {{
            width: 80px;
            text-align: center;
            font-size: 1.2em;
            font-weight: 500;
            padding: 8px;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            background: white;
        }}
        .setpoint-input:focus {{
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
        }}
        .setpoint-set-btn {{
            padding: 6px 12px;
            border: 1px solid #27ae60;
            background: #27ae60;
            color: white;
            border-radius: 4px;
            font-size: 0.8em;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .setpoint-set-btn:hover {{
            background: #229954;
        }}
        
        /* Thermostat Lockout Styles */
        .lockout-controls {{
            display: flex;
            justify-content: center;
            margin-top: 16px;
            padding: 16px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e9ecef;
        }}
        .lockout-toggle {{
            display: flex;
            align-items: center;
            gap: 12px;
            cursor: pointer;
            padding: 12px 16px;
            border-radius: 6px;
            transition: all 0.2s ease;
            user-select: none;
            width: 100%;
        }}
        .lockout-toggle:hover {{
            background: rgba(52, 152, 219, 0.1);
        }}
        .lockout-toggle input[type="checkbox"] {{
            width: 20px;
            height: 20px;
            cursor: pointer;
            flex-shrink: 0;
        }}
        .lockout-label {{
            display: flex;
            flex-direction: column;
            gap: 2px;
            cursor: pointer;
            flex: 1;
        }}
        .lockout-text {{
            font-size: 1em;
            font-weight: 500;
            color: #2c3e50;
        }}
        .lockout-description {{
            font-size: 0.8em;
            color: #7f8c8d;
            font-style: italic;
        }}
        .lockout-toggle.active {{
            background: rgba(231, 76, 60, 0.1);
            border: 1px solid rgba(231, 76, 60, 0.3);
            border-radius: 6px;
        }}
        .lockout-toggle.active .lockout-text {{
            color: #e74c3c;
        }}
        .lockout-toggle.active .lockout-description {{
            color: #c0392b;
        }}
        
        .mode-display {{
            text-align: center;
            padding: 12px 24px;
            border-radius: 24px;
            font-size: 1em;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            min-width: 120px;
        }}
        .mode-display.cooling {{ 
            background: #e8f4ff;
            color: #2980b9;
            border: 1px solid #bde0ff;
        }}
        .mode-display.heating {{ 
            background: #fff4e8;
            color: #d35400;
            border: 1px solid #ffd6b3;
        }}
        .mode-display.peak-savings {{ 
            background: #e8f8f5;
            color: #229954;
            border: 1px solid #a9dfbf;
        }}
        .mode-display.deadband {{ 
            background: #f8f9fa;
            color: #6c757d;
            border: 1px solid #dee2e6;
        }}
        .chart-container {{ 
            position: relative; 
            height: 320px; 
            margin-top: 24px;
        }}
        .chart-controls {{
            display: flex;
            justify-content: center;
            gap: 8px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }}
        .time-range-btn {{
            padding: 10px 20px;
            border: 1px solid #bdc3c7;
            background: white;
            color: #5a6c7d;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            font-weight: 500;
            transition: all 0.2s ease;
            letter-spacing: 0.3px;
        }}
        .time-range-btn:hover {{
            background: #ecf0f1;
            border-color: #95a5a6;
        }}
        .time-range-btn.active {{
            background: #3498db;
            color: white;
            border-color: #3498db;
        }}
        .last-updated {{ 
            font-size: 0.85em; 
            color: #7f8c8d; 
            text-align: center; 
            margin-top: 16px;
            font-weight: 400;
        }}
        .control-buttons {{
            display: flex;
            justify-content: center;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .btn {{ 
            padding: 12px 24px;
            border: 1px solid #3498db;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.95em;
            font-weight: 500;
            background: white;
            color: #3498db;
            transition: all 0.2s ease;
            letter-spacing: 0.3px;
        }}
        .btn:hover {{ 
            background: #3498db;
            color: white;
        }}
        .btn.primary {{
            background: #3498db;
            color: white;
        }}
        .btn.primary:hover {{
            background: #2980b9;
        }}
        .loading {{ 
            text-align: center; 
            color: #7f8c8d; 
            font-style: italic;
            font-size: 0.9em;
        }}
        .error {{ 
            color: #e74c3c; 
            text-align: center;
            font-size: 0.9em;
        }}
        .success {{
            color: #27ae60;
            text-align: center;
            font-size: 0.9em;
        }}
        
        /* Status message styles */
        .status-message {{
            padding: 12px;
            border-radius: 6px;
            margin: 12px 0;
            text-align: center;
            font-weight: 500;
            display: none;
        }}
        .status-message.success {{
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
            display: block;
        }}
        .status-message.error {{
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
            display: block;
        }}
        
        /* Responsive design */
        @media (max-width: 768px) {{
            .header {{
                flex-direction: column;
                gap: 16px;
                text-align: center;
            }}
            .header-left {{
                flex-direction: column;
                gap: 12px;
            }}
            .temperature-display {{
                flex-direction: column;
                gap: 24px;
            }}
            .temperature-circle {{
                width: 240px;
                height: 240px;
            }}
            .temperature-value {{
                font-size: 3.5em;
            }}
            .setpoint-controls {{
                flex-direction: column;
                gap: 16px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-left">
                <div class="stasis-logo">
                    <img src="https://raw.githubusercontent.com/stasisluke/stasis-dashboard/main/stasis-logo.png" alt="Stasis Energy Group" onerror="this.style.display='none'">
                </div>
                <div class="header-text">
                    <h1>{DISPLAY_SITE_NAME}</h1>
                    <h2 id="deviceTitle">{DISPLAY_DEVICE_NAME if DISPLAY_DEVICE_NAME else 'Device ' + DEVICE}</h2>
                    <p class="powered-by">Thermal Energy Storage Dashboard</p>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h3>Current Temperature & Controls</h3>
            <div class="temperature-display">
                <div class="temperature-circle" id="tempCircle">
                    <div class="temperature-value" id="currentTemp">--</div>
                    <div class="temperature-unit">°F</div>
                </div>
                <div class="status-panel">
                    <div class="setpoint-display">
                        <div class="setpoint-label">Target Temperature</div>
                        <div class="setpoint-value" id="setpointValue">--°F</div>
                    </div>
                    
                    <!-- Setpoint Controls -->
                    <div class="setpoint-controls">
                        <button class="setpoint-btn" onclick="adjustSetpoint(-1)" title="Decrease by 1°F">−</button>
                        <div class="setpoint-input-container">
                            <input type="number" class="setpoint-input" id="setpointInput" step="0.5" onkeypress="handleSetpointKeypress(event)">
                            <button class="setpoint-set-btn" onclick="setCustomSetpoint()">Set</button>
                        </div>
                        <button class="setpoint-btn" onclick="adjustSetpoint(1)" title="Increase by 1°F">+</button>
                    </div>
                    
                    <!-- Thermostat Lockout Toggle -->
                    <div class="lockout-controls">
                        <div class="lockout-toggle">
                            <input type="checkbox" id="lockoutCheckbox" onchange="toggleThermostatLockout()">
                            <label for="lockoutCheckbox" class="lockout-label">
                                <span class="lockout-text">Thermostat Lockout</span>
                                <span class="lockout-description">ON: Blocks thermostat | OFF: Allows temporary overrides</span>
                            </label>
                        </div>
                    </div>
                    
                    <div class="mode-display" id="modeDisplay">Standby</div>
                </div>
            </div>
            
            <!-- Status message area -->
            <div id="statusMessage" class="status-message"></div>
            
            <div class="last-updated" id="lastUpdated">Never updated</div>
        </div>
        
        <div class="card">
            <h3>Temperature History</h3>
            <div class="chart-controls">
                <button class="time-range-btn active" onclick="loadTrendData('1h')">Last Hour</button>
                <button class="time-range-btn" onclick="loadTrendData('4h')">Last 4 Hours</button>
                <button class="time-range-btn" onclick="loadTrendData('12h')">Last 12 Hours</button>
                <button class="time-range-btn" onclick="loadTrendData('24h')">Last 24 Hours</button>
            </div>
            <div class="chart-container">
                <canvas id="temperatureChart"></canvas>
            </div>
            <div id="chartStatus" class="loading">Loading chart data...</div>
        </div>
        
        <div class="card">
            <div class="control-buttons">
                <button class="btn primary" onclick="fetchData()">Refresh Data</button>
                <button class="btn" onclick="toggleAutoRefresh()">Toggle Auto-Refresh</button>
                <button class="btn" onclick="refreshChart()">Refresh Chart</button>
            </div>
        </div>
    </div>

    <script>
        let chart;
        let autoRefresh = false;
        let refreshInterval;
        let currentTimeRange = '1h';
        let currentSetpoint = null;
        let setpointLimits = {{ min: 60, max: 85 }}; // Default limits, will be updated from AV10/AV11
        let thermostatLockout = false; // Track lockout state
        
        // Initialize chart with Ecobee-inspired styling
        function initChart() {{
            const ctx = document.getElementById('temperatureChart').getContext('2d');
            chart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: [],
                    datasets: [{{
                        label: 'Temperature (°F)',
                        data: [],
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.08)',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 1,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#3498db',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        intersect: false,
                        mode: 'index'
                    }},
                    plugins: {{
                        legend: {{
                            display: false
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(44, 62, 80, 0.95)',
                            titleColor: '#ffffff',
                            bodyColor: '#ffffff',
                            borderColor: '#bdc3c7',
                            borderWidth: 1,
                            cornerRadius: 8,
                            callbacks: {{
                                label: function(context) {{
                                    return `Temperature: ${{context.parsed.y.toFixed(1)}}°F`;
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            display: true,
                            grid: {{
                                color: '#ecf0f1',
                                borderColor: '#bdc3c7'
                            }},
                            ticks: {{
                                color: '#7f8c8d',
                                font: {{
                                    size: 11
                                }}
                            }}
                        }},
                        y: {{
                            display: true,
                            grid: {{
                                color: '#ecf0f1',
                                borderColor: '#bdc3c7'
                            }},
                            ticks: {{
                                color: '#7f8c8d',
                                font: {{
                                    size: 11
                                }},
                                callback: function(value) {{
                                    return value + '°F';
                                }}
                            }},
                            beginAtZero: false
                        }}
                    }}
                }}
            }});
        }}
        
        // Setpoint control functions
        function adjustSetpoint(change) {{
            if (currentSetpoint === null) {{
                showStatusMessage('Current setpoint not available', 'error');
                return;
            }}
            
            const newSetpoint = currentSetpoint + change;
            if (newSetpoint < setpointLimits.min || newSetpoint > setpointLimits.max) {{
                showStatusMessage(`Setpoint must be between ${{setpointLimits.min}}°F and ${{setpointLimits.max}}°F`, 'error');
                return;
            }}
            
            updateSetpoint(newSetpoint);
        }}
        
        function setCustomSetpoint() {{
            const input = document.getElementById('setpointInput');
            const newSetpoint = parseFloat(input.value);
            
            if (isNaN(newSetpoint)) {{
                showStatusMessage('Please enter a valid temperature', 'error');
                return;
            }}
            
            if (newSetpoint < setpointLimits.min || newSetpoint > setpointLimits.max) {{
                showStatusMessage(`Setpoint must be between ${{setpointLimits.min}}°F and ${{setpointLimits.max}}°F`, 'error');
                return;
            }}
            
            updateSetpoint(newSetpoint);
        }}
        
        function handleSetpointKeypress(event) {{
            if (event.key === 'Enter') {{
                setCustomSetpoint();
            }}
        }}
        
        async function updateSetpoint(newSetpoint) {{
            try {{
                // Disable controls during update
                document.querySelectorAll('.setpoint-btn, .setpoint-set-btn').forEach(btn => {{
                    btn.disabled = true;
                }});
                
                // IMMEDIATELY update the display optimistically
                document.getElementById('setpointValue').textContent = newSetpoint.toFixed(1) + '°F';
                document.getElementById('setpointInput').value = newSetpoint.toFixed(1);
                currentSetpoint = newSetpoint;
                
                showStatusMessage(`Setting temperature to ${{newSetpoint}}°F...`, 'success');
                
                console.log('Sending setpoint request:', {{ setpoint: newSetpoint, lockout: thermostatLockout }});
                
                const response = await fetch('/api/setpoint', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{ 
                        setpoint: newSetpoint,
                        lockout: thermostatLockout 
                    }})
                }});
                
                console.log('Response status:', response.status);
                
                if (!response.ok) {{
                    // If failed, revert the optimistic update
                    fetchData();
                    throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                }}
                
                const result = await response.json();
                console.log('Response data:', result);
                
                if (result && result.success === true) {{
                    const message = result.message || `Temperature set to ${{newSetpoint}}°F successfully!`;
                    showStatusMessage(message, 'success');
                    console.log('Success! Refreshing data in 500ms for confirmation...');
                    
                    // Quick refresh to confirm the change took effect
                    setTimeout(() => {{
                        console.log('Confirming setpoint change...');
                        fetchData();
                    }}, 500); // Reduced from 1000ms to 500ms
                }} else {{
                    // If failed, revert the optimistic update
                    fetchData();
                    const errorMsg = result?.error || 'Unknown error occurred';
                    showStatusMessage(`Error: ${{errorMsg}}`, 'error');
                    console.error('Setpoint error:', result);
                }}
                
            }} catch (error) {{
                // If failed, revert the optimistic update
                fetchData();
                console.error('Network error:', error);
                showStatusMessage(`Network Error: ${{error.message}}`, 'error');
            }} finally {{
                // Re-enable controls
                console.log('Re-enabling controls...');
                document.querySelectorAll('.setpoint-btn, .setpoint-set-btn').forEach(btn => {{
                    btn.disabled = false;
                }});
            }}
        }}
        
        // Thermostat Lockout Functions
        function toggleThermostatLockout() {{
            const checkbox = document.getElementById('lockoutCheckbox');
            
            // Get the current state from the checkbox itself
            thermostatLockout = checkbox.checked;
            
            console.log(`Thermostat lockout toggled to: ${{thermostatLockout}}`);
            
            // Update visual display
            updateLockoutDisplay();
            
            if (thermostatLockout) {{
                showStatusMessage('Thermostat LOCKED - Local changes blocked completely', 'success');
            }} else {{
                showStatusMessage('Thermostat UNLOCKED - Can temporarily override (until next admin change)', 'success');
            }}
        }}
        
        function updateLockoutDisplay() {{
            const checkbox = document.getElementById('lockoutCheckbox');
            const toggle = document.querySelector('.lockout-toggle');
            
            // Don't force checkbox state - let it follow user clicks
            // checkbox.checked = thermostatLockout; // Remove this line
            
            if (thermostatLockout) {{
                toggle.classList.add('active');
            }} else {{
                toggle.classList.remove('active');
            }}
        }}
        
        function showStatusMessage(message, type) {{
            console.log(`Showing status message: "${{message}}" (type: ${{type}})`);
            const statusDiv = document.getElementById('statusMessage');
            statusDiv.textContent = message;
            statusDiv.className = `status-message ${{type}}`;
            statusDiv.style.display = 'block'; // Make sure it's visible
            
            // Auto-hide success messages after 5 seconds (increased from 3)
            if (type === 'success') {{
                setTimeout(() => {{
                    console.log('Auto-hiding success message');
                    statusDiv.style.display = 'none';
                }}, 5000);
            }}
        }}
        
        // Fetch current thermostat data
        async function fetchData() {{
            try {{
                const response = await fetch('/api/thermostat');
                const data = await response.json();
                
                if (data.error) {{
                    showStatusMessage('Error: ' + data.error, 'error');
                    return;
                }}
                
                updateCurrentDisplay(data);
            }} catch (error) {{
                console.error('Error fetching data:', error);
                showStatusMessage('Failed to fetch data: ' + error.message, 'error');
            }}
        }}
        
        function updateCurrentDisplay(data) {{
            // Update temperature circle
            const tempValue = data.temperature ? data.temperature.toFixed(1) : '--';
            const setpointValue = data.setpoint ? data.setpoint.toFixed(1) : '--';
            
            document.getElementById('currentTemp').textContent = tempValue;
            document.getElementById('setpointValue').textContent = setpointValue + '°F';
            
            // Update current setpoint for controls
            currentSetpoint = data.setpoint;
            
            // Update setpoint limits from AV10/AV11
            if (data.setpoint_limits) {{
                setpointLimits = data.setpoint_limits;
                
                // Update input field constraints
                const input = document.getElementById('setpointInput');
                input.min = setpointLimits.min;
                input.max = setpointLimits.max;
            }}
            
            // Update the input field with current setpoint
            if (data.setpoint) {{
                document.getElementById('setpointInput').value = data.setpoint.toFixed(1);
            }}
            
            // Determine mode and styling
            const circle = document.getElementById('tempCircle');
            const modeDisplay = document.getElementById('modeDisplay');
            
            // Clear all mode classes
            circle.className = 'temperature-circle';
            modeDisplay.className = 'mode-display';
            
            if (data.peak_savings) {{
                circle.classList.add('peak-savings');
                modeDisplay.classList.add('peak-savings');
                modeDisplay.textContent = 'Peak Savings';
            }} else if (data.system_mode === 'Cooling') {{
                circle.classList.add('cooling');
                modeDisplay.classList.add('cooling');
                modeDisplay.textContent = 'Cooling';
            }} else if (data.system_mode === 'Heating') {{
                circle.classList.add('heating');
                modeDisplay.classList.add('heating');
                modeDisplay.textContent = 'Heating';
            }} else {{
                circle.classList.add('deadband');
                modeDisplay.classList.add('deadband');
                modeDisplay.textContent = 'Standby';
            }}
            
            // Update device title
            if ('{DISPLAY_DEVICE_NAME}') {{
                document.getElementById('deviceTitle').textContent = '{DISPLAY_DEVICE_NAME}';
            }} else if (data.device_name && data.device_name !== 'Device {DEVICE}') {{
                document.getElementById('deviceTitle').textContent = data.device_name;
            }} else {{
                document.getElementById('deviceTitle').textContent = `Device {DEVICE}`;
            }}
            
            document.getElementById('lastUpdated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
        }}
        
        // Load trend data for chart
        async function loadTrendData(timeRange) {{
            try {{
                document.getElementById('chartStatus').textContent = 'Loading trend data...';
                document.getElementById('chartStatus').className = 'loading';
                
                // Update active button
                document.querySelectorAll('.time-range-btn').forEach(btn => {{
                    btn.classList.remove('active');
                }});
                
                const buttonMap = {{
                    '1h': 'Last Hour',
                    '4h': 'Last 4 Hours', 
                    '12h': 'Last 12 Hours',
                    '24h': 'Last 24 Hours'
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
                document.getElementById('chartStatus').textContent = `Loaded ${{data.records.length}} data points`;
                document.getElementById('chartStatus').className = 'success';
                
            }} catch (error) {{
                console.error('Error fetching trend data:', error);
                document.getElementById('chartStatus').textContent = 'Failed to load trend data: ' + error.message;
                document.getElementById('chartStatus').className = 'error';
            }}
        }}
        
        // Update chart with trend data
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
        
        // Refresh chart with current time range
        function refreshChart() {{
            loadTrendData(currentTimeRange);
        }}
        
        // Toggle auto-refresh for current data
        function toggleAutoRefresh() {{
            autoRefresh = !autoRefresh;
            const btn = event.target;
            if (autoRefresh) {{
                refreshInterval = setInterval(fetchData, 5000);
                btn.textContent = 'Stop Auto-Refresh';
                btn.classList.add('primary');
            }} else {{
                clearInterval(refreshInterval);
                btn.textContent = 'Toggle Auto-Refresh';
                btn.classList.remove('primary');
            }}
        }}
        
        // Initialize on page load
        window.onload = function() {{
            initChart();
            fetchData();
            loadTrendData('1h');
        }};
    </script>
</body>
</html>'''

@app.route('/api/thermostat')
def get_thermostat_data():
    """API endpoint for current thermostat data"""
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
        
        # Fetch setpoint limits from AV10 (max) and AV11 (min)
        setpoint_limits = {}
        
        # Fetch maximum setpoint limit (AV10)
        max_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/analog-value,{SETPOINT_MAX_AV}/present-value?alt=json"
        response = requests.get(max_url, headers=auth_header, timeout=10)
        if response.ok:
            max_data = response.json()
            setpoint_limits['max'] = float(max_data.get('value', 85))  # Default to 85 if not available
        else:
            setpoint_limits['max'] = 85
        
        # Fetch minimum setpoint limit (AV11)
        min_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/analog-value,{SETPOINT_MIN_AV}/present-value?alt=json"
        response = requests.get(min_url, headers=auth_header, timeout=10)
        if response.ok:
            min_data = response.json()
            setpoint_limits['min'] = float(min_data.get('value', 60))  # Default to 60 if not available
        else:
            setpoint_limits['min'] = 60
        
        data['setpoint_limits'] = setpoint_limits
        
        # Fetch system mode
        mode_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/multi-state-value,{SYSTEM_MODE_MV}/present-value?alt=json"
        response = requests.get(mode_url, headers=auth_header, timeout=10)
        if response.ok:
            mode_data = response.json()
            mode_value = mode_data.get('value', '3')
            
            try:
                mode_number = int(mode_value)
            except:
                mode_number = 3
            
            mode_map = {
                1: 'Heating',
                2: 'Cooling', 
                3: 'Deadband'
            }
            
            data['system_mode'] = mode_map.get(mode_number, 'Deadband')
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
            data['peak_savings'] = peak_value in ['active', 'Active', 'On', True, 1]
        
        # Fetch fan status
        fan_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/binary-output,{FAN_STATUS_BO}/present-value?alt=json"
        response = requests.get(fan_url, headers=auth_header, timeout=10)
        if response.ok:
            fan_data = response.json()
            fan_value = fan_data.get('value')
            data['fan'] = fan_value in ['active', 'Active', 'On', True, 1]
        
        # Fetch device name
        device_name_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/device,{DEVICE}/object-name?alt=json"
        response = requests.get(device_name_url, headers=auth_header, timeout=10)
        if response.ok:
            device_name_data = response.json()
            data['device_name'] = device_name_data.get('value', f'Device {DEVICE}')
        else:
            data['device_name'] = f'Device {DEVICE}'
            
        return jsonify(data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/setpoint', methods=['POST'])
def set_setpoint():
    """API endpoint to write new setpoint to AV1"""
    print(f"\n=== SETPOINT REQUEST START ===", flush=True)
    app.logger.info("=== SETPOINT REQUEST START ===")
    
    try:
        # Get the new setpoint from request
        request_data = request.get_json()
        print(f"Request data received: {request_data}", flush=True)
        app.logger.info(f"Request data: {request_data}")
        
        if not request_data or 'setpoint' not in request_data:
            error_msg = "Missing setpoint value in request"
            print(f"ERROR: {error_msg}", flush=True)
            app.logger.error(error_msg)
            return jsonify({'success': False, 'error': 'Missing setpoint value'}), 400
        
        new_setpoint = float(request_data['setpoint'])
        print(f"New setpoint: {new_setpoint}", flush=True)
        app.logger.info(f"New setpoint: {new_setpoint}")
        
        # Validate setpoint range
        if new_setpoint < 60 or new_setpoint > 85:
            error_msg = f"Setpoint {new_setpoint} out of range"
            print(f"ERROR: {error_msg}", flush=True)
            app.logger.error(error_msg)
            return jsonify({
                'success': False, 
                'error': f'Setpoint must be between 60°F and 85°F'
            }), 400
        
        # Prepare the request body
        request_body = {
            "$base": "Real",
            "value": str(new_setpoint)
        }
        print(f"Request body: {request_body}", flush=True)
        app.logger.info(f"Body: {request_body}")
        
        # Build the setpoint URL based on lockout mode
        lockout_mode = request_data.get('lockout', False)
        
        if lockout_mode:
            # Priority 8 = Manual Operator (blocks thermostat completely)
            priority = 8
            setpoint_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/analog-value,{SETPOINT_AV}/present-value?priority={priority}&alt=json"
            print(f"LOCKOUT MODE: Using priority {priority} - thermostat blocked", flush=True)
            app.logger.info(f"Lockout mode: priority {priority} - thermostat blocked")
        else:
            # Priority 8 for the command, but we'll also clear Priority 10 to allow thermostat temporary control
            priority = 8
            setpoint_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/analog-value,{SETPOINT_AV}/present-value?priority={priority}&alt=json"
            print(f"NORMAL MODE: Using priority {priority} - will clear thermostat priority to allow temporary overrides", flush=True)
            app.logger.info(f"Normal mode: priority {priority} - allowing thermostat temporary control")
        
        print(f"Setpoint URL: {setpoint_url}", flush=True)
        app.logger.info(f"URL: {setpoint_url}")
        
        # Make the PUT request to set our command
        print("Making PUT request to BACnet API...", flush=True)
        app.logger.info("Making PUT request to BACnet API...")
        
        response = requests.put(
            setpoint_url, 
            headers=auth_header, 
            json=request_body, 
            timeout=15
        )
        
        print(f"PUT response status: {response.status_code}", flush=True)
        print(f"PUT response text: {response.text}", flush=True)
        app.logger.info(f"PUT response: {response.status_code} - {response.text}")
        
        # If normal mode (lockout OFF), also clear Priority 10 to allow thermostat temporary control
        if not lockout_mode and response.ok:
            print("NORMAL MODE: Clearing thermostat priority 10 to allow temporary overrides...", flush=True)
            app.logger.info("Clearing thermostat priority 10 for temporary control")
            
            # Clear Priority 10 (thermostat) by sending NULL
            clear_url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/analog-value,{SETPOINT_AV}/present-value?priority=10&alt=json"
            clear_body = {"$base": "Null", "value": ""}
            
            clear_response = requests.put(
                clear_url,
                headers=auth_header,
                json=clear_body,
                timeout=15
            )
            
            print(f"Clear priority 10 response: {clear_response.status_code} - {clear_response.text}", flush=True)
            app.logger.info(f"Clear priority 10 response: {clear_response.status_code} - {clear_response.text}")
        
        if response.ok:
            try:
                response_data = response.json()
                print(f"PUT response JSON: {response_data}", flush=True)
                app.logger.info(f"Response JSON: {response_data}")
                
                # Check BACnet response
                error_code = response_data.get('error', '0')
                error_text = response_data.get('errorText', 'Unknown')
                
                print(f"BACnet error code: {error_code}, text: {error_text}", flush=True)
                app.logger.info(f"BACnet error: {error_code} - {error_text}")
                
                if error_code == '-1' or error_text == 'OK':
                    lockout_status = "LOCKED" if lockout_mode else "UNLOCKED"
                    mode_description = "Thermostat blocked" if lockout_mode else "Thermostat can temporarily override"
                    
                    result = {
                        'success': True, 
                        'setpoint': new_setpoint,
                        'priority': priority,
                        'lockout': lockout_mode,
                        'message': f'Admin setpoint: {new_setpoint}°F ({lockout_status} - {mode_description})'
                    }
                    print(f"SUCCESS: Returning {result}", flush=True)
                    app.logger.info(f"SUCCESS: {result}")
                    return jsonify(result)
                else:
                    result = {
                        'success': False, 
                        'error': f'BACnet error: {error_text} (code: {error_code})'
                    }
                    print(f"BACNET ERROR: Returning {result}", flush=True)
                    app.logger.warning(f"BACnet error: {result}")
                    return jsonify(result), 400
                    
            except Exception as json_error:
                result = {
                    'success': False, 
                    'error': f'Could not parse response: {str(json_error)}'
                }
                print(f"JSON PARSE ERROR: {json_error}", flush=True)
                app.logger.error(f"JSON parse error: {json_error}")
                return jsonify(result), 500
        else:
            result = {
                'success': False, 
                'error': f'HTTP {response.status_code}: {response.text}'
            }
            print(f"HTTP ERROR: Returning {result}", flush=True)
            app.logger.error(f"HTTP error: {result}")
            return jsonify(result), response.status_code
            
    except Exception as e:
        result = {
            'success': False, 
            'error': f'Server error: {str(e)}'
        }
        print(f"EXCEPTION: {e}", flush=True)
        app.logger.error(f"Exception: {e}")
        import traceback
        print(f"Full traceback:", flush=True)
        traceback.print_exc()
        return jsonify(result), 500
    
    finally:
        print("=== SETPOINT REQUEST END ===\n", flush=True)
        app.logger.info("=== SETPOINT REQUEST END ===")

@app.route('/api/trends')
def get_trend_data():
    """API endpoint for trend log data"""
    try:
        time_range = request.args.get('range', '1h')
        
        # Set time ranges and max results
        now = datetime.now(timezone.utc)
        if time_range == '1h':
            start_time = now - timedelta(hours=1)
            max_results = 60
        elif time_range == '4h':
            start_time = now - timedelta(hours=4)
            max_results = 120
        elif time_range == '12h':
            start_time = now - timedelta(hours=12)
            max_results = 300
        elif time_range == '24h':
            start_time = now - timedelta(hours=24)
            max_results = 500
        else:
            start_time = now - timedelta(hours=1)
            max_results = 60

        # Build URL for trend log
        url = f"https://{SERVER}/enteliweb/api/.bacnet/{SITE}/{DEVICE}/trend-log,{TEMP_TREND_LOG_INSTANCE}/log-buffer"
        
        params = {
            "alt": "json",
            "max-results": max_results,
            "published-ge": start_time.isoformat(timespec='seconds') + "Z",
            "published-le": now.isoformat(timespec='seconds') + "Z"
        }
        
        # Fetch trend data (single request only)
        response = requests.get(url, params=params, headers=auth_header, timeout=30)
        response.raise_for_status()
        
        trend_data = response.json()
        records = []
        
        # Process the trend data
        for key, value in trend_data.items():
            if key in ('$base', 'next') or not isinstance(value, dict) or "timestamp" not in value:
                continue
                
            log_datum = value.get("logDatum", {})
            
            # Skip status-only records
            if any(k in log_datum for k in ("log-status", "event-state", "string-value")):
                continue
            
            # Extract temperature value
            temp_value = None
            if "real-value" in log_datum and isinstance(log_datum["real-value"], dict):
                temp_value = log_datum["real-value"].get("value")
            
            if temp_value is None:
                for item in log_datum.values():
                    if isinstance(item, dict) and "value" in item:
                        temp_value = item["value"]
                        break
            
            if temp_value is None:
                continue
            
            # Convert to float and validate - be very explicit about type conversion
            try:
                temp_float = float(str(temp_value))  # Convert to string first, then float
            except (ValueError, TypeError):
                continue
            
            # Filter out erroneous temperature readings (reasonable HVAC range: 40-120°F)
            if temp_float < 40 or temp_float > 120:
                continue
            
            # Parse timestamp
            timestamp_raw = value["timestamp"]["value"]
            if timestamp_raw.endswith('Z'):
                timestamp_dt = datetime.fromisoformat(timestamp_raw[:-1]).replace(tzinfo=timezone.utc)
            else:
                timestamp_dt = datetime.fromisoformat(timestamp_raw.replace('Z', '+00:00'))
            
            # Format time label based on range
            if time_range in ("1h", "4h"):
                formatted_time = timestamp_dt.strftime('%H:%M')
            elif time_range in ("12h", "24h"):
                formatted_time = timestamp_dt.strftime('%m/%d %H:%M')
            else:
                formatted_time = timestamp_dt.strftime('%m/%d')
            
            records.append({
                "timestamp": timestamp_raw,
                "temperature": temp_float,
                "formatted_time": formatted_time,
                "sort_time": timestamp_dt
            })
        
        # Sort by timestamp
        records.sort(key=lambda x: x['sort_time'])
        
        # Remove sort_time field
        for record in records:
            record.pop('sort_time', None)
        
        result = {
            "records": records,
            "time_range": time_range,
            "total_records": len(records)
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "records": [],
            "total_records": 0
        })

if __name__ == '__main__':
    print(f"Starting Thermostat Dashboard with AV1 Setpoint Control and Thermostat Lockout...")
    print(f"EnteliWeb Server: {SERVER}")
    print(f"Site: {SITE}")
    print(f"Device: {DEVICE}")
    print(f"Setpoint Control: AV{SETPOINT_AV} (Analog Value {SETPOINT_AV})")
    print(f"Setpoint Max Limit: AV{SETPOINT_MAX_AV} (Analog Value {SETPOINT_MAX_AV})")
    print(f"Setpoint Min Limit: AV{SETPOINT_MIN_AV} (Analog Value {SETPOINT_MIN_AV})")
    print(f"Temperature Trend Log Instance: {TEMP_TREND_LOG_INSTANCE}")
    print(f"Dashboard URL: http://localhost:8000")
    print(f"API Test: http://localhost:8000/api/thermostat")
    print(f"Trend API Test: http://localhost:8000/api/trends?range=1h")
    print("\nMake sure to update the PASSWORD variable!")
    print(f"\nSetpoint Control Features:")
    print(f"- +/- buttons for 1°F adjustments")
    print(f"- Manual input field for precise control")
    print(f"- Dynamic safety limits from AV{SETPOINT_MAX_AV} (max) and AV{SETPOINT_MIN_AV} (min)")
    print(f"- Thermostat Lockout toggle for admin control")
    print(f"- Real-time feedback and status messages")
    
    app.run(host='0.0.0.0', port=8000, debug=True)
