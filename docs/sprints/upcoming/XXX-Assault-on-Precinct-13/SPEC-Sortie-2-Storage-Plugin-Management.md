# SPEC: Sortie 2 - Isolated Storage & Plugin Management

**Sprint:** Sprint 12 "Assault on Precinct 13" - Defending the boundaries  
**Sortie:** 2 of 4  
**Version:** 1.0  
**Status:** Planning  
**Estimated Duration:** 6-8 hours  
**Dependencies:** Sortie 1 (Plugin Archive Format & CLI Foundation) MUST be complete  

---

## Executive Summary

Sortie 2 implements the **plugin runtime system** with isolated storage, plugin installation from local files and Git repositories, and complete lifecycle management. This sortie builds on Sortie 1's archive format to create a secure, isolated environment for each plugin with private SQLite databases and sandboxed file access.

**Core Deliverables**:

1. `PluginStorage` class (database + file API)
2. Per-plugin SQLite database isolation (SQLAlchemy)
3. Sandboxed file system access
4. Plugin installation (`rosey plugin install <file|url>`)
5. Plugin removal with complete cleanup
6. Git repository cloning (HTTPS + SSH)
7. Plugin listing with status

**Success Metric**: Install a plugin from `.roseyplug` or Git, verify isolated storage, remove plugin with zero orphaned data.

---

## 1. Problem Statement

### 1.1 Current State (Post-Sortie 1)

**What We Have**:

- ✅ `.roseyplug` archive format defined
- ✅ Manifest validation working
- ✅ CLI framework (`rosey plugin create/build`)
- ✅ Plugin templates

**What's Missing**:

- ❌ No plugin installation mechanism
- ❌ No storage isolation
- ❌ Plugins share `bot_data.db` (data corruption risk)
- ❌ No cleanup on removal (orphaned tables)
- ❌ No Git repository support
- ❌ No plugin lifecycle management

### 1.2 Goals

**Storage Goals**:

- [x] Each plugin gets private SQLite database
- [x] Each plugin gets sandboxed file directory
- [x] Storage API prevents cross-plugin access
- [x] Complete cleanup on plugin removal
- [x] Storage quotas (optional, monitored)

**Installation Goals**:

- [x] Install from local `.roseyplug` files
- [x] Install from Git HTTPS URLs
- [x] Install from Git SSH URLs
- [x] Validate manifest during install
- [x] Install Python dependencies automatically
- [x] Show permissions during install (trust-based)

**Management Goals**:

- [x] `rosey plugin install <source>` - Install plugin
- [x] `rosey plugin remove <name>` - Remove with cleanup
- [x] `rosey plugin list` - Show installed plugins
- [x] `rosey plugin enable/disable <name>` - Control auto-start
- [x] Plugin metadata stored in registry

---

## 2. Technical Design

### 2.1 Directory Structure

**Plugin Storage Layout**:

```text
data/
├── plugins/
│   ├── .registry.json          # Plugin metadata registry
│   ├── markov-chat/            # Plugin installation directory
│   │   ├── manifest.yaml       # Plugin manifest (from archive)
│   │   ├── plugin.py           # Plugin code (from archive)
│   │   ├── requirements.txt    # Dependencies (from archive)
│   │   ├── assets/             # Static files (from archive)
│   │   ├── tests/              # Tests (from archive)
│   │   ├── database.db         # PRIVATE SQLite database
│   │   ├── files/              # SANDBOXED file directory
│   │   │   ├── markov_model.txt
│   │   │   └── cache/
│   │   └── config.yaml         # Plugin-specific config (created at install)
│   ├── quote-bot/
│   │   ├── manifest.yaml
│   │   ├── plugin.py
│   │   ├── database.db
│   │   ├── files/
│   │   │   └── quotes.json
│   │   └── config.yaml
│   └── weather-alerts/
│       ├── manifest.yaml
│       ├── plugin.py
│       ├── database.db
│       ├── files/
│       └── config.yaml
└── bot_data.db                 # Bot core database (ISOLATED from plugins)
```

**Plugin Registry** (`data/plugins/.registry.json`):

```json
{
  "version": "1.0",
  "plugins": {
    "markov-chat": {
      "name": "markov-chat",
      "version": "1.2.0",
      "display_name": "Markov Chat Bot",
      "author": "community_user",
      "install_source": "file:///path/to/markov-chat-1.2.0.roseyplug",
      "installed_at": "2025-11-21T10:30:00Z",
      "enabled": true,
      "status": "stopped",
      "permissions": ["read_messages", "send_messages", "database_access"],
      "storage": {
        "database_size": 2048576,
        "files_size": 512000,
        "total_size": 2560576
      }
    },
    "quote-bot": {
      "name": "quote-bot",
      "version": "2.0.1",
      "display_name": "Quote Bot",
      "author": "rosey_team",
      "install_source": "https://github.com/rosey-plugins/quote-bot",
      "installed_at": "2025-11-20T15:00:00Z",
      "enabled": true,
      "status": "stopped",
      "permissions": ["read_messages", "send_messages", "database_access", "file_write"],
      "storage": {
        "database_size": 1024000,
        "files_size": 256000,
        "total_size": 1280000
      }
    }
  }
}
```

**New Code Structure**:

```text
rosey/
├── plugin/
│   ├── storage.py              # NEW - PluginStorage class
│   ├── manager.py              # NEW - PluginManager class
│   ├── installer.py            # NEW - Plugin installation logic
│   ├── registry.py             # NEW - Plugin registry management
│   └── git.py                  # NEW - Git repository cloning
└── cli/
    └── plugin.py               # UPDATE - Add install/remove/list commands
```

### 2.2 Component Details

