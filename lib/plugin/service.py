"""
lib/plugin/service.py

Service definition for plugin services.
"""

from dataclasses import dataclass, field
from typing import Dict
from abc import ABC, abstractmethod


class Service(ABC):
    """
    Base class for plugin services.

    Services provide reusable APIs for other plugins through dependency injection.

    Example:
        class WeatherService(Service):
            @property
            def service_name(self) -> str:
                return 'weather'

            @property
            def service_version(self) -> str:
                return '1.0.0'

            async def get_weather(self, location: str) -> dict:
                # Implementation
                return {'temp': 72, 'conditions': 'Sunny'}
    """

    @property
    @abstractmethod
    def service_name(self) -> str:
        """
        Service identifier (unique across all plugins).

        Returns:
            Service name (e.g., 'weather', 'database', 'cache')
        """

    @property
    @abstractmethod
    def service_version(self) -> str:
        """
        Service version (semantic versioning: major.minor.patch).

        Returns:
            Version string (e.g., '1.0.0', '2.1.3')
        """

    async def start(self) -> None:
        """
        Start service (optional lifecycle hook).

        Use for async initialization:
        - Opening database connections
        - Starting background tasks
        - Initializing API clients

        Called when service is started via ServiceRegistry.start().
        """
        pass

    async def stop(self) -> None:
        """
        Stop service (optional lifecycle hook).

        Use for cleanup:
        - Closing connections
        - Stopping background tasks
        - Releasing resources

        Called when service is stopped via ServiceRegistry.stop().
        """
        pass

    def __repr__(self) -> str:
        """Developer representation."""
        return f"<{self.__class__.__name__}: {self.service_name} v{self.service_version}>"


@dataclass
class ServiceRegistration:
    """
    Service registration information.

    Tracks service instance, provider plugin, version, and dependencies.

    Attributes:
        service: Service instance
        provider: Name of plugin providing service
        version: Service version (from service.service_version)
        dependencies: Required services {service_name: min_version}
    """

    service: Service
    provider: str
    version: str
    dependencies: Dict[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:
        """Developer representation."""
        dep_str = f", deps={list(self.dependencies.keys())}" if self.dependencies else ""
        return (
            f"<ServiceRegistration: {self.service.service_name} v{self.version} "
            f"by {self.provider}{dep_str}>"
        )
