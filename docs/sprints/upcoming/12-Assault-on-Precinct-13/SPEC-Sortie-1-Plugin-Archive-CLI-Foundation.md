# SPEC: Sortie 1 - Plugin Archive Format & CLI Foundation

**Sprint:** Sprint 12 "Assault on Precinct 13" - Defending the boundaries  
**Sortie:** 1 of 4  
**Version:** 1.0  
**Status:** Planning  
**Estimated Duration:** 6-8 hours  
**Dependencies:** Sprint 11 (SQLAlchemy ORM migration) MUST be complete  

---

## Executive Summary

Sortie 1 establishes the foundation for Rosey's plugin system by defining the `.roseyplug` archive format, implementing manifest validation, and creating the basic `rosey` CLI framework. This sortie focuses on **packaging and scaffolding tools** - enabling developers to create, validate, and build plugins without requiring the full plugin runtime system.

**Core Deliverables**:

1. `.roseyplug` archive format specification (ZIP-based)
2. Manifest schema (`manifest.yaml`) with YAML validator
3. Archive extractor and validator
4. Plugin template generator (`rosey plugin create`)
5. Plugin builder (`rosey plugin build`)
6. Basic `rosey` CLI framework (Click-based)

**Success Metric**: Create a plugin from template, build it into `.roseyplug`, and extract/validate the archive - all via CLI commands.

---

## 1. Problem Statement

### 1.1 Current State

**No Packaging Standard**:

- Plugins are loose directories (`examples/markov/`, `examples/echo/`)
- No version tracking
- No dependency declarations
- No permission documentation
- Manual installation instructions in README files

**No Developer Tools**:

- Developers start from scratch each time
- No template or scaffolding
- No validation tools
- No automated build process
- Error-prone manual manifest creation

**No CLI Tool**:

- All bot interaction is via Python scripts
- No unified command interface
- No service management
- No plugin management

### 1.2 Goals

**Packaging Goals**:

- [x] Define `.roseyplug` archive format (ZIP-based)
- [x] Create manifest schema with validation
- [x] Support optional files (assets, migrations, tests)
- [x] Enable Git-based distribution (prepare for Sortie 2)

**Developer Experience Goals**:

- [x] `rosey plugin create <name>` - generate template
- [x] `rosey plugin build [dir]` - package plugin
- [x] Validate manifest during build
- [x] Clear error messages for common mistakes

**CLI Framework Goals**:

- [x] Click-based command structure
- [x] Extensible subcommand architecture
- [x] Consistent output formatting
- [x] Proper exit codes for scripting

---

## 2. Technical Design

### 2.1 `.roseyplug` Archive Format

**File Structure** (ZIP archive):

```text
markov-chat-1.2.0.roseyplug  (ZIP file)
├── manifest.yaml             # REQUIRED - Plugin metadata
├── plugin.py                 # REQUIRED - Entry point
├── requirements.txt          # OPTIONAL - Python dependencies
├── assets/                   # OPTIONAL - Static files
│   ├── icon.png
│   ├── templates/
│   └── static/
├── migrations/               # OPTIONAL - Database migrations
│   ├── 001_initial.sql
│   └── 002_add_indexes.sql
├── tests/                    # OPTIONAL - Unit tests
│   ├── test_plugin.py
│   └── fixtures/
├── README.md                 # OPTIONAL - Documentation
└── LICENSE                   # OPTIONAL - License file
```

**Archive Properties**:

- **Format**: ZIP (Python `zipfile` module)
- **Compression**: DEFLATE (standard ZIP compression)
- **Naming**: `{plugin-name}-{version}.roseyplug`
- **Max Size**: 50MB (soft limit, configurable)
- **Validation**: Manifest must exist at root, `plugin.py` must exist

**Entry Point Requirements**:

- `plugin.py` must contain a class inheriting from `rosey.plugin.Plugin`
- Class name defaults to `{PluginName}Plugin` but configurable via `manifest.yaml:main_class`
- Class must implement `__init__(storage, config, nats, logger)` signature

### 2.2 Manifest Schema (`manifest.yaml`)

**Full Schema** (with validation rules):

```yaml
# ===== REQUIRED FIELDS =====
name: markov-chat                      # Validation: ^[a-z0-9-]+$, length 3-50
version: 1.2.0                         # Validation: Semantic versioning (major.minor.patch)
description: "Short description"       # Validation: 10-500 characters
author: community_user                 # Validation: 2-100 characters

# ===== OPTIONAL IDENTITY FIELDS =====
display_name: Markov Chat Bot          # Default: title(name), Validation: 3-100 chars
homepage: https://github.com/user/markov-chat  # Validation: Valid URL
license: MIT                           # Validation: SPDX identifier (MIT, Apache-2.0, GPL-3.0, etc.)

# ===== ENTRY POINT (OPTIONAL) =====
entry_point: plugin.py                 # Default: plugin.py, Validation: Must exist in archive
main_class: MarkovPlugin               # Default: {PluginName}Plugin, Validation: Valid Python identifier

# ===== DEPENDENCIES (OPTIONAL) =====
python_requires: ">=3.10,<4.0"         # Default: ">=3.10", Validation: PEP 440 version specifier
dependencies:                          # Default: [], Validation: List of valid pip packages
  - markovify>=0.9.0
  - nltk>=3.8.0

# ===== PERMISSIONS (OPTIONAL) =====
permissions:                           # Default: [], Validation: Known permission names only
  - read_messages                      # Subscribe to rosey.chat.message.*
  - send_messages                      # Publish to rosey.chat.send_message
  - database_access                    # Access plugin-specific database
  - http_requests                      # Make external HTTP/HTTPS requests
  - file_read                          # Read from plugin storage directory
  - file_write                         # Write to plugin storage directory

# ===== RESOURCE LIMITS (OPTIONAL - INFORMATIONAL) =====
resources:                             # Default: None, Validation: Positive numbers with units
  cpu_limit: 0.25                      # Suggested max CPU (0.25 = 25%)
  memory_limit: 100M                   # Suggested max RAM (M=MB, G=GB)
  storage_limit: 500M                  # Suggested max storage

# ===== CONFIGURATION SCHEMA (OPTIONAL) =====
config_schema:                         # JSON Schema for plugin config validation
  type: object
  properties:
    markov_order:
      type: integer
      minimum: 1
      maximum: 5
      default: 2
      description: "Markov chain order"
    learn_enabled:
      type: boolean
      default: false
      description: "Learn from chat automatically"
  required:
    - markov_order

# ===== METADATA (OPTIONAL) =====
tags:                                  # Default: [], Validation: 1-30 chars each, max 10 tags
  - chat
  - ai
  - markov
  - text-generation
```

