# Sortie 7: Deploy Dashboard

**Status**: Planning  
**Owner**: Agent (development), User (deployment)  
**Estimated Effort**: 2-3 hours  
**Related Issue**: #25  
**Depends On**: Sortie 6 (Prometheus operational)

## Overview

Create and deploy web-based monitoring dashboard showing bot status, metrics, and alert history in a user-friendly interface. This complements Prometheus (for deep technical queries) with an at-a-glance status view.

**What we're building:**

- Single-page web dashboard
- Real-time bot status
- Metrics graphs
- Recent alert history
- Accessible without Prometheus knowledge

## Design

### Dashboard Features

**Top section: Current Status**

- Bot online/offline indicator
- Channel name
- Uptime
- Current user count
- Connection quality (based on error rate)

**Middle section: Metrics Charts**

- User count over last hour (line chart)
- Request rate over last hour (area chart)
- Error count over last hour (line chart)

**Bottom section: Recent Activity**

- Recent alerts (last 24 hours)
- Recent deployments
- Bot restarts

### Technology Stack

- **Frontend:** HTML, CSS, JavaScript (vanilla)
- **Charts:** Chart.js (lightweight, no jQuery)
- **API:** Prometheus HTTP API
- **Refresh:** Auto-refresh every 30 seconds

**Why not React/Vue/etc?** Keep it simple. Static HTML with JavaScript is fine for a monitoring dashboard.

## Implementation

### File Structure

```
web/
  dashboard.py          # Flask server (exists from Sprint 5)
  static/
    style.css           # Dashboard CSS
    dashboard.js        # Dashboard JavaScript
  templates/
    dashboard.html      # Main dashboard page
```

### dashboard.html

File: `web/templates/dashboard.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rosey Bot Dashboard</title>
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Rosey Bot Dashboard</h1>
            <div class="last-updated">Last updated: <span id="last-updated">Loading...</span></div>
        </header>

        <!-- Current Status -->
        <section class="status-section">
            <div class="status-card" id="status-online">
                <div class="status-indicator"></div>
                <div class="status-text">
                    <div class="status-label">Bot Status</div>
                    <div class="status-value" id="bot-status">Loading...</div>
                </div>
            </div>

            <div class="status-card">
                <div class="status-text">
                    <div class="status-label">Channel</div>
                    <div class="status-value" id="bot-channel">-</div>
                </div>
            </div>

            <div class="status-card">
                <div class="status-text">
                    <div class="status-label">Uptime</div>
                    <div class="status-value" id="bot-uptime">-</div>
                </div>
            </div>

            <div class="status-card">
                <div class="status-text">
                    <div class="status-label">Users</div>
                    <div class="status-value" id="bot-users">-</div>
                </div>
            </div>
        </section>

        <!-- Metrics Charts -->
        <section class="charts-section">
            <div class="chart-container">
                <h2>User Count (Last Hour)</h2>
                <canvas id="usersChart"></canvas>
            </div>

            <div class="chart-container">
                <h2>Requests per Minute</h2>
                <canvas id="requestsChart"></canvas>
            </div>

            <div class="chart-container">
                <h2>Errors (Last Hour)</h2>
                <canvas id="errorsChart"></canvas>
            </div>
        </section>

        <!-- Recent Alerts -->
        <section class="alerts-section">
            <h2>Recent Alerts (Last 24 Hours)</h2>
            <div id="alerts-list">
                <p>Loading alerts...</p>
            </div>
        </section>
    </div>

    <script src="/static/dashboard.js"></script>
</body>
</html>
```

### style.css

File: `web/static/style.css`

