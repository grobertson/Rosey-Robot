"""
Global pytest configuration and fixtures for Rosey v1.0 tests

Provides:
- Mock NATS/EventBus
- Mock database service
- Test configuration
- Common test utilities
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom settings"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "plugin: Plugin tests")
    config.addinivalue_line("markers", "core: Core infrastructure tests")


# ============================================================================
# Event Loop Fixture
# ============================================================================

@pytest.fixture(scope="function")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Mock EventBus
# ============================================================================

@pytest.fixture
def mock_event_bus():
    """Mock EventBus for testing without NATS"""
    
    class MockEventBus:
        def __init__(self):
            self.connected = True
            self.subscribers = {}
            self.published_events = []
            
        async def connect(self):
            self.connected = True
            
        async def disconnect(self):
            self.connected = False
            
        async def publish(self, subject: str, data: Dict[str, Any], **kwargs):
            """Record published events"""
            event = {
                'subject': subject,
                'data': data,
                **kwargs
            }
            self.published_events.append(event)
            return event
            
        async def subscribe(self, subject: str, callback, **kwargs):
            """Record subscriptions"""
            if subject not in self.subscribers:
                self.subscribers[subject] = []
            self.subscribers[subject].append(callback)
            return MagicMock(unsubscribe=AsyncMock())
            
        async def request(self, subject: str, data: Dict[str, Any], timeout: float = 5.0):
            """Mock request/reply"""
            return {
                'success': True,
                'data': {'mock': 'response'}
            }
            
        def get_published(self, subject_pattern: Optional[str] = None) -> List[Dict]:
            """Get published events, optionally filtered by subject"""
            if not subject_pattern:
                return self.published_events
            return [e for e in self.published_events if subject_pattern in e['subject']]
            
        def clear_published(self):
            """Clear published events history"""
            self.published_events.clear()
    
    return MockEventBus()


# ============================================================================
# Mock Database Service
# ============================================================================

@pytest.fixture
def mock_database():
    """Mock database service for testing without actual database"""
    
    class MockDatabase:
        def __init__(self):
            self.data = {}  # Simple in-memory storage
            self.started = False
            
        async def start(self):
            self.started = True
            
        async def stop(self):
            self.started = False
            
        async def kv_get(self, namespace: str, key: str) -> Optional[Any]:
            """Mock KV get"""
            ns_data = self.data.get(namespace, {})
            return ns_data.get(key)
            
        async def kv_set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None):
            """Mock KV set"""
            if namespace not in self.data:
                self.data[namespace] = {}
            self.data[namespace][key] = value
            
        async def kv_delete(self, namespace: str, key: str):
            """Mock KV delete"""
            if namespace in self.data:
                self.data[namespace].pop(key, None)
                
        async def row_insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
            """Mock row insert"""
            if table not in self.data:
                self.data[table] = []
            row = {'id': len(self.data[table]) + 1, **data}
            self.data[table].append(row)
            return row
            
        async def row_select(self, table: str, filters: Optional[Dict] = None) -> List[Dict]:
            """Mock row select"""
            rows = self.data.get(table, [])
            if not filters:
                return rows
            # Simple filter implementation
            return [r for r in rows if all(r.get(k) == v for k, v in filters.items())]
            
        async def row_update(self, table: str, filters: Dict, updates: Dict) -> int:
            """Mock row update"""
            rows = self.data.get(table, [])
            count = 0
            for row in rows:
                if all(row.get(k) == v for k, v in filters.items()):
                    row.update(updates)
                    count += 1
            return count
            
        async def row_delete(self, table: str, filters: Dict) -> int:
            """Mock row delete"""
            rows = self.data.get(table, [])
            before = len(rows)
            self.data[table] = [r for r in rows if not all(r.get(k) == v for k, v in filters.items())]
            return before - len(self.data[table])
            
        def clear_data(self):
            """Clear all mock data"""
            self.data.clear()
    
    return MockDatabase()


# ============================================================================
# Test Configuration
# ============================================================================

@pytest.fixture
def test_config():
    """Test configuration object"""
    
    @dataclass
    class TestConfig:
        nats_url: str = "nats://localhost:4222"
        database: Dict[str, Any] = None
        plugin_dir: str = "plugins"
        
        class cytube:
            host: str = "test.cytu.be"
            secure: bool = False
            channel: str = "test-channel"
            username: str = "TestBot"
            
        def get(self, key: str, default: Any = None) -> Any:
            return getattr(self, key, default)
    
    config = TestConfig()
    config.database = {'type': 'sqlite', 'path': ':memory:'}
    return config


# ============================================================================
# Mock CyTube Events
# ============================================================================

@pytest.fixture
def mock_cytube_events():
    """Factory for creating mock CyTube events"""
    
    def create_chat_event(username: str = "TestUser", msg: str = "test message"):
        return {
            'username': username,
            'msg': msg,
            'time': 1234567890,
            'meta': {}
        }
    
    def create_user_join_event(username: str = "TestUser"):
        return {
            'name': username,
            'rank': 1,
            'profile': {}
        }
    
    def create_media_event(title: str = "Test Video", duration: int = 180):
        return {
            'title': title,
            'duration': duration,
            'type': 'yt',
            'id': 'test123'
        }
    
    return type('MockCytubeEvents', (), {
        'chat': create_chat_event,
        'user_join': create_user_join_event,
        'media': create_media_event
    })()


# ============================================================================
# Async Test Utilities
# ============================================================================

@pytest.fixture
def async_timeout():
    """Utility for async timeout in tests"""
    async def wait_for(coro, timeout=1.0):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            pytest.fail(f"Operation timed out after {timeout}s")
    return wait_for