**Validation Rules**:

1. **Required Fields**: `name`, `version`, `description`, `author`
2. **Name Format**: Lowercase alphanumeric + hyphens, 3-50 chars
3. **Version Format**: Semantic versioning (`major.minor.patch`)
4. **Permissions**: Must be from known permission list (see section 2.3)
5. **Config Schema**: Valid JSON Schema (draft 7)
6. **File References**: `entry_point` must exist in archive

**Known Permission Names** (validated at build time):

```python
VALID_PERMISSIONS = [
    # Communication
    "read_messages", "send_messages", "read_media", "control_media",
    # Data Access
    "database_access", "database_migrations", "config_read", "config_write",
    # File System
    "file_read", "file_write", "temp_files",
    # Network
    "http_requests", "websocket_client",
    # Admin (warnings)
    "bot_control", "plugin_management", "system_commands"
]
```

### 2.3 Directory Structure

**New Files**:

```text
rosey/
├── __init__.py
├── __main__.py                 # NEW - CLI entry point
├── cli/                        # NEW - CLI commands
│   ├── __init__.py
│   ├── main.py                 # Root CLI command
│   ├── plugin.py               # Plugin subcommands
│   └── utils.py                # CLI utilities (formatting, colors)
├── plugin/                     # NEW - Plugin system core
│   ├── __init__.py
│   ├── archive.py              # Archive creation/extraction
│   ├── manifest.py             # Manifest validation
│   ├── templates/              # Plugin templates
│   │   ├── manifest.yaml
│   │   ├── plugin.py
│   │   ├── requirements.txt
│   │   ├── tests/
│   │   │   └── test_plugin.py
│   │   ├── README.md
│   │   └── LICENSE
│   └── validator.py            # Archive validation

# Existing structure (unchanged)
lib/
common/
bot/rosey/
examples/
tests/
```

**Installation**:

```bash
# rosey command will be installed via setup.py entry point
[console_scripts]
rosey = rosey.cli.main:main
```

### 2.4 Component Details

#### Component 1: Manifest Validator (`rosey/plugin/manifest.py`)

**Responsibilities**:

- Parse `manifest.yaml` using PyYAML
- Validate required fields
- Validate field formats (name, version, permissions)
- Validate JSON schema for `config_schema`
- Return structured errors with line numbers

**Key Classes**:

```python
class ManifestError(Exception):
    """Raised when manifest validation fails"""
    def __init__(self, field: str, message: str, line: Optional[int] = None):
        self.field = field
        self.message = message
        self.line = line

class ManifestValidator:
    """Validates plugin manifest files"""
    
    VALID_PERMISSIONS = [...]  # List from section 2.3
    
    def validate(self, manifest_path: Path) -> dict:
        """
        Validate manifest file and return parsed data.
        
        Args:
            manifest_path: Path to manifest.yaml
            
        Returns:
            Parsed manifest dict
            
        Raises:
            ManifestError: If validation fails
        """
        pass
    
    def _validate_name(self, name: str) -> None:
        """Validate plugin name format"""
        pass
    
    def _validate_version(self, version: str) -> None:
        """Validate semantic version"""
        pass
    
    def _validate_permissions(self, permissions: List[str]) -> None:
        """Validate permission names"""
        pass
    
    def _validate_config_schema(self, schema: dict) -> None:
        """Validate JSON schema syntax"""
        pass
```

**Validation Examples**:

```python
# Valid manifest
manifest = {
    "name": "markov-chat",
    "version": "1.2.0",
    "description": "Markov chain text generation",
    "author": "community_user",
    "permissions": ["read_messages", "send_messages"]
}
validator.validate(manifest_path)  # ✅ Success

# Invalid: bad name format
manifest["name"] = "Markov_Chat"  # Uppercase + underscore
validator.validate(manifest_path)  # ❌ ManifestError: Invalid name format

# Invalid: unknown permission
manifest["permissions"] = ["read_messages", "nuclear_launch"]
validator.validate(manifest_path)  # ❌ ManifestError: Unknown permission 'nuclear_launch'
```

#### Component 2: Archive Manager (`rosey/plugin/archive.py`)

**Responsibilities**:

- Create `.roseyplug` ZIP archives from directories
- Extract `.roseyplug` archives to directories
- Validate archive structure
- Handle compression

**Key Classes**:

```python
class ArchiveError(Exception):
    """Raised when archive operations fail"""
    pass

class PluginArchive:
    """Manages .roseyplug archive creation and extraction"""
    
    MAX_SIZE = 50 * 1024 * 1024  # 50MB
    REQUIRED_FILES = ["manifest.yaml", "plugin.py"]
    
    def __init__(self, archive_path: Path):
        self.archive_path = archive_path
    
    def create(self, source_dir: Path) -> None:
        """
        Create .roseyplug archive from directory.
        
        Args:
            source_dir: Directory containing plugin files
            
        Raises:
            ArchiveError: If creation fails
        """
        pass
    
    def extract(self, dest_dir: Path) -> None:
        """
        Extract .roseyplug archive to directory.
        
        Args:
            dest_dir: Destination directory
            
        Raises:
            ArchiveError: If extraction fails
        """
        pass
    
    def validate(self) -> None:
        """
        Validate archive structure and contents.
        
        Raises:
            ArchiveError: If validation fails
        """
        pass
    
    def get_manifest(self) -> dict:
        """
        Read and parse manifest from archive without extracting.
        
        Returns:
            Parsed manifest dict
        """
        pass
```

