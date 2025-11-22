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
            ])

            # Request/Reply subscriptions (queries)
            self._subscriptions.extend([
                await self.nats.subscribe('rosey.db.messages.outbound.get',
                                        cb=self._handle_outbound_query),
                await self.nats.subscribe('rosey.db.stats.recent_chat.get',
                                        cb=self._handle_recent_chat_query),
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
                self.db.user_joined(username)
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
                self.db.user_left(username)
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
                self.db.user_chat_message(username, message)
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
            self.db.log_user_count(chat_count, connected_count)
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

            self.db.update_high_water_mark(chat_count, connected_count)
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
                self.db.update_current_status(**status_data)
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
                self.db.mark_outbound_sent(message_id)
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
            messages = self.db.get_unsent_outbound_messages(
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

            messages = self.db.get_recent_chat(limit=limit)
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
