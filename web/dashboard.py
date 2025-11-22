"""
Deployment Dashboard for Rosey Bot

Provides web interface for monitoring deployments, viewing history,
and managing rollbacks.

Usage:
    python web/dashboard.py [--port 5000] [--host 0.0.0.0]
"""

import os
import sqlite3
import sys
from datetime import datetime
from typing import Dict

import requests
from flask import Flask, jsonify, render_template, request

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)
app.config['DATABASE'] = 'data/deployments.db'

# Database schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS deployments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    environment TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    deployed_by TEXT,
    reason TEXT,
    rollback_of INTEGER,
    FOREIGN KEY (rollback_of) REFERENCES deployments(id)
);

CREATE TABLE IF NOT EXISTS deployment_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id INTEGER NOT NULL,
    check_name TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    message TEXT,
    checked_at TEXT NOT NULL,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
);

CREATE INDEX IF NOT EXISTS idx_deployments_env ON deployments(environment);
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_deployment_checks_deployment ON deployment_checks(deployment_id);
"""


def get_db():
    """Get database connection."""
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db


def init_db():
    """Initialize database."""
    os.makedirs('data', exist_ok=True)
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    db.close()


def get_health_status(environment: str) -> Dict:
    """Get health status from bot."""
    port = 8000 if environment == 'prod' else 8001
    try:
        response = requests.get(f'http://localhost:{port}/api/health', timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {'status': 'unknown', 'connected': False}


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/deployments')
def api_deployments():
    """Get deployment history."""
    environment = request.args.get('environment', 'all')
    limit = request.args.get('limit', 50, type=int)

    db = get_db()

    if environment == 'all':
        rows = db.execute(
            'SELECT * FROM deployments ORDER BY started_at DESC LIMIT ?',
            (limit,)
        ).fetchall()
    else:
        rows = db.execute(
            'SELECT * FROM deployments WHERE environment = ? ORDER BY started_at DESC LIMIT ?',
            (environment, limit)
        ).fetchall()

    deployments = []
    for row in rows:
        deployment = dict(row)

        # Get checks for this deployment
        checks = db.execute(
            'SELECT * FROM deployment_checks WHERE deployment_id = ? ORDER BY checked_at',
            (row['id'],)
        ).fetchall()
        deployment['checks'] = [dict(check) for check in checks]

        deployments.append(deployment)

    db.close()
    return jsonify(deployments)


@app.route('/api/status')
def api_status():
    """Get current status of all environments."""
    test_status = get_health_status('test')
    prod_status = get_health_status('prod')

    db = get_db()

    # Get latest deployment for each environment
    test_deploy = db.execute(
        'SELECT * FROM deployments WHERE environment = "test" ORDER BY started_at DESC LIMIT 1'
    ).fetchone()

    prod_deploy = db.execute(
        'SELECT * FROM deployments WHERE environment = "prod" ORDER BY started_at DESC LIMIT 1'
    ).fetchone()

    db.close()

    return jsonify({
        'test': {
            'health': test_status,
            'latest_deployment': dict(test_deploy) if test_deploy else None
        },
        'prod': {
            'health': prod_status,
            'latest_deployment': dict(prod_deploy) if prod_deploy else None
        }
    })


@app.route('/api/deployment/<int:deployment_id>')
def api_deployment_detail(deployment_id: int):
    """Get detailed information about a deployment."""
    db = get_db()

    deployment = db.execute(
        'SELECT * FROM deployments WHERE id = ?',
        (deployment_id,)
    ).fetchone()

    if not deployment:
        db.close()
        return jsonify({'error': 'Deployment not found'}), 404

    checks = db.execute(
        'SELECT * FROM deployment_checks WHERE deployment_id = ? ORDER BY checked_at',
        (deployment_id,)
    ).fetchall()

    db.close()

    result = dict(deployment)
    result['checks'] = [dict(check) for check in checks]

    return jsonify(result)


@app.route('/api/deployment', methods=['POST'])
def api_create_deployment():
    """Create a new deployment record."""
    data = request.json

    required = ['environment', 'version', 'deployed_by']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400

    db = get_db()
    cursor = db.execute(
        '''INSERT INTO deployments 
           (environment, version, status, started_at, deployed_by, reason)
           VALUES (?, ?, 'in_progress', ?, ?, ?)''',
        (data['environment'], data['version'], datetime.utcnow().isoformat(),
         data['deployed_by'], data.get('reason', ''))
    )
    deployment_id = cursor.lastrowid
    db.commit()
    db.close()

    return jsonify({'id': deployment_id, 'status': 'created'}), 201


@app.route('/api/deployment/<int:deployment_id>', methods=['PATCH'])
def api_update_deployment(deployment_id: int):
    """Update deployment status."""
    data = request.json

    db = get_db()

    updates = []
    values = []

    if 'status' in data:
        updates.append('status = ?')
        values.append(data['status'])

    if 'completed_at' in data or data.get('status') in ('success', 'failed'):
        updates.append('completed_at = ?')
        values.append(datetime.utcnow().isoformat())

    if not updates:
        db.close()
        return jsonify({'error': 'No updates provided'}), 400

    values.append(deployment_id)

    db.execute(
        f'UPDATE deployments SET {", ".join(updates)} WHERE id = ?',
        values
    )
    db.commit()
    db.close()

    return jsonify({'status': 'updated'})


@app.route('/api/deployment/<int:deployment_id>/check', methods=['POST'])
def api_add_check(deployment_id: int):
    """Add a deployment check result."""
    data = request.json

    required = ['check_name', 'passed']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400

    db = get_db()
    db.execute(
        '''INSERT INTO deployment_checks 
           (deployment_id, check_name, passed, message, checked_at)
           VALUES (?, ?, ?, ?, ?)''',
        (deployment_id, data['check_name'], data['passed'],
         data.get('message', ''), datetime.utcnow().isoformat())
    )
    db.commit()
    db.close()

    return jsonify({'status': 'created'}), 201


@app.route('/api/stats')
def api_stats():
    """Get deployment statistics."""
    db = get_db()

    # Total deployments
    total = db.execute('SELECT COUNT(*) as count FROM deployments').fetchone()['count']

    # Success rate
    success = db.execute(
        'SELECT COUNT(*) as count FROM deployments WHERE status = "success"'
    ).fetchone()['count']

    # Failed deployments
    failed = db.execute(
        'SELECT COUNT(*) as count FROM deployments WHERE status = "failed"'
    ).fetchone()['count']

    # Recent deployments (last 7 days)
    recent = db.execute(
        '''SELECT environment, COUNT(*) as count 
           FROM deployments 
           WHERE started_at >= datetime('now', '-7 days')
           GROUP BY environment'''
    ).fetchall()

    # Average deployment time
    avg_time = db.execute(
        '''SELECT AVG(
               (julianday(completed_at) - julianday(started_at)) * 86400
           ) as avg_seconds
           FROM deployments 
           WHERE completed_at IS NOT NULL'''
    ).fetchone()['avg_seconds']

    db.close()

    return jsonify({
        'total_deployments': total,
        'success_rate': (success / total * 100) if total > 0 else 0,
        'failed_deployments': failed,
        'recent_by_environment': {row['environment']: row['count'] for row in recent},
        'avg_deployment_time_seconds': avg_time or 0
    })


def main():
    """Run the dashboard server."""
    import argparse

    parser = argparse.ArgumentParser(description='Rosey Bot Deployment Dashboard')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')

    args = parser.parse_args()

    # Initialize database
    init_db()

    print(f"🚀 Starting Rosey Bot Dashboard on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