**Archive Creation Algorithm**:

```python
def create(self, source_dir: Path) -> None:
    # 1. Validate source directory exists
    if not source_dir.exists():
        raise ArchiveError(f"Source directory not found: {source_dir}")
    
    # 2. Validate required files exist
    for required in self.REQUIRED_FILES:
        if not (source_dir / required).exists():
            raise ArchiveError(f"Required file missing: {required}")
    
    # 3. Validate manifest
    manifest_path = source_dir / "manifest.yaml"
    manifest = ManifestValidator().validate(manifest_path)
    
    # 4. Create ZIP archive
    with zipfile.ZipFile(self.archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(source_dir)
                # Skip __pycache__, .pyc, .DS_Store, etc.
                if self._should_include(file_path):
                    zf.write(file_path, arcname)
    
    # 5. Validate archive size
    size = self.archive_path.stat().st_size
    if size > self.MAX_SIZE:
        self.archive_path.unlink()
        raise ArchiveError(f"Archive too large: {size / 1024 / 1024:.1f}MB (max: 50MB)")
```

#### Component 3: Plugin Template Generator (`rosey/plugin/templates/`)

**Template Files** (copied verbatim on `rosey plugin create`):

**`manifest.yaml`**:

```yaml
# Plugin Identity
name: my-plugin
version: 0.1.0
display_name: My Plugin
description: A new Rosey plugin
author: your_name
homepage: https://github.com/your_name/my-plugin
license: MIT

# Python Requirements
python_requires: ">=3.10,<4.0"
dependencies: []

# Permissions (uncomment as needed)
permissions:
  - read_messages    # Subscribe to chat events
  - send_messages    # Send chat messages
  # - database_access  # Use plugin database
  # - http_requests    # Make HTTP requests
  # - file_read        # Read from plugin storage
  # - file_write       # Write to plugin storage

# Configuration Schema
config_schema:
  type: object
  properties:
    enabled:
      type: boolean
      default: true
      description: Enable/disable plugin
  required: []

# Discovery Tags
tags:
  - example
```

**`plugin.py`**:

```python
"""My Plugin - A new Rosey plugin"""
from typing import Any, Dict
from rosey.plugin import Plugin, on_event
import logging

logger = logging.getLogger(__name__)


class MyPlugin(Plugin):
    """Main plugin class"""
    
    def __init__(self, storage: Any, config: Dict[str, Any], nats: Any, logger: logging.Logger):
        """
        Initialize plugin.
        
        Args:
            storage: PluginStorage instance (database + files)
            config: Plugin configuration dict
            nats: NATS client instance
            logger: Logger instance
        """
        super().__init__(storage, config, nats, logger)
        self.enabled = config.get('enabled', True)
        logger.info("MyPlugin initialized")
    
    async def on_load(self) -> None:
        """
        Called when plugin loads.
        
        Use this for:
        - Database table creation
        - Loading models/data
        - Initializing state
        """
        self.logger.info("Plugin loaded!")
        
        # Example: Create database table
        # await self.storage.execute("""
        #     CREATE TABLE IF NOT EXISTS my_data (
        #         id INTEGER PRIMARY KEY,
        #         content TEXT NOT NULL,
        #         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        #     )
        # """)
    
    @on_event('rosey.chat.message.user_joined')
    async def handle_user_joined(self, event: Dict[str, Any]) -> None:
        """
        Handle user joined event.
        
        Args:
            event: Event data with 'username', 'rank', etc.
        """
        if not self.enabled:
            return
        
        username = event.get('username', 'Unknown')
        self.logger.info(f"{username} joined the chat")
        
        # Example: Send welcome message
        # await self.send_message(f"Welcome {username}!")
    
    @on_event('rosey.chat.message.chat')
    async def handle_chat_message(self, event: Dict[str, Any]) -> None:
        """
        Handle chat message event.
        
        Args:
            event: Event data with 'user', 'content', 'timestamp', etc.
        """
        if not self.enabled:
            return
        
        user = event.get('user', 'Unknown')
        content = event.get('content', '')
        
        # Example: Respond to command
        if content.startswith('!myplugin'):
            await self.send_message(f"{user}: Plugin is working! 🎉")
    
    async def on_unload(self) -> None:
        """
        Called when plugin unloads.
        
        Use this for:
        - Saving state
        - Closing connections
        - Cleanup
        """
        self.logger.info("Plugin unloaded!")
```

**`requirements.txt`**:

```text
# Add your plugin dependencies here
# Example:
# requests>=2.31.0
# beautifulsoup4>=4.12.0
```

**`tests/test_plugin.py`**:

