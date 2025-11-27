"""
plugins/countdown/plugin.py

Countdown timer plugin using NATS-based architecture.

NATS Subjects:
    Command Handlers:
        rosey.command.countdown.create - Create a countdown (one-time or recurring)
        rosey.command.countdown.check - Check remaining time
        rosey.command.countdown.list - List all countdowns
        rosey.command.countdown.delete - Delete a countdown
        rosey.command.countdown.alerts - Configure T-minus alerts
        rosey.command.countdown.pause - Pause a recurring countdown
        rosey.command.countdown.resume - Resume a paused recurring countdown
    
    Events (Published):
        rosey.event.countdown.created - Countdown was created
        rosey.event.countdown.completed - Countdown reached T-0
        rosey.event.countdown.deleted - Countdown was deleted
        rosey.event.countdown.alert - T-minus alert fired
        rosey.event.countdown.recurring.reset - Recurring countdown reset
        rosey.event.countdown.paused - Recurring countdown paused
        rosey.event.countdown.resumed - Recurring countdown resumed
    
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
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from nats.aio.client import Client as NATS

try:
    from .countdown import Countdown, parse_datetime, format_remaining
    from .scheduler import CountdownScheduler
    from .recurrence import RecurrenceRule
    from .alerts import AlertConfig, AlertManager
except ImportError:
    from countdown import Countdown, parse_datetime, format_remaining
    from scheduler import CountdownScheduler
    from recurrence import RecurrenceRule
    from alerts import AlertConfig, AlertManager


class CountdownPlugin:
    """
    Countdown timer plugin.
    
    Commands:
        !countdown <name> <datetime> - Create a one-time countdown
        !countdown <name> every <pattern> - Create recurring countdown
        !countdown <name> - Check remaining time
        !countdown list - List all countdowns in channel
        !countdown delete <name> - Delete a countdown
        !countdown alerts <name> <minutes> - Set T-minus alerts (e.g., 5,1)
        !countdown pause <name> - Pause a recurring countdown
        !countdown resume <name> - Resume a recurring countdown
    
    Features:
        - One-time countdowns to specific datetimes
        - Recurring countdowns (daily, weekly, monthly)
        - T-minus alerts (configurable warnings before T-0)
        - Automatic T-0 announcements
        - Channel-scoped (each channel has its own countdowns)
        - Persistent storage via NATS storage API
        - Recovery on restart (loads pending countdowns)
    """
    
    # Plugin metadata
    NAMESPACE = "countdown"
    VERSION = "2.0.0"
    DESCRIPTION = "Track countdowns to events with recurring and alerts"
    REQUIRED_MIGRATIONS = [1, 2]  # Migration versions this code depends on
    
    # NATS subjects - Commands
    SUBJECT_CREATE = "rosey.command.countdown.create"
    SUBJECT_CHECK = "rosey.command.countdown.check"
    SUBJECT_LIST = "rosey.command.countdown.list"
    SUBJECT_DELETE = "rosey.command.countdown.delete"
    SUBJECT_ALERTS = "rosey.command.countdown.alerts"
    SUBJECT_PAUSE = "rosey.command.countdown.pause"
    SUBJECT_RESUME = "rosey.command.countdown.resume"
    
    # NATS subjects - Events
    EVENT_CREATED = "rosey.event.countdown.created"
    EVENT_COMPLETED = "rosey.event.countdown.completed"
    EVENT_DELETED = "rosey.event.countdown.deleted"
    EVENT_ALERT = "rosey.event.countdown.alert"
    EVENT_RECURRING_RESET = "rosey.event.countdown.recurring.reset"
    EVENT_PAUSED = "rosey.event.countdown.paused"
    EVENT_RESUMED = "rosey.event.countdown.resumed"
    
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
        self.default_alerts = self.config.get("default_alerts", [5, 1])
        self.allow_custom_alerts = self.config.get("allow_custom_alerts", True)
        self.max_alert_minutes = self.config.get("max_alert_minutes", 60)
        
        # Scheduler
        self.scheduler: Optional[CountdownScheduler] = None
        
        # Alert manager
        self.alert_manager: Optional[AlertManager] = None
        
        # Subscription tracking
        self._subscriptions = []
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        Initialize the plugin.
        
        - Checks migration status
        - Initializes scheduler and alert manager
        - Loads pending countdowns
        - Subscribes to NATS subjects
        """
        self.logger.info(f"Initializing {self.NAMESPACE} plugin v{self.VERSION}")
        
        # Check migration status
        await self._check_migrations()
        
        # Initialize alert manager
        self.alert_manager = AlertManager(on_alert=self._on_alert)
        
        # Initialize scheduler with completion callback and alert checking
        self.scheduler = CountdownScheduler(
            check_interval=self.check_interval,
            on_complete=self._on_countdown_complete,
            on_check=self._on_scheduler_check
        )
        
        # Load existing countdowns into scheduler
        pending = await self._load_pending_countdowns()
        for countdown in pending:
            countdown_id = f"{countdown.channel}:{countdown.name}"
            
            # Skip paused recurring countdowns
            if countdown.is_paused:
                continue
            
            self.scheduler.schedule(countdown_id, countdown.target_time)
            
            # Configure alerts if set
            if countdown.alert_minutes:
                try:
                    config = AlertConfig.parse(countdown.alert_minutes)
                    self.alert_manager.configure(countdown_id, config)
                except ValueError:
                    pass  # Invalid config, skip
        
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
        
        sub = await self.nats.subscribe(self.SUBJECT_ALERTS, cb=self._handle_alerts)
        self._subscriptions.append(sub)
        
        sub = await self.nats.subscribe(self.SUBJECT_PAUSE, cb=self._handle_pause)
        self._subscriptions.append(sub)
        
        sub = await self.nats.subscribe(self.SUBJECT_RESUME, cb=self._handle_resume)
        self._subscriptions.append(sub)
        
        self._initialized = True
        self.logger.info(
            f"{self.NAMESPACE} plugin loaded with {len(pending)} pending countdowns"
        )
    
    async def shutdown(self) -> None:
        """
        Shutdown the plugin.
        
        - Stops scheduler
        - Clears alert manager
        - Unsubscribes from NATS subjects
        """
        # Stop scheduler
        if self.scheduler:
            await self.scheduler.stop()
        
        # Clear alert manager
        if self.alert_manager:
            self.alert_manager.clear_all()
        
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
                "is_paused": countdown.is_paused,
                "alert_minutes": countdown.alert_minutes,
                "last_alert_sent": countdown.last_alert_sent,
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
    
    async def _storage_update_target_time(
        self, countdown_id: int, new_target: datetime
    ) -> None:
        """
        Update the target time for a countdown (used for recurring reset).
        
        Args:
            countdown_id: Database ID of the countdown.
            new_target: New target time (UTC).
        """
        payload = {
            "table": "countdowns",
            "filters": {"id": {"$eq": countdown_id}},
            "data": {"target_time": new_target.isoformat()}
        }
        
        try:
            await self.nats.request(
                self.STORAGE_UPDATE,
                json.dumps(payload).encode(),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            self.logger.error(
                f"NATS timeout updating target time for countdown {countdown_id}"
            )
    
    async def _storage_update_alerts(
        self, countdown_id: int, alert_minutes: str
    ) -> None:
        """
        Update alert configuration for a countdown.
        
        Args:
            countdown_id: Database ID of the countdown.
            alert_minutes: Comma-separated minutes string (e.g., "5,1").
        """
        payload = {
            "table": "countdowns",
            "filters": {"id": {"$eq": countdown_id}},
            "data": {"alert_minutes": alert_minutes}
        }
        
        try:
            await self.nats.request(
                self.STORAGE_UPDATE,
                json.dumps(payload).encode(),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            self.logger.error(
                f"NATS timeout updating alerts for countdown {countdown_id}"
            )
    
    async def _storage_update_paused(
        self, countdown_id: int, is_paused: bool
    ) -> None:
        """
        Update paused state for a recurring countdown.
        
        Args:
            countdown_id: Database ID of the countdown.
            is_paused: New paused state.
        """
        payload = {
            "table": "countdowns",
            "filters": {"id": {"$eq": countdown_id}},
            "data": {"is_paused": is_paused}
        }
        
        try:
            await self.nats.request(
                self.STORAGE_UPDATE,
                json.dumps(payload).encode(),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            self.logger.error(
                f"NATS timeout updating paused state for countdown {countdown_id}"
            )
    
    async def _storage_update_last_alert(
        self, countdown_id: int, minutes: int
    ) -> None:
        """
        Update last alert sent for a countdown.
        
        Args:
            countdown_id: Database ID of the countdown.
            minutes: Minutes value of last alert sent.
        """
        payload = {
            "table": "countdowns",
            "filters": {"id": {"$eq": countdown_id}},
            "data": {"last_alert_sent": minutes}
        }
        
        try:
            await self.nats.request(
                self.STORAGE_UPDATE,
                json.dumps(payload).encode(),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            self.logger.error(
                f"NATS timeout updating last alert for countdown {countdown_id}"
            )

    # =========================================================================
    # Command Handlers
    # =========================================================================
    
    async def _handle_create(self, msg) -> None:
        """
        Handle !countdown <name> <datetime|every pattern> command.
        
        Supports both one-time and recurring countdowns:
        - "movie_night 2025-12-01 20:00" - One-time countdown
        - "friday_movie every friday 19:00" - Recurring countdown
        
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
            
            # Parse arguments: <name> <datetime|every pattern>
            parts = args.split(None, 1)
            if len(parts) < 2:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": (
                        "⏰ Usage: !countdown <name> <datetime>\n"
                        "         !countdown <name> every <pattern>\n"
                        "Examples:\n"
                        "  !countdown movie 2025-12-01 20:00\n"
                        "  !countdown movie every friday 19:00"
                    )
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
            
            # Check for recurring pattern
            if time_str.lower().startswith("every "):
                await self._create_recurring(
                    name, time_str[6:], channel, user, reply_to
                )
            else:
                await self._create_oneshot(
                    name, time_str, channel, user, reply_to
                )
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in create request: {e}")
        except Exception as e:
            self.logger.exception(f"Error handling create: {e}")
            if "reply_to" in dir() and reply_to:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": "⏰ An error occurred creating the countdown."
                })
    
    async def _create_oneshot(
        self, name: str, time_str: str, channel: str, user: str, reply_to: str
    ) -> None:
        """
        Create a one-time countdown.
        
        Args:
            name: Countdown name.
            time_str: Datetime string to parse.
            channel: Channel for the countdown.
            user: User creating the countdown.
            reply_to: NATS subject for reply.
        """
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
        max_target = datetime.now(timezone.utc) + timedelta(days=self.max_duration_days)
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
                "is_recurring": False,
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
    
    async def _create_recurring(
        self, name: str, pattern: str, channel: str, user: str, reply_to: str
    ) -> None:
        """
        Create a recurring countdown.
        
        Args:
            name: Countdown name.
            pattern: Recurrence pattern (e.g., "friday 19:00").
            channel: Channel for the countdown.
            user: User creating the countdown.
            reply_to: NATS subject for reply.
        """
        # Parse recurrence pattern
        try:
            rule = RecurrenceRule.parse(pattern)
        except ValueError as e:
            await self._send_reply(reply_to, {
                "success": False,
                "error": f"⏰ {e}"
            })
            return
        
        # Calculate next occurrence
        target_time = rule.next_occurrence()
        
        # Create countdown with recurrence
        countdown = Countdown(
            name=name,
            channel=channel,
            target_time=target_time,
            created_by=user,
            is_recurring=True,
            recurrence_rule=rule.to_string()
        )
        
        # Store in database
        countdown.id = await self._storage_insert(countdown)
        
        # Schedule in memory
        countdown_id = f"{channel}:{name}"
        self.scheduler.schedule(countdown_id, target_time)
        
        # Format response
        remaining = countdown.format_remaining()
        description = rule.describe()
        
        await self._send_reply(reply_to, {
            "success": True,
            "result": {
                "name": name,
                "target_time": target_time.isoformat(),
                "created_by": user,
                "channel": channel,
                "remaining": remaining,
                "is_recurring": True,
                "recurrence": description,
                "message": (
                    f"⏰🔄 Recurring countdown '{name}' created!\n"
                    f"Pattern: {description}\n"
                    f"Next occurrence: {remaining}"
                )
            }
        })
        
        # Emit event
        if self.emit_events:
            await self._emit_event(self.EVENT_CREATED, {
                "channel": channel,
                "user": user,
                "countdown": countdown.to_dict(),
                "is_recurring": True,
                "pattern": description
            })
        
        self.logger.info(
            f"Created recurring countdown {channel}:{name} ({description}), "
            f"next: {target_time}"
        )
    
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
            
            # Build message based on recurring status
            if countdown.is_recurring:
                rule = RecurrenceRule.from_string(countdown.recurrence_rule)
                status = "⏸️ paused" if countdown.is_paused else "active"
                message = (
                    f"⏰🔄 '{name}' (recurring, {status})\n"
                    f"Pattern: {rule.describe()}\n"
                    f"Next: {remaining}"
                )
            else:
                message = f"⏰ '{name}' — {remaining} remaining"
            
            await self._send_reply(reply_to, {
                "success": True,
                "result": {
                    "name": name,
                    "target_time": countdown.target_time.isoformat(),
                    "remaining": remaining,
                    "is_recurring": countdown.is_recurring,
                    "is_paused": countdown.is_paused,
                    "message": message
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
            
            # Remove from alert manager
            self.alert_manager.remove(countdown_id)
            
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
    
    async def _handle_alerts(self, msg) -> None:
        """
        Handle !countdown alerts <name> <minutes> command.
        
        Message format:
        {
            "channel": "string",
            "user": "string",
            "args": "movie_night 5,1",
            "reply_to": "rosey.reply.xyz"
        }
        """
        try:
            data = json.loads(msg.data.decode())
            channel = data.get("channel", "unknown")
            args = data.get("args", "").strip()
            reply_to = data.get("reply_to")
            
            # Parse arguments: <name> <minutes>
            parts = args.split()
            if len(parts) < 2:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": "⏰ Usage: !countdown alerts <name> <minutes>\n"
                             "Example: !countdown alerts movie 5,1"
                })
                return
            
            name = parts[0].lower()
            minutes_str = parts[1]
            
            # Check if countdown exists
            countdown = await self._storage_get_by_name(channel, name)
            if not countdown:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ No countdown named '{name}' found in this channel"
                })
                return
            
            if not self.allow_custom_alerts:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": "⏰ Custom alerts are disabled"
                })
                return
            
            # Parse alert config
            try:
                config = AlertConfig.parse(minutes_str)
            except ValueError as e:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ {e}"
                })
                return
            
            # Update storage
            await self._storage_update_alerts(countdown.id, config.to_string())
            
            # Configure alert manager
            countdown_id = f"{channel}:{name}"
            self.alert_manager.configure(countdown_id, config)
            
            await self._send_reply(reply_to, {
                "success": True,
                "result": {
                    "name": name,
                    "alerts": config.minutes,
                    "message": f"⏰ Alerts set for '{name}': {config}"
                }
            })
            
            self.logger.info(f"Configured alerts for {countdown_id}: {config.minutes}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in alerts request: {e}")
        except Exception as e:
            self.logger.exception(f"Error handling alerts: {e}")
    
    async def _handle_pause(self, msg) -> None:
        """
        Handle !countdown pause <name> command.
        
        Only works for recurring countdowns.
        
        Message format:
        {
            "channel": "string",
            "user": "string",
            "args": "friday_movie",
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
                    "error": "⏰ Usage: !countdown pause <name>"
                })
                return
            
            # Check if countdown exists
            countdown = await self._storage_get_by_name(channel, name)
            if not countdown:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ No countdown named '{name}' found in this channel"
                })
                return
            
            # Verify it's recurring
            if not countdown.is_recurring:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ '{name}' is not a recurring countdown"
                })
                return
            
            # Check if already paused
            if countdown.is_paused:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ '{name}' is already paused"
                })
                return
            
            # Update storage
            await self._storage_update_paused(countdown.id, True)
            
            # Remove from scheduler (won't fire while paused)
            countdown_id = f"{channel}:{name}"
            self.scheduler.cancel(countdown_id)
            
            await self._send_reply(reply_to, {
                "success": True,
                "result": {
                    "name": name,
                    "message": f"⏰⏸️ '{name}' paused. Use !countdown resume to continue."
                }
            })
            
            # Emit event
            if self.emit_events:
                await self._emit_event(self.EVENT_PAUSED, {
                    "channel": channel,
                    "user": user,
                    "countdown_name": name
                })
            
            self.logger.info(f"Paused recurring countdown {countdown_id}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in pause request: {e}")
        except Exception as e:
            self.logger.exception(f"Error handling pause: {e}")
    
    async def _handle_resume(self, msg) -> None:
        """
        Handle !countdown resume <name> command.
        
        Only works for paused recurring countdowns.
        
        Message format:
        {
            "channel": "string",
            "user": "string",
            "args": "friday_movie",
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
                    "error": "⏰ Usage: !countdown resume <name>"
                })
                return
            
            # Check if countdown exists
            countdown = await self._storage_get_by_name(channel, name)
            if not countdown:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ No countdown named '{name}' found in this channel"
                })
                return
            
            # Verify it's recurring
            if not countdown.is_recurring:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ '{name}' is not a recurring countdown"
                })
                return
            
            # Check if actually paused
            if not countdown.is_paused:
                await self._send_reply(reply_to, {
                    "success": False,
                    "error": f"⏰ '{name}' is not paused"
                })
                return
            
            # Calculate next occurrence from now
            rule = RecurrenceRule.from_string(countdown.recurrence_rule)
            next_target = rule.next_occurrence()
            
            # Update storage
            await self._storage_update_paused(countdown.id, False)
            await self._storage_update_target_time(countdown.id, next_target)
            
            # Add back to scheduler
            countdown_id = f"{channel}:{name}"
            self.scheduler.schedule(countdown_id, next_target)
            
            # Reset alert tracking
            self.alert_manager.reset(countdown_id)
            
            remaining = format_remaining(next_target - datetime.now(timezone.utc))
            
            await self._send_reply(reply_to, {
                "success": True,
                "result": {
                    "name": name,
                    "next_target": next_target.isoformat(),
                    "remaining": remaining,
                    "message": f"⏰▶️ '{name}' resumed! Next: {remaining}"
                }
            })
            
            # Emit event
            if self.emit_events:
                await self._emit_event(self.EVENT_RESUMED, {
                    "channel": channel,
                    "user": user,
                    "countdown_name": name,
                    "next_target": next_target.isoformat()
                })
            
            self.logger.info(f"Resumed recurring countdown {countdown_id}, next: {next_target}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in resume request: {e}")
        except Exception as e:
            self.logger.exception(f"Error handling resume: {e}")

    # =========================================================================
    # Completion Handling
    # =========================================================================
    
    async def _on_countdown_complete(self, countdown_id: str) -> None:
        """
        Called by scheduler when a countdown reaches T-0.
        
        For one-time countdowns: marks as completed.
        For recurring countdowns: resets to next occurrence.
        
        Args:
            countdown_id: The "channel:name" identifier.
        """
        try:
            channel, name = countdown_id.split(":", 1)
            countdown = await self._storage_get_by_name(channel, name)
            
            if not countdown or countdown.completed:
                return
            
            # Announce completion
            if self.announce_completion:
                await self._announce_completion(countdown)
            
            # Emit completion event
            if self.emit_events:
                await self._emit_event(self.EVENT_COMPLETED, {
                    "channel": channel,
                    "countdown": countdown.to_dict(),
                    "message": f"🎉 TIME'S UP! '{name}' has arrived!"
                })
            
            # Handle recurring vs one-time
            if countdown.is_recurring and not countdown.is_paused:
                await self._reset_recurring(countdown)
            else:
                # One-time: mark as completed
                await self._storage_mark_completed(countdown.id)
                # Remove from alert manager
                self.alert_manager.remove(countdown_id)
            
            self.logger.info(f"Countdown completed: {countdown_id}")
            
        except Exception as e:
            self.logger.exception(f"Error handling completion for {countdown_id}: {e}")
    
    async def _reset_recurring(self, countdown: Countdown) -> None:
        """
        Reset a recurring countdown to its next occurrence.
        
        Args:
            countdown: The recurring countdown to reset.
        """
        try:
            rule = RecurrenceRule.from_string(countdown.recurrence_rule)
            previous_target = countdown.target_time
            next_target = rule.next_occurrence()
            
            # Update target time in storage
            await self._storage_update_target_time(countdown.id, next_target)
            
            # Reschedule
            countdown_id = f"{countdown.channel}:{countdown.name}"
            self.scheduler.schedule(countdown_id, next_target)
            
            # Reset alert tracking
            self.alert_manager.reset(countdown_id)
            
            # Emit recurring reset event
            if self.emit_events:
                await self._emit_event(self.EVENT_RECURRING_RESET, {
                    "channel": countdown.channel,
                    "countdown": {
                        "name": countdown.name,
                        "previous_target": previous_target.isoformat(),
                        "next_target": next_target.isoformat()
                    }
                })
            
            # Announce next occurrence
            remaining = format_remaining(next_target - datetime.now(timezone.utc))
            await self.nats.publish(
                f"rosey.chat.{countdown.channel}.send",
                json.dumps({
                    "channel": countdown.channel,
                    "message": f"⏰🔄 '{countdown.name}' will repeat. Next: {remaining}",
                    "type": "countdown_recurring_reset"
                }).encode()
            )
            
            self.logger.info(
                f"Recurring countdown reset: {countdown.channel}:{countdown.name} "
                f"-> {next_target}"
            )
            
        except Exception as e:
            self.logger.exception(f"Error resetting recurring countdown: {e}")
    
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
    # Alert Handling
    # =========================================================================
    
    async def _on_scheduler_check(
        self, countdown_id: str, remaining: timedelta
    ) -> None:
        """
        Called by scheduler during each check loop for alert processing.
        
        Args:
            countdown_id: The "channel:name" identifier.
            remaining: Time remaining until T-0.
        """
        # Check if any alerts should fire
        alerts = self.alert_manager.check_alerts(countdown_id, remaining)
        
        if alerts:
            # Get countdown info for announcement
            channel, name = countdown_id.split(":", 1)
            countdown = await self._storage_get_by_name(channel, name)
            
            if countdown:
                for minutes in alerts:
                    await self._fire_alert(countdown, minutes)
    
    async def _on_alert(self, countdown_id: str, minutes: int) -> None:
        """
        Called by alert manager when an alert fires.
        
        Note: This is called by AlertManager.process_alerts if using that method.
        We use check_alerts directly in _on_scheduler_check instead.
        
        Args:
            countdown_id: The "channel:name" identifier.
            minutes: Minutes value of the alert.
        """
        channel, name = countdown_id.split(":", 1)
        countdown = await self._storage_get_by_name(channel, name)
        
        if countdown:
            await self._fire_alert(countdown, minutes)
    
    async def _fire_alert(self, countdown: Countdown, minutes: int) -> None:
        """
        Fire a T-minus alert for a countdown.
        
        Args:
            countdown: The countdown triggering the alert.
            minutes: Minutes before T-0.
        """
        try:
            plural = "" if minutes == 1 else "s"
            message = f"⏰ {minutes} minute{plural} until '{countdown.name}'!"
            
            # Send to channel
            await self.nats.publish(
                f"rosey.chat.{countdown.channel}.send",
                json.dumps({
                    "channel": countdown.channel,
                    "message": message,
                    "type": "countdown_alert"
                }).encode()
            )
            
            # Emit event
            if self.emit_events:
                await self._emit_event(self.EVENT_ALERT, {
                    "channel": countdown.channel,
                    "countdown": {
                        "name": countdown.name,
                        "target_time": countdown.target_time.isoformat()
                    },
                    "minutes_remaining": minutes,
                    "message": message
                })
            
            # Update last alert sent in storage
            await self._storage_update_last_alert(countdown.id, minutes)
            
            self.logger.info(
                f"Alert fired: {countdown.channel}:{countdown.name} T-{minutes}"
            )
            
        except Exception as e:
            self.logger.exception(
                f"Error firing alert for {countdown.channel}:{countdown.name}: {e}"
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
