"""
plugins/countdown/plugin.py

Countdown timer plugin using NATS-based architecture.

NATS Subjects:
    Command Handlers:
        rosey.command.countdown.create - Create a countdown
        rosey.command.countdown.check - Check remaining time
        rosey.command.countdown.list - List all countdowns
        rosey.command.countdown.delete - Delete a countdown
    
    Events (Published):
        rosey.event.countdown.created - Countdown was created
        rosey.event.countdown.completed - Countdown reached T-0
        rosey.event.countdown.deleted - Countdown was deleted
    
    Storage API (via NATS):
        rosey.db.row.countdown.insert - Create countdown record
        rosey.db.row.countdown.select - Query countdown records
        rosey.db.row.countdown.update - Update countdown record
        rosey.db.row.countdown.delete - Delete countdown record
        rosey.db.migrate.countdown.status - Check migration status
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from nats.aio.client import Client as NATS

try:
    from .countdown import Countdown, parse_datetime, format_remaining
    from .scheduler import CountdownScheduler
except ImportError:
    from countdown import Countdown, parse_datetime, format_remaining
    from scheduler import CountdownScheduler


class CountdownPlugin:
    """
    Countdown timer plugin.
    
    Commands:
        !countdown <name> <datetime> - Create a countdown
        !countdown <name> - Check remaining time
        !countdown list - List all countdowns in channel
        !countdown delete <name> - Delete a countdown
    
    Features:
        - One-time countdowns to specific datetimes
        - Automatic T-0 announcements
        - Channel-scoped (each channel has its own countdowns)
        - Persistent storage via NATS storage API
        - Recovery on restart (loads pending countdowns)
    """
    
    # Plugin metadata
    NAMESPACE = "countdown"
    VERSION = "1.0.0"
    DESCRIPTION = "Track countdowns to events"
    REQUIRED_MIGRATIONS = [1]  # Migration version this code depends on
    
    # NATS subjects
    SUBJECT_CREATE = "rosey.command.countdown.create"
    SUBJECT_CHECK = "rosey.command.countdown.check"
    SUBJECT_LIST = "rosey.command.countdown.list"
    SUBJECT_DELETE = "rosey.command.countdown.delete"
    
    EVENT_CREATED = "rosey.event.countdown.created"
    EVENT_COMPLETED = "rosey.event.countdown.completed"
    EVENT_DELETED = "rosey.event.countdown.deleted"
    
    # Storage API subjects (via NATS)
    STORAGE_INSERT = f"rosey.db.row.{NAMESPACE}.insert"
    STORAGE_SELECT = f"rosey.db.row.{NAMESPACE}.select"
    STORAGE_UPDATE = f"rosey.db.row.{NAMESPACE}.update"
    STORAGE_DELETE = f"rosey.db.row.{NAMESPACE}.delete"
    MIGRATION_STATUS = f"rosey.db.migrate.{NAMESPACE}.status"
    
    def __init__(self, nats_client: NATS, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the countdown plugin.
        
        Args:
            nats_client: Connected NATS client for messaging.
            config: Optional configuration dictionary.
        """
        self.nats = nats_client
        self.config = config or {}
        self.logger = logging.getLogger(f"plugin.{self.NAMESPACE}")
        
        # Configuration with defaults
        self.check_interval = self.config.get("check_interval", 30.0)
        self.max_countdowns_per_channel = self.config.get("max_countdowns_per_channel", 20)
        self.max_duration_days = self.config.get("max_duration_days", 365)
        self.emit_events = self.config.get("emit_events", True)
        self.announce_completion = self.config.get("announce_completion", True)
        
        # Scheduler
        self.scheduler: Optional[CountdownScheduler] = None
        
        # Subscription tracking
        self._subscriptions = []
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        Initialize the plugin.
        
        - Checks migration status
        - Initializes scheduler
        - Loads pending countdowns
        - Subscribes to NATS subjects
        """
        self.logger.info(f"Initializing {self.NAMESPACE} plugin v{self.VERSION}")
        
        # Check migration status
        await self._check_migrations()
        
        # Initialize scheduler with completion callback
        self.scheduler = CountdownScheduler(
            check_interval=self.check_interval,
            on_complete=self._on_countdown_complete
        )
        
        # Load existing countdowns into scheduler
        pending = await self._load_pending_countdowns()
        for countdown in pending:
            countdown_id = f"{countdown.channel}:{countdown.name}"
            self.scheduler.schedule(countdown_id, countdown.target_time)
        
        # Start scheduler
        await self.scheduler.start()
        
        # Subscribe to command subjects
        sub = await self.nats.subscribe(self.SUBJECT_CREATE, cb=self._handle_create)
        self._subscriptions.append(sub)
        
        sub = await self.nats.subscribe(self.SUBJECT_CHECK, cb=self._handle_check)
        self._subscriptions.append(sub)
        
        sub = await self.nats.subscribe(self.SUBJECT_LIST, cb=self._handle_list)
        self._subscriptions.append(sub)
        
        sub = await self.nats.subscribe(self.SUBJECT_DELETE, cb=self._handle_delete)
        self._subscriptions.append(sub)
        
        self._initialized = True
        self.logger.info(
            f"{self.NAMESPACE} plugin loaded with {len(pending)} pending countdowns"
        )
    
    async def shutdown(self) -> None:
        """
        Shutdown the plugin.
        
        - Stops scheduler
        - Unsubscribes from NATS subjects
        """
        # Stop scheduler
        if self.scheduler:
            await self.scheduler.stop()
        
        # Unsubscribe from all subjects
        for sub in self._subscriptions:
            await sub.unsubscribe()
        self._subscriptions.clear()
        
        self._initialized = False
        self.logger.info(f"{self.NAMESPACE} plugin unloaded")
    
    # =========================================================================
    # Migration Support
    # =========================================================================
    
    async def _check_migrations(self) -> None:
        """
        Check migration status via NATS.
        
        Raises:
            RuntimeError: If migrations not up to date.
        """
        try:
            response = await self.nats.request(
                self.MIGRATION_STATUS,
                b"{}",
                timeout=5.0
            )
            result = json.loads(response.data.decode())
            
            if not result.get("success"):
                raise RuntimeError(
                    f"Failed to check migration status: {result.get('error', 'unknown')}"
                )
            
            current_version = result.get("current_version", 0)
            max_required = max(self.REQUIRED_MIGRATIONS)
            
            if current_version < max_required:
                raise RuntimeError(
                    f"Migrations not up to date. Current: {current_version}, "
                    f"Required: {max_required}. "
                    f"Run: db.migrate.{self.NAMESPACE}.apply"
                )
            
            self.logger.info(f"Migration check passed (version: {current_version})")
            
        except asyncio.TimeoutError:
            self.logger.warning(
                "Migration status check timed out - assuming migrations applied"
            )
    
    # =========================================================================
    # Storage Operations (via NATS)
    # =========================================================================
    
    async def _storage_insert(self, countdown: Countdown) -> int:
        """
        Insert a countdown into storage via NATS.
        
        Args:
            countdown: Countdown to insert.
            
        Returns:
            The ID of the inserted countdown.
            
        Raises:
            Exception: On storage error.
        """
        payload = {
            "table": "countdowns",
            "data": {
                "name": countdown.name,
                "channel": countdown.channel,
                "target_time": countdown.target_time.isoformat(),
                "created_by": countdown.created_by,
                "created_at": countdown.created_at.isoformat(),
                "is_recurring": countdown.is_recurring,
                "recurrence_rule": countdown.recurrence_rule,
                "completed": countdown.completed,
            }
        }
        
        try:
            response = await self.nats.request(
                self.STORAGE_INSERT,
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            return result["id"]
            
        except asyncio.TimeoutError:
            self.logger.error("NATS timeout inserting countdown")
            raise
    
    async def _storage_get_by_name(
        self, channel: str, name: str
    ) -> Optional[Countdown]:
        """
        Get a countdown by channel and name via NATS.
        
        Args:
            channel: Channel to search in.
            name: Countdown name.
            
        Returns:
            Countdown if found, None otherwise.
        """
        payload = {
            "table": "countdowns",
            "filters": {
                "channel": {"$eq": channel},
                "name": {"$eq": name}
            },
            "limit": 1
        }
        
        try:
            response = await self.nats.request(
                self.STORAGE_SELECT,
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            rows = result.get("rows", [])
            
            if rows:
                return Countdown.from_dict(rows[0])
            return None
            
        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout getting countdown {channel}:{name}")
            raise
    
    async def _storage_get_for_channel(self, channel: str) -> List[Countdown]:
        """
        Get all active (non-completed) countdowns for a channel.
        
        Args:
            channel: Channel to get countdowns for.
            
        Returns:
            List of active countdowns.
        """
        payload = {
            "table": "countdowns",
            "filters": {
                "channel": {"$eq": channel},
                "completed": {"$eq": False}
            },
            "order_by": [{"field": "target_time", "direction": "asc"}],
            "limit": self.max_countdowns_per_channel
        }
        
        try:
            response = await self.nats.request(
                self.STORAGE_SELECT,
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            rows = result.get("rows", [])
            
            return [Countdown.from_dict(row) for row in rows]
            
        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout getting countdowns for {channel}")
            raise
    
    async def _load_pending_countdowns(self) -> List[Countdown]:
        """
        Load all pending (non-completed) countdowns from storage.
        
        Called during initialization to restore scheduler state.
        
        Returns:
            List of pending countdowns.
        """
        payload = {
            "table": "countdowns",
            "filters": {"completed": {"$eq": False}},
            "limit": 1000  # Reasonable upper bound
        }
        
        try:
            response = await self.nats.request(
                self.STORAGE_SELECT,
                json.dumps(payload).encode(),
                timeout=5.0
            )
            result = json.loads(response.data.decode())
            rows = result.get("rows", [])
            
            return [Countdown.from_dict(row) for row in rows]
            
        except asyncio.TimeoutError:
            self.logger.error("NATS timeout loading pending countdowns")
            return []
        except Exception as e:
            self.logger.error(f"Error loading pending countdowns: {e}")
            return []
    
    async def _storage_mark_completed(self, countdown_id: int) -> None:
        """
        Mark a countdown as completed in storage.
        
        Args:
            countdown_id: Database ID of the countdown.
        """
        payload = {
            "table": "countdowns",
            "filters": {"id": {"$eq": countdown_id}},
            "data": {"completed": True}
        }
        
        try:
            await self.nats.request(
                self.STORAGE_UPDATE,
                json.dumps(payload).encode(),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout marking countdown {countdown_id} completed")
    
    async def _storage_delete(self, channel: str, name: str) -> bool:
        """
        Delete a countdown from storage.
        
        Args:
            channel: Channel of the countdown.
            name: Name of the countdown.
            
        Returns:
            True if deleted, False if not found.
        """
        payload = {
            "table": "countdowns",
            "filters": {
                "channel": {"$eq": channel},
                "name": {"$eq": name}
            }
        }
        
        try:
            response = await self.nats.request(
                self.STORAGE_DELETE,
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            return result.get("deleted", 0) > 0
            
        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout deleting countdown {channel}:{name}")
            raise
    
    async def _storage_count_for_channel(self, channel: str) -> int:
        """
        Count active countdowns for a channel.
        
        Args:
            channel: Channel to count for.
            
        Returns:
            Number of active countdowns.
        """
        payload = {
            "table": "countdowns",
            "filters": {
                "channel": {"$eq": channel},
                "completed": {"$eq": False}
            },
            "count_only": True
        }
        
        try:
            response = await self.nats.request(
                self.STORAGE_SELECT,
                json.dumps(payload).encode(),
                timeout=2.0
            )
            result = json.loads(response.data.decode())
            return result.get("count", 0)
            
        except asyncio.TimeoutError:
            self.logger.error(f"NATS timeout counting countdowns for {channel}")
            return 0
    
    # =========================================================================
    # Command Handlers
    # =========================================================================
    
    async def _handle_create(self, msg) -> None:
        """
        Handle !countdown <name> <datetime> command.
        
        Message format:
        {
            "channel": "string",
            "user": "string",
            "args": "movie_night 2025-12-01 20:00",
            "reply_to": "rosey.reply.xyz"
        }
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "unknown")
            user = data.get("user", "anonymous")
            args = data.get("args", "").strip()
            reply_to = data.get("reply_to")
            
            # Parse arguments: <name> <datetime>
            parts = args.split(None, 1)
            if len(parts) < 2:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": "⏰ Usage: !countdown <name> <datetime>\n"
                             "Example: !countdown movie_night 2025-12-01 20:00"
                })
                return
            
            name = parts[0].lower()
            time_str = parts[1]
            
            # Validate name
            if not self._validate_name(name):
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": "⏰ Invalid name. Use letters, numbers, and underscores only."
                })
                return
            
            # Check if name already exists
            existing = await self._storage_get_by_name(channel, name)
            if existing:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ A countdown named '{name}' already exists. "
                             "Delete it first or use a different name."
                })
                return
            
            # Check channel limit
            count = await self._storage_count_for_channel(channel)
            if count >= self.max_countdowns_per_channel:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ This channel has reached the limit of "
                             f"{self.max_countdowns_per_channel} countdowns. Delete some first."
                })
                return
            
            # Parse datetime
            try:
                target_time = parse_datetime(time_str)
            except ValueError as e:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ {e}"
                })
                return
            
            # Check if in past
            if target_time <= datetime.now(timezone.utc):
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": "⏰ That time has already passed! Pick a future time."
                })
                return
            
            # Check max duration
            max_target = datetime.now(timezone.utc) + \
                         __import__('datetime').timedelta(days=self.max_duration_days)
            if target_time > max_target:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ That's too far in the future. Max is {self.max_duration_days} days."
                })
                return
            
            # Create countdown
            countdown = Countdown(
                name=name,
                channel=channel,
                target_time=target_time,
                created_by=user
            )
            
            # Store in database
            countdown.id = await self._storage_insert(countdown)
            
            # Schedule in memory
            countdown_id = f"{channel}:{name}"
            self.scheduler.schedule(countdown_id, target_time)
            
            # Format response
            remaining = countdown.format_remaining()
            
            await self._send_reply(reply_to, {
                "success": True,
                "result": {
                    "name": name,
                    "target_time": target_time.isoformat(),
                    "created_by": user,
                    "channel": channel,
                    "remaining": remaining,
                    "message": f"⏰ Countdown '{name}' created! Time remaining: {remaining}"
                }
            })
            
            # Emit event
            if self.emit_events:
                await self._emit_event(self.EVENT_CREATED, {
                    "channel": channel,
                    "user": user,
                    "countdown": countdown.to_dict()
                })
            
            self.logger.info(f"Created countdown {channel}:{name} for {target_time}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in create request: {e}")
        except Exception as e:
            self.logger.exception(f"Error handling create: {e}")
            if "reply_to" in dir() and reply_to:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": "⏰ An error occurred creating the countdown."
                })
    
    async def _handle_check(self, msg) -> None:
        """
        Handle !countdown <name> command to check remaining time.
        
        Message format:
        {
            "channel": "string",
            "user": "string",
            "args": "movie_night",
            "reply_to": "rosey.reply.xyz"
        }
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "unknown")
            name = data.get("args", "").strip().lower()
            reply_to = data.get("reply_to")
            
            if not name:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": "⏰ Usage: !countdown <name>"
                })
                return
            
            # Look up countdown
            countdown = await self._storage_get_by_name(channel, name)
            
            if not countdown:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ No countdown named '{name}' found in this channel"
                })
                return
            
            remaining = countdown.format_remaining()
            
            await self._send_reply(reply_to, {
                "success": True,
                "result": {
                    "name": name,
                    "target_time": countdown.target_time.isoformat(),
                    "remaining": remaining,
                    "message": f"⏰ '{name}' — {remaining} remaining"
                }
            })
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in check request: {e}")
        except Exception as e:
            self.logger.exception(f"Error handling check: {e}")
    
    async def _handle_list(self, msg) -> None:
        """
        Handle !countdown list command.
        
        Message format:
        {
            "channel": "string",
            "user": "string",
            "args": "",
            "reply_to": "rosey.reply.xyz"
        }
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "unknown")
            reply_to = data.get("reply_to")
            
            # Get all countdowns for channel
            countdowns = await self._storage_get_for_channel(channel)
            
            if not countdowns:
                await self._send_reply(reply_to, {
                    "success": True,
                    "result": {
                        "countdowns": [],
                        "message": "⏰ No active countdowns in this channel"
                    }
                })
                return
            
            # Format list
            countdown_list = []
            lines = ["⏰ Active countdowns:"]
            
            for cd in countdowns:
                remaining = cd.format_remaining(short=True)
                countdown_list.append({
                    "name": cd.name,
                    "remaining": remaining
                })
                lines.append(f"  • {cd.name} — {remaining}")
            
            await self._send_reply(reply_to, {
                "success": True,
                "result": {
                    "countdowns": countdown_list,
                    "message": "\n".join(lines)
                }
            })
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in list request: {e}")
        except Exception as e:
            self.logger.exception(f"Error handling list: {e}")
    
    async def _handle_delete(self, msg) -> None:
        """
        Handle !countdown delete <name> command.
        
        Message format:
        {
            "channel": "string",
            "user": "string",
            "args": "movie_night",
            "reply_to": "rosey.reply.xyz"
        }
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "unknown")
            user = data.get("user", "anonymous")
            name = data.get("args", "").strip().lower()
            reply_to = data.get("reply_to")
            
            if not name:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": "⏰ Usage: !countdown delete <name>"
                })
                return
            
            # Check if exists
            countdown = await self._storage_get_by_name(channel, name)
            if not countdown:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ No countdown named '{name}' found in this channel"
                })
                return
            
            # Delete from storage
            await self._storage_delete(channel, name)
            
            # Remove from scheduler
            countdown_id = f"{channel}:{name}"
            self.scheduler.cancel(countdown_id)
            
            await self._send_reply(reply_to, {
                "success": True,
                "result": {
                    "name": name,
                    "message": f"⏰ Countdown '{name}' deleted."
                }
            })
            
            # Emit event
            if self.emit_events:
                await self._emit_event(self.EVENT_DELETED, {
                    "channel": channel,
                    "user": user,
                    "countdown_name": name
                })
            
            self.logger.info(f"Deleted countdown {channel}:{name}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in delete request: {e}")
        except Exception as e:
            self.logger.exception(f"Error handling delete: {e}")
    
    # =========================================================================
    # Completion Handling
    # =========================================================================
    
    async def _on_countdown_complete(self, countdown_id: str) -> None:
        """
        Called by scheduler when a countdown reaches T-0.
        
        Args:
            countdown_id: The "channel:name" identifier.
        """
        try:
            channel, name = countdown_id.split(":", 1)
            countdown = await self._storage_get_by_name(channel, name)
            
            if not countdown or countdown.completed:
                return
            
            # Mark as completed in storage
            await self._storage_mark_completed(countdown.id)
            
            # Announce completion
            if self.announce_completion:
                await self._announce_completion(countdown)
            
            # Emit event
            if self.emit_events:
                await self._emit_event(self.EVENT_COMPLETED, {
                    "channel": channel,
                    "countdown": countdown.to_dict(),
                    "message": f"🎉 TIME'S UP! '{name}' has arrived!"
                })
            
            self.logger.info(f"Countdown completed: {countdown_id}")
            
        except Exception as e:
            self.logger.exception(f"Error handling completion for {countdown_id}: {e}")
    
    async def _announce_completion(self, countdown: Countdown) -> None:
        """
        Send completion announcement to the channel.
        
        Args:
            countdown: The completed countdown.
        """
        # Publish to channel announcement subject
        announcement = {
            "channel": countdown.channel,
            "message": f"🎉 TIME'S UP! '{countdown.name}' has arrived!",
            "type": "countdown_complete"
        }
        
        # Use the chat subject for channel announcements
        await self.nats.publish(
            f"rosey.chat.{countdown.channel}.send",
            json.dumps(announcement).encode()
        )
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _validate_name(self, name: str) -> bool:
        """
        Validate countdown name.
        
        Names must be alphanumeric with underscores, 1-50 characters.
        
        Args:
            name: Name to validate.
            
        Returns:
            True if valid, False otherwise.
        """
        import re
        return bool(re.match(r'^[a-z0-9_]{1,50}$', name))
    
    async def _send_reply(self, reply_to: Optional[str], response: dict) -> None:
        """
        Send a reply to a command.
        
        Args:
            reply_to: NATS subject to reply to.
            response: Response dictionary.
        """
        if reply_to:
            await self.nats.publish(reply_to, json.dumps(response).encode())
    
    async def _emit_event(self, event_type: str, data: dict) -> None:
        """
        Emit an event via NATS.
        
        Args:
            event_type: The event subject.
            data: Event data.
        """
        event = {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data
        }
        await self.nats.publish(event_type, json.dumps(event).encode())