```python
"""Tests for my-plugin"""
import pytest
from rosey.plugin.testing import PluginTestCase


class TestMyPlugin(PluginTestCase):
    """Test suite for MyPlugin"""
    
    plugin_class = None  # Will be set by test framework
    
    @pytest.fixture
    def config(self):
        """Plugin configuration for tests"""
        return {"enabled": True}
    
    async def test_user_joined_sends_welcome(self):
        """Test that user joined event triggers welcome message"""
        # Simulate user_joined event
        await self.emit_event('rosey.chat.message.user_joined', {
            'username': 'TestUser'
        })
        
        # Verify message was sent (when implemented)
        # messages = self.get_sent_messages()
        # assert len(messages) == 1
        # assert "Welcome TestUser" in messages[0]['content']
    
    async def test_command_response(self):
        """Test that !myplugin command triggers response"""
        # Simulate chat message
        await self.emit_event('rosey.chat.message.chat', {
            'user': 'TestUser',
            'content': '!myplugin'
        })
        
        # Verify response (when implemented)
        # messages = self.get_sent_messages()
        # assert len(messages) == 1
        # assert "Plugin is working" in messages[0]['content']
    
    async def test_disabled_plugin_ignores_events(self):
        """Test that disabled plugin doesn't respond"""
        # Configure plugin as disabled
        self.plugin.enabled = False
        
        # Simulate event
        await self.emit_event('rosey.chat.message.chat', {
            'user': 'TestUser',
            'content': '!myplugin'
        })
        
        # Verify no messages sent
        # messages = self.get_sent_messages()
        # assert len(messages) == 0
```

**`README.md`**:

```markdown
# My Plugin

A new Rosey plugin.

## Description

[Add detailed description here]

## Features

- Feature 1
- Feature 2

## Installation

```bash
rosey plugin install my-plugin-0.1.0.roseyplug
```

## Configuration

```yaml
plugins:
  my-plugin:
    enabled: true
```

## Commands

- `!myplugin` - Test command

## Permissions

- `read_messages` - Subscribe to chat events
- `send_messages` - Send chat messages

## Development

```bash
# Create development environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/
```

## License

MIT
```

**`LICENSE`**:

```text
MIT License

Copyright (c) [year] [author]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

[... standard MIT license text ...]
```

### Component 4: CLI Framework (`rosey/cli/`)

**Command Structure**:

```bash
rosey                           # Root command (shows help)
├── plugin                      # Plugin management (this sortie)
│   ├── create <name>          # Generate plugin template
│   ├── build [directory]      # Build .roseyplug archive
│   └── info <archive>         # Show archive info (manifest)
├── start [service]            # Start services (Sortie 3)
├── stop [service]             # Stop services (Sortie 3)
├── status                     # Service status (Sortie 3)
├── logs [service]             # Tail logs (Sortie 3)
├── db                         # Database commands (Sortie 4)
│   ├── migrate
│   ├── backup
│   └── shell
├── config                     # Config commands (Sortie 4)
│   ├── show
│   └── validate
└── version                    # Show version (Sortie 4)
```

**CLI Implementation** (`rosey/cli/main.py`):

```python
"""Rosey CLI - Main entry point"""
import click
from rosey.cli.plugin import plugin_cli


@click.group()
@click.version_option(version='0.7.0', prog_name='rosey')
def main():
    """
    Rosey - CyTube Bot with Plugin System
    
    Manage bot services, plugins, database, and configuration.
    """
    pass


# Register subcommands
main.add_command(plugin_cli, name='plugin')

# Sortie 3 will add: start, stop, restart, status, logs, dev
# Sortie 4 will add: db, config, version, doctor, clean


if __name__ == '__main__':
    main()
```

**Plugin Commands** (`rosey/cli/plugin.py`):

```python
"""Rosey CLI - Plugin commands"""
import click
from pathlib import Path
from rosey.plugin.archive import PluginArchive, ArchiveError
from rosey.plugin.manifest import ManifestValidator, ManifestError
from rosey.cli.utils import success, error, info, format_manifest
import shutil


@click.group()
def plugin_cli():
    """Manage plugins (create, build, install, remove)"""
    pass


@plugin_cli.command('create')
@click.argument('name')
@click.option('--author', default='', help='Plugin author name')
def create_plugin(name: str, author: str):
    """
    Create a new plugin from template.
    
    Args:
        name: Plugin name (lowercase, hyphens only)
    """
    try:
        # Validate name format
        if not name.islower() or not name.replace('-', '').isalnum():
            raise click.ClickException("Name must be lowercase alphanumeric with hyphens")
        
        # Create plugin directory
        plugin_dir = Path(name)
        if plugin_dir.exists():
            raise click.ClickException(f"Directory '{name}' already exists")
        
        plugin_dir.mkdir()
        
        # Copy template files
        template_dir = Path(__file__).parent.parent / 'plugin' / 'templates'
        
        # Copy and customize manifest.yaml
        manifest_content = (template_dir / 'manifest.yaml').read_text()
        manifest_content = manifest_content.replace('my-plugin', name)
        if author:
            manifest_content = manifest_content.replace('your_name', author)
        (plugin_dir / 'manifest.yaml').write_text(manifest_content)
        
        # Copy other template files
        for template_file in ['plugin.py', 'requirements.txt', 'README.md', 'LICENSE']:
            content = (template_dir / template_file).read_text()
            content = content.replace('my-plugin', name)
            content = content.replace('MyPlugin', _to_class_name(name))
            (plugin_dir / template_file).write_text(content)
        
        # Copy tests directory
        tests_dir = plugin_dir / 'tests'
        tests_dir.mkdir()
        shutil.copy(template_dir / 'tests' / 'test_plugin.py', tests_dir)
        
        success(f"Created plugin '{name}' in ./{name}/")
        info("\nNext steps:")
        info(f"  1. cd {name}")
        info("  2. Edit manifest.yaml with plugin details")
        info("  3. Implement plugin.py")
        info("  4. rosey plugin build")
        
    except Exception as e:
        error(f"Failed to create plugin: {e}")
        raise click.Abort()


@plugin_cli.command('build')
@click.argument('directory', type=click.Path(exists=True), default='.')
@click.option('--output', '-o', help='Output path (default: <name>-<version>.roseyplug)')
def build_plugin(directory: str, output: str):
    """
    Build .roseyplug archive from plugin directory.
    
    Args:
        directory: Plugin directory (default: current directory)
        output: Output archive path
    """
    try:
        source_dir = Path(directory)
        
        # Validate manifest first
        manifest_path = source_dir / 'manifest.yaml'
        if not manifest_path.exists():
            raise click.ClickException("manifest.yaml not found")
        
        info("Validating manifest...")
        validator = ManifestValidator()
        manifest = validator.validate(manifest_path)
        
        # Determine output path
        if not output:
            name = manifest['name']
            version = manifest['version']
            output = f"{name}-{version}.roseyplug"
        
        output_path = Path(output)
        
        # Create archive
        info(f"Building {output_path.name}...")
        archive = PluginArchive(output_path)
        archive.create(source_dir)
        
        # Show summary
        size = output_path.stat().st_size
        size_mb = size / 1024 / 1024
        success(f"Built {output_path.name} ({size_mb:.2f}MB)")
        
        info("\nPlugin Details:")
        info(f"  Name: {manifest['name']}")
        info(f"  Version: {manifest['version']}")
        info(f"  Author: {manifest['author']}")
        if manifest.get('permissions'):
            info(f"  Permissions: {', '.join(manifest['permissions'])}")
        
        info("\nNext steps:")
        info(f"  rosey plugin install {output_path.name}")
        info("  OR share on GitHub with topic: rosey-plugin")
        
    except ManifestError as e:
        error(f"Manifest validation failed: {e.message}")
        if e.field:
            error(f"  Field: {e.field}")
        raise click.Abort()
    except ArchiveError as e:
        error(f"Archive build failed: {e}")
        raise click.Abort()
    except Exception as e:
        error(f"Build failed: {e}")
        raise click.Abort()


@plugin_cli.command('info')
@click.argument('archive', type=click.Path(exists=True))
def plugin_info(archive: str):
    """
    Show information about a .roseyplug archive.
    
    Args:
        archive: Path to .roseyplug file
    """
    try:
        archive_path = Path(archive)
        
        # Validate and read manifest
        info("Reading archive...")
        plugin_archive = PluginArchive(archive_path)
        plugin_archive.validate()
        manifest = plugin_archive.get_manifest()
        
        # Format and display
        click.echo(format_manifest(manifest, archive_path))
        
    except ArchiveError as e:
        error(f"Invalid archive: {e}")
        raise click.Abort()
    except Exception as e:
        error(f"Failed to read archive: {e}")
        raise click.Abort()


def _to_class_name(plugin_name: str) -> str:
    """Convert plugin-name to PluginName"""
    return ''.join(word.capitalize() for word in plugin_name.split('-'))
```

