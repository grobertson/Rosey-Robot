"""
tests/unit/test_service_registry_sortie5.py

Comprehensive tests for Sprint 8 Sortie 5: Service Registry

Tests service registration, dependency injection, semantic versioning,
lifecycle management, and dependency resolution.
"""

import pytest
import logging

from lib.plugin import (
    Service,
    ServiceRegistry,
    PluginError,
)


# =================================================================
# Test Fixtures - Mock Services
# =================================================================

class MockService(Service):
    """Mock service for testing."""

    def __init__(self, name: str, version: str):
        self._name = name
        self._version = version
        self.start_called = False
        self.stop_called = False

    @property
    def service_name(self) -> str:
        return self._name

    @property
    def service_version(self) -> str:
        return self._version

    async def start(self):
        self.start_called = True

    async def stop(self):
        self.stop_called = True


class FailingService(Service):
    """Service that fails during start/stop for testing error handling."""

    def __init__(self, name: str, version: str, fail_on: str = "start"):
        self._name = name
        self._version = version
        self.fail_on = fail_on

    @property
    def service_name(self) -> str:
        return self._name

    @property
    def service_version(self) -> str:
        return self._version

    async def start(self):
        if self.fail_on == "start":
            raise RuntimeError(f"Service '{self._name}' failed to start")

    async def stop(self):
        if self.fail_on == "stop":
            raise RuntimeError(f"Service '{self._name}' failed to stop")


@pytest.fixture
def logger():
    """Create test logger."""
    return logging.getLogger("test_service_registry")


@pytest.fixture
def registry(logger):
    """Create service registry for testing."""
    return ServiceRegistry(logger)


@pytest.fixture
def weather_service():
    """Create weather service instance."""
    return MockService("weather", "1.0.0")


@pytest.fixture
def location_service():
    """Create location service instance."""
    return MockService("location", "1.2.0")


@pytest.fixture
def forecast_service():
    """Create forecast service instance (depends on weather)."""
    return MockService("forecast", "2.0.0")


# =================================================================
# Service Registration Tests
# =================================================================

def test_register_service(registry, weather_service):
    """Test basic service registration."""
    registry.register(weather_service, provider="weather_plugin")

    assert registry.has("weather")
    assert registry.get("weather") == weather_service

    services = registry.list_services()
    assert len(services) == 1
    assert services[0]["name"] == "weather"
    assert services[0]["version"] == "1.0.0"
    assert services[0]["provider"] == "weather_plugin"
    assert not services[0]["started"]


def test_register_service_with_dependencies(registry, forecast_service):
    """Test registering service with dependencies."""
    deps = {"weather": "1.0.0", "location": "1.0.0"}
    registry.register(forecast_service, provider="forecast_plugin", dependencies=deps)

    services = registry.list_services()
    assert len(services) == 1
    assert services[0]["dependencies"] == deps


def test_register_duplicate_service(registry, weather_service):
    """Test registering duplicate service raises error."""
    registry.register(weather_service, provider="plugin_a")

    # Try to register again
    duplicate = MockService("weather", "2.0.0")
    with pytest.raises(PluginError, match="already registered"):
        registry.register(duplicate, provider="plugin_b")


def test_register_invalid_version(registry):
    """Test registering service with invalid version."""
    service = MockService("test", "not-a-version")

    with pytest.raises(PluginError, match="Invalid service version"):
        registry.register(service, provider="test_plugin")


def test_unregister_service(registry, weather_service):
    """Test unregistering service."""
    registry.register(weather_service, provider="weather_plugin")
    assert registry.has("weather")

    registry.unregister("weather")
    assert not registry.has("weather")


def test_unregister_nonexistent_service(registry):
    """Test unregistering non-existent service raises error."""
    with pytest.raises(PluginError, match="not registered"):
        registry.unregister("nonexistent")