#### Component 1: PluginStorage Class (`rosey/plugin/storage.py`)

**Responsibilities**:

- Create isolated SQLite database per plugin
- Provide sandboxed file access API
- Enforce storage boundaries (no cross-plugin access)
- Track storage usage (quotas)
- Clean up all data on plugin removal

**Class Definition**:

```python
"""Plugin storage management with isolation"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import aiosqlite
import logging

logger = logging.getLogger(__name__)


class PluginStorageError(Exception):
    """Raised when storage operations fail"""
    pass


class PluginStorage:
    """
    Isolated storage API for plugins.
    
    Each plugin gets:
    - Private SQLite database (SQLAlchemy async)
    - Sandboxed file directory
    - No access to other plugins' data
    - No access to bot core database
    """
    
    def __init__(self, plugin_name: str, base_dir: Path):
        """
        Initialize plugin storage.
        
        Args:
            plugin_name: Name of the plugin (from manifest)
            base_dir: Base data directory (e.g., data/plugins/)
        """
        self.plugin_name = plugin_name
        self.base_dir = base_dir
        self.plugin_dir = base_dir / plugin_name
        self.db_path = self.plugin_dir / "database.db"
        self.files_dir = self.plugin_dir / "files"
        
        # SQLAlchemy engine (created on first use)
        self._engine: Optional[AsyncEngine] = None
        self._session_maker: Optional[sessionmaker] = None
        
        # Storage limits (from manifest resources)
        self.storage_limit: Optional[int] = None  # bytes
    
    async def initialize(self) -> None:
        """
        Initialize storage directories and database.
        
        Creates:
        - Plugin directory
        - Files subdirectory
        - SQLite database file
        """
        try:
            # Create directories
            self.plugin_dir.mkdir(parents=True, exist_ok=True)
            self.files_dir.mkdir(exist_ok=True)
            
            # Initialize database
            db_url = f"sqlite+aiosqlite:///{self.db_path}"
            self._engine = create_async_engine(
                db_url,
                echo=False,
                future=True
            )
            self._session_maker = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create database file if not exists
            if not self.db_path.exists():
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("SELECT 1")
                    await db.commit()
                logger.info(f"Created database for plugin '{self.plugin_name}'")
            
        except Exception as e:
            raise PluginStorageError(f"Failed to initialize storage: {e}")
    
    # ===== DATABASE API =====
    
    async def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute SELECT query.
        
        Args:
            sql: SQL query string
            params: Query parameters (dict)
            
        Returns:
            List of rows as dicts
        """
        if not self.db_path.exists():
            raise PluginStorageError("Database not initialized")
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(sql, params or {})
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query failed for plugin '{self.plugin_name}': {e}")
            raise PluginStorageError(f"Query failed: {e}")
    
    async def execute(self, sql: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        Execute INSERT/UPDATE/DELETE query.
        
        Args:
            sql: SQL query string
            params: Query parameters (dict)
            
        Returns:
            Number of rows affected
        """
        if not self.db_path.exists():
            raise PluginStorageError("Database not initialized")
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(sql, params or {})
                await db.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Execute failed for plugin '{self.plugin_name}': {e}")
            raise PluginStorageError(f"Execute failed: {e}")
    
    async def get_session(self) -> AsyncSession:
        """
        Get SQLAlchemy async session for ORM usage.
        
        Returns:
            AsyncSession instance
            
        Example:
            async with storage.get_session() as session:
                result = await session.execute(select(MyModel))
                items = result.scalars().all()
        """
        if not self._session_maker:
            raise PluginStorageError("Database not initialized")
        
        return self._session_maker()
    
    # ===== FILE API =====
    
    def _validate_file_path(self, path: str) -> Path:
        """
        Validate file path is within plugin's files directory.
        
        Args:
            path: Relative file path
            
        Returns:
            Absolute resolved path
            
        Raises:
            PluginStorageError: If path escapes sandbox
        """
        # Resolve relative to files directory
        file_path = (self.files_dir / path).resolve()
        
        # Ensure path is within files directory (prevent ../../../ escape)
        if not str(file_path).startswith(str(self.files_dir.resolve())):
            raise PluginStorageError(f"Path escapes sandbox: {path}")
        
        return file_path
    
    async def read_file(self, path: str) -> bytes:
        """
        Read file from plugin storage.
        
        Args:
            path: Relative file path (e.g., "model.txt" or "cache/data.json")
            
        Returns:
            File contents as bytes
        """
        file_path = self._validate_file_path(path)
        
        if not file_path.exists():
            raise PluginStorageError(f"File not found: {path}")
        
        try:
            return file_path.read_bytes()
        except Exception as e:
            raise PluginStorageError(f"Failed to read file: {e}")
    
    async def write_file(self, path: str, content: bytes) -> None:
        """
        Write file to plugin storage.
        
        Args:
            path: Relative file path
            content: File contents as bytes
        """
        file_path = self._validate_file_path(path)
        
        # Check storage limit
        if self.storage_limit:
            current_size = await self.get_storage_size()
            if current_size + len(content) > self.storage_limit:
                raise PluginStorageError(
                    f"Storage limit exceeded: {current_size + len(content)} > {self.storage_limit}"
                )
        
        try:
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            file_path.write_bytes(content)
        except Exception as e:
            raise PluginStorageError(f"Failed to write file: {e}")
    
    async def list_files(self, directory: str = "") -> List[str]:
        """
        List files in directory.
        
        Args:
            directory: Relative directory path (default: root)
            
        Returns:
            List of relative file paths
        """
        dir_path = self._validate_file_path(directory) if directory else self.files_dir
        
        if not dir_path.exists():
            return []
        
        try:
            files = []
            for item in dir_path.rglob('*'):
                if item.is_file():
                    rel_path = item.relative_to(self.files_dir)
                    files.append(str(rel_path))
            return files
        except Exception as e:
            raise PluginStorageError(f"Failed to list files: {e}")
    
    async def delete_file(self, path: str) -> None:
        """
        Delete file from plugin storage.
        
        Args:
            path: Relative file path
        """
        file_path = self._validate_file_path(path)
        
        if not file_path.exists():
            raise PluginStorageError(f"File not found: {path}")
        
        try:
            file_path.unlink()
        except Exception as e:
            raise PluginStorageError(f"Failed to delete file: {e}")
    
    # ===== STORAGE MANAGEMENT =====
    
    async def get_storage_size(self) -> int:
        """
        Get total storage usage (database + files) in bytes.
        
        Returns:
            Total size in bytes
        """
        total = 0
        
        # Database size
        if self.db_path.exists():
            total += self.db_path.stat().st_size
        
        # Files size
        if self.files_dir.exists():
            for file in self.files_dir.rglob('*'):
                if file.is_file():
                    total += file.stat().st_size
        
        return total
    
    async def cleanup(self) -> None:
        """
        Delete all plugin data (database + files).
        
        WARNING: This is irreversible!
        """
        import shutil
        
        try:
            # Close database connections
            if self._engine:
                await self._engine.dispose()
            
            # Delete entire plugin directory
            if self.plugin_dir.exists():
                shutil.rmtree(self.plugin_dir)
                logger.info(f"Cleaned up storage for plugin '{self.plugin_name}'")
        except Exception as e:
            raise PluginStorageError(f"Failed to cleanup storage: {e}")
```

