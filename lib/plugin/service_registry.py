"""Service registry for plugin dependency injection.

This module provides a service registry that enables plugins to provide and consume
services with dependency injection, semantic versioning, and lifecycle management.

Example:
    >>> # Plugin providing a service
    >>> class WeatherService(Service):
    ...     @property
    ...     def service_name(self) -> str:
    ...         return "weather"
    ...
    ...     @property
    ...     def service_version(self) -> str:
    ...         return "1.0.0"
    ...
    ...     async def start(self):
    ...         # Initialize API connections
    ...         pass
    ...
    ...     def get_weather(self, location: str) -> dict:
    ...         # Fetch weather data
    ...         return {"temp": 72, "condition": "sunny"}
    >>>
    >>> # Register the service
    >>> registry = ServiceRegistry(logger)
    >>> weather = WeatherService()
    >>> registry.register(weather, provider="weather_plugin")
    >>>
    >>> # Plugin consuming a service
    >>> weather_service = registry.require("weather", min_version="1.0.0")
    >>> data = weather_service.get_weather("Seattle")
"""

import logging
from typing import Any, Dict, List, Optional, Set

from packaging.version import parse

from .errors import PluginError
from .service import Service, ServiceRegistration


class ServiceRegistry:
    """Registry for managing plugin services with dependency injection.

    The service registry enables plugins to provide and consume services without
    tight coupling. Services are versioned using semantic versioning, and the
    registry handles dependency resolution and lifecycle management.

    Features:
    - Semantic versioning for service compatibility
    - Dependency resolution with cycle detection
    - Lifecycle management (start/stop hooks)
    - Service discovery

    Attributes:
        _services: Mapping of service names to their registrations
        _started: Set of started service names
        _logger: Logger instance
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the service registry.

        Args:
            logger: Optional logger instance. If not provided, uses module logger.
        """
        self._services: Dict[str, ServiceRegistration] = {}
        self._started: Set[str] = set()
        self._logger = logger or logging.getLogger(__name__)

    def register(
        self,
        service: Service,
        provider: str,
        dependencies: Optional[Dict[str, str]] = None
    ) -> None:
        """Register a service with the registry.

        Args:
            service: Service instance to register
            provider: Name of the plugin providing the service
            dependencies: Optional mapping of required service names to minimum versions

        Raises:
            PluginError: If service name is already registered
            PluginError: If service version is invalid

        Example:
            >>> weather = WeatherService()
            >>> registry.register(
            ...     weather,
            ...     provider="weather_plugin",
            ...     dependencies={"location": "1.0.0"}
            ... )
        """
        service_name = service.service_name
        service_version = service.service_version

        # Validate service version
        try:
            parse(service_version)
        except Exception as e:
            raise PluginError(
                f"Invalid service version '{service_version}' for service '{service_name}': {e}"
            )

        # Check if already registered
        if service_name in self._services:
            existing = self._services[service_name]
            raise PluginError(
                f"Service '{service_name}' already registered by plugin '{existing.provider}'"
            )

        # Create registration
        registration = ServiceRegistration(
            service=service,
            provider=provider,
            version=service_version,
            dependencies=dependencies or {}
        )

        self._services[service_name] = registration
        self._logger.info(
            f"Registered service '{service_name}' v{service_version} "
            f"from plugin '{provider}'"
        )

        # Log dependencies if any
        if registration.dependencies:
            deps_str = ", ".join(
                f"{name}>={ver}" for name, ver in registration.dependencies.items()
            )
            self._logger.debug(f"  Dependencies: {deps_str}")

    def unregister(self, service_name: str) -> None:
        """Unregister a service from the registry.

        Args:
            service_name: Name of the service to unregister

        Raises:
            PluginError: If service is not registered
            PluginError: If service is still started

        Example:
            >>> registry.unregister("weather")
        """
        if service_name not in self._services:
            raise PluginError(f"Service '{service_name}' is not registered")

        if service_name in self._started:
            raise PluginError(
                f"Cannot unregister service '{service_name}' while it is started. "
                "Stop the service first."
            )

        registration = self._services[service_name]
        del self._services[service_name]

        self._logger.info(
            f"Unregistered service '{service_name}' from plugin '{registration.provider}'"
        )

    def get(self, service_name: str, min_version: Optional[str] = None) -> Optional[Service]:
        """Get a service by name with optional version constraint.

        Args:
            service_name: Name of the service to retrieve
            min_version: Optional minimum version requirement (semantic version)

        Returns:
            Service instance if found and version compatible, None otherwise

        Example:
            >>> weather = registry.get("weather", min_version="1.0.0")
            >>> if weather:
            ...     data = weather.get_weather("Seattle")
        """
        if service_name not in self._services:
            return None

        registration = self._services[service_name]

        # Check version constraint if specified
        if min_version:
            try:
                service_ver = parse(registration.version)
                required_ver = parse(min_version)

                if service_ver < required_ver:
                    self._logger.warning(
                        f"Service '{service_name}' version {registration.version} "
                        f"is older than required {min_version}"
                    )
                    return None
            except Exception as e:
                self._logger.error(
                    f"Version comparison failed for service '{service_name}': {e}"
                )
                return None

        return registration.service

    def require(self, service_name: str, min_version: Optional[str] = None) -> Service:
        """Get a service by name, raising an error if not available.

        Args:
            service_name: Name of the service to retrieve
            min_version: Optional minimum version requirement

        Returns:
            Service instance

        Raises:
            PluginError: If service is not registered
            PluginError: If service version is incompatible

        Example:
            >>> weather = registry.require("weather", min_version="1.0.0")
            >>> data = weather.get_weather("Seattle")
        """
        service = self.get(service_name, min_version)

        if service is None:
            if service_name not in self._services:
                raise PluginError(f"Required service '{service_name}' is not registered")
            else:
                registration = self._services[service_name]
                raise PluginError(
                    f"Service '{service_name}' version {registration.version} "
                    f"is incompatible with required version {min_version}"
                )

        return service

    def has(self, service_name: str) -> bool:
        """Check if a service is registered.

        Args:
            service_name: Name of the service to check

        Returns:
            True if service is registered, False otherwise

        Example:
            >>> if registry.has("weather"):
            ...     weather = registry.get("weather")
        """
        return service_name in self._services

    async def start(self, service_name: str) -> None:
        """Start a service and its dependencies.

        Services are started in dependency order. If a service has dependencies,
        they will be started first. Circular dependencies are detected and raise
        an error.

        Args:
            service_name: Name of the service to start

        Raises:
            PluginError: If service is not registered
            PluginError: If dependencies cannot be resolved (circular or missing)
            PluginError: If service start() method fails

        Example:
            >>> await registry.start("weather")
        """
        if service_name not in self._services:
            raise PluginError(f"Cannot start unregistered service '{service_name}'")

        if service_name in self._started:
            # Already started
            return

        registration = self._services[service_name]

        # Start dependencies first
        for dep_name, min_version in registration.dependencies.items():
            if dep_name not in self._services:
                raise PluginError(
                    f"Service '{service_name}' depends on unregistered service '{dep_name}'"
                )

            # Verify version compatibility
            dep_registration = self._services[dep_name]
            try:
                dep_ver = parse(dep_registration.version)
                required_ver = parse(min_version)

                if dep_ver < required_ver:
                    raise PluginError(
                        f"Service '{service_name}' requires '{dep_name}' >={min_version}, "
                        f"but version {dep_registration.version} is registered"
                    )
            except PluginError:
                raise
            except Exception as e:
                raise PluginError(
                    f"Version comparison failed for dependency '{dep_name}': {e}"
                )

            # Recursively start dependency
            await self.start(dep_name)

        # Start the service
        try:
            self._logger.info(f"Starting service '{service_name}'...")
            await registration.service.start()
            self._started.add(service_name)
            self._logger.info(f"Started service '{service_name}'")
        except Exception as e:
            raise PluginError(
                f"Failed to start service '{service_name}': {e}"
            )

    async def stop(self, service_name: str) -> None:
        """Stop a service.

        Args:
            service_name: Name of the service to stop

        Raises:
            PluginError: If service is not registered
            PluginError: If service stop() method fails

        Example:
            >>> await registry.stop("weather")
        """
        if service_name not in self._services:
            raise PluginError(f"Cannot stop unregistered service '{service_name}'")

        if service_name not in self._started:
            # Not started
            return

        registration = self._services[service_name]

        try:
            self._logger.info(f"Stopping service '{service_name}'...")
            await registration.service.stop()
            self._started.remove(service_name)
            self._logger.info(f"Stopped service '{service_name}'")
        except Exception as e:
            # Still mark as stopped even if stop() fails
            self._started.discard(service_name)
            raise PluginError(
                f"Failed to stop service '{service_name}': {e}"
            )

    async def start_all(self) -> None:
        """Start all registered services in dependency order.

        Uses topological sort to determine the correct start order and detect
        circular dependencies.

        Raises:
            PluginError: If circular dependencies are detected
            PluginError: If any service fails to start

        Example:
            >>> await registry.start_all()
        """
        # Resolve dependency order
        try:
            start_order = self._resolve_dependencies()
        except PluginError as e:
            self._logger.error(f"Cannot start services: {e}")
            raise

        # Start services in order
        for service_name in start_order:
            if service_name not in self._started:
                await self.start(service_name)

    async def stop_all(self) -> None:
        """Stop all started services in reverse dependency order.

        Services are stopped in reverse order to ensure dependents are stopped
        before their dependencies.

        Example:
            >>> await registry.stop_all()
        """
        # Stop in reverse dependency order
        try:
            start_order = self._resolve_dependencies()
            stop_order = list(reversed(start_order))
        except PluginError:
            # If we can't resolve dependencies, just stop in reverse registration order
            stop_order = list(reversed(list(self._services.keys())))

        # Stop all started services
        for service_name in stop_order:
            if service_name in self._started:
                try:
                    await self.stop(service_name)
                except PluginError as e:
                    self._logger.error(f"Error stopping service '{service_name}': {e}")
                    # Continue stopping other services

    def _resolve_dependencies(self) -> List[str]:  # noqa: C901 (dependency resolution)
        """Resolve service dependencies using topological sort.

        Returns:
            List of service names in dependency order (dependencies first)

        Raises:
            PluginError: If circular dependencies are detected
        """
        # Build dependency graph
        graph: Dict[str, Set[str]] = {}
        in_degree: Dict[str, int] = {}

        for service_name, registration in self._services.items():
            graph[service_name] = set(registration.dependencies.keys())
            in_degree[service_name] = 0

        # Calculate in-degrees
        for service_name, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1

        # Topological sort using Kahn's algorithm
        queue: List[str] = []
        result: List[str] = []

        # Start with services that have no dependents
        for service_name, degree in in_degree.items():
            if degree == 0:
                queue.append(service_name)

        while queue:
            service_name = queue.pop(0)
            result.append(service_name)

            # Process this service's dependencies
            for dep in graph[service_name]:
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        # Reverse to get dependencies-first order
        result.reverse()

        # Check for cycles
        if len(result) != len(self._services):
            # Find services involved in cycle
            cycle_services = set(self._services.keys()) - set(result)
            raise PluginError(
                f"Circular dependencies detected among services: {', '.join(cycle_services)}"
            )

        return result

    def list_services(self) -> List[Dict[str, Any]]:
        """List all registered services with their metadata.

        Returns:
            List of service information dictionaries containing:
            - name: Service name
            - version: Service version
            - provider: Plugin providing the service
            - started: Whether service is started
            - dependencies: Dict of required services and versions

        Example:
            >>> services = registry.list_services()
            >>> for svc in services:
            ...     print(f"{svc['name']} v{svc['version']} by {svc['provider']}")
        """
        services = []
        for service_name, registration in self._services.items():
            services.append({
                "name": service_name,
                "version": registration.version,
                "provider": registration.provider,
                "started": service_name in self._started,
                "dependencies": dict(registration.dependencies)
            })
        return services

    def get_providers(self, plugin_name: str) -> List[str]:
        """Get list of services provided by a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            List of service names provided by the plugin

        Example:
            >>> weather_services = registry.get_providers("weather_plugin")
            >>> print(f"Weather plugin provides: {weather_services}")
        """
        return [
            service_name
            for service_name, registration in self._services.items()
            if registration.provider == plugin_name
        ]

    def __repr__(self) -> str:
        """Return string representation of the registry.

        Returns:
            String showing number of services and started count
        """
        return (
            f"<ServiceRegistry: {len(self._services)} services, "
            f"{len(self._started)} started>"
        )