@pytest.mark.asyncio
async def test_unregister_started_service(registry, weather_service):
    """Test unregistering started service raises error."""
    registry.register(weather_service, provider="weather_plugin")
    await registry.start("weather")

    with pytest.raises(PluginError, match="while it is started"):
        registry.unregister("weather")

    # Should succeed after stopping
    await registry.stop("weather")
    registry.unregister("weather")
    assert not registry.has("weather")


# =================================================================
# Service Retrieval Tests
# =================================================================

def test_get_service(registry, weather_service):
    """Test retrieving registered service."""
    registry.register(weather_service, provider="weather_plugin")

    retrieved = registry.get("weather")
    assert retrieved == weather_service


def test_get_nonexistent_service(registry):
    """Test getting non-existent service returns None."""
    assert registry.get("nonexistent") is None


def test_get_service_with_version_constraint(registry):
    """Test version constraint checking."""
    service = MockService("weather", "2.0.0")
    registry.register(service, provider="weather_plugin")

    # Compatible version
    assert registry.get("weather", min_version="1.0.0") == service
    assert registry.get("weather", min_version="2.0.0") == service

    # Incompatible version (service is older than required)
    assert registry.get("weather", min_version="3.0.0") is None


def test_require_service(registry, weather_service):
    """Test requiring service succeeds when available."""
    registry.register(weather_service, provider="weather_plugin")

    retrieved = registry.require("weather")
    assert retrieved == weather_service


def test_require_nonexistent_service(registry):
    """Test requiring non-existent service raises error."""
    with pytest.raises(PluginError, match="not registered"):
        registry.require("nonexistent")


def test_require_incompatible_version(registry):
    """Test requiring incompatible version raises error."""
    service = MockService("weather", "1.0.0")
    registry.register(service, provider="weather_plugin")

    with pytest.raises(PluginError, match="incompatible"):
        registry.require("weather", min_version="2.0.0")


def test_has_service(registry, weather_service):
    """Test checking service existence."""
    assert not registry.has("weather")

    registry.register(weather_service, provider="weather_plugin")
    assert registry.has("weather")


# =================================================================
# Lifecycle Management Tests
# =================================================================

@pytest.mark.asyncio
async def test_start_service(registry, weather_service):
    """Test starting service."""
    registry.register(weather_service, provider="weather_plugin")

    await registry.start("weather")

    assert weather_service.start_called
    assert "weather" in registry._started

    services = registry.list_services()
    assert services[0]["started"]


@pytest.mark.asyncio
async def test_start_nonexistent_service(registry):
    """Test starting non-existent service raises error."""
    with pytest.raises(PluginError, match="unregistered service"):
        await registry.start("nonexistent")


@pytest.mark.asyncio
async def test_start_already_started_service(registry, weather_service):
    """Test starting already-started service is idempotent."""
    registry.register(weather_service, provider="weather_plugin")

    await registry.start("weather")
    await registry.start("weather")  # Should not error

    # Start should only be called once
    assert weather_service.start_called


@pytest.mark.asyncio
async def test_start_service_with_dependencies(registry, weather_service, forecast_service):
    """Test starting service with dependencies."""
    # Register services
    registry.register(weather_service, provider="weather_plugin")
    registry.register(
        forecast_service,
        provider="forecast_plugin",
        dependencies={"weather": "1.0.0"}
    )

    # Start forecast (should auto-start weather)
    await registry.start("forecast")

    assert weather_service.start_called
    assert forecast_service.start_called
    assert "weather" in registry._started
    assert "forecast" in registry._started


@pytest.mark.asyncio
async def test_start_service_missing_dependency(registry, forecast_service):
    """Test starting service with missing dependency raises error."""
    registry.register(
        forecast_service,
        provider="forecast_plugin",
        dependencies={"weather": "1.0.0"}
    )

    with pytest.raises(PluginError, match="depends on unregistered service"):
        await registry.start("forecast")