#### Component 2: Plugin Manager (`rosey/plugin/manager.py`)

**Responsibilities**:

- Manage plugin lifecycle (install, enable, disable, remove)
- Maintain plugin registry
- Validate plugin compatibility
- Install Python dependencies

**Class Definition**:

```python
"""Plugin lifecycle management"""
from pathlib import Path
from typing import Dict, List, Optional
import json
import subprocess
import shutil
from datetime import datetime
from rosey.plugin.archive import PluginArchive
from rosey.plugin.manifest import ManifestValidator
from rosey.plugin.storage import PluginStorage
from rosey.plugin.registry import PluginRegistry
import logging

logger = logging.getLogger(__name__)


class PluginManagerError(Exception):
    """Raised when plugin management fails"""
    pass


class PluginManager:
    """
    Manages plugin lifecycle and registry.
    """
    
    def __init__(self, data_dir: Path):
        """
        Initialize plugin manager.
        
        Args:
            data_dir: Base data directory (e.g., data/)
        """
        self.data_dir = data_dir
        self.plugins_dir = data_dir / "plugins"
        self.registry = PluginRegistry(self.plugins_dir)
        
        # Create plugins directory if not exists
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
    
    async def install(self, source: str) -> Dict[str, str]:
        """
        Install plugin from file or Git repository.
        
        Args:
            source: Local file path or Git URL
            
        Returns:
            Plugin metadata dict
            
        Raises:
            PluginManagerError: If installation fails
        """
        logger.info(f"Installing plugin from: {source}")
        
        # Step 1: Extract archive (local file)
        if Path(source).exists():
            return await self._install_from_file(Path(source))
        
        # Step 2: Clone from Git (URL)
        elif source.startswith(('http://', 'https://', 'git@')):
            return await self._install_from_git(source)
        
        else:
            raise PluginManagerError(f"Invalid source: {source}")
    
    async def _install_from_file(self, archive_path: Path) -> Dict[str, str]:
        """Install plugin from .roseyplug file"""
        try:
            # Validate archive
            archive = PluginArchive(archive_path)
            archive.validate()
            
            # Read manifest
            manifest = archive.get_manifest()
            plugin_name = manifest['name']
            
            # Check if already installed
            if self.registry.is_installed(plugin_name):
                raise PluginManagerError(
                    f"Plugin '{plugin_name}' is already installed. "
                    f"Remove it first: rosey plugin remove {plugin_name}"
                )
            
            # Extract to plugins directory
            plugin_dir = self.plugins_dir / plugin_name
            archive.extract(plugin_dir)
            
            # Initialize storage
            storage = PluginStorage(plugin_name, self.plugins_dir)
            await storage.initialize()
            
            # Install Python dependencies
            await self._install_dependencies(plugin_dir)
            
            # Register plugin
            self.registry.register(
                name=plugin_name,
                version=manifest['version'],
                display_name=manifest.get('display_name', plugin_name),
                author=manifest['author'],
                install_source=f"file://{archive_path.absolute()}",
                permissions=manifest.get('permissions', []),
                enabled=True
            )
            
            logger.info(f"Installed plugin '{plugin_name}' v{manifest['version']}")
            
            return {
                'name': plugin_name,
                'version': manifest['version'],
                'source': str(archive_path)
            }
            
        except Exception as e:
            # Cleanup on failure
            plugin_dir = self.plugins_dir / manifest.get('name', 'unknown')
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            raise PluginManagerError(f"Installation failed: {e}")
    
    async def _install_from_git(self, git_url: str) -> Dict[str, str]:
        """Install plugin from Git repository"""
        from rosey.plugin.git import GitInstaller
        
        try:
            # Clone repository to temporary directory
            git_installer = GitInstaller(self.plugins_dir)
            temp_dir = await git_installer.clone(git_url)
            
            # Build .roseyplug archive from cloned repo
            manifest_path = temp_dir / "manifest.yaml"
            if not manifest_path.exists():
                raise PluginManagerError("No manifest.yaml in repository root")
            
            validator = ManifestValidator()
            manifest = validator.validate(manifest_path)
            plugin_name = manifest['name']
            
            # Create archive
            archive_path = temp_dir.parent / f"{plugin_name}.roseyplug"
            archive = PluginArchive(archive_path)
            archive.create(temp_dir)
            
            # Install from created archive
            result = await self._install_from_file(archive_path)
            
            # Update registry with Git source
            self.registry.update(plugin_name, {'install_source': git_url})
            
            # Cleanup temp files
            shutil.rmtree(temp_dir)
            archive_path.unlink()
            
            return result
            
        except Exception as e:
            raise PluginManagerError(f"Git installation failed: {e}")
    
    async def _install_dependencies(self, plugin_dir: Path) -> None:
        """Install plugin Python dependencies"""
        requirements_file = plugin_dir / "requirements.txt"
        
        if not requirements_file.exists():
            logger.debug("No requirements.txt found")
            return
        
        try:
            logger.info("Installing plugin dependencies...")
            
            # Use pip to install requirements
            result = subprocess.run(
                ["pip", "install", "-r", str(requirements_file)],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("Dependencies installed successfully")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e.stderr}")
            raise PluginManagerError(f"Dependency installation failed: {e.stderr}")
    
    async def remove(self, plugin_name: str) -> None:
        """
        Remove plugin and clean up all data.
        
        Args:
            plugin_name: Name of plugin to remove
            
        Raises:
            PluginManagerError: If removal fails
        """
        logger.info(f"Removing plugin: {plugin_name}")
        
        # Check if installed
        if not self.registry.is_installed(plugin_name):
            raise PluginManagerError(f"Plugin '{plugin_name}' is not installed")
        
        try:
            # Cleanup storage (database + files)
            storage = PluginStorage(plugin_name, self.plugins_dir)
            await storage.cleanup()
            
            # Unregister plugin
            self.registry.unregister(plugin_name)
            
            logger.info(f"Removed plugin '{plugin_name}'")
            
        except Exception as e:
            raise PluginManagerError(f"Removal failed: {e}")
    
    def list_plugins(self) -> List[Dict[str, str]]:
        """
        List all installed plugins.
        
        Returns:
            List of plugin metadata dicts
        """
        return self.registry.list_all()
    
    def enable(self, plugin_name: str) -> None:
        """Enable plugin (auto-start)"""
        if not self.registry.is_installed(plugin_name):
            raise PluginManagerError(f"Plugin '{plugin_name}' is not installed")
        
        self.registry.update(plugin_name, {'enabled': True})
        logger.info(f"Enabled plugin '{plugin_name}'")
    
    def disable(self, plugin_name: str) -> None:
        """Disable plugin (don't auto-start)"""
        if not self.registry.is_installed(plugin_name):
            raise PluginManagerError(f"Plugin '{plugin_name}' is not installed")
        
        self.registry.update(plugin_name, {'enabled': False})
        logger.info(f"Disabled plugin '{plugin_name}'")
    
    def get_info(self, plugin_name: str) -> Dict[str, Any]:
        """Get detailed plugin information"""
        if not self.registry.is_installed(plugin_name):
            raise PluginManagerError(f"Plugin '{plugin_name}' is not installed")
        
        plugin = self.registry.get(plugin_name)
        
        # Add storage statistics
        storage = PluginStorage(plugin_name, self.plugins_dir)
        plugin['storage']['total_size'] = asyncio.run(storage.get_storage_size())
        
        return plugin
```

