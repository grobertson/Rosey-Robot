"""Common utilities for CyTube bots."""
from .config import configure_logger, configure_proxy, get_config
# Legacy Shell class - commented out during Sprint 22 NATS migration
# from .shell import Shell

__all__ = ['get_config', 'configure_logger', 'configure_proxy']