```css
/* Dashboard styles */

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #333;
    min-height: 100vh;
    padding: 20px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
}

header {
    background: white;
    padding: 30px;
    border-radius: 10px;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

header h1 {
    font-size: 32px;
    margin-bottom: 10px;
}

.last-updated {
    color: #666;
    font-size: 14px;
}

/* Status Cards */
.status-section {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
}

.status-card {
    background: white;
    padding: 25px;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    display: flex;
    align-items: center;
    gap: 15px;
}

.status-indicator {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #10b981;
    animation: pulse 2s infinite;
}

.status-card.offline .status-indicator {
    background: #ef4444;
    animation: none;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.status-text {
    flex: 1;
}

.status-label {
    font-size: 12px;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 5px;
}

.status-value {
    font-size: 24px;
    font-weight: bold;
    color: #333;
}

/* Charts Section */
.charts-section {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
}

.chart-container {
    background: white;
    padding: 25px;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.chart-container h2 {
    font-size: 18px;
    margin-bottom: 15px;
    color: #333;
}

/* Alerts Section */
.alerts-section {
    background: white;
    padding: 25px;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.alerts-section h2 {
    font-size: 20px;
    margin-bottom: 15px;
}

.alert-item {
    padding: 15px;
    border-left: 4px solid #3b82f6;
    background: #f8fafc;
    margin-bottom: 10px;
    border-radius: 4px;
}

.alert-item.critical {
    border-color: #ef4444;
    background: #fef2f2;
}

.alert-item.warning {
    border-color: #f59e0b;
    background: #fffbeb;
}

.alert-name {
    font-weight: bold;
    color: #333;
    margin-bottom: 5px;
}

.alert-description {
    color: #666;
    font-size: 14px;
    margin-bottom: 5px;
}

.alert-time {
    color: #999;
    font-size: 12px;
}

.no-alerts {
    color: #666;
    font-style: italic;
}
```

### dashboard.js

File: `web/static/dashboard.js`

```javascript
// Dashboard JavaScript

const PROMETHEUS_URL = 'http://localhost:9090';
const REFRESH_INTERVAL = 30000; // 30 seconds

let usersChart, requestsChart, errorsChart;

// Initialize dashboard
async function init() {
    initCharts();
    await updateDashboard();
    
    // Auto-refresh
    setInterval(updateDashboard, REFRESH_INTERVAL);
}

// Initialize Chart.js charts
function initCharts() {
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: {
                display: false
            }
        },
        scales: {
            x: {
                type: 'time',
                time: {
                    unit: 'minute'
                }
            },
            y: {
                beginAtZero: true
            }
        }
    };

    // Users chart
    const usersCtx = document.getElementById('usersChart').getContext('2d');
    usersChart = new Chart(usersCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Users',
                data: [],
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.4
            }]
        },
        options: chartOptions
    });

    // Requests chart
    const requestsCtx = document.getElementById('requestsChart').getContext('2d');
    requestsChart = new Chart(requestsCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Requests/min',
                data: [],
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: chartOptions
    });

    // Errors chart
    const errorsCtx = document.getElementById('errorsChart').getContext('2d');
    errorsChart = new Chart(errorsCtx, {
        type: 'bar',
        data: {
            datasets: [{
                label: 'Errors',
                data: [],
                backgroundColor: '#ef4444'
            }]
        },
        options: {
            ...chartOptions,
            scales: {
                ...chartOptions.scales,
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

// Update all dashboard data
async function updateDashboard() {
    try {
        await updateStatus();
        await updateCharts();
        await updateAlerts();
        
        // Update timestamp
        document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
    } catch (error) {
        console.error('Dashboard update failed:', error);
    }
}

// Update status cards
async function updateStatus() {
    const query = 'bot_connected';
    const data = await queryPrometheus(query);
    
    if (data && data.length > 0) {
        const metric = data[0].metric;
        const value = parseInt(data[0].value[1]);
        
        // Update status
        const statusCard = document.getElementById('status-online');
        const statusText = document.getElementById('bot-status');
        
        if (value === 1) {
            statusCard.classList.remove('offline');
            statusText.textContent = 'Online';
        } else {
            statusCard.classList.add('offline');
            statusText.textContent = 'Offline';
        }
    }
    
    // Update other metrics
    const uptimeData = await queryPrometheus('bot_uptime_seconds');
    if (uptimeData && uptimeData.length > 0) {
        const seconds = parseInt(uptimeData[0].value[1]);
        document.getElementById('bot-uptime').textContent = formatUptime(seconds);
    }
    
    const usersData = await queryPrometheus('bot_users');
    if (usersData && usersData.length > 0) {
        document.getElementById('bot-users').textContent = usersData[0].value[1];
    }
}

// Update charts
async function updateCharts() {
    const now = Math.floor(Date.now() / 1000);
    const oneHourAgo = now - 3600;
    
    // Users over time
    const usersData = await queryPrometheusRange('bot_users', oneHourAgo, now, 60);
    updateChart(usersChart, usersData);
    
    // Requests per minute
    const requestsData = await queryPrometheusRange('rate(bot_requests_total[1m])', oneHourAgo, now, 60);
    updateChart(requestsChart, requestsData);
    
    // Errors
    const errorsData = await queryPrometheusRange('increase(bot_errors_total[5m])', oneHourAgo, now, 300);
    updateChart(errorsChart, errorsData);
}

// Update alerts list
async function updateAlerts() {
    try {
        const response = await fetch('http://localhost:9093/api/v2/alerts');
        const alerts = await response.json();
        
        const alertsList = document.getElementById('alerts-list');
        
        if (alerts.length === 0) {
            alertsList.innerHTML = '<p class="no-alerts">No active alerts 🎉</p>';
            return;
        }
        
        alertsList.innerHTML = alerts.map(alert => `
            <div class="alert-item ${alert.labels.severity}">
                <div class="alert-name">${alert.labels.alertname}</div>
                <div class="alert-description">${alert.annotations.description}</div>
                <div class="alert-time">Since: ${new Date(alert.startsAt).toLocaleString()}</div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to fetch alerts:', error);
    }
}