#### Component 3: Plugin Registry (`rosey/plugin/registry.py`)

**Responsibilities**:

- Store plugin metadata in JSON file
- Track installation status
- Update plugin state (enabled/disabled/running)
- Persist changes atomically

**Class Definition**:

```python
"""Plugin registry management"""
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Manages plugin metadata registry.
    
    Registry stored as JSON at: data/plugins/.registry.json
    """
    
    def __init__(self, plugins_dir: Path):
        """
        Initialize registry.
        
        Args:
            plugins_dir: Plugin storage directory
        """
        self.plugins_dir = plugins_dir
        self.registry_file = plugins_dir / ".registry.json"
        self._data = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load registry from file"""
        if not self.registry_file.exists():
            return {
                "version": "1.0",
                "plugins": {}
            }
        
        try:
            with open(self.registry_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            return {"version": "1.0", "plugins": {}}
    
    def _save(self) -> None:
        """Save registry to file (atomic)"""
        try:
            # Write to temp file first
            temp_file = self.registry_file.with_suffix('.json.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self._data, f, indent=2)
            
            # Atomic rename
            temp_file.replace(self.registry_file)
            
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")
            raise
    
    def register(
        self,
        name: str,
        version: str,
        display_name: str,
        author: str,
        install_source: str,
        permissions: List[str],
        enabled: bool = True
    ) -> None:
        """Register new plugin"""
        self._data['plugins'][name] = {
            'name': name,
            'version': version,
            'display_name': display_name,
            'author': author,
            'install_source': install_source,
            'installed_at': datetime.utcnow().isoformat() + 'Z',
            'enabled': enabled,
            'status': 'stopped',
            'permissions': permissions,
            'storage': {
                'database_size': 0,
                'files_size': 0,
                'total_size': 0
            }
        }
        self._save()
    
    def unregister(self, name: str) -> None:
        """Unregister plugin"""
        if name in self._data['plugins']:
            del self._data['plugins'][name]
            self._save()
    
    def update(self, name: str, updates: Dict[str, Any]) -> None:
        """Update plugin metadata"""
        if name in self._data['plugins']:
            self._data['plugins'][name].update(updates)
            self._save()
    
    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """Get plugin metadata"""
        return self._data['plugins'].get(name)
    
    def is_installed(self, name: str) -> bool:
        """Check if plugin is installed"""
        return name in self._data['plugins']
    
    def list_all(self) -> List[Dict[str, Any]]:
        """List all plugins"""
        return list(self._data['plugins'].values())
    
    def list_enabled(self) -> List[Dict[str, Any]]:
        """List enabled plugins"""
        return [p for p in self._data['plugins'].values() if p['enabled']]
```