@pytest.mark.asyncio
async def test_start_service_incompatible_dependency(registry, weather_service, forecast_service):
    """Test starting service with incompatible dependency version."""
    # Weather is v1.0.0 but forecast needs v2.0.0+
    registry.register(weather_service, provider="weather_plugin")
    registry.register(
        forecast_service,
        provider="forecast_plugin",
        dependencies={"weather": "2.0.0"}
    )

    with pytest.raises(PluginError, match="requires.*>=2.0.0"):
        await registry.start("forecast")


@pytest.mark.asyncio
async def test_start_service_failure(registry):
    """Test service start failure is handled."""
    failing = FailingService("fail", "1.0.0", fail_on="start")
    registry.register(failing, provider="test_plugin")

    with pytest.raises(PluginError, match="Failed to start service"):
        await registry.start("fail")


@pytest.mark.asyncio
async def test_stop_service(registry, weather_service):
    """Test stopping service."""
    registry.register(weather_service, provider="weather_plugin")
    await registry.start("weather")

    await registry.stop("weather")

    assert weather_service.stop_called
    assert "weather" not in registry._started

    services = registry.list_services()
    assert not services[0]["started"]


@pytest.mark.asyncio
async def test_stop_nonexistent_service(registry):
    """Test stopping non-existent service raises error."""
    with pytest.raises(PluginError, match="unregistered service"):
        await registry.stop("nonexistent")


@pytest.mark.asyncio
async def test_stop_not_started_service(registry, weather_service):
    """Test stopping not-started service is idempotent."""
    registry.register(weather_service, provider="weather_plugin")

    await registry.stop("weather")  # Should not error

    # Stop should not be called
    assert not weather_service.stop_called


@pytest.mark.asyncio
async def test_stop_service_failure(registry):
    """Test service stop failure is handled."""
    failing = FailingService("fail", "1.0.0", fail_on="stop")
    registry.register(failing, provider="test_plugin")
    await registry.start("fail")

    with pytest.raises(PluginError, match="Failed to stop service"):
        await registry.stop("fail")

    # Service should still be marked as stopped
    assert "fail" not in registry._started


# =================================================================
# Dependency Resolution Tests
# =================================================================

@pytest.mark.asyncio
async def test_start_all_simple(registry, weather_service, location_service):
    """Test starting all services with no dependencies."""
    registry.register(weather_service, provider="weather_plugin")
    registry.register(location_service, provider="location_plugin")

    await registry.start_all()

    assert weather_service.start_called
    assert location_service.start_called


@pytest.mark.asyncio
async def test_start_all_with_dependencies(registry, weather_service, location_service, forecast_service):
    """Test starting all services respects dependency order."""
    # Register in random order
    registry.register(
        forecast_service,
        provider="forecast_plugin",
        dependencies={"weather": "1.0.0", "location": "1.0.0"}
    )
    registry.register(weather_service, provider="weather_plugin")
    registry.register(location_service, provider="location_plugin")

    await registry.start_all()

    # All should be started
    assert weather_service.start_called
    assert location_service.start_called
    assert forecast_service.start_called


@pytest.mark.asyncio
async def test_circular_dependency_detection(registry):
    """Test circular dependency detection."""
    # Service A depends on B, B depends on A
    service_a = MockService("service_a", "1.0.0")
    service_b = MockService("service_b", "1.0.0")

    registry.register(service_a, provider="plugin_a", dependencies={"service_b": "1.0.0"})
    registry.register(service_b, provider="plugin_b", dependencies={"service_a": "1.0.0"})

    with pytest.raises(PluginError, match="Circular dependencies detected"):
        await registry.start_all()