// Helper: Query Prometheus
async function queryPrometheus(query) {
    const url = `${PROMETHEUS_URL}/api/v1/query?query=${encodeURIComponent(query)}`;
    const response = await fetch(url);
    const json = await response.json();
    return json.data.result;
}

// Helper: Query Prometheus range
async function queryPrometheusRange(query, start, end, step) {
    const url = `${PROMETHEUS_URL}/api/v1/query_range?query=${encodeURIComponent(query)}&start=${start}&end=${end}&step=${step}`;
    const response = await fetch(url);
    const json = await response.json();
    return json.data.result;
}

// Helper: Update chart with data
function updateChart(chart, data) {
    if (!data || data.length === 0) return;
    
    const values = data[0].values.map(v => ({
        x: new Date(v[0] * 1000),
        y: parseFloat(v[1])
    }));
    
    chart.data.datasets[0].data = values;
    chart.update('none'); // Update without animation
}

// Helper: Format uptime
function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
}

// Start dashboard
document.addEventListener('DOMContentLoaded', init);
```

### Update dashboard.py

Ensure Flask serves static files and templates:

```python
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/health')
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
```

## Deployment

### Step 1: Commit Dashboard Files

```bash
# On your machine
cd d:\Devel\Rosey-Robot

# Add all dashboard files
git add web/static/style.css
git add web/static/dashboard.js
git add web/templates/dashboard.html
git add web/dashboard.py

git commit -m "feat: Add monitoring dashboard UI"
git push origin main
```

### Step 2: Deploy to Servers

Dashboard deploys automatically with bot (rsync includes `web/` directory).

```bash
# Trigger deployment
git push origin main

# Or manually SSH and pull
ssh rosey@SERVER_IP
cd /opt/rosey-bot
git pull origin main
sudo systemctl restart rosey-dashboard
```

### Step 3: Access Dashboard

**Test server:**

- URL: `http://TEST_IP:5000`
- Or SSH tunnel: `ssh -L 5000:localhost:5000 rosey@TEST_IP`

**Production server:**

- URL: `http://PROD_IP:5000`
- Or SSH tunnel: `ssh -L 5000:localhost:5000 rosey@PROD_IP`

## Validation Checklist

- [ ] Dashboard HTML/CSS/JS files created
- [ ] Dashboard served by Flask
- [ ] Status cards show current bot state
- [ ] Charts display metrics from Prometheus
- [ ] Alerts section shows active alerts
- [ ] Auto-refresh working (every 30 seconds)
- [ ] Mobile responsive design
- [ ] Deployed to both test and production
- [ ] Accessible from browser

## Common Issues

### Issue: Charts Not Loading

**Cause:** Prometheus not accessible from browser

**Fix:** CORS issue - Prometheus needs to allow browser requests

Add to `prometheus.yml`:

```yaml
global:
  # ... existing config ...
  
web:
  cors:
    origin: '*'
```

### Issue: Dashboard Shows Old Data

**Cause:** Browser caching

**Fix:** Hard refresh (Ctrl+Shift+R) or clear cache

## Success Criteria

Sortie 7 complete when:

1. Dashboard UI created and styled
2. Real-time status display working
3. Charts showing metrics
4. Alerts display functional
5. Auto-refresh operational
6. Deployed to both servers
7. Accessible and useful for monitoring

## Time Estimate

- **Create HTML/CSS/JS**: 2 hours
- **Deploy and test**: 30 minutes
- **Refinements**: 30 minutes
- **Total**: ~3 hours

Dashboard complete! 📊✨