**CLI Utilities** (`rosey/cli/utils.py`):

```python
"""Rosey CLI - Utility functions"""
import click
from typing import Dict, Any
from pathlib import Path


def success(message: str):
    """Print success message (green)"""
    click.secho(f"✓ {message}", fg='green')


def error(message: str):
    """Print error message (red)"""
    click.secho(f"✗ {message}", fg='red', err=True)


def info(message: str):
    """Print info message (cyan)"""
    click.secho(message, fg='cyan')


def warning(message: str):
    """Print warning message (yellow)"""
    click.secho(f"⚠ {message}", fg='yellow')


def format_manifest(manifest: Dict[str, Any], archive_path: Path = None) -> str:
    """
    Format manifest for display.
    
    Args:
        manifest: Parsed manifest dict
        archive_path: Optional path to archive file
        
    Returns:
        Formatted string
    """
    lines = []
    
    if archive_path:
        size = archive_path.stat().st_size
        size_mb = size / 1024 / 1024
        lines.append(f"Archive: {archive_path.name} ({size_mb:.2f}MB)")
        lines.append("")
    
    lines.append(f"Name: {manifest['name']}")
    lines.append(f"Version: {manifest['version']}")
    lines.append(f"Description: {manifest['description']}")
    lines.append(f"Author: {manifest['author']}")
    
    if manifest.get('homepage'):
        lines.append(f"Homepage: {manifest['homepage']}")
    
    if manifest.get('license'):
        lines.append(f"License: {manifest['license']}")
    
    if manifest.get('python_requires'):
        lines.append(f"Python: {manifest['python_requires']}")
    
    if manifest.get('dependencies'):
        lines.append("\nDependencies:")
        for dep in manifest['dependencies']:
            lines.append(f"  - {dep}")
    
    if manifest.get('permissions'):
        lines.append("\nPermissions:")
        for perm in manifest['permissions']:
            lines.append(f"  - {perm}")
    
    if manifest.get('tags'):
        lines.append(f"\nTags: {', '.join(manifest['tags'])}")
    
    return "\n".join(lines)
```

---

## 3. Implementation Plan

### 3.1 Phase 1: Core Infrastructure (2-3 hours)

**Tasks**:

1. **Create directory structure**:
   - `rosey/cli/` with `main.py`, `plugin.py`, `utils.py`
   - `rosey/plugin/` with `archive.py`, `manifest.py`, `validator.py`
   - `rosey/plugin/templates/` with all template files

2. **Implement ManifestValidator**:
   - Parse YAML
   - Validate required fields
   - Validate formats (name, version, permissions)
   - Error messages with line numbers

3. **Implement PluginArchive**:
   - Create ZIP archives from directories
   - Extract archives
   - Validate archive structure
   - Size limits

4. **Set up CLI framework**:
   - Click-based command structure
   - Entry point in `setup.py`
   - Basic `rosey` command

**Acceptance Criteria**:

- ✅ `rosey --version` works
- ✅ `ManifestValidator` validates all test cases
- ✅ `PluginArchive` creates valid ZIP archives

### 3.2 Phase 2: Plugin Commands (2-3 hours)

**Tasks**:

1. **Implement `rosey plugin create`**:
   - Copy template files
   - Customize manifest with plugin name
   - Create tests directory
   - Show next steps

