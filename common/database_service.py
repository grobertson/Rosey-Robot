#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NATS-enabled database service for process isolation

This service wraps BotDatabase and subscribes to NATS subjects, enabling
the database to run in a separate process from the bot.

Architecture:
    Bot Layer → NATS Events → DatabaseService → BotDatabase → SQLite

Usage:
    # Start as standalone service
    python -m common.database_service

    # Or integrate with bot
    from common.database_service import DatabaseService
    db_service = DatabaseService(nats_client, "bot_data.db")
    await db_service.start()
"""
import asyncio
import json
import logging
import sys

try:
    from nats.aio.client import Client as NATS  # noqa: N814 (NATS convention)
except ImportError:
    NATS = None

from common.database import BotDatabase


class DatabaseService:
    """NATS-enabled wrapper around BotDatabase for process isolation.

    This service subscribes to NATS subjects and forwards database operations
    to the underlying BotDatabase. Enables running database in separate process.

    NATS Subject Design:
        rosey.db.user.joined           - User joined channel (pub/sub)
        rosey.db.user.left             - User left channel (pub/sub)
        rosey.db.message.log           - Log chat message (pub/sub)
        rosey.db.stats.user_count      - Update user count stats (pub/sub)
        rosey.db.stats.high_water      - Update high water mark (pub/sub)
        rosey.db.status.update         - Bot status update (pub/sub)
        rosey.db.messages.outbound.mark_sent - Mark message sent (pub/sub)
        rosey.db.action.pm_command     - Log PM command (pub/sub)
        rosey.db.messages.outbound.get - Query outbound messages (request/reply)
        rosey.db.stats.recent_chat.get - Get recent chat (request/reply)

    Example:
        # Start database service
        nats = await nats.connect("nats://localhost:4222")
        db_service = DatabaseService(nats, "bot_data.db")
        await db_service.start()

        # Service now handles all database operations via NATS
        # Can run in separate process from bot
    """

    def __init__(self, nats_client, db_path: str = 'bot_data.db'):
        """Initialize database service.

        Args:
            nats_client: Connected NATS client instance
            db_path: Path to SQLite database file
        """
        if NATS is None:
            raise ImportError("NATS not available - install nats-py package")

        self.nats = nats_client
        self.db = BotDatabase(db_path)
        self.logger = logging.getLogger(__name__)
        self._subscriptions = []
        self._running = False

    async def start(self):
        """Subscribe to all database subjects and start handling events.

        Sets up both pub/sub (fire-and-forget) and request/reply subscriptions.
        """
        if self._running:
            self.logger.warning("DatabaseService already running")
            return

        self.logger.info("Starting DatabaseService...")

        # Connect database (Sprint 10 - async lifecycle)
        await self.db.connect()

        # Pub/Sub subscriptions (fire-and-forget events)
        try:
            self._subscriptions.extend([
                await self.nats.subscribe('rosey.db.user.joined',
                                        cb=self._handle_user_joined),
                await self.nats.subscribe('rosey.db.user.left',
                                        cb=self._handle_user_left),
                await self.nats.subscribe('rosey.db.message.log',
                                        cb=self._handle_message_log),
                await self.nats.subscribe('rosey.db.stats.user_count',
                                        cb=self._handle_user_count),
                await self.nats.subscribe('rosey.db.stats.high_water',
                                        cb=self._handle_high_water),
                await self.nats.subscribe('rosey.db.status.update',
                                        cb=self._handle_status_update),
                await self.nats.subscribe('rosey.db.messages.outbound.mark_sent',
                                        cb=self._handle_mark_sent),
                await self.nats.subscribe('rosey.db.action.pm_command',
                                        cb=self._handle_pm_action),
            ])

            # Request/Reply subscriptions (queries)
            self._subscriptions.extend([
                await self.nats.subscribe('rosey.db.messages.outbound.get',
                                        cb=self._handle_outbound_query),
                await self.nats.subscribe('rosey.db.stats.recent_chat.get',
                                        cb=self._handle_recent_chat_query),
                await self.nats.subscribe('rosey.db.query.channel_stats',
                                        cb=self._handle_channel_stats_query),
                await self.nats.subscribe('rosey.db.query.user_stats',
                                        cb=self._handle_user_stats_query),
            ])

            # KV Storage handlers (request/reply)
            self._subscriptions.extend([
                await self.nats.subscribe('rosey.db.kv.set',
                                        cb=self._handle_kv_set),
                await self.nats.subscribe('rosey.db.kv.get',
                                        cb=self._handle_kv_get),
                await self.nats.subscribe('rosey.db.kv.delete',
                                        cb=self._handle_kv_delete),
                await self.nats.subscribe('rosey.db.kv.list',
                                        cb=self._handle_kv_list),
            ])

            self._running = True
            self.logger.info(
                f"DatabaseService started with {len(self._subscriptions)} subscriptions"
            )

        except Exception as e:
            self.logger.error(f"Failed to start DatabaseService: {e}", exc_info=True)
            # Cleanup partial subscriptions
            await self.stop()
            raise

    async def stop(self):
        """Unsubscribe from all subjects and stop service.

        Performs graceful shutdown by unsubscribing from all NATS subjects.
        """
        if not self._running and not self._subscriptions:
            return

        self.logger.info("Stopping DatabaseService...")

        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                self.logger.error(f"Error unsubscribing: {e}")

        self._subscriptions = []
        self._running = False

        # Close database (Sprint 10 - async lifecycle)
        if self.db.is_connected:
            await self.db.close()

        self.logger.info("DatabaseService stopped")

    # ========================================================================
    # Event Handlers (Pub/Sub - Fire and Forget)
    # ========================================================================

    async def _handle_user_joined(self, msg):
        """Handle user joined event.

        NATS Subject: rosey.db.user.joined
        Payload: {'username': str}
        """
        try:
            data = json.loads(msg.data.decode())
            username = data.get('username', '')

            if username:
                await self.db.user_joined(username)
                self.logger.debug(f"[NATS] User joined: {username}")
            else:
                self.logger.warning("[NATS] user_joined: Missing username")

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in user_joined: {e}")
        except Exception as e:
            self.logger.error(f"Error handling user_joined: {e}", exc_info=True)

    async def _handle_user_left(self, msg):
        """Handle user left event.

        NATS Subject: rosey.db.user.left
        Payload: {'username': str}
        """
        try:
            data = json.loads(msg.data.decode())
            username = data.get('username', '')

            if username:
                await self.db.user_left(username)
                self.logger.debug(f"[NATS] User left: {username}")
            else:
                self.logger.warning("[NATS] user_left: Missing username")

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in user_left: {e}")
        except Exception as e:
            self.logger.error(f"Error handling user_left: {e}", exc_info=True)

    async def _handle_message_log(self, msg):
        """Handle chat message logging.

        NATS Subject: rosey.db.message.log
        Payload: {'username': str, 'message': str}
        """
        try:
            data = json.loads(msg.data.decode())
            username = data.get('username', '')
            message = data.get('message', '')

            if username and message:
                # BotDatabase method is user_chat_message()
                await self.db.user_chat_message(username, message)
                self.logger.debug(f"[NATS] Message logged: {username}")
            else:
                self.logger.warning(
                    f"[NATS] message_log: Missing data (username={bool(username)}, "
                    f"message={bool(message)})"
                )

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in message_log: {e}")
        except Exception as e:
            self.logger.error(f"Error handling message_log: {e}", exc_info=True)

    async def _handle_user_count(self, msg):
        """Handle user count statistics update.

        NATS Subject: rosey.db.stats.user_count
        Payload: {'chat_count': int, 'connected_count': int}
        """
        try:
            data = json.loads(msg.data.decode())
            chat_count = data.get('chat_count', 0)
            connected_count = data.get('connected_count', 0)

            # BotDatabase method is log_user_count()
            await self.db.log_user_count(chat_count, connected_count)
            self.logger.debug(
                f"[NATS] User count logged: chat={chat_count}, "
                f"connected={connected_count}"
            )

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in user_count: {e}")
        except Exception as e:
            self.logger.error(f"Error handling user_count: {e}", exc_info=True)

    async def _handle_high_water(self, msg):
        """Handle high water mark update.

        NATS Subject: rosey.db.stats.high_water
        Payload: {'chat_count': int, 'connected_count': int}
        """
        try:
            data = json.loads(msg.data.decode())
            chat_count = data.get('chat_count', 0)
            connected_count = data.get('connected_count', None)

            await self.db.update_high_water_mark(chat_count, connected_count)
            self.logger.debug(
                f"[NATS] High water updated: chat={chat_count}, "
                f"connected={connected_count}"
            )

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in high_water: {e}")
        except Exception as e:
            self.logger.error(f"Error handling high_water: {e}", exc_info=True)

    async def _handle_status_update(self, msg):
        """Handle bot status update.

        NATS Subject: rosey.db.status.update
        Payload: {'status_data': dict} - any fields for update_current_status()
        """
        try:
            data = json.loads(msg.data.decode())
            status_data = data.get('status_data', {})

            if status_data:
                await self.db.update_current_status(**status_data)
                self.logger.debug(f"[NATS] Status updated: {list(status_data.keys())}")
            else:
                self.logger.warning("[NATS] status_update: No status data")

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in status_update: {e}")
        except Exception as e:
            self.logger.error(f"Error handling status_update: {e}", exc_info=True)

    async def _handle_mark_sent(self, msg):
        """Handle marking outbound message as sent.

        NATS Subject: rosey.db.messages.outbound.mark_sent
        Payload: {'message_id': int}
        """
        try:
            data = json.loads(msg.data.decode())
            message_id = data.get('message_id')

            if message_id is not None:
                await self.db.mark_outbound_sent(message_id)
                self.logger.debug(f"[NATS] Marked message sent: {message_id}")
            else:
                self.logger.warning("[NATS] mark_sent: Missing message_id")

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in mark_sent: {e}")
        except Exception as e:
            self.logger.error(f"Error handling mark_sent: {e}", exc_info=True)

    # ========================================================================
    # Query Handlers (Request/Reply)
    # ========================================================================

    async def _handle_outbound_query(self, msg):
        """Handle query for outbound messages (request/reply).

        NATS Subject: rosey.db.messages.outbound.get
        Payload: {'limit': int, 'max_retries': int}
        Reply: List of message dicts
        """
        try:
            data = json.loads(msg.data.decode())
            limit = data.get('limit', 50)
            max_retries = data.get('max_retries', 3)

            # BotDatabase method signature: get_unsent_outbound_messages(limit, max_retries)
            messages = await self.db.get_unsent_outbound_messages(
                limit=limit,
                max_retries=max_retries
            )

            response = json.dumps(messages).encode()
            await self.nats.publish(msg.reply, response)
            self.logger.debug(
                f"[NATS] Replied to outbound query: {len(messages)} messages"
            )

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in outbound_query: {e}")
            await self.nats.publish(msg.reply, json.dumps([]).encode())
        except Exception as e:
            self.logger.error(f"Error handling outbound_query: {e}", exc_info=True)
            # Send empty response on error
            await self.nats.publish(msg.reply, json.dumps([]).encode())

    async def _handle_recent_chat_query(self, msg):
        """Handle query for recent chat messages (request/reply).

        NATS Subject: rosey.db.stats.recent_chat.get
        Payload: {'limit': int}
        Reply: List of message dicts with timestamp, username, message
        """
        try:
            data = json.loads(msg.data.decode())
            limit = data.get('limit', 50)

            messages = await self.db.get_recent_chat(limit=limit)
            response = json.dumps(messages).encode()

            await self.nats.publish(msg.reply, response)
            self.logger.debug(
                f"[NATS] Replied to recent_chat query: {len(messages)} messages"
            )

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in recent_chat_query: {e}")
            await self.nats.publish(msg.reply, json.dumps([]).encode())
        except Exception as e:
            self.logger.error(f"Error handling recent_chat_query: {e}", exc_info=True)
            await self.nats.publish(msg.reply, json.dumps([]).encode())

    async def _handle_channel_stats_query(self, msg):
        """Handle channel statistics query (request/reply).

        NATS Subject: rosey.db.query.channel_stats
        Request Payload: {} (empty JSON object)
        Response Payload: {
            'high_water_mark': {'users': int, 'timestamp': int},
            'high_water_connected': {'users': int, 'timestamp': int},
            'top_chatters': [{'username': str, 'chat_lines': int}, ...],
            'total_users_seen': int,
            'success': bool
        }
        """
        try:
            # Get high water mark (max users in chat)
            max_users, max_users_ts = await self.db.get_high_water_mark()

            # Get high water mark for connected viewers
            max_connected, max_connected_ts = await self.db.get_high_water_mark_connected()

            # Get top chatters (top 10)
            top_chatters_raw = await self.db.get_top_chatters(limit=10)
            top_chatters = [
                {'username': username, 'chat_lines': chat_lines}
                for username, chat_lines in top_chatters_raw
            ]

            # Get total unique users
            total_users = await self.db.get_total_users_seen()

            # Build response
            response_data = {
                'high_water_mark': {
                    'users': max_users,
                    'timestamp': max_users_ts
                },
                'high_water_connected': {
                    'users': max_connected,
                    'timestamp': max_connected_ts
                },
                'top_chatters': top_chatters,
                'total_users_seen': total_users,
                'success': True
            }

            # Send response back to requester
            await self.nats.publish(
                msg.reply,
                json.dumps(response_data).encode()
            )

            self.logger.debug("[NATS] Channel stats query served")

        except Exception as e:
            self.logger.error(f"Error handling channel stats query: {e}", exc_info=True)

            # Send error response
            error_response = {
                'success': False,
                'error': str(e)
            }
            await self.nats.publish(
                msg.reply,
                json.dumps(error_response).encode()
            )

    async def _handle_user_stats_query(self, msg):
        """Handle user statistics query (request/reply).

        NATS Subject: rosey.db.query.user_stats
        Request Payload: {'username': str}
        Response Payload: {
            'username': str,
            'first_seen': int,
            'last_seen': int,
            'total_chat_lines': int,
            'total_time_connected': int,
            'current_session_start': int | None,
            'success': bool,
            'found': bool
        }
        """
        try:
            # Parse request
            data = json.loads(msg.data.decode())
            username = data.get('username', '')

            if not username:
                raise ValueError("Missing username in request")

            # Query user stats
            user_stats = await self.db.get_user_stats(username)

            if user_stats:
                # User found - return stats
                response_data = {
                    'username': user_stats['username'],
                    'first_seen': user_stats['first_seen'],
                    'last_seen': user_stats['last_seen'],
                    'total_chat_lines': user_stats['total_chat_lines'],
                    'total_time_connected': user_stats['total_time_connected'],
                    'current_session_start': user_stats.get('current_session_start'),
                    'success': True,
                    'found': True
                }
            else:
                # User not found in database
                response_data = {
                    'username': username,
                    'success': True,
                    'found': False,
                    'message': f"No statistics found for user '{username}'"
                }

            # Send response
            await self.nats.publish(
                msg.reply,
                json.dumps(response_data).encode()
            )

            self.logger.debug(f"[NATS] User stats query for '{username}' served")

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in user stats query: {e}")
            error_response = {
                'success': False,
                'error': 'Invalid request format'
            }
            await self.nats.publish(msg.reply, json.dumps(error_response).encode())

        except Exception as e:
            self.logger.error(f"Error handling user stats query: {e}", exc_info=True)
            error_response = {
                'success': False,
                'error': str(e)
            }
            await self.nats.publish(msg.reply, json.dumps(error_response).encode())

    async def _handle_pm_action(self, msg):
        """Handle PM command action logging.

        NATS Subject: rosey.db.action.pm_command
        Payload: {
            'timestamp': int,
            'username': str,
            'command': str,
            'args': str,
            'result': str ('success' | 'error' | 'pending'),
            'error': str | None
        }

        This logs moderator PM commands for audit trail and security compliance.
        Fire-and-forget semantics - failures are logged but don't affect bot.

        Example:
            await bot.nats.publish(
                'rosey.db.action.pm_command',
                json.dumps({
                    'timestamp': time.time(),
                    'username': 'ModUser',
                    'command': 'stats',
                    'args': '',
                    'result': 'success',
                    'error': None
                }).encode()
            )
        """
        try:
            data = json.loads(msg.data.decode())

            # Extract fields
            username = data.get('username', '')
            command = data.get('command', '')
            args = data.get('args', '')
            result = data.get('result', 'unknown')
            error = data.get('error')

            if not username or not command:
                self.logger.warning("[NATS] pm_action: Missing required fields")
                return

            # Build details string
            details_parts = []
            if args:
                details_parts.append(f"args: {args}")
            if result:
                details_parts.append(f"result: {result}")
            if error:
                details_parts.append(f"error: {error}")

            details = ', '.join(details_parts) if details_parts else None

            # Log to database (SQL injection safe: uses parameterized queries)
            await self.db.log_user_action(
                username=username,
                action_type='pm_command',
                details=f"cmd={command}, {details}" if details else f"cmd={command}"
            )

            self.logger.debug(
                "[NATS] PM command logged: %s executed %s",
                username, command
            )

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in pm_action: {e}")
        except Exception as e:
            self.logger.error(f"Error handling pm_action: {e}", exc_info=True)

    # ==================== KV Storage Handlers ====================

    async def _handle_kv_set(self, msg):
        """Handle rosey.db.kv.set requests.
        
        NATS Subject: rosey.db.kv.set (request/reply)
        
        Request:
            {
                "plugin_name": str,
                "key": str,
                "value": Any,
                "ttl_seconds": Optional[int]
            }
        
        Response:
            {"success": true, "data": {}}
            or
            {"success": false, "error": {"code": str, "message": str}}
        
        Error Codes:
            INVALID_JSON - Malformed JSON request
            MISSING_FIELD - Required field missing
            VALUE_TOO_LARGE - Value exceeds 64KB
            INTERNAL_ERROR - Database operation failed
        """
        try:
            # Parse request
            try:
                request = json.loads(msg.data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INVALID_JSON",
                        "message": f"Invalid JSON: {str(e)}"
                    }
                }).encode())
                return
            
            # Validate required fields
            plugin_name = request.get("plugin_name")
            key = request.get("key")
            value = request.get("value")
            
            if not plugin_name:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "MISSING_FIELD",
                        "message": "Required field 'plugin_name' is missing"
                    }
                }).encode())
                return
            
            if not key:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "MISSING_FIELD",
                        "message": "Required field 'key' is missing"
                    }
                }).encode())
                return
            
            if "value" not in request:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "MISSING_FIELD",
                        "message": "Required field 'value' is missing"
                    }
                }).encode())
                return
            
            ttl_seconds = request.get("ttl_seconds")
            
            # Call database method
            try:
                await self.db.kv_set(plugin_name, key, value, ttl_seconds)
            except ValueError as e:
                # Value too large or other validation error
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "VALUE_TOO_LARGE" if "64KB" in str(e) else "VALIDATION_ERROR",
                        "message": str(e)
                    }
                }).encode())
                return
            except Exception as e:
                self.logger.error(f"Error in kv_set: {e}", exc_info=True)
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Database operation failed"
                    }
                }).encode())
                return
            
            # Success response
            await msg.respond(json.dumps({
                "success": True,
                "data": {}
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Unexpected error in _handle_kv_set: {e}", exc_info=True)
            try:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Unexpected error occurred"
                    }
                }).encode())
            except:
                pass  # Can't respond, connection may be dead

    async def _handle_kv_get(self, msg):
        """Handle rosey.db.kv.get requests.
        
        NATS Subject: rosey.db.kv.get (request/reply)
        
        Request:
            {"plugin_name": str, "key": str}
        
        Response:
            {"success": true, "data": {"exists": bool, "value": Any}}
            or
            {"success": false, "error": {"code": str, "message": str}}
        """
        try:
            # Parse request
            try:
                request = json.loads(msg.data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INVALID_JSON",
                        "message": f"Invalid JSON: {str(e)}"
                    }
                }).encode())
                return
            
            # Validate required fields
            plugin_name = request.get("plugin_name")
            key = request.get("key")
            
            if not plugin_name:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "MISSING_FIELD",
                        "message": "Required field 'plugin_name' is missing"
                    }
                }).encode())
                return
            
            if not key:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "MISSING_FIELD",
                        "message": "Required field 'key' is missing"
                    }
                }).encode())
                return
            
            # Call database method
            try:
                result = await self.db.kv_get(plugin_name, key)
            except Exception as e:
                self.logger.error(f"Error in kv_get: {e}", exc_info=True)
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Database operation failed"
                    }
                }).encode())
                return
            
            # Success response
            await msg.respond(json.dumps({
                "success": True,
                "data": result
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Unexpected error in _handle_kv_get: {e}", exc_info=True)
            try:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Unexpected error occurred"
                    }
                }).encode())
            except:
                pass

    async def _handle_kv_delete(self, msg):
        """Handle rosey.db.kv.delete requests.
        
        NATS Subject: rosey.db.kv.delete (request/reply)
        
        Request:
            {"plugin_name": str, "key": str}
        
        Response:
            {"success": true, "data": {"deleted": bool}}
            or
            {"success": false, "error": {"code": str, "message": str}}
        """
        try:
            # Parse request
            try:
                request = json.loads(msg.data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INVALID_JSON",
                        "message": f"Invalid JSON: {str(e)}"
                    }
                }).encode())
                return
            
            # Validate required fields
            plugin_name = request.get("plugin_name")
            key = request.get("key")
            
            if not plugin_name:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "MISSING_FIELD",
                        "message": "Required field 'plugin_name' is missing"
                    }
                }).encode())
                return
            
            if not key:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "MISSING_FIELD",
                        "message": "Required field 'key' is missing"
                    }
                }).encode())
                return
            
            # Call database method
            try:
                deleted = await self.db.kv_delete(plugin_name, key)
            except Exception as e:
                self.logger.error(f"Error in kv_delete: {e}", exc_info=True)
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Database operation failed"
                    }
                }).encode())
                return
            
            # Success response
            await msg.respond(json.dumps({
                "success": True,
                "data": {"deleted": deleted}
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Unexpected error in _handle_kv_delete: {e}", exc_info=True)
            try:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Unexpected error occurred"
                    }
                }).encode())
            except:
                pass

    async def _handle_kv_list(self, msg):
        """Handle rosey.db.kv.list requests.
        
        NATS Subject: rosey.db.kv.list (request/reply)
        
        Request:
            {
                "plugin_name": str,
                "prefix": Optional[str],
                "limit": Optional[int]
            }
        
        Response:
            {"success": true, "data": {"keys": [str], "count": int, "truncated": bool}}
            or
            {"success": false, "error": {"code": str, "message": str}}
        """
        try:
            # Parse request
            try:
                request = json.loads(msg.data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INVALID_JSON",
                        "message": f"Invalid JSON: {str(e)}"
                    }
                }).encode())
                return
            
            # Validate required fields
            plugin_name = request.get("plugin_name")
            
            if not plugin_name:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "MISSING_FIELD",
                        "message": "Required field 'plugin_name' is missing"
                    }
                }).encode())
                return
            
            prefix = request.get("prefix", "")
            limit = request.get("limit", 1000)
            
            # Call database method
            try:
                result = await self.db.kv_list(plugin_name, prefix, limit)
            except Exception as e:
                self.logger.error(f"Error in kv_list: {e}", exc_info=True)
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Database operation failed"
                    }
                }).encode())
                return
            
            # Success response
            await msg.respond(json.dumps({
                "success": True,
                "data": result
            }).encode())
            
        except Exception as e:
            self.logger.error(f"Unexpected error in _handle_kv_list: {e}", exc_info=True)
            try:
                await msg.respond(json.dumps({
                    "success": False,
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Unexpected error occurred"
                    }
                }).encode())
            except:
                pass


async def main():
    """Standalone database service entry point.

    Run this file directly to start database service as separate process:
        python -m common.database_service [--db-path PATH] [--nats-url URL]
    """
    import argparse

    # Parse arguments
    parser = argparse.ArgumentParser(description='Database Service with NATS')
    parser.add_argument(
        '--db-path',
        default='bot_data.db',
        help='Path to SQLite database file (default: bot_data.db)'
    )
    parser.add_argument(
        '--nats-url',
        default='nats://localhost:4222',
        help='NATS server URL (default: nats://localhost:4222)'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    if NATS is None:
        logger.error("NATS package not installed. Install with: pip install nats-py")
        sys.exit(1)

    # Connect to NATS
    logger.info(f"Connecting to NATS at {args.nats_url}...")
    nats = NATS()

    try:
        await nats.connect(args.nats_url)
        logger.info("Connected to NATS")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        sys.exit(1)

    # Start database service
    db_service = DatabaseService(nats, args.db_path)

    try:
        await db_service.start()
        logger.info(
            f"DatabaseService running (DB: {args.db_path}) - press Ctrl+C to stop"
        )

        # Keep service running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await db_service.stop()
        await nats.close()
        logger.info("DatabaseService shutdown complete")


if __name__ == '__main__':
    asyncio.run(main())
