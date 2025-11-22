"""
Prometheus metrics exporter for Rosey Bot

Exposes deployment and health metrics for Prometheus scraping.

Usage:
    python web/metrics_exporter.py [--port 9090] [--host 0.0.0.0]
"""

import sys
import os
import time
from typing import Dict
from flask import Flask, Response
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

# Metric templates
GAUGE_TEMPLATE = "# TYPE {name} gauge\n{name}{{env=\"{env}\"{labels}}} {value}\n"
COUNTER_TEMPLATE = "# TYPE {name} counter\n{name}{{env=\"{env}\"{labels}}} {value}\n"


def get_health_data(environment: str) -> Dict:
    """Fetch health data from bot."""
    port = 8000 if environment == 'prod' else 8001
    try:
        response = requests.get(f'http://localhost:{port}/api/health', timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {
            'status': 'down',
            'connected': False,
            'error': str(e)
        }


def format_label(key: str, value: str) -> str:
    """Format a Prometheus label."""
    # Escape quotes and backslashes
    value = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f',{key}="{value}"'


def generate_metrics() -> str:
    """Generate Prometheus metrics."""
    metrics = []
    timestamp = int(time.time() * 1000)
    
    # Bot status metrics for each environment
    for env in ['test', 'prod']:
        health = get_health_data(env)
        
        # Bot up/down status (1 = up, 0 = down)
        status_value = 1 if health.get('status') == 'running' else 0
        metrics.append(GAUGE_TEMPLATE.format(
            name='rosey_bot_up',
            env=env,
            labels='',
            value=status_value
        ))
        
        # Connection status (1 = connected, 0 = disconnected)
        connected_value = 1 if health.get('connected') else 0
        metrics.append(GAUGE_TEMPLATE.format(
            name='rosey_bot_connected',
            env=env,
            labels='',
            value=connected_value
        ))
        
        # Uptime in seconds
        uptime = health.get('uptime', 0)
        metrics.append(GAUGE_TEMPLATE.format(
            name='rosey_bot_uptime_seconds',
            env=env,
            labels='',
            value=uptime
        ))
        
        # User count in channel
        user_count = health.get('user_count', 0)
        metrics.append(GAUGE_TEMPLATE.format(
            name='rosey_bot_channel_users',
            env=env,
            labels=format_label('channel', health.get('channel', 'unknown')),
            value=user_count
        ))
        
        # Request count
        request_count = health.get('requests', 0)
        metrics.append(COUNTER_TEMPLATE.format(
            name='rosey_bot_requests_total',
            env=env,
            labels='',
            value=request_count
        ))
        
        # Error count
        error_count = health.get('errors', 0)
        metrics.append(COUNTER_TEMPLATE.format(
            name='rosey_bot_errors_total',
            env=env,
            labels='',
            value=error_count
        ))
        
        # Error rate (percentage)
        if request_count > 0:
            error_rate = (error_count / request_count) * 100
        else:
            error_rate = 0
        metrics.append(GAUGE_TEMPLATE.format(
            name='rosey_bot_error_rate_percent',
            env=env,
            labels='',
            value=f'{error_rate:.2f}'
        ))
    
    # Scrape metadata
    metrics.append("# TYPE rosey_bot_scrape_timestamp_ms gauge\n")
    metrics.append(f"rosey_bot_scrape_timestamp_ms {timestamp}\n")
    
    return ''.join(metrics)


@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint."""
    metrics_text = generate_metrics()
    return Response(metrics_text, mimetype='text/plain')


@app.route('/health')
def health():
    """Health check endpoint for the exporter itself."""
    return {'status': 'healthy', 'service': 'metrics_exporter'}


def main():
    """Run the metrics exporter."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Rosey Bot Metrics Exporter')
    parser.add_argument('--port', type=int, default=9090, help='Port to run on')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    
    args = parser.parse_args()
    
    print(f"📊 Starting Metrics Exporter on http://{args.host}:{args.port}")
    print(f"📈 Metrics available at http://{args.host}:{args.port}/metrics")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
