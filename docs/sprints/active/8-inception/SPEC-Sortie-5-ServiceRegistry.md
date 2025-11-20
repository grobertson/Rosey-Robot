# Sprint 8, Sortie 5: Service Registry

**Status:** Planning  
**Estimated Effort:** 4 hours  
**Sprint:** Inception (Sprint 8)  
**Phase:** 2 - Plugin Communication  
**Dependencies:** Sortie 1 (Plugin base), Sortie 2 (PluginManager)

## Objective

Implement service registry for dependency injection between plugins. Enable plugins to provide services (APIs) that other plugins can consume, creating reusable plugin components.

## Background

Plugins need shared services:
- **Weather plugin** provides weather lookup service
- **Forecast plugin** uses weather service
- **Database plugin** provides data access service
- **Stats plugin** uses database service

Service registry enables dependency injection without tight coupling.

## Success Criteria

- ✅ Service registry with register/get
- ✅ Service versioning
- ✅ Service dependencies
- ✅ Service lifecycle (start/stop)
- ✅ Service discovery (list available)
- ✅ Type-safe service access

## Technical Design

### Service Structure

```python
"""
lib/plugin/service.py

Service definition for plugin services.
"""

from dataclasses import dataclass
from typing import Any, Optional, Protocol
from abc import ABC, abstractmethod


class Service(ABC):
    """
    Base class for plugin services.
    
    Services provide reusable APIs for other plugins.
    
    Example:
        class WeatherService(Service):
            async def get_weather(self, location: str) -> dict:
                # Implementation
                pass
    """
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """Service identifier."""
        pass
    
    @property
    @abstractmethod
    def service_version(self) -> str:
        """Service version (semantic versioning)."""
        pass
    
    async def start(self) -> None:
        """
        Start service (optional).
        
        Use for initialization that needs async I/O.
        """
        pass
    
    async def stop(self) -> None:
        """
        Stop service (optional).
        
        Use for cleanup.
        """
        pass


@dataclass
class ServiceRegistration:
    """
    Service registration information.
    
    Attributes:
        service: Service instance
        provider: Name of plugin providing service
        version: Service version
        dependencies: Required services (name: version)
    """
    service: Service
    provider: str
    version: str
    dependencies: dict[str, str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = {}
```

### Service Registry Implementation