#### Component 4: Git Installer (`rosey/plugin/git.py`)

**Responsibilities**:

- Clone Git repositories (HTTPS + SSH)
- Handle authentication
- Verify repository structure

**Class Definition**:

```python
"""Git repository cloning for plugin installation"""
from pathlib import Path
import subprocess
import tempfile
import logging

logger = logging.getLogger(__name__)


class GitInstallerError(Exception):
    """Raised when Git operations fail"""
    pass


class GitInstaller:
    """
    Handles Git repository cloning for plugin installation.
    """
    
    def __init__(self, plugins_dir: Path):
        """
        Initialize Git installer.
        
        Args:
            plugins_dir: Plugin storage directory
        """
        self.plugins_dir = plugins_dir
    
    async def clone(self, git_url: str, branch: Optional[str] = None) -> Path:
        """
        Clone Git repository to temporary directory.
        
        Args:
            git_url: Git repository URL (HTTPS or SSH)
            branch: Optional branch name (default: default branch)
            
        Returns:
            Path to cloned repository
            
        Raises:
            GitInstallerError: If clone fails
        """
        try:
            # Create temporary directory
            temp_dir = Path(tempfile.mkdtemp(prefix="rosey_plugin_"))
            
            # Build git clone command
            cmd = ["git", "clone"]
            
            if branch:
                cmd.extend(["--branch", branch])
            
            cmd.extend([git_url, str(temp_dir)])
            
            # Clone repository
            logger.info(f"Cloning repository: {git_url}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("Repository cloned successfully")
            return temp_dir
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git clone failed: {e.stderr}")
            raise GitInstallerError(f"Failed to clone repository: {e.stderr}")
        except Exception as e:
            raise GitInstallerError(f"Git clone failed: {e}")
    
    @staticmethod
    def is_git_available() -> bool:
        """Check if git command is available"""
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
```

### 2.3 CLI Commands (Update `rosey/cli/plugin.py`)

**New Commands**:

```python
@plugin_cli.command('install')
@click.argument('source')
def install_plugin(source: str):
    """
    Install plugin from file or Git repository.
    
    Args:
        source: Local .roseyplug file or Git URL
        
    Examples:
        rosey plugin install ./markov-chat-1.2.0.roseyplug
        rosey plugin install https://github.com/user/plugin.git
        rosey plugin install git@github.com:user/plugin.git
    """
    import asyncio
    from rosey.plugin.manager import PluginManager
    from pathlib import Path
    
    try:
        # Initialize manager
        manager = PluginManager(Path("data"))
        
        # Install plugin
        info("Installing plugin...")
        result = asyncio.run(manager.install(source))
        
        # Show success
        success(f"Installed {result['name']} v{result['version']}")
        
        # Show permissions
        plugin_info = manager.get_info(result['name'])
        if plugin_info.get('permissions'):
            info("\nPermissions:")
            for perm in plugin_info['permissions']:
                info(f"  - {perm}")
            info("\nNote: Permissions are informational (trust-based)")
        
        info("\nNext steps:")
        info(f"  rosey start                    # Start bot with plugin")
        info(f"  rosey plugin list              # Verify installation")
        
    except Exception as e:
        error(f"Installation failed: {e}")
        raise click.Abort()


@plugin_cli.command('remove')
@click.argument('name')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def remove_plugin(name: str, yes: bool):
    """
    Remove plugin and delete all data.
    
    Args:
        name: Plugin name
    """
    import asyncio
    from rosey.plugin.manager import PluginManager
    from pathlib import Path
    
    try:
        # Confirmation
        if not yes:
            if not click.confirm(f"Remove plugin '{name}' and delete all data?"):
                info("Cancelled")
                return
        
        # Initialize manager
        manager = PluginManager(Path("data"))
        
        # Remove plugin
        info(f"Removing plugin '{name}'...")
        asyncio.run(manager.remove(name))
        
        success(f"Removed plugin '{name}'")
        
    except Exception as e:
        error(f"Removal failed: {e}")
        raise click.Abort()


@plugin_cli.command('list')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def list_plugins(verbose: bool):
    """
    List installed plugins.
    """
    from rosey.plugin.manager import PluginManager
    from pathlib import Path
    
    try:
        manager = PluginManager(Path("data"))
        plugins = manager.list_plugins()
        
        if not plugins:
            info("No plugins installed")
            return
        
        # Show table
        click.echo("\nInstalled Plugins:\n")
        
        for plugin in plugins:
            status_icon = "✓" if plugin['enabled'] else "○"
            click.echo(f"{status_icon} {plugin['name']} v{plugin['version']}")
            
            if verbose:
                click.echo(f"   Author: {plugin['author']}")
                click.echo(f"   Source: {plugin['install_source']}")
                click.echo(f"   Status: {plugin['status']}")
                if plugin.get('permissions'):
                    click.echo(f"   Permissions: {', '.join(plugin['permissions'])}")
                click.echo()
        
        click.echo(f"Total: {len(plugins)} plugin(s)\n")
        
    except Exception as e:
        error(f"Failed to list plugins: {e}")
        raise click.Abort()


@plugin_cli.command('enable')
@click.argument('name')
def enable_plugin(name: str):
    """Enable plugin (auto-start with bot)"""
    from rosey.plugin.manager import PluginManager
    from pathlib import Path
    
    try:
        manager = PluginManager(Path("data"))
        manager.enable(name)
        success(f"Enabled plugin '{name}'")
    except Exception as e:
        error(f"Failed to enable plugin: {e}")
        raise click.Abort()


@plugin_cli.command('disable')
@click.argument('name')
def disable_plugin(name: str):
    """Disable plugin (don't auto-start)"""
    from rosey.plugin.manager import PluginManager
    from pathlib import Path
    
    try:
        manager = PluginManager(Path("data"))
        manager.disable(name)
        success(f"Disabled plugin '{name}'")
    except Exception as e:
        error(f"Failed to disable plugin: {e}")
        raise click.Abort()
```