2. **Implement `rosey plugin build`**:
   - Validate manifest
   - Create archive
   - Show summary with size and details
   - Error handling

3. **Implement `rosey plugin info`**:
   - Read archive manifest
   - Format and display
   - Show file count and size

4. **Create template files**:
   - Complete all templates from section 2.4
   - Test substitution logic

**Acceptance Criteria**:

- ✅ `rosey plugin create test-plugin` generates valid template
- ✅ `rosey plugin build` creates valid `.roseyplug` archive
- ✅ `rosey plugin info test-plugin-0.1.0.roseyplug` displays manifest

### 3.3 Phase 3: Testing & Documentation (2 hours)

**Tasks**:

1. **Unit tests**:
   - `test_manifest_validator.py` - all validation rules
   - `test_plugin_archive.py` - create/extract/validate
   - `test_cli_plugin.py` - create/build/info commands

2. **Integration test**:
   - Full workflow: create → edit → build → info
   - Validate archive structure
   - Validate manifest in archive

3. **Documentation**:
   - Update README with CLI usage
   - Add developer guide for plugin creation
   - Add troubleshooting section

**Acceptance Criteria**:

- ✅ 90%+ test coverage for new code
- ✅ All CLI commands tested
- ✅ Documentation complete

---

## 4. Testing Strategy

### 4.1 Unit Tests

**`tests/unit/plugin/test_manifest_validator.py`**:

```python
"""Tests for manifest validation"""
import pytest
from pathlib import Path
from rosey.plugin.manifest import ManifestValidator, ManifestError


def test_validate_valid_manifest(tmp_path):
    """Test validation of valid manifest"""
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("""
name: test-plugin
version: 1.0.0
description: Test plugin
author: test_user
permissions:
  - read_messages
  - send_messages
""")
    
    validator = ManifestValidator()
    result = validator.validate(manifest)
    
    assert result['name'] == 'test-plugin'
    assert result['version'] == '1.0.0'
    assert len(result['permissions']) == 2


def test_validate_missing_required_field(tmp_path):
    """Test validation fails with missing required field"""
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("""
name: test-plugin
version: 1.0.0
# Missing: description, author
""")
    
    validator = ManifestValidator()
    
    with pytest.raises(ManifestError) as exc:
        validator.validate(manifest)
    
    assert 'description' in str(exc.value).lower()


def test_validate_invalid_name_format(tmp_path):
    """Test validation fails with invalid name"""
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("""
name: Test_Plugin
version: 1.0.0
description: Test
author: test
""")
    
    validator = ManifestValidator()
    
    with pytest.raises(ManifestError) as exc:
        validator.validate(manifest)
    
    assert 'name' in exc.value.field.lower()


def test_validate_invalid_version(tmp_path):
    """Test validation fails with invalid version"""
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("""
name: test-plugin
version: 1.0
description: Test
author: test
""")
    
    validator = ManifestValidator()
    
    with pytest.raises(ManifestError) as exc:
        validator.validate(manifest)
    
    assert 'version' in exc.value.field.lower()


def test_validate_unknown_permission(tmp_path):
    """Test validation fails with unknown permission"""
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("""
name: test-plugin
version: 1.0.0
description: Test
author: test
permissions:
  - read_messages
  - nuclear_launch
""")
    
    validator = ManifestValidator()
    
    with pytest.raises(ManifestError) as exc:
        validator.validate(manifest)
    
    assert 'nuclear_launch' in str(exc.value)
```

**`tests/unit/plugin/test_plugin_archive.py`**:

```python
"""Tests for plugin archive management"""
import pytest
from pathlib import Path
from rosey.plugin.archive import PluginArchive, ArchiveError
import zipfile


def test_create_archive(tmp_path):
    """Test creating .roseyplug archive"""
    # Create plugin directory
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()
    
    (plugin_dir / "manifest.yaml").write_text("""
name: test-plugin
version: 1.0.0
description: Test
author: test
""")
    (plugin_dir / "plugin.py").write_text("# Plugin code")
    
    # Create archive
    archive_path = tmp_path / "test-plugin-1.0.0.roseyplug"
    archive = PluginArchive(archive_path)
    archive.create(plugin_dir)
    
    # Verify archive exists and is valid ZIP
    assert archive_path.exists()
    assert zipfile.is_zipfile(archive_path)
    
    # Verify contents
    with zipfile.ZipFile(archive_path) as zf:
        names = zf.namelist()
        assert "manifest.yaml" in names
        assert "plugin.py" in names


def test_create_archive_missing_manifest(tmp_path):
    """Test archive creation fails without manifest"""
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text("# Code")
    
    archive_path = tmp_path / "test.roseyplug"
    archive = PluginArchive(archive_path)
    
    with pytest.raises(ArchiveError) as exc:
        archive.create(plugin_dir)
    
    assert 'manifest.yaml' in str(exc.value).lower()


def test_extract_archive(tmp_path):
    """Test extracting .roseyplug archive"""
    # Create archive first
    plugin_dir = tmp_path / "source"
    plugin_dir.mkdir()
    (plugin_dir / "manifest.yaml").write_text("name: test\nversion: 1.0.0\ndescription: Test\nauthor: test")
    (plugin_dir / "plugin.py").write_text("# Code")
    
    archive_path = tmp_path / "test.roseyplug"
    archive = PluginArchive(archive_path)
    archive.create(plugin_dir)
    
    # Extract to new directory
    extract_dir = tmp_path / "extracted"
    archive.extract(extract_dir)
    
    # Verify extracted files
    assert (extract_dir / "manifest.yaml").exists()
    assert (extract_dir / "plugin.py").exists()


def test_validate_archive(tmp_path):
    """Test archive validation"""
    # Create valid archive
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "manifest.yaml").write_text("name: test\nversion: 1.0.0\ndescription: Test\nauthor: test")
    (plugin_dir / "plugin.py").write_text("# Code")
    
    archive_path = tmp_path / "test.roseyplug"
    archive = PluginArchive(archive_path)
    archive.create(plugin_dir)
    
    # Should not raise
    archive.validate()


def test_get_manifest(tmp_path):
    """Test reading manifest from archive"""
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "manifest.yaml").write_text("""
name: test-plugin
version: 1.2.3
description: Test plugin
author: test_user
""")
    (plugin_dir / "plugin.py").write_text("# Code")
    
    archive_path = tmp_path / "test.roseyplug"
    archive = PluginArchive(archive_path)
    archive.create(plugin_dir)
    
    # Read manifest without extracting
    manifest = archive.get_manifest()
    
    assert manifest['name'] == 'test-plugin'
    assert manifest['version'] == '1.2.3'
    assert manifest['author'] == 'test_user'
```

