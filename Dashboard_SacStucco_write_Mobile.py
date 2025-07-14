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
            margin-top: 8px;
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
        
        /* Loading State Styles */
        .loading-state {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 16px;
            padding: 40px;
            text-align: center;
        }}
        .loading-spinner {{
            width: 40px;
            height: 40px;
            border: 4px solid #e8e8e8;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        .loading-text {{
            font-size: 1.1em;
            color: #7f8c8d;
            font-weight: 500;
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
            .container {{
                padding: 16px;
            }}
            .header {{
                flex-direction: column;
                gap: 16px;
                text-align: center;
                padding: 20px;
            }}
            .header-left {{
                flex-direction: column;
                gap: 12px;
            }}
            .header-text h1 {{
                font-size: 1.8em;
            }}
            .header-text h2 {{
                font-size: 1.1em;
            }}
            .card {{
                padding: 24px 20px;
                margin-bottom: 20px;
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
                flex-direction: row;
                gap: 16px;
                padding: 12px;
                justify-content: center;
                align-items: center;
            }}
            .setpoint-btn {{
                width: 50px;
                height: 50px;
                font-size: 1.8em;
            }}
            .setpoint-input {{
                width: 100px;
                font-size: 1.4em;
                padding: 12px;
            }}
            .setpoint-input-container {{
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 8px;
                margin: 0 8px;
            }}
            .lockout-controls {{
                padding: 12px;
            }}
            .lockout-toggle {{
                padding: 16px 12px;
            }}
            .lockout-text {{
                font-size: 1.1em;
            }}
            .chart-container {{
                height: 280px;
                margin-top: 20px;
            }}
            .chart-controls {{
                gap: 6px;
                margin-bottom: 20px;
            }}
            .time-range-btn {{
                padding: 8px 12px;
                font-size: 0.85em;
            }}
            .control-buttons {{
                gap: 8px;
            }}
            .btn {{
                padding: 10px 16px;
                font-size: 0.9em;
            }}
            /* Make touch targets larger for mobile */
            .setpoint-btn:hover {{
                transform: none;
            }}
            .setpoint-btn:active {{
                transform: scale(0.95);
                background: #3498db;
                color: white;
            }}
        }}
        
        /* Extra small screens */
        @media (max-width: 480px) {{
            .container {{
                padding: 12px;
            }}
            .header-text h1 {{
                font-size: 1.6em;
            }}
            .temperature-circle {{
                width: 200px;
                height: 200px;
            }}
            .temperature-value {{
                font-size: 3em;
            }}
            .setpoint-controls {{
                padding: 8px;
            }}
            .setpoint-btn {{
                width: 45px;
                height: 45px;
                font-size: 1.6em;
            }}
            .chart-container {{
                height: 240px;
            }}
            .time-range-btn {{
                padding: 6px 8px;
                font-size: 0.8em;
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
                    <div class="setpoint-controls" id="setpointControls" style="display: none;">
                        <button class="setpoint-btn" onclick="adjustSetpoint(-1)" title="Decrease by 1°F">−</button>
                        <div class="setpoint-input-container">
                            <input type="number" class="setpoint-input" id="setpointInput" step="0.5" onkeypress="handleSetpointKeypress(event)">
                            <button class="setpoint-set-btn" onclick="setCustomSetpoint()">Set</button>
                        </div>
                        <button class="setpoint-btn" onclick="adjustSetpoint(1)" title="Increase by 1°F">+</button>
                    </div>
                    
                    <!-- Thermostat Lockout Toggle -->
                    <div class="lockout-controls" id="lockoutControls" style="display: none;">
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
            
            <!-- Loading State -->
            <div id="loadingState" class="loading-state">
                <div class="loading-spinner"></div>
                <div class="loading-text">Loading thermostat data...</div>
            </div>
            
            <!-- Status message area -->
            <div id="statusMessage" class="status-message"></div>
            
            <div class="last-updated" id="lastUpdated">Initializing...</div>
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
        let setpointLimits = {{ min: 60, max: 85 }};
        let thermostatLockout = false;
        
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
                                    return 'Temperature: ' + context.parsed.y.toFixed(1) + '°F';
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
                                }},
                                stepSize: 1
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
                showStatusMessage('Setpoint must be between ' + setpointLimits.min + '°F and ' + setpointLimits.max + '°F', 'error');
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
                showStatusMessage('Setpoint must be between ' + setpointLimits.min + '°F and ' + setpointLimits.max + '°F', 'error');
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
                document.getElementById('setpointValue').text