---

## 3. Implementation Plan

### 3.1 Phase 1: Storage Foundation (2-3 hours)

**Tasks**:

1. **Implement PluginStorage class**:
   - Database initialization (SQLAlchemy)
   - File API with path validation
   - Storage size tracking
   - Cleanup method

2. **Implement PluginRegistry class**:
   - JSON persistence
   - Atomic saves
   - CRUD operations

3. **Create directory structure**:
   - `data/plugins/` directory
   - `.registry.json` file

**Acceptance Criteria**:

- ✅ PluginStorage creates isolated database
- ✅ File operations restricted to plugin directory
- ✅ Path traversal attacks prevented (../../../)
- ✅ Registry persists across restarts

### 3.2 Phase 2: Plugin Installation (2-3 hours)

**Tasks**:

1. **Implement PluginManager class**:
   - Install from local file
   - Dependency installation
   - Registry integration

2. **Implement GitInstaller class**:
   - HTTPS cloning
   - SSH cloning
   - Error handling

3. **Add CLI commands**:
   - `rosey plugin install <source>`
   - `rosey plugin remove <name>`
   - `rosey plugin list`
   - `rosey plugin enable/disable <name>`

**Acceptance Criteria**:

- ✅ Install from `.roseyplug` file works
- ✅ Install from Git HTTPS URL works
- ✅ Install from Git SSH URL works
- ✅ Dependencies installed automatically
- ✅ Permissions displayed during install

### 3.3 Phase 3: Testing & Documentation (2 hours)

**Tasks**:

1. **Unit tests**:
   - `test_plugin_storage.py` - isolation, path validation
   - `test_plugin_manager.py` - install/remove
   - `test_plugin_registry.py` - persistence
   - `test_git_installer.py` - cloning

2. **Integration tests**:
   - Install → verify storage → remove → verify cleanup
   - Git clone → install → list

3. **Documentation**:
   - Update plugin development guide
   - Add installation examples
   - Document storage API

**Acceptance Criteria**:

- ✅ 90%+ test coverage
- ✅ All edge cases tested (path traversal, missing files, etc.)
- ✅ Documentation complete

---

## 4. Testing Strategy

### 4.1 Unit Tests

**`tests/unit/plugin/test_plugin_storage.py`**:

```python
"""Tests for plugin storage isolation"""
import pytest
from pathlib import Path
from rosey.plugin.storage import PluginStorage, PluginStorageError


@pytest.mark.asyncio
async def test_initialize_storage(tmp_path):
    """Test storage initialization"""
    storage = PluginStorage("test-plugin", tmp_path)
    await storage.initialize()
    
    # Verify directories created
    assert (tmp_path / "test-plugin").exists()
    assert (tmp_path / "test-plugin" / "files").exists()
    assert (tmp_path / "test-plugin" / "database.db").exists()


@pytest.mark.asyncio
async def test_database_isolation(tmp_path):
    """Test database isolation between plugins"""
    # Create two plugin storages
    storage1 = PluginStorage("plugin1", tmp_path)
    storage2 = PluginStorage("plugin2", tmp_path)
    
    await storage1.initialize()
    await storage2.initialize()
    
    # Write to plugin1 database
    await storage1.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
    await storage1.execute("INSERT INTO test (data) VALUES (?)", {"data": "plugin1_data"})
    
    # Verify plugin2 database is separate
    rows = await storage2.query("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = [row['name'] for row in rows]
    assert 'test' not in table_names


@pytest.mark.asyncio
async def test_file_path_validation(tmp_path):
    """Test path traversal protection"""
    storage = PluginStorage("test-plugin", tmp_path)
    await storage.initialize()
    
    # Valid paths
    await storage.write_file("test.txt", b"data")
    await storage.write_file("subdir/test.txt", b"data")
    
    # Invalid paths (escape attempts)
    with pytest.raises(PluginStorageError):
        await storage.write_file("../../../etc/passwd", b"data")
    
    with pytest.raises(PluginStorageError):
        await storage.write_file("/absolute/path.txt", b"data")


@pytest.mark.asyncio
async def test_storage_cleanup(tmp_path):
    """Test complete data removal"""
    storage = PluginStorage("test-plugin", tmp_path)
    await storage.initialize()
    
    # Create data
    await storage.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
    await storage.write_file("test.txt", b"data")
    
    # Cleanup
    await storage.cleanup()
    
    # Verify everything deleted
    assert not (tmp_path / "test-plugin").exists()
```

**`tests/unit/plugin/test_plugin_manager.py`**:

```python
"""Tests for plugin manager"""
import pytest
from pathlib import Path
from rosey.plugin.manager import PluginManager


@pytest.mark.asyncio
async def test_install_from_file(tmp_path, test_plugin_archive):
    """Test plugin installation from .roseyplug file"""
    manager = PluginManager(tmp_path)
    
    # Install plugin
    result = await manager.install(str(test_plugin_archive))
    
    assert result['name'] == 'test-plugin'
    assert result['version'] == '1.0.0'
    
    # Verify files extracted
    plugin_dir = tmp_path / "plugins" / "test-plugin"
    assert (plugin_dir / "manifest.yaml").exists()
    assert (plugin_dir / "plugin.py").exists()
    assert (plugin_dir / "database.db").exists()
    
    # Verify registry updated
    assert manager.registry.is_installed('test-plugin')


@pytest.mark.asyncio
async def test_remove_plugin(tmp_path, test_plugin_archive):
    """Test plugin removal and cleanup"""
    manager = PluginManager(tmp_path)
    
    # Install then remove
    await manager.install(str(test_plugin_archive))
    await manager.remove('test-plugin')
    
    # Verify complete cleanup
    plugin_dir = tmp_path / "plugins" / "test-plugin"
    assert not plugin_dir.exists()
    
    # Verify unregistered
    assert not manager.registry.is_installed('test-plugin')


@pytest.mark.asyncio
async def test_duplicate_install_fails(tmp_path, test_plugin_archive):
    """Test that installing same plugin twice fails"""
    manager = PluginManager(tmp_path)
    
    # First install succeeds
    await manager.install(str(test_plugin_archive))
    
    # Second install fails
    with pytest.raises(Exception) as exc:
        await manager.install(str(test_plugin_archive))
    
    assert "already installed" in str(exc.value).lower()
```

### 4.2 Integration Tests

**`tests/integration/test_plugin_lifecycle.py`**:

```python
"""Integration tests for complete plugin lifecycle"""
import pytest
from pathlib import Path
from click.testing import CliRunner
from rosey.cli.main import main


@pytest.mark.asyncio
async def test_full_lifecycle(tmp_path, monkeypatch):
    """Test: create → build → install → list → remove"""
    runner = CliRunner()
    monkeypatch.setenv('ROSEY_DATA_DIR', str(tmp_path))
    
    with runner.isolated_filesystem():
        # Create plugin
        result = runner.invoke(main, ['plugin', 'create', 'test-plugin'])
        assert result.exit_code == 0
        
        # Build archive
        result = runner.invoke(main, ['plugin', 'build', 'test-plugin'])
        assert result.exit_code == 0
        assert Path('test-plugin-0.1.0.roseyplug').exists()
        
        # Install
        result = runner.invoke(main, ['plugin', 'install', 'test-plugin-0.1.0.roseyplug'])
        assert result.exit_code == 0
        assert 'Installed' in result.output
        
        # List
        result = runner.invoke(main, ['plugin', 'list'])
        assert result.exit_code == 0
        assert 'test-plugin' in result.output
        
        # Remove
        result = runner.invoke(main, ['plugin', 'remove', 'test-plugin', '--yes'])
        assert result.exit_code == 0
        assert 'Removed' in result.output
        
        # Verify cleanup
        result = runner.invoke(main, ['plugin', 'list'])
        assert 'No plugins installed' in result.output
```

---

## 5. Dependencies

### 5.1 Python Packages

**New Dependencies** (add to `requirements.txt`):

```text
sqlalchemy>=2.0.0          # ORM for plugin databases
aiosqlite>=0.19.0          # Async SQLite driver
```

**Already Available** (from Sortie 1):

- `click` - CLI framework
- `pyyaml` - YAML parsing

---

## 6. Acceptance Criteria

### 6.1 Functional Requirements

- [x] Install plugin from local `.roseyplug` file
- [x] Install plugin from Git HTTPS URL
- [x] Install plugin from Git SSH URL
- [x] Each plugin has isolated SQLite database
- [x] Each plugin has sandboxed file directory
- [x] Path traversal attacks prevented
- [x] Python dependencies installed automatically
- [x] Permissions displayed during install
- [x] Complete cleanup on removal (zero orphaned data)
- [x] Registry persists across restarts
- [x] Enable/disable plugin functionality

### 6.2 Non-Functional Requirements

- [x] Install time <30 seconds (local file)
- [x] Install time <60 seconds (Git clone)
- [x] Storage isolation verified (no cross-plugin access)
- [x] Atomic registry updates (no corruption on crash)
- [x] Clear error messages for common failures

### 6.3 Test Coverage

- [x] Unit tests: 90%+ coverage
- [x] Integration tests: Full lifecycle
- [x] Security tests: Path traversal, SQL injection attempts
- [x] Edge cases: Duplicate installs, missing files, corrupt archives

---

## 7. Documentation Requirements

### 7.1 User Documentation

**Update `docs/guides/PLUGIN_DEVELOPMENT.md`**:

```markdown
## Installing Plugins

### From Local File

```bash
rosey plugin install ./markov-chat-1.2.0.roseyplug
```

### From GitHub Repository

```bash
# HTTPS
rosey plugin install https://github.com/user/markov-chat

# SSH (requires SSH key)
rosey plugin install git@github.com:user/markov-chat.git
```

### Managing Plugins

```bash
# List installed plugins
rosey plugin list

# Enable/disable auto-start
rosey plugin enable markov-chat
rosey plugin disable markov-chat

# Remove plugin
rosey plugin remove markov-chat
```

## Plugin Storage API

### Database Access

```python
# Raw SQL
rows = await self.storage.query("SELECT * FROM my_table")
await self.storage.execute("INSERT INTO my_table (data) VALUES (?)", {"data": "value"})

# SQLAlchemy ORM
async with self.storage.get_session() as session:
    result = await session.execute(select(MyModel))
    items = result.scalars().all()
```

### File Access

```python
# Read file
data = await self.storage.read_file("model.txt")

# Write file
await self.storage.write_file("cache/data.json", json.dumps(data).encode())

# List files
files = await self.storage.list_files()