```python
"""
lib/plugin/service_registry.py

Service registry for dependency injection.
"""

from typing import Dict, List, Optional, Type
import logging
from packaging import version

from .service import Service, ServiceRegistration
from .errors import PluginError


class ServiceRegistry:
    """
    Registry for plugin services.
    
    Features:
    - Register services by name
    - Get services by name (with version constraint)
    - Service dependency resolution
    - Service lifecycle management
    - Service discovery
    
    Args:
        logger: Optional logger instance
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger('plugin.service_registry')
        
        # Services: service_name -> ServiceRegistration
        self._services: Dict[str, ServiceRegistration] = {}
        
        # Track service states
        self._started: set[str] = set()
    
    def register(self, service: Service, provider: str,
                dependencies: Optional[Dict[str, str]] = None) -> None:
        """
        Register service.
        
        Args:
            service: Service instance
            provider: Name of plugin providing service
            dependencies: Required services {name: min_version}
        
        Raises:
            PluginError: If service already registered
        
        Example:
            registry.register(
                WeatherService(),
                'weather_plugin',
                dependencies={'cache': '1.0.0'}
            )
        """
        name = service.service_name
        
        if name in self._services:
            existing = self._services[name]
            raise PluginError(
                f"Service '{name}' already registered by {existing.provider}"
            )
        
        registration = ServiceRegistration(
            service=service,
            provider=provider,
            version=service.service_version,
            dependencies=dependencies or {}
        )
        
        self._services[name] = registration
        self.logger.info(f"Registered service: {name} v{service.service_version} "
                        f"(provider: {provider})")
    
    def unregister(self, service_name: str) -> None:
        """
        Unregister service.
        
        Args:
            service_name: Name of service to unregister
        """
        if service_name in self._services:
            del self._services[service_name]
            self._started.discard(service_name)
            self.logger.info(f"Unregistered service: {service_name}")
    
    def get(self, service_name: str,
           min_version: Optional[str] = None) -> Optional[Service]:
        """
        Get service by name.
        
        Args:
            service_name: Name of service
            min_version: Minimum required version (semantic versioning)
        
        Returns:
            Service instance or None if not found
        
        Raises:
            PluginError: If service version doesn't meet requirement
        
        Example:
            weather = registry.get('weather', min_version='1.0.0')
            if weather:
                forecast = await weather.get_weather('Seattle')
        """
        registration = self._services.get(service_name)
        
        if not registration:
            return None
        
        # Check version constraint
        if min_version:
            service_ver = version.parse(registration.version)
            required_ver = version.parse(min_version)
            
            if service_ver < required_ver:
                raise PluginError(
                    f"Service '{service_name}' version {registration.version} "
                    f"doesn't meet requirement {min_version}"
                )
        
        return registration.service
    
    def require(self, service_name: str,
               min_version: Optional[str] = None) -> Service:
        """
        Get service (raises if not found).
        
        Args:
            service_name: Name of service
            min_version: Minimum required version
        
        Returns:
            Service instance
        
        Raises:
            PluginError: If service not found or version mismatch
        
        Example:
            weather = registry.require('weather', '1.0.0')
            # Guaranteed to be non-None or raises
        """
        service = self.get(service_name, min_version)
        
        if service is None:
            raise PluginError(f"Required service not found: {service_name}")
        
        return service
    
    def has(self, service_name: str) -> bool:
        """
        Check if service is registered.
        
        Args:
            service_name: Name of service
        
        Returns:
            True if service is registered
        """
        return service_name in self._services
    
    async def start(self, service_name: str) -> None:
        """
        Start service (call service.start()).
        
        Args:
            service_name: Name of service
        
        Raises:
            PluginError: If service not found
        """
        registration = self._services.get(service_name)
        
        if not registration:
            raise PluginError(f"Service not found: {service_name}")
        
        if service_name in self._started:
            self.logger.warning(f"Service already started: {service_name}")
            return
        
        # Check dependencies are started
        for dep_name, dep_version in registration.dependencies.items():
            if dep_name not in self._started:
                await self.start(dep_name)
        
        # Start service
        await registration.service.start()
        self._started.add(service_name)
        self.logger.info(f"Started service: {service_name}")
    
    async def stop(self, service_name: str) -> None:
        """
        Stop service (call service.stop()).
        
        Args:
            service_name: Name of service
        """
        registration = self._services.get(service_name)
        
        if not registration:
            return
        
        if service_name not in self._started:
            return
        
        await registration.service.stop()
        self._started.discard(service_name)
        self.logger.info(f"Stopped service: {service_name}")
    
    async def start_all(self) -> None:
        """Start all registered services (in dependency order)."""
        # Resolve dependency order
        order = self._resolve_dependencies()
        
        for service_name in order:
            if service_name not in self._started:
                await self.start(service_name)
    
    async def stop_all(self) -> None:
        """Stop all started services (reverse dependency order)."""
        order = self._resolve_dependencies()
        
        for service_name in reversed(order):
            if service_name in self._started:
                await self.stop(service_name)
    
    def _resolve_dependencies(self) -> List[str]:
        """
        Resolve service dependencies (topological sort).
        
        Returns:
            List of service names in start order
        
        Raises:
            PluginError: If circular dependency detected
        """
        # Build dependency graph
        graph: Dict[str, set[str]] = {}
        in_degree: Dict[str, int] = {}
        
        for name, reg in self._services.items():
            graph[name] = set(reg.dependencies.keys())
            in_degree[name] = 0
        
        # Calculate in-degrees
        for name, deps in graph.items():
            for dep in deps:
                if dep not in graph:
                    raise PluginError(
                        f"Service {name} depends on missing service: {dep}"
                    )
                in_degree[name] += 1
        
        # Topological sort
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            name = queue.pop(0)
            result.append(name)
            
            for other_name, deps in graph.items():
                if name in deps:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)
        
        if len(result) != len(graph):
            raise PluginError("Circular service dependency detected")
        
        return result
    
    def list_services(self) -> List[Dict[str, any]]:
        """
        List all registered services.
        
        Returns:
            List of service info dicts
        """
        return [
            {
                'name': reg.service.service_name,
                'version': reg.version,
                'provider': reg.provider,
                'started': reg.service.service_name in self._started,
                'dependencies': reg.dependencies
            }
            for reg in self._services.values()
        ]
    
    def get_providers(self, plugin_name: str) -> List[str]:
        """
        Get services provided by plugin.
        
        Args:
            plugin_name: Name of plugin
        
        Returns:
            List of service names
        """
        return [
            name for name, reg in self._services.items()
            if reg.provider == plugin_name
        ]
```

