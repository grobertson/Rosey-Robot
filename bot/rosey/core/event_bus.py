"""
Event Bus for NATS-based messaging

Provides a high-level interface to NATS for event-driven communication.
Wraps nats-py with Rosey-specific functionality.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext

from bot.rosey.core.subjects import Subjects

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Event:
    """
    Event message for NATS communication
    
    Represents a single event/message in the system.
    All communication between components uses Event objects.
    
    Attributes:
        subject: NATS subject (routing key)
        event_type: Type of event (message, user.join, etc.)
        source: Component that created the event
        data: Event payload (dict)
        correlation_id: Unique ID for tracking related events
        timestamp: When event was created
        priority: Message priority
        metadata: Additional metadata
    """
    subject: str
    event_type: str
    source: str
    data: Dict[str, Any]
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    priority: Priority = Priority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert event to dictionary for serialization
        
        Returns:
            Dictionary representation of event
        """
        result = asdict(self)
        # Convert priority enum to value
        result['priority'] = self.priority.value
        return result
    
    def to_json(self) -> str:
        """
        Convert event to JSON string
        
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict())
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Event':
        """
        Create event from dictionary
        
        Args:
            data: Dictionary with event data
        
        Returns:
            Event instance
        """
        # Convert priority value to enum
        priority_value = data.pop('priority', Priority.NORMAL.value)
        if isinstance(priority_value, int):
            priority = Priority(priority_value)
        else:
            priority = priority_value
        
        return Event(
            **data,
            priority=priority
        )
    
    @staticmethod
    def from_json(json_str: str) -> 'Event':
        """
        Create event from JSON string
        
        Args:
            json_str: JSON string with event data
        
        Returns:
            Event instance
        """
        data = json.loads(json_str)
        return Event.from_dict(data)


class EventBus:
    """
    Event Bus for NATS-based messaging
    
    High-level interface to NATS with:
    - Simple publish/subscribe
    - Request/reply pattern
    - JetStream for persistence
    - Automatic reconnection
    - Connection state management
    
    Example:
        bus = EventBus(servers=["nats://localhost:4222"])
        await bus.connect()
        
        # Publish
        event = Event(
            subject="rosey.events.message",
            event_type="message",
            source="cytube",
            data={"text": "hello"}
        )
        await bus.publish(event)
        
        # Subscribe
        async def handler(event):
            print(f"Received: {event.data}")
        
        await bus.subscribe("rosey.events.>", handler)
        
        # Cleanup
        await bus.disconnect()
    """
    
    def __init__(
        self,
        servers: List[str] = None,
        name: str = "rosey-bot",
        max_reconnect_attempts: int = 60,
        reconnect_wait: float = 2.0
    ):
        """
        Initialize EventBus
        
        Args:
            servers: List of NATS server URLs
            name: Client name for NATS
            max_reconnect_attempts: Max reconnection attempts
            reconnect_wait: Seconds between reconnection attempts
        """
        self.servers = servers or ["nats://localhost:4222"]
        self.name = name
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_wait = reconnect_wait
        
        self._nc: Optional[NATS] = None
        self._js: Optional[JetStreamContext] = None
        self._subscriptions: Dict[str, int] = {}  # subject -> subscription id
        self._reconnecting = False
        
        # Callbacks
        self._on_connect_callbacks: List[Callable] = []
        self._on_disconnect_callbacks: List[Callable] = []
        self._on_error_callbacks: List[Callable] = []
    
    async def connect(self):
        """
        Connect to NATS server
        
        Establishes connection and sets up JetStream.
        
        Raises:
            Exception: If connection fails
        """
        if self._nc and self._nc.is_connected:
            logger.warning("Already connected to NATS")
            return
        
        logger.info(f"Connecting to NATS: {self.servers}")
        
        try:
            self._nc = await nats.connect(
                servers=self.servers,
                name=self.name,
                max_reconnect_attempts=self.max_reconnect_attempts,
                reconnect_time_wait=self.reconnect_wait,
                error_cb=self._error_cb,
                disconnected_cb=self._disconnected_cb,
                reconnected_cb=self._reconnected_cb,
                closed_cb=self._closed_cb,
            )
            
            # Setup JetStream
            self._js = self._nc.jetstream()
            
            logger.info("Connected to NATS successfully")
            
            # Call connect callbacks
            for callback in self._on_connect_callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
        
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}", exc_info=True)
            raise
    
    async def disconnect(self):
        """Disconnect from NATS server"""
        if not self._nc:
            return
        
        logger.info("Disconnecting from NATS...")
        
        try:
            # Drain and close connection
            await self._nc.drain()
            await self._nc.close()
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
        finally:
            self._nc = None
            self._js = None
            self._subscriptions.clear()
        
        logger.info("Disconnected from NATS")
    
    def is_connected(self) -> bool:
        """Check if connected to NATS"""
        return self._nc is not None and self._nc.is_connected
    
    # ========== Publishing ==========
    
    async def publish(self, event: Event, headers: Dict[str, str] = None):
        """
        Publish event to NATS (at-most-once delivery)
        
        Args:
            event: Event to publish
            headers: Optional NATS headers
        
        Raises:
            RuntimeError: If not connected
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to NATS")
        
        try:
            payload = event.to_json().encode('utf-8')
            await self._nc.publish(
                event.subject,
                payload,
                headers=headers
            )
            
            logger.debug(f"Published to {event.subject}: {event.event_type}")
        
        except Exception as e:
            logger.error(f"Failed to publish to {event.subject}: {e}")
            raise
    
    async def publish_js(
        self,
        event: Event,
        stream: str = None,
        headers: Dict[str, str] = None
    ):
        """
        Publish event with JetStream (at-least-once delivery)
        
        Args:
            event: Event to publish
            stream: JetStream stream name (optional)
            headers: Optional NATS headers
        
        Returns:
            JetStream publish acknowledgment
        
        Raises:
            RuntimeError: If not connected or JetStream not available
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to NATS")
        
        if not self._js:
            raise RuntimeError("JetStream not available")
        
        try:
            payload = event.to_json().encode('utf-8')
            ack = await self._js.publish(
                event.subject,
                payload,
                headers=headers,
                stream=stream
            )
            
            logger.debug(f"Published (JS) to {event.subject}: {event.event_type}")
            return ack
        
        except Exception as e:
            logger.error(f"Failed to publish (JS) to {event.subject}: {e}")
            raise
    
    # ========== Subscribing ==========
    
    async def subscribe(
        self,
        subject: str,
        callback: Callable,
        queue: str = None
    ) -> int:
        """
        Subscribe to subject with callback
        
        Args:
            subject: Subject pattern to subscribe to
            callback: Async function to handle events
            queue: Optional queue group name
        
        Returns:
            Subscription ID
        
        Example:
            async def handler(event):
                print(f"Got: {event.data}")
            
            sub_id = await bus.subscribe("rosey.events.>", handler)
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to NATS")
        
        async def wrapper(msg):
            """Wrapper to convert NATS message to Event"""
            try:
                event = Event.from_json(msg.data.decode('utf-8'))
                
                # Call user callback
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            
            except Exception as e:
                logger.error(
                    f"Error in subscription callback for {subject}: {e}",
                    exc_info=True
                )
        
        try:
            sub = await self._nc.subscribe(subject, queue=queue, cb=wrapper)
            self._subscriptions[subject] = sub._id
            
            logger.debug(f"Subscribed to {subject}")
            return sub._id
        
        except Exception as e:
            logger.error(f"Failed to subscribe to {subject}: {e}")
            raise
    
    async def unsubscribe(self, subject: str):
        """
        Unsubscribe from subject
        
        Args:
            subject: Subject to unsubscribe from
        """
        if subject in self._subscriptions:
            sub_id = self._subscriptions[subject]
            # Note: In nats-py, subscriptions are managed automatically
            # We just remove from our tracking
            del self._subscriptions[subject]
            logger.debug(f"Unsubscribed from {subject}")
    
    # ========== Request/Reply ==========
    
    async def request(
        self,
        subject: str,
        data: Dict[str, Any],
        timeout: float = 5.0
    ) -> Dict[str, Any]:
        """
        Send request and wait for reply
        
        Args:
            subject: Subject to send request to
            data: Request data
            timeout: Timeout in seconds
        
        Returns:
            Reply data as dictionary
        
        Raises:
            TimeoutError: If no reply within timeout
            RuntimeError: If not connected
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to NATS")
        
        try:
            # Create request event
            event = Event(
                subject=subject,
                event_type="request",
                source=self.name,
                data=data
            )
            
            # Send request
            msg = await self._nc.request(
                subject,
                event.to_json().encode('utf-8'),
                timeout=timeout
            )
            
            # Parse reply
            reply_data = json.loads(msg.data.decode('utf-8'))
            
            logger.debug(f"Request to {subject} got reply")
            return reply_data
        
        except asyncio.TimeoutError:
            logger.error(f"Request to {subject} timed out after {timeout}s")
            raise TimeoutError(f"Request to {subject} timed out")
        
        except Exception as e:
            logger.error(f"Request to {subject} failed: {e}")
            raise
    
    async def reply(self, msg, data: Dict[str, Any]):
        """
        Send reply to a request
        
        Args:
            msg: Original NATS message to reply to
            data: Reply data
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to NATS")
        
        try:
            reply_json = json.dumps(data)
            await self._nc.publish(
                msg.reply,
                reply_json.encode('utf-8')
            )
        
        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            raise
    
    # ========== JetStream Management ==========
    
    async def create_stream(
        self,
        name: str,
        subjects: List[str],
        retention: str = "limits",
        max_msgs: int = 10000,
        max_bytes: int = 1024 * 1024 * 100  # 100MB
    ):
        """
        Create JetStream stream
        
        Args:
            name: Stream name
            subjects: Subjects to store
            retention: Retention policy ("limits", "interest", "workqueue")
            max_msgs: Maximum messages to retain
            max_bytes: Maximum bytes to retain
        """
        if not self._js:
            raise RuntimeError("JetStream not available")
        
        try:
            await self._js.add_stream(
                name=name,
                subjects=subjects,
                retention=retention,
                max_msgs=max_msgs,
                max_bytes=max_bytes
            )
            
            logger.info(f"Created JetStream stream: {name}")
        
        except Exception as e:
            logger.error(f"Failed to create stream {name}: {e}")
            raise
    
    # ========== Connection Callbacks ==========
    
    def on_connect(self, callback: Callable):
        """Register callback for connection events"""
        self._on_connect_callbacks.append(callback)
    
    def on_disconnect(self, callback: Callable):
        """Register callback for disconnection events"""
        self._on_disconnect_callbacks.append(callback)
    
    def on_error(self, callback: Callable):
        """Register callback for error events"""
        self._on_error_callbacks.append(callback)
    
    # ========== NATS Event Handlers ==========
    
    async def _error_cb(self, e):
        """Handle NATS errors"""
        logger.error(f"NATS error: {e}")
        for callback in self._on_error_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback(e)
            else:
                callback(e)
    
    async def _disconnected_cb(self):
        """Handle NATS disconnection"""
        logger.warning("Disconnected from NATS")
        for callback in self._on_disconnect_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()
    
    async def _reconnected_cb(self):
        """Handle NATS reconnection"""
        logger.info("Reconnected to NATS")
        for callback in self._on_connect_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()
    
    async def _closed_cb(self):
        """Handle NATS connection closed"""
        logger.info("NATS connection closed")


# ========== Global Instance ==========

_event_bus: Optional[EventBus] = None


async def initialize_event_bus(**kwargs) -> EventBus:
    """
    Initialize global EventBus instance
    
    Args:
        **kwargs: Arguments for EventBus constructor
    
    Returns:
        EventBus instance
    """
    global _event_bus
    
    if _event_bus is not None:
        logger.warning("EventBus already initialized")
        return _event_bus
    
    _event_bus = EventBus(**kwargs)
    await _event_bus.connect()
    
    logger.info("Global EventBus initialized")
    return _event_bus


async def get_event_bus() -> EventBus:
    """
    Get global EventBus instance
    
    Returns:
        EventBus instance
    
    Raises:
        RuntimeError: If EventBus not initialized
    """
    if _event_bus is None:
        raise RuntimeError("EventBus not initialized. Call initialize_event_bus() first.")
    
    return _event_bus


async def shutdown_event_bus():
    """Shutdown global EventBus instance"""
    global _event_bus
    
    if _event_bus:
        await _event_bus.disconnect()
        _event_bus = None
        logger.info("Global EventBus shut down")