# Delete file
await self.storage.delete_file("old_cache.txt")
```

## Storage Isolation

Each plugin has:

- **Private database**: `data/plugins/<name>/database.db`
- **Sandboxed files**: `data/plugins/<name>/files/`
- **No access** to other plugins' data
- **No access** to bot core database

All data is deleted on plugin removal.
```

---

## 8. Rollback Plan

### 8.1 Rollback Triggers

- Critical storage isolation bug (cross-plugin access)
- Data loss on plugin removal
- Registry corruption
- Git cloning security vulnerability

### 8.2 Rollback Procedure

1. **Disable plugin installation**: Comment out `install` command
2. **Keep existing plugins**: Don't auto-remove
3. **Revert code**: Remove `storage.py`, `manager.py`, `registry.py`, `git.py`
4. **Clear registry**: Remove `.registry.json`

**Recovery Time**: <30 minutes (no data loss for existing plugins)

---

## 9. Deployment Checklist

### 9.1 Pre-Deployment

- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Security tests pass (path traversal, SQL injection)
- [ ] Git cloning tested (HTTPS + SSH)
- [ ] Documentation updated

### 9.2 Deployment Steps

```bash
# 1. Update dependencies
pip install -r requirements.txt

# 2. Reinstall package
pip install -e .

# 3. Test plugin installation
rosey plugin create test-demo
rosey plugin build test-demo
rosey plugin install test-demo-0.1.0.roseyplug

# 4. Verify isolation
rosey plugin list
ls -la data/plugins/test-demo/

# 5. Test removal
rosey plugin remove test-demo --yes
ls -la data/plugins/  # Should not have test-demo/
```

### 9.3 Post-Deployment Validation

- [ ] Install plugin from local file works
- [ ] Install plugin from Git works
- [ ] Plugin has isolated storage
- [ ] Removal cleans up all data
- [ ] Registry updates correctly
- [ ] No regression in existing bot functionality

---

## 10. Security Considerations

### 10.1 Storage Isolation

**Path Traversal Prevention**:

```python
# BLOCKED: ../../../etc/passwd
# BLOCKED: /absolute/path
# ALLOWED: subdir/file.txt
# ALLOWED: ./file.txt
```

**Database Isolation**:

- Each plugin has separate SQLite file
- No access to `bot_data.db`
- No access to other plugins' databases

### 10.2 Installation Security

**Trust Model**:

- Users trust plugins they install
- Permissions displayed (not enforced)
- Review source code before install
- Git repos allow code inspection

**Dependency Safety**:

- Dependencies installed via `pip`
- No automatic execution during install
- Users can review `requirements.txt` before install

---

## Appendices

### A. Example Plugin Directory

```text
data/plugins/markov-chat/
├── manifest.yaml          # From archive
├── plugin.py              # From archive
├── requirements.txt       # From archive
├── assets/                # From archive
│   └── icon.png
├── tests/                 # From archive
│   └── test_plugin.py
├── database.db            # CREATED by PluginStorage
├── files/                 # CREATED by PluginStorage
│   ├── markov_model.txt   # Plugin-created data
│   └── cache/
│       └── corpus.txt
└── config.yaml            # CREATED at install (from manifest.config_schema)
```

### B. Storage API Usage Examples

**Database Operations**:

```python
# Create table
await self.storage.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

# Insert data
await self.storage.execute(
    "INSERT INTO messages (user, content) VALUES (:user, :content)",
    {"user": "Alice", "content": "Hello!"}
)

# Query data
rows = await self.storage.query(
    "SELECT * FROM messages WHERE user = :user ORDER BY timestamp DESC LIMIT 10",
    {"user": "Alice"}
)
for row in rows:
    print(f"{row['user']}: {row['content']}")
```

**File Operations**:

```python
# Save model
model_data = train_markov_model(corpus)
await self.storage.write_file("model.pkl", pickle.dumps(model_data))

# Load model
model_bytes = await self.storage.read_file("model.pkl")
model_data = pickle.loads(model_bytes)

# Cache API response
cache_file = f"cache/weather_{city}.json"
await self.storage.write_file(cache_file, json.dumps(weather_data).encode())

# List cached files
cached_files = await self.storage.list_files("cache")
print(f"Found {len(cached_files)} cached files")
```

### C. CLI Output Examples

**`rosey plugin install ./markov-chat-1.2.0.roseyplug`**:

```text
Installing plugin...
✓ Installed markov-chat v1.2.0

Permissions:
  - read_messages
  - send_messages
  - database_access
  - file_read
  - file_write

Note: Permissions are informational (trust-based)

Next steps:
  rosey start                    # Start bot with plugin
  rosey plugin list              # Verify installation
```

**`rosey plugin list`**:

```text
Installed Plugins:

✓ markov-chat v1.2.0
✓ quote-bot v2.0.1
○ weather-alerts v1.5.0

Total: 3 plugin(s)
```

**`rosey plugin remove markov-chat`**:

```text
Remove plugin 'markov-chat' and delete all data? [y/N]: y
Removing plugin 'markov-chat'...
✓ Removed plugin 'markov-chat'
```

---

**Document Status**: ✅ Ready for Implementation  
**Estimated Effort**: 6-8 hours  
**Risk Level**: MEDIUM (storage isolation critical)  
**Next Sortie**: Sortie 3 - Service Management & Hot Reload  

**Key Success Factors**:

1. ✅ Storage isolation bulletproof (path traversal, DB separation)
2. ✅ Complete cleanup (zero orphaned data)
3. ✅ Git cloning robust (HTTPS + SSH)
4. ✅ Clear error messages (install failures, missing deps)
5. ✅ Atomic registry updates (no corruption)

**Movie Quote**: *"The walls are up, the doors are locked. Now we defend what's inside."* 🎬
