#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web status server for displaying bot metrics and statistics"""
import logging
import os
import sys
import time
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.database import BotDatabase

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Global database path
db_path = None


def get_db():
    """Get database connection for current request

    Creates a new connection per request to avoid SQLite threading issues.
    The connection is stored in Flask's g object and automatically closed.
    """
    if 'db' not in g:
        if db_path is None:
            raise RuntimeError('Database not initialized')
        g.db = BotDatabase(db_path)
    return g.db


@app.teardown_appcontext
def close_db(error):
    """Close database connection at end of request"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_database(path='bot_data.db'):
    """Initialize database path

    Args:
        path: Path to SQLite database file
    """
    global db_path
    # Convert relative path to absolute from bot root
    if not os.path.isabs(path):
        root_dir = Path(__file__).parent.parent
        path = root_dir / path

    db_path = str(path)
    logging.info('Status server configured for database: %s', db_path)


@app.route('/')
def index():
    """Main status page"""
    return render_template('status.html')


@app.route('/api/stats')
def api_stats():
    """API endpoint for current statistics"""
    try:
        db = get_db()

        # Get high water marks
        max_chat, max_chat_time = db.get_high_water_mark()
        max_connected, max_connected_time = db.get_high_water_mark_connected()

        # Get total users seen
        total_users = db.get_total_users_seen()

        # Get top chatters
        top_chatters = db.get_top_chatters(10)

        stats = {
            'high_water_marks': {
                'chat': {
                    'count': max_chat,
                    'timestamp': max_chat_time
                },
                'connected': {
                    'count': max_connected,
                    'timestamp': max_connected_time
                }
            },
            'total_users_seen': total_users,
            'top_chatters': [
                {'username': username, 'messages': count}
                for username, count in top_chatters
            ]
        }

        return jsonify(stats)

    except Exception as e:
        logging.error('Error fetching stats: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/history/<int:hours>')
def api_history(hours):
    """API endpoint for user count history

    Args:
        hours: Number of hours of history to retrieve (max 168 = 1 week)
    """
    # Limit to 1 week maximum
    hours = min(hours, 168)

    try:
        db = get_db()
        history = db.get_user_count_history(hours)
        return jsonify({
            'hours': hours,
            'data': history
        })

    except Exception as e:
        logging.error('Error fetching history: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/<username>')
def api_user(username):
    """API endpoint for individual user statistics

    Args:
        username: Username to look up
    """
    try:
        db = get_db()
        stats = db.get_user_stats(username)

        if not stats:
            return jsonify({'error': 'User not found'}), 404

        return jsonify(stats)

    except Exception as e:
        logging.error('Error fetching user stats: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/current')
def api_current():
    """API endpoint for current bot status and recent chat

    Returns current user counts, bot info, and recent messages
    """
    try:
        db = get_db()

        # Get current status
        status = db.get_current_status()

        # Get recent chat messages (last 20 minutes)
        recent_chat = db.get_recent_chat_since(minutes=20)

        result = {
            'status': status or {},
            'recent_chat': recent_chat
        }

        return jsonify(result)

    except Exception as e:
        logging.error('Error fetching current data: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/say', methods=['POST'])
def api_say():
    """API endpoint to queue an outbound message to be sent by the bot.

    Requires authentication via X-API-Token header.

    Request:
        Headers: X-API-Token: <your-token>
        JSON body: {"message": "text to send"}

    Response:
        Success: {"queued": true, "id": <message-id>}
        Error: {"error": "description"} with appropriate status code
    """
    try:
        # Check for API token in header
        token = request.headers.get('X-API-Token')

        db = get_db()

        if not db.validate_api_token(token):
            logging.warning('Unauthorized /api/say attempt from %s',
                          request.remote_addr)
            return jsonify({'error': 'Unauthorized - invalid or missing API token'}), 401

        payload = request.get_json(force=True)
        if not payload or 'message' not in payload:
            return jsonify({'error': 'Missing message'}), 400

        message = payload.get('message', '').strip()
        if not message:
            return jsonify({'error': 'Empty message'}), 400

        outbound_id = db.enqueue_outbound_message(message)
        logging.info('Queued outbound message id=%d from token', outbound_id)
        return jsonify({'queued': True, 'id': outbound_id})

    except Exception as e:
        logging.error('Error queueing outbound message: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/tokens', methods=['GET'])
def api_list_tokens():
    """List all active API tokens (admin endpoint).

    Returns token metadata with truncated token previews.
    """
    try:
        db = get_db()
        tokens = db.list_api_tokens(include_revoked=False)
        return jsonify({'tokens': tokens})

    except Exception as e:
        logging.error('Error listing tokens: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/tokens', methods=['POST'])
def api_create_token():
    """Create a new API token (admin endpoint).

    Request JSON body: {"description": "optional description"}

    Returns: {"token": "full-token-string", "description": "..."}

    Warning: The full token is only returned once. Store it securely.
    """
    try:
        payload = request.get_json(force=True) or {}
        description = payload.get('description', '')

        db = get_db()
        token = db.generate_api_token(description)

        return jsonify({
            'token': token,
            'description': description,
            'created_at': int(time.time())
        })

    except Exception as e:
        logging.error('Error creating token: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/tokens/<token_prefix>', methods=['DELETE'])
def api_revoke_token(token_prefix):
    """Revoke an API token (admin endpoint).

    Args:
        token_prefix: First 8+ characters of the token to revoke

    Returns: {"revoked": count}
    """
    try:
        db = get_db()
        count = db.revoke_api_token(token_prefix)

        if count > 0:
            return jsonify({'revoked': count})
        else:
            return jsonify({'error': 'Token not found'}), 404

    except Exception as e:
        logging.error('Error revoking token: %s', e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/outbound/recent', methods=['GET'])
def api_outbound_recent():
    """Get recent outbound messages with their status.

    Returns last N messages (sent and pending) for status display.
    Query params:
        limit: Number of messages to return (default 20, max 100)
    """
    try:
        limit = min(int(request.args.get('limit', 20)), 100)

        db = get_db()
        cursor = db.conn.cursor()

        # Get recent outbound messages (both sent and pending)
        cursor.execute('''
            SELECT id, timestamp, message, sent, sent_timestamp,
                   retry_count, last_error
            FROM outbound_messages
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        messages = []
        for row in cursor.fetchall():
            msg_data = dict(row)
            # Truncate long messages for display
            if len(msg_data['message']) > 100:
                msg_data['message_preview'] = (
                    msg_data['message'][:100] + '...'
                )
            else:
                msg_data['message_preview'] = msg_data['message']

            # Determine status
            if msg_data['sent'] == 1:
                if msg_data.get('last_error'):
                    msg_data['status'] = 'failed'
                else:
                    msg_data['status'] = 'sent'
            else:
                retry_count = msg_data.get('retry_count', 0)
                if retry_count >= 3:
                    msg_data['status'] = 'abandoned'
                elif retry_count > 0:
                    msg_data['status'] = 'retrying'
                else:
                    msg_data['status'] = 'queued'

            messages.append(msg_data)

        return jsonify({'messages': messages})

    except Exception as e:
        logging.error('Error fetching outbound status: %s', e)
        return jsonify({'error': str(e)}), 500


def run_server(host='127.0.0.1', port=5000, db_path='bot_data.db',
               debug=False):
    """Run the Flask web server

    Args:
        host: Host to bind to (default: 127.0.0.1)
        port: Port to bind to (default: 5000)
        db_path: Path to SQLite database file
        debug: Enable debug mode
    """
    init_database(db_path)

    logging.info('Starting web status server on http://%s:%d', host, port)
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(
        description='Web status server for CyTube bot'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind to (default: 5000)'
    )
    parser.add_argument(
        '--db',
        default='bot_data.db',
        help='Path to database file (default: bot_data.db)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        db_path=args.db,
        debug=args.debug
    )