### Plugin Integration

```python
# lib/plugin/base.py

class Plugin(ABC):
    """Plugin with service registry access."""
    
    @property
    def services(self):
        """Access service registry."""
        return self.bot.plugin_manager.service_registry
    
    def provide_service(self, service: Service,
                       dependencies: Optional[Dict[str, str]] = None) -> None:
        """
        Provide service to other plugins.
        
        Args:
            service: Service instance
            dependencies: Required services {name: min_version}
        
        Example:
            class MyPlugin(Plugin):
                async def setup(self):
                    self.provide_service(WeatherService())
        """
        self.services.register(service, self.metadata.name, dependencies)
    
    def get_service(self, service_name: str,
                   min_version: Optional[str] = None) -> Optional[Service]:
        """
        Get service by name.
        
        Args:
            service_name: Name of service
            min_version: Minimum version required
        
        Returns:
            Service instance or None
        
        Example:
            weather = self.get_service('weather', '1.0.0')
            if weather:
                data = await weather.get_weather('Seattle')
        """
        return self.services.get(service_name, min_version)
    
    def require_service(self, service_name: str,
                       min_version: Optional[str] = None) -> Service:
        """
        Get service (raises if not found).
        
        Args:
            service_name: Name of service
            min_version: Minimum version required
        
        Returns:
            Service instance (guaranteed)
        
        Raises:
            PluginError: If service not found
        
        Example:
            weather = self.require_service('weather', '1.0.0')
            data = await weather.get_weather('Seattle')
        """
        return self.services.require(service_name, min_version)
```

### Example: Weather Service

```python
# plugins/weather_plugin.py

from lib.plugin import Plugin, PluginMetadata, Service


class WeatherService(Service):
    """Weather lookup service."""
    
    @property
    def service_name(self) -> str:
        return 'weather'
    
    @property
    def service_version(self) -> str:
        return '1.0.0'
    
    async def get_weather(self, location: str) -> dict:
        """Get weather for location."""
        # Call weather API
        return {
            'location': location,
            'temp': 72,
            'conditions': 'Sunny'
        }


class WeatherPlugin(Plugin):
    """Weather plugin that provides weather service."""
    
    @property
    def metadata(self):
        return PluginMetadata(
            name='weather',
            display_name='Weather',
            version='1.0.0',
            description='Weather service and commands',
            author='Copilot'
        )
    
    async def setup(self):
        """Provide weather service."""
        self.provide_service(WeatherService())
        
        @self.on_command('weather')
        async def handle_weather(username, args):
            if not args:
                await self.send_message("Usage: !weather <location>")
                return
            
            location = ' '.join(args)
            weather = await self.weather_service.get_weather(location)
            
            await self.send_message(
                f"{location}: {weather['temp']}°F, {weather['conditions']}"
            )
    
    @property
    def weather_service(self) -> WeatherService:
        return self.require_service('weather')


# plugins/forecast_plugin.py

class ForecastPlugin(Plugin):
    """Forecast plugin that uses weather service."""
    
    @property
    def metadata(self):
        return PluginMetadata(
            name='forecast',
            display_name='Forecast',
            version='1.0.0',
            description='Extended weather forecast',
            author='Copilot',
            dependencies=['weather']  # Requires weather plugin
        )
    
    async def setup(self):
        """Use weather service."""
        @self.on_command('forecast')
        async def handle_forecast(username, args):
            # Get weather service
            weather = self.get_service('weather', '1.0.0')
            
            if not weather:
                await self.send_message("Weather service not available")
                return
            
            location = ' '.join(args)
            # Use service
            data = await weather.get_weather(location)
            
            await self.send_message(f"Forecast for {location}: {data}")
```

## Implementation Steps

1. **Install packaging library** (5 min)
   ```bash
   pip install packaging
   # Add to requirements.txt:
   # packaging>=23.0
   ```

2. **Create service module** (30 min)
   ```bash
   touch lib/plugin/service.py
   touch lib/plugin/service_registry.py
   ```

