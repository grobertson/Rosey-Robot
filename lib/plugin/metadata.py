"""
lib/plugin/metadata.py

Plugin metadata structure.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PluginMetadata:
    """
    Plugin metadata and requirements.
    
    Defines plugin identity, version, dependencies, and requirements.
    Used by PluginManager for discovery and dependency resolution.
    
    Attributes:
        name: Plugin identifier (lowercase, alphanumeric + underscores)
        display_name: Human-readable name for UI/logs
        version: Semantic version string (e.g., '1.0.0')
        description: Short description of plugin functionality
        author: Plugin author/maintainer
        dependencies: List of required plugin names (loaded before this)
        min_bot_version: Minimum bot version required (optional)
        config_schema: Optional JSON schema for config validation
    
    Example:
        metadata = PluginMetadata(
            name='dice_roller',
            display_name='Dice Roller',
            version='1.0.0',
            description='Roll dice with !roll command',
            author='YourName',
            dependencies=['random_utils']
        )
    """
    name: str
    display_name: str
    version: str
    description: str
    author: str
    dependencies: List[str] = field(default_factory=list)
    min_bot_version: Optional[str] = None
    config_schema: Optional[dict] = None

    def __post_init__(self):
        """Validate metadata after initialization."""
        # Validate name format (lowercase alphanumeric + underscores)
        if not self.name.replace('_', '').isalnum() or not self.name.islower():
            raise ValueError(
                f"Plugin name '{self.name}' must be lowercase alphanumeric "
                "with underscores only"
            )

        # Validate version format (basic semver check)
        version_parts = self.version.split('.')
        if len(version_parts) != 3 or not all(p.isdigit() for p in version_parts):
            raise ValueError(
                f"Plugin version '{self.version}' must be semantic version "
                "(e.g., '1.0.0')"
            )

    def __str__(self) -> str:
        """String representation for logs."""
        return f"{self.display_name} v{self.version}"

    def __repr__(self) -> str:
        """Developer representation."""
        deps = f", deps={self.dependencies}" if self.dependencies else ""
        return f"PluginMetadata(name='{self.name}', version='{self.version}'{deps})"