### 4.2 Integration Tests

**`tests/integration/test_plugin_workflow.py`**:

```python
"""Integration tests for plugin workflow"""
import pytest
from pathlib import Path
from click.testing import CliRunner
from rosey.cli.main import main


def test_full_plugin_workflow(tmp_path):
    """Test complete plugin creation workflow"""
    runner = CliRunner()
    
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Step 1: Create plugin
        result = runner.invoke(main, ['plugin', 'create', 'test-plugin', '--author', 'test_user'])
        assert result.exit_code == 0
        assert 'Created plugin' in result.output
        assert Path('test-plugin').exists()
        
        # Step 2: Verify template files exist
        assert (Path('test-plugin') / 'manifest.yaml').exists()
        assert (Path('test-plugin') / 'plugin.py').exists()
        assert (Path('test-plugin') / 'tests').exists()
        
        # Step 3: Build archive
        result = runner.invoke(main, ['plugin', 'build', 'test-plugin'])
        assert result.exit_code == 0
        assert 'Built' in result.output
        assert Path('test-plugin-0.1.0.roseyplug').exists()
        
        # Step 4: Show info
        result = runner.invoke(main, ['plugin', 'info', 'test-plugin-0.1.0.roseyplug'])
        assert result.exit_code == 0
        assert 'test-plugin' in result.output
        assert '0.1.0' in result.output
```

### 4.3 Manual Testing Checklist

**End-to-End Workflow**:

- [ ] Create plugin: `rosey plugin create my-test-plugin`
- [ ] Verify files created: `manifest.yaml`, `plugin.py`, `tests/`, `README.md`, `LICENSE`
- [ ] Edit manifest: Add description, permissions
- [ ] Build archive: `rosey plugin build my-test-plugin`
- [ ] Verify archive created: `my-test-plugin-0.1.0.roseyplug`
- [ ] Show info: `rosey plugin info my-test-plugin-0.1.0.roseyplug`
- [ ] Verify manifest displayed correctly

**Error Handling**:

- [ ] Create plugin with invalid name (uppercase, underscores)
- [ ] Build plugin without manifest.yaml
- [ ] Build plugin with invalid manifest (missing fields)
- [ ] Build plugin with unknown permissions
- [ ] Show info on non-existent file
- [ ] Show info on invalid archive

---

## 5. Dependencies

### 5.1 Python Packages

**New Dependencies** (add to `requirements.txt`):

```text
click>=8.1.0              # CLI framework
pyyaml>=6.0               # YAML parsing
jsonschema>=4.17.0        # JSON schema validation
```

**Dev Dependencies** (add to `requirements-dev.txt`):

```text
pytest-click>=1.1.0       # Click CLI testing
```

### 5.2 External Dependencies

**None** - This sortie is self-contained (no NATS, no database runtime).

---

## 6. Acceptance Criteria

### 6.1 Functional Requirements

- [x] `rosey plugin create <name>` generates complete plugin template
- [x] `rosey plugin build [dir]` creates valid `.roseyplug` archive
- [x] `rosey plugin info <archive>` displays manifest information
- [x] Manifest validation catches all error cases
- [x] Archive creation handles file exclusions (`.pyc`, `__pycache__`, etc.)
- [x] CLI shows colored output (success=green, error=red, info=cyan)
- [x] CLI returns proper exit codes (0=success, non-zero=error)

### 6.2 Non-Functional Requirements

- [x] CLI responses are fast (<100ms for create/build)
- [x] Error messages are clear and actionable
- [x] Template files are production-ready (valid Python, proper docstrings)
- [x] Archive size limit enforced (50MB)
- [x] Manifest validation comprehensive (catches 95%+ of common errors)

### 6.3 Test Coverage

- [x] Unit tests: 90%+ coverage for `manifest.py`, `archive.py`
- [x] CLI tests: All commands (`create`, `build`, `info`)
- [x] Integration tests: Full workflow (create → build → info)
- [x] Edge cases: Invalid inputs, missing files, large archives

---

## 7. Documentation Requirements

### 7.1 User Documentation

**`docs/guides/PLUGIN_DEVELOPMENT.md`** (create):

```markdown
# Plugin Development Guide

## Quick Start

​```bash
# Create plugin from template
rosey plugin create my-awesome-plugin --author your_name

# Edit plugin files
cd my-awesome-plugin
# Edit manifest.yaml, plugin.py

# Build archive
rosey plugin build

# Test (Sortie 2+)
rosey plugin install my-awesome-plugin-0.1.0.roseyplug
```

## Manifest Reference

[Full manifest schema with examples]

## Plugin Template

[Explain plugin.py structure, on_event decorator, storage API]

## Best Practices

[Permissions, error handling, testing, documentation]
```

### 7.2 Developer Documentation

**Update `README.md`**:

```markdown
## Plugin System (v0.7.0)

Rosey now supports a plugin system with `.roseyplug` archives.

### Creating Plugins

```bash
# Generate plugin template
rosey plugin create my-plugin

