"""
Mock NATS client for testing without requiring a real NATS server
"""
import asyncio
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class MockMsg:
    """Mock NATS message"""
    subject: str
    data: bytes
    reply: Optional[str] = None

    def respond(self, data: bytes):
        """Mock respond method"""
        pass


class MockSubscription:
    """Mock NATS subscription"""

    _id_counter = 0

    def __init__(self, subject: str, callback: Callable):
        self.subject = subject
        self.callback = callback
        self.queue = asyncio.Queue()
        self._task = None

        # Generate unique ID for subscription
        MockSubscription._id_counter += 1
        self._id = MockSubscription._id_counter

    async def start(self):
        """Start processing messages"""
        self._task = asyncio.create_task(self._process())

    async def _process(self):
        """Process queued messages"""
        while True:
            try:
                msg = await self.queue.get()
                if msg is None:  # Shutdown signal
                    break
                await self.callback(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in mock subscription: {e}")

    async def unsubscribe(self):
        """Stop subscription"""
        if self._task:
            await self.queue.put(None)
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


class MockNATSClient:
    """
    Mock NATS client for testing

    Simulates NATS pub/sub without requiring actual server
    """

    def __init__(self):
        self.is_connected = False
        self.subscriptions: Dict[str, List[MockSubscription]] = {}
        self.subscription_by_id: Dict[int, MockSubscription] = {}  # Track by ID
        self._js = None

    async def connect(self, servers=None, **kwargs):
        """Mock connect"""
        self.is_connected = True

    async def drain(self):
        """Mock drain"""
        await self.close()

    async def close(self):
        """Mock close"""
        # Unsubscribe all
        for subs_list in self.subscriptions.values():
            for sub in subs_list:
                await sub.unsubscribe()

        self.subscriptions.clear()
        self.is_connected = False

    async def publish(self, subject: str, payload: bytes, reply: str = "", headers=None):
        """
        Mock publish - deliver to matching subscriptions
        """
        msg = MockMsg(subject=subject, data=payload, reply=reply)

        # Find matching subscriptions (only active ones)
        for sub_pattern, subs_list in list(self.subscriptions.items()):
            if self._matches(subject, sub_pattern):
                for sub in subs_list:
                    # Only deliver to active subscriptions
                    if sub._task and not sub._task.done():
                        await sub.queue.put(msg)

    async def subscribe(self, subject: str, cb: Callable, queue: str = ""):
        """Mock subscribe"""
        sub = MockSubscription(subject, cb)

        if subject not in self.subscriptions:
            self.subscriptions[subject] = []

        self.subscriptions[subject].append(sub)
        self.subscription_by_id[sub._id] = sub  # Track by ID
        await sub.start()

        return sub

    async def unsubscribe_by_subject(self, subject: str):
        """Unsubscribe all subscriptions for a subject (for testing)"""
        if subject in self.subscriptions:
            subs = self.subscriptions[subject]
            for sub in subs:
                await sub.unsubscribe()
                if sub._id in self.subscription_by_id:
                    del self.subscription_by_id[sub._id]
            del self.subscriptions[subject]

    async def request(self, subject: str, payload: bytes, timeout: float = 1.0):
        """Mock request/reply"""
        # Create response future
        response_future = asyncio.Future()

        # Create temporary inbox subscription
        inbox = f"_INBOX.{id(response_future)}"

        async def reply_handler(msg):
            if not response_future.done():
                response_future.set_result(msg)

        sub = await self.subscribe(inbox, reply_handler)

        try:
            # Publish request with reply inbox
            await self.publish(subject, payload, reply=inbox)

            # Wait for response
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return response

        finally:
            await sub.unsubscribe()

    def jetstream(self):
        """Mock JetStream"""
        if self._js is None:
            self._js = MockJetStream()
        return self._js

    @staticmethod
    def _matches(subject: str, pattern: str) -> bool:
        """
        Check if subject matches subscription pattern

        Supports:
        - Exact match: "rosey.events.message"
        - Single wildcard (*): "rosey.events.*"
        - Multi wildcard (>): "rosey.events.>"
        """
        if subject == pattern:
            return True

        subject_parts = subject.split('.')
        pattern_parts = pattern.split('.')

        for i, pattern_part in enumerate(pattern_parts):
            if pattern_part == '>':
                # Multi-level wildcard matches rest
                return True

            if i >= len(subject_parts):
                return False

            if pattern_part == '*':
                # Single-level wildcard matches one token
                continue

            if pattern_part != subject_parts[i]:
                return False

        # All parts matched
        return len(subject_parts) == len(pattern_parts)


class MockJetStream:
    """Mock NATS JetStream"""

    def __init__(self):
        self.streams: Dict[str, List[bytes]] = {}

    async def add_stream(self, name: str, subjects: List[str], **kwargs):
        """Mock add stream"""
        if name not in self.streams:
            self.streams[name] = []

    async def publish(self, subject: str, payload: bytes, **kwargs):
        """Mock JetStream publish"""
        # Store in all matching streams
        for stream_name in self.streams:
            self.streams[stream_name].append(payload)

    async def subscribe(self, subject: str, **kwargs):
        """Mock JetStream subscribe"""
        return MockSubscription(subject, lambda msg: None)


def create_mock_nats():
    """Factory function to create mock NATS client"""
    mock = MockNATSClient()
    mock.is_connected = True  # Pre-connect it
    return mock