3. **Implement Service base class** (30 min)
   - Abstract service interface
   - Lifecycle methods (start/stop)

4. **Implement ServiceRegistration** (15 min)
   - Dataclass for tracking services

5. **Implement ServiceRegistry** (2 hours)
   - Register/unregister methods
   - Get/require methods
   - Version checking
   - Dependency resolution
   - Lifecycle management
   - Service discovery

6. **Integrate with Plugin** (30 min)
   - Add services property
   - Add provide_service()
   - Add get_service()
   - Add require_service()

7. **Integrate with PluginManager** (15 min)
   - Create ServiceRegistry in __init__
   - Start services after plugin setup
   - Stop services before plugin teardown

8. **Write unit tests** (1 hour)
   ```python
   # test/test_service_registry.py
   
   import pytest
   from lib.plugin import Service, ServiceRegistry, PluginError
   
   
   class MockService(Service):
       @property
       def service_name(self):
           return 'mock'
       
       @property
       def service_version(self):
           return '1.0.0'
   
   
   def test_register_and_get():
       """Test service registration."""
       registry = ServiceRegistry()
       service = MockService()
       
       registry.register(service, 'mock_plugin')
       
       retrieved = registry.get('mock')
       assert retrieved is service
   
   
   def test_version_constraint():
       """Test version checking."""
       registry = ServiceRegistry()
       
       class OldService(Service):
           @property
           def service_name(self):
               return 'test'
           
           @property
           def service_version(self):
               return '1.0.0'
       
       registry.register(OldService(), 'provider')
       
       # Should work (>= 1.0.0)
       service = registry.get('test', '1.0.0')
       assert service is not None
       
       # Should fail (< 2.0.0)
       with pytest.raises(PluginError):
           registry.get('test', '2.0.0')
   
   
   @pytest.mark.asyncio
   async def test_dependency_resolution():
       """Test service dependency resolution."""
       registry = ServiceRegistry()
       
       # Service A depends on B
       service_a = MockService()
       service_b = MockService()
       
       registry.register(service_b, 'plugin_b')
       registry.register(service_a, 'plugin_a', dependencies={'mock': '1.0.0'})
       
       order = registry._resolve_dependencies()
       
       # B should come before A
       assert order.index('mock') < order.index('mock')
   ```

9. **Example plugins** (30 min)
   - Create weather service example
   - Create forecast consumer example

10. **Validation** (30 min)
    ```bash
    mypy lib/plugin/service*.py
    pylint lib/plugin/service*.py
    pytest test/test_service_registry.py -v
    ```

## Testing Strategy

### Unit Tests

- ✅ Service registration
- ✅ Service retrieval
- ✅ Version constraints
- ✅ Dependency resolution
- ✅ Lifecycle management
- ✅ Service discovery

### Integration Tests

- ✅ Plugin provides service
- ✅ Another plugin consumes it
- ✅ Service hot reload

## Dependencies

**Python Packages:**
- `packaging>=23.0` - Semantic version parsing

**Internal Modules:**
- `lib/plugin/base.py` (Sortie 1)
- `lib/plugin/manager.py` (Sortie 2)

## Validation

Before moving to Sortie 6:

1. ✅ ServiceRegistry complete
2. ✅ Service registration works
3. ✅ Version checking works
4. ✅ Dependency resolution works
5. ✅ Plugin integration complete
6. ✅ All tests pass

## Risks & Mitigations

**Risk:** Service version conflicts  
**Mitigation:** Semantic versioning, explicit min_version requirements

**Risk:** Circular service dependencies  
**Mitigation:** Topological sort detects cycles

**Risk:** Service API changes break consumers  
**Mitigation:** Semantic versioning, version constraints

## Design Decisions

### Why Service Base Class?

Type safety, enforced interface, lifecycle hooks.

### Why Semantic Versioning?

Industry standard, clear compatibility rules (major.minor.patch).

### Why Dependency Injection?

Loose coupling, testability, flexibility.

### Why Lifecycle Methods?

Services may need async initialization (DB connections, API setup).

## Next Steps

After completion, proceed to:

- **Sortie 6:** Plugin management commands (!plugin list/reload/enable/disable)

---

**Created:** November 12, 2025  
**Author:** Copilot  
**Sprint:** 8 - Inception