# Build archive
cd my-plugin
rosey plugin build
```

### Installing Plugins (Coming in v0.7.0)

```bash
# Local file
rosey plugin install my-plugin-1.0.0.roseyplug

# Git repository
rosey plugin install https://github.com/user/plugin.git
```

See [Plugin Development Guide](docs/guides/PLUGIN_DEVELOPMENT.md) for details.
```

---

## 8. Rollback Plan

### 8.1 Rollback Triggers

- Critical bugs in manifest validation
- CLI crashes on common inputs
- Archive corruption issues
- Breaking changes to template format

### 8.2 Rollback Procedure

1. **Remove `rosey` CLI entry point** from `setup.py`
2. **Remove new directories**: `rosey/cli/`, `rosey/plugin/`
3. **Restore `requirements.txt`**: Remove `click`, `pyyaml`, `jsonschema`
4. **Revert documentation changes**

**Recovery Time**: <15 minutes (no runtime impact, just CLI tools)

---

## 9. Deployment Checklist

### 9.1 Pre-Deployment

- [ ] All unit tests pass (90%+ coverage)
- [ ] All integration tests pass
- [ ] Manual workflow tested end-to-end
- [ ] Documentation complete and reviewed
- [ ] CLI help text verified (`rosey --help`, `rosey plugin --help`)

### 9.2 Deployment Steps

```bash
# 1. Update dependencies
pip install -r requirements.txt

# 2. Reinstall package with CLI entry point
pip install -e .

# 3. Verify CLI installation
rosey --version

# 4. Test plugin creation
rosey plugin create test-demo
rosey plugin build test-demo

# 5. Verify archive
rosey plugin info test-demo-0.1.0.roseyplug
```

### 9.3 Post-Deployment Validation

- [ ] `rosey --version` shows v0.7.0
- [ ] `rosey plugin create` generates valid template
- [ ] `rosey plugin build` creates valid archive
- [ ] All existing bot functionality still works (no regression)

---

## 10. Future Enhancements (Deferred)

**Not in Sortie 1** (handled by later sorties):

- ❌ Plugin installation (`rosey plugin install`) - Sortie 2
- ❌ Plugin loading/runtime - Sortie 2
- ❌ Service management (`rosey start/stop`) - Sortie 3
- ❌ Database CLI (`rosey db`) - Sortie 4
- ❌ Git repository cloning - Sortie 2
- ❌ Plugin storage isolation - Sortie 2

**Possible Sortie 1 Improvements** (if time permits):

- `rosey plugin validate <dir>` - Validate plugin without building
- `rosey plugin pack <archive>` - Repack existing archive (update manifest)
- `rosey plugin unpack <archive> <dir>` - Alias for extract
- Better error messages with suggestions (e.g., "Did you mean 'read_messages'?")

---

## Appendices

### A. File Exclusion List

**Files to skip during archive creation**:

```python
EXCLUDED_PATTERNS = [
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '*.pyd',
    '.DS_Store',
    '.git',
    '.gitignore',
    '.venv',
    'venv',
    '*.egg-info',
    '.pytest_cache',
    '.coverage',
    'htmlcov',
]
```

### B. Example Valid Manifest

```yaml
name: markov-chat
version: 1.2.0
display_name: Markov Chat Bot
description: Generates responses using Markov chains trained on chat history
author: community_user
homepage: https://github.com/community_user/markov-chat
license: MIT

python_requires: ">=3.10,<4.0"
dependencies:
  - markovify>=0.9.0
  - nltk>=3.8.0

permissions:
  - read_messages
  - send_messages
  - database_access
  - file_read
  - file_write

resources:
  cpu_limit: 0.25
  memory_limit: 100M
  storage_limit: 500M

config_schema:
  type: object
  properties:
    markov_order:
      type: integer
      minimum: 1
      maximum: 5
      default: 2
    learn_enabled:
      type: boolean
      default: false
  required:
    - markov_order

tags:
  - chat
  - ai
  - markov
  - text-generation
```

### C. CLI Output Examples

**`rosey plugin create my-plugin`**:

```text
✓ Created plugin 'my-plugin' in ./my-plugin/

Next steps:
  1. cd my-plugin
  2. Edit manifest.yaml with plugin details
  3. Implement plugin.py
  4. rosey plugin build
```

**`rosey plugin build my-plugin`**:

```text
Validating manifest...
Building my-plugin-0.1.0.roseyplug...
✓ Built my-plugin-0.1.0.roseyplug (0.02MB)

Plugin Details:
  Name: my-plugin
  Version: 0.1.0
  Author: your_name
  Permissions: read_messages, send_messages

Next steps:
  rosey plugin install my-plugin-0.1.0.roseyplug
  OR share on GitHub with topic: rosey-plugin
```

**`rosey plugin info my-plugin-0.1.0.roseyplug`**:

```text
Archive: my-plugin-0.1.0.roseyplug (0.02MB)

Name: my-plugin
Version: 0.1.0
Description: A new Rosey plugin
Author: your_name
Homepage: https://github.com/your_name/my-plugin
License: MIT
Python: >=3.10,<4.0

Permissions:
  - read_messages
  - send_messages

Tags: example
```

---

**Document Status**: ✅ Ready for Implementation  
**Estimated Effort**: 6-8 hours  
**Risk Level**: LOW (no runtime dependencies, pure tooling)  
**Next Sortie**: Sortie 2 - Storage & Plugin Management  

**Key Success Factors**:

1. ✅ Comprehensive manifest validation (catch errors early)
2. ✅ Production-ready templates (developers can use as-is)
3. ✅ Clear CLI output (users know next steps)
4. ✅ Robust archive handling (no corruption)
5. ✅ Excellent error messages (actionable guidance)

**Movie Quote**: *"We're building the walls strong and clear. The siege comes later."* 🎬