@pytest.mark.asyncio
async def test_stop_all_services(registry, weather_service, location_service, forecast_service):
    """Test stopping all services in reverse dependency order."""
    # Register with dependencies
    registry.register(weather_service, provider="weather_plugin")
    registry.register(location_service, provider="location_plugin")
    registry.register(
        forecast_service,
        provider="forecast_plugin",
        dependencies={"weather": "1.0.0"}
    )

    # Start all
    await registry.start_all()

    # Stop all
    await registry.stop_all()

    # All should be stopped
    assert weather_service.stop_called
    assert location_service.stop_called
    assert forecast_service.stop_called


@pytest.mark.asyncio
async def test_stop_all_continues_on_error(registry):
    """Test stop_all continues even if one service fails."""
    good = MockService("good", "1.0.0")
    bad = FailingService("bad", "1.0.0", fail_on="stop")

    registry.register(good, provider="plugin_a")
    registry.register(bad, provider="plugin_b")

    await registry.start_all()

    # Should not raise, but should log errors
    await registry.stop_all()

    # Good service should still be stopped
    assert good.stop_called
    assert "good" not in registry._started


# =================================================================
# Service Discovery Tests
# =================================================================

def test_list_services_empty(registry):
    """Test listing services when registry is empty."""
    services = registry.list_services()
    assert services == []


def test_list_services_multiple(registry, weather_service, location_service):
    """Test listing multiple services."""
    registry.register(weather_service, provider="weather_plugin")
    registry.register(location_service, provider="location_plugin")

    services = registry.list_services()
    assert len(services) == 2

    names = {s["name"] for s in services}
    assert names == {"weather", "location"}


def test_get_providers_by_plugin(registry, weather_service, location_service):
    """Test getting services provided by specific plugin."""
    registry.register(weather_service, provider="weather_plugin")
    registry.register(location_service, provider="location_plugin")

    # Same plugin provides multiple services
    forecast = MockService("forecast", "1.0.0")
    alerts = MockService("alerts", "1.0.0")
    registry.register(forecast, provider="weather_plugin")
    registry.register(alerts, provider="weather_plugin")

    weather_services = registry.get_providers("weather_plugin")
    assert set(weather_services) == {"weather", "forecast", "alerts"}

    location_services = registry.get_providers("location_plugin")
    assert location_services == ["location"]


def test_get_providers_no_services(registry):
    """Test getting providers for plugin with no services."""
    providers = registry.get_providers("nonexistent_plugin")
    assert providers == []


# =================================================================
# Utility Tests
# =================================================================

def test_registry_repr(registry, weather_service):
    """Test string representation of registry."""
    assert "0 services" in repr(registry)
    assert "0 started" in repr(registry)

    registry.register(weather_service, provider="weather_plugin")
    assert "1 services" in repr(registry)


@pytest.mark.asyncio
async def test_registry_repr_with_started(registry, weather_service):
    """Test repr shows started count."""
    registry.register(weather_service, provider="weather_plugin")
    await registry.start("weather")

    repr_str = repr(registry)
    assert "1 services" in repr_str
    assert "1 started" in repr_str


# =================================================================
# Integration Tests
# =================================================================

@pytest.mark.asyncio
async def test_full_lifecycle(registry):
    """Test complete service lifecycle with dependencies."""
    # Create service chain: forecast -> weather -> location
    location = MockService("location", "1.0.0")
    weather = MockService("weather", "1.5.0")
    forecast = MockService("forecast", "2.0.0")

    # Register in reverse order
    registry.register(forecast, provider="forecast_plugin", dependencies={"weather": "1.0.0"})
    registry.register(weather, provider="weather_plugin", dependencies={"location": "1.0.0"})
    registry.register(location, provider="location_plugin")

    # Start all (should resolve dependency order)
    await registry.start_all()

    assert location.start_called
    assert weather.start_called
    assert forecast.start_called

    # Verify all started
    services = registry.list_services()
    assert all(s["started"] for s in services)

    # Stop all
    await registry.stop_all()

    assert location.stop_called
    assert weather.stop_called
    assert forecast.stop_called

    # Verify all stopped
    services = registry.list_services()
    assert not any(s["started"] for s in services)
