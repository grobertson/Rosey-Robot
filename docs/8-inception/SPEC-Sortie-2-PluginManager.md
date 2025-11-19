# Sprint 8, Sortie 2: Plugin Manager

**Status:** Planning  
**Estimated Effort:** 8 hours  
**Sprint:** Inception (Sprint 8)  
**Phase:** 1 - Core Plugin Infrastructure  
**Dependencies:** Sortie 1 (Plugin base class complete)

## Objective

Implement `PluginManager` to handle plugin discovery, loading, dependency resolution, lifecycle management, and error isolation. This is the core of the plugin system.

## Background

We have Plugin base class. Now we need a manager to:
- **Discover** plugins in plugins/ directory
- **Load** plugin modules dynamically
- **Resolve** dependencies between plugins
- **Manage** lifecycle (setup, enable, disable, teardown)
- **Isolate** errors (one plugin failure doesn't crash bot)
- **Track** plugin state (loaded, enabled, disabled, failed)

## Success Criteria

- ✅ Plugin discovery from directory
- ✅ Dynamic module loading
- ✅ Dependency resolution (topological sort)
- ✅ Lifecycle management for all plugins
- ✅ Error isolation per plugin
- ✅ Plugin registry with status tracking
- ✅ Get plugin by name
- ✅ List all plugins

## Technical Design

### Plugin States

```
┌──────────┐
│UNLOADED  │ Initial state
└────┬─────┘
     │ load()
     ▼
┌──────────┐
│ LOADED   │ Module imported, Plugin() instantiated
└────┬─────┘
     │ setup()
     ▼
┌──────────┐
│  SETUP   │ setup() complete, ready to enable
└────┬─────┘
     │ enable()
     ▼
┌──────────┐
│ ENABLED  │ Active, handling events
└────┬─────┘
     │ disable()
     ▼
┌──────────┐
│ DISABLED │ Inactive, not handling events
└────┬─────┘
     │ teardown()
     ▼
┌──────────┐
│TORN DOWN │ Cleanup complete
└──────────┘
     │
     ▼
┌──────────┐
│  FAILED  │ Error occurred (from any state)
└──────────┘
```

### PluginManager Implementation

```python
"""
lib/plugin/manager.py

Plugin discovery, loading, and lifecycle management.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
from enum import Enum
import logging
import traceback

from .base import Plugin
from .metadata import PluginMetadata
from .errors import (
    PluginError,
    PluginLoadError,
    PluginSetupError,
    PluginDependencyError
)


class PluginState(Enum):
    """Plugin lifecycle states."""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    SETUP = "setup"
    ENABLED = "enabled"
    DISABLED = "disabled"
    TORN_DOWN = "torn_down"
    FAILED = "failed"


class PluginInfo:
    """
    Plugin information and state tracking.
    
    Attributes:
        plugin: Plugin instance (None if not loaded)
        state: Current plugin state
        error: Error message if state == FAILED
        file_path: Path to plugin file
    """
    
    def __init__(self, file_path: Path):
        self.plugin: Optional[Plugin] = None
        self.state: PluginState = PluginState.UNLOADED
        self.error: Optional[str] = None
        self.file_path: Path = file_path
    
    @property
    def name(self) -> Optional[str]:
        """Plugin name (None if not loaded)."""
        return self.plugin.metadata.name if self.plugin else None
    
    @property
    def metadata(self) -> Optional[PluginMetadata]:
        """Plugin metadata (None if not loaded)."""
        return self.plugin.metadata if self.plugin else None
    
    def __str__(self) -> str:
        if self.plugin:
            return f"{self.plugin.metadata.display_name} ({self.state.value})"
        return f"{self.file_path.stem} ({self.state.value})"


class PluginManager:
    """
    Manage plugin discovery, loading, and lifecycle.
    
    Features:
    - Discover plugins from directory
    - Load plugins dynamically
    - Resolve dependencies
    - Manage lifecycle (setup, enable, disable, teardown)
    - Isolate errors (one plugin failure doesn't crash others)
    - Track plugin state
    
    Args:
        bot: Bot instance
        plugin_dir: Directory containing plugin files (default: plugins/)
        logger: Optional logger instance
    """
    
    def __init__(self, bot, plugin_dir: str = 'plugins',
                 logger: Optional[logging.Logger] = None):
        self.bot = bot
        self.plugin_dir = Path(plugin_dir)
        self.logger = logger or logging.getLogger('plugin.manager')
        
        # Plugin registry: name -> PluginInfo
        self._plugins: Dict[str, PluginInfo] = {}
        
        # File tracking: path -> name
        self._file_to_name: Dict[Path, str] = {}
    
    # Discovery
    
    def discover(self) -> List[Path]:
        """
        Discover plugin files in plugin directory.
        
        Returns:
            List of plugin file paths
        
        Raises:
            PluginError: If plugin directory doesn't exist
        """
        if not self.plugin_dir.exists():
            raise PluginError(f"Plugin directory not found: {self.plugin_dir}")
        
        # Find all .py files except __init__.py
        plugin_files = [
            f for f in self.plugin_dir.glob('*.py')
            if f.name != '__init__.py'
        ]
        
        self.logger.info(f"Discovered {len(plugin_files)} plugin files")
        return plugin_files
    
    # Loading
    
    async def load_all(self) -> None:
        """
        Discover and load all plugins.
        
        This:
        1. Discovers plugin files
        2. Loads each plugin module
        3. Resolves dependencies
        4. Sets up plugins in dependency order
        5. Enables all plugins
        """
        # Discover
        plugin_files = self.discover()
        
        # Load all modules first
        for file_path in plugin_files:
            try:
                await self._load_plugin_file(file_path)
            except Exception as e:
                self.logger.error(f"Failed to load {file_path}: {e}")
                # Continue loading other plugins
        
        # Resolve dependencies and get load order
        try:
            load_order = self._resolve_dependencies()
        except PluginDependencyError as e:
            self.logger.error(f"Dependency resolution failed: {e}")
            return
        
        # Setup plugins in dependency order
        for name in load_order:
            info = self._plugins[name]
            if info.state == PluginState.LOADED:
                try:
                    await self._setup_plugin(name)
                except Exception as e:
                    self.logger.error(f"Setup failed for {name}: {e}")
        
        # Enable all successfully setup plugins
        for name in load_order:
            info = self._plugins[name]
            if info.state == PluginState.SETUP:
                try:
                    await self._enable_plugin(name)
                except Exception as e:
                    self.logger.error(f"Enable failed for {name}: {e}")
        
        enabled_count = sum(1 for p in self._plugins.values()
                           if p.state == PluginState.ENABLED)
        self.logger.info(f"Loaded {enabled_count}/{len(self._plugins)} plugins")
    
    async def _load_plugin_file(self, file_path: Path) -> None:
        """
        Load plugin from file.
        
        Args:
            file_path: Path to plugin .py file
        
        Raises:
            PluginLoadError: If load fails
        """
        try:
            # Import module dynamically
            spec = importlib.util.spec_from_file_location(
                file_path.stem, file_path
            )
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Failed to load spec for {file_path}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # Find Plugin subclass in module
            plugin_class = None
            for name in dir(module):
                obj = getattr(module, name)
                if (isinstance(obj, type) and 
                    issubclass(obj, Plugin) and 
                    obj is not Plugin):
                    plugin_class = obj
                    break
            
            if plugin_class is None:
                raise PluginLoadError(f"No Plugin subclass found in {file_path}")
            
            # Instantiate plugin
            plugin = plugin_class(self.bot)
            
            # Create plugin info
            info = PluginInfo(file_path)
            info.plugin = plugin
            info.state = PluginState.LOADED
            
            # Register
            self._plugins[plugin.metadata.name] = info
            self._file_to_name[file_path] = plugin.metadata.name
            
            self.logger.info(f"Loaded plugin: {plugin.metadata.display_name}")
        
        except Exception as e:
            # Create failed plugin info
            info = PluginInfo(file_path)
            info.state = PluginState.FAILED
            info.error = str(e)
            self._plugins[file_path.stem] = info
            
            self.logger.error(f"Failed to load {file_path}: {e}")
            self.logger.debug(traceback.format_exc())
            raise PluginLoadError(f"Failed to load {file_path}") from e
    
    # Dependency Resolution
    
    def _resolve_dependencies(self) -> List[str]:
        """
        Resolve plugin dependencies using topological sort.
        
        Returns:
            List of plugin names in load order (dependencies first)
        
        Raises:
            PluginDependencyError: If circular dependency or missing dependency
        """
        # Build dependency graph
        graph: Dict[str, Set[str]] = {}
        in_degree: Dict[str, int] = {}
        
        for name, info in self._plugins.items():
            if info.state != PluginState.LOADED:
                continue
            
            graph[name] = set(info.metadata.dependencies)
            in_degree[name] = 0
        
        # Calculate in-degrees
        for name, deps in graph.items():
            for dep in deps:
                if dep not in graph:
                    raise PluginDependencyError(
                        f"Plugin {name} depends on missing plugin: {dep}"
                    )
                in_degree[name] += 1
        
        # Topological sort (Kahn's algorithm)
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            name = queue.pop(0)
            result.append(name)
            
            # Reduce in-degree for dependents
            for other_name, deps in graph.items():
                if name in deps:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)
        
        if len(result) != len(graph):
            raise PluginDependencyError("Circular dependency detected")
        
        return result
    
    # Lifecycle Management
    
    async def _setup_plugin(self, name: str) -> None:
        """
        Run plugin setup.
        
        Args:
            name: Plugin name
        
        Raises:
            PluginSetupError: If setup fails
        """
        info = self._plugins[name]
        
        try:
            await info.plugin.setup()
            info.state = PluginState.SETUP
            self.logger.info(f"Setup complete: {name}")
        
        except Exception as e:
            info.state = PluginState.FAILED
            info.error = str(e)
            self.logger.error(f"Setup failed for {name}: {e}")
            self.logger.debug(traceback.format_exc())
            raise PluginSetupError(f"Setup failed for {name}") from e
    
    async def _enable_plugin(self, name: str) -> None:
        """
        Enable plugin.
        
        Args:
            name: Plugin name
        """
        info = self._plugins[name]
        
        try:
            await info.plugin.on_enable()
            info.state = PluginState.ENABLED
            self.logger.info(f"Enabled: {name}")
        
        except Exception as e:
            info.state = PluginState.FAILED
            info.error = str(e)
            self.logger.error(f"Enable failed for {name}: {e}")
            raise
    
    async def _disable_plugin(self, name: str) -> None:
        """
        Disable plugin.
        
        Args:
            name: Plugin name
        """
        info = self._plugins[name]
        
        try:
            await info.plugin.on_disable()
            info.state = PluginState.DISABLED
            self.logger.info(f"Disabled: {name}")
        
        except Exception as e:
            self.logger.error(f"Disable failed for {name}: {e}")
            # Don't fail on disable errors
    
    async def _teardown_plugin(self, name: str) -> None:
        """
        Run plugin teardown.
        
        Args:
            name: Plugin name
        """
        info = self._plugins[name]
        
        try:
            await info.plugin.teardown()
            info.state = PluginState.TORN_DOWN
            self.logger.info(f"Teardown complete: {name}")
        
        except Exception as e:
            self.logger.error(f"Teardown failed for {name}: {e}")
            # Don't fail on teardown errors (best effort)
    
    # Public API
    
    async def enable(self, name: str) -> None:
        """
        Enable plugin by name.
        
        Args:
            name: Plugin name
        
        Raises:
            PluginError: If plugin not found or not in correct state
        """
        if name not in self._plugins:
            raise PluginError(f"Plugin not found: {name}")
        
        info = self._plugins[name]
        
        if info.state == PluginState.ENABLED:
            self.logger.warning(f"Plugin already enabled: {name}")
            return
        
        if info.state != PluginState.DISABLED and info.state != PluginState.SETUP:
            raise PluginError(f"Cannot enable plugin in state: {info.state}")
        
        await self._enable_plugin(name)
    
    async def disable(self, name: str) -> None:
        """
        Disable plugin by name.
        
        Args:
            name: Plugin name
        
        Raises:
            PluginError: If plugin not found
        """
        if name not in self._plugins:
            raise PluginError(f"Plugin not found: {name}")
        
        info = self._plugins[name]
        
        if info.state != PluginState.ENABLED:
            self.logger.warning(f"Plugin not enabled: {name}")
            return
        
        await self._disable_plugin(name)
    
    async def reload(self, name: str) -> None:
        """
        Reload plugin (disable, teardown, reload module, setup, enable).
        
        Args:
            name: Plugin name
        
        Raises:
            PluginError: If reload fails
        """
        if name not in self._plugins:
            raise PluginError(f"Plugin not found: {name}")
        
        info = self._plugins[name]
        file_path = info.file_path
        
        # Disable if enabled
        if info.state == PluginState.ENABLED:
            await self._disable_plugin(name)
        
        # Teardown if setup
        if info.state in (PluginState.DISABLED, PluginState.SETUP):
            await self._teardown_plugin(name)
        
        # Remove from registry
        del self._plugins[name]
        if file_path in self._file_to_name:
            del self._file_to_name[file_path]
        
        # Reload module
        await self._load_plugin_file(file_path)
        
        # Setup and enable
        await self._setup_plugin(name)
        await self._enable_plugin(name)
        
        self.logger.info(f"Reloaded plugin: {name}")
    
    def get(self, name: str) -> Optional[Plugin]:
        """
        Get plugin instance by name.
        
        Args:
            name: Plugin name
        
        Returns:
            Plugin instance or None if not found
        """
        info = self._plugins.get(name)
        return info.plugin if info else None
    
    def list_plugins(self) -> List[PluginInfo]:
        """
        Get list of all plugins.
        
        Returns:
            List of PluginInfo objects
        """
        return list(self._plugins.values())
    
    def get_enabled(self) -> List[Plugin]:
        """
        Get list of enabled plugins.
        
        Returns:
            List of enabled Plugin instances
        """
        return [
            info.plugin for info in self._plugins.values()
            if info.state == PluginState.ENABLED
        ]
    
    async def unload_all(self) -> None:
        """
        Unload all plugins (disable, teardown, remove from registry).
        """
        for name in list(self._plugins.keys()):
            info = self._plugins[name]
            
            if info.state == PluginState.ENABLED:
                await self._disable_plugin(name)
            
            if info.state in (PluginState.DISABLED, PluginState.SETUP):
                await self._teardown_plugin(name)
        
        self._plugins.clear()
        self._file_to_name.clear()
        
        self.logger.info("All plugins unloaded")
```

## Implementation Steps

1. **Create manager module** (15 min)
   ```bash
   touch lib/plugin/manager.py
   ```

2. **Implement PluginState enum** (15 min)
   - Define all states
   - Add docstrings

3. **Implement PluginInfo class** (30 min)
   - Track plugin, state, error, file_path
   - Add properties for name, metadata

4. **Implement plugin discovery** (45 min)
   - discover() method
   - Find .py files in plugins/
   - Filter out __init__.py

5. **Implement plugin loading** (1.5 hours)
   - _load_plugin_file() method
   - Dynamic module import
   - Find Plugin subclass
   - Instantiate plugin
   - Error isolation

6. **Implement dependency resolution** (1 hour)
   - _resolve_dependencies() method
   - Topological sort (Kahn's algorithm)
   - Detect circular dependencies
   - Detect missing dependencies

7. **Implement lifecycle methods** (1.5 hours)
   - _setup_plugin()
   - _enable_plugin()
   - _disable_plugin()
   - _teardown_plugin()
   - Error isolation for each

8. **Implement public API** (1 hour)
   - load_all()
   - enable()
   - disable()
   - reload()
   - get()
   - list_plugins()
   - get_enabled()
   - unload_all()

9. **Write unit tests** (2 hours)
   ```python
   # test/test_plugin_manager.py
   
   import pytest
   from pathlib import Path
   from lib.plugin import PluginManager, Plugin, PluginMetadata
   
   
   @pytest.mark.asyncio
   async def test_discover(tmp_path, mock_bot):
       """Test plugin discovery."""
       plugin_dir = tmp_path / "plugins"
       plugin_dir.mkdir()
       
       # Create plugin files
       (plugin_dir / "plugin1.py").write_text("# Plugin 1")
       (plugin_dir / "plugin2.py").write_text("# Plugin 2")
       (plugin_dir / "__init__.py").write_text("")
       
       manager = PluginManager(mock_bot, str(plugin_dir))
       files = manager.discover()
       
       assert len(files) == 2
       assert all(f.suffix == '.py' for f in files)
   
   
   @pytest.mark.asyncio
   async def test_dependency_resolution(mock_bot):
       """Test dependency resolution."""
       # Create mock plugins with dependencies
       class PluginA(Plugin):
           @property
           def metadata(self):
               return PluginMetadata(
                   name='a', display_name='A', version='1.0.0',
                   description='Plugin A', author='Test',
                   dependencies=['b']
               )
       
       class PluginB(Plugin):
           @property
           def metadata(self):
               return PluginMetadata(
                   name='b', display_name='B', version='1.0.0',
                   description='Plugin B', author='Test'
               )
       
       manager = PluginManager(mock_bot)
       
       # Manually add plugins
       from lib.plugin.manager import PluginInfo, PluginState
       info_a = PluginInfo(Path('a.py'))
       info_a.plugin = PluginA(mock_bot)
       info_a.state = PluginState.LOADED
       
       info_b = PluginInfo(Path('b.py'))
       info_b.plugin = PluginB(mock_bot)
       info_b.state = PluginState.LOADED
       
       manager._plugins = {'a': info_a, 'b': info_b}
       
       # Resolve dependencies
       order = manager._resolve_dependencies()
       
       # B should come before A
       assert order.index('b') < order.index('a')
   
   
   @pytest.mark.asyncio
   async def test_circular_dependency(mock_bot):
       """Test circular dependency detection."""
       # Create plugins with circular dependency
       class PluginA(Plugin):
           @property
           def metadata(self):
               return PluginMetadata(
                   name='a', display_name='A', version='1.0.0',
                   description='Plugin A', author='Test',
                   dependencies=['b']
               )
       
       class PluginB(Plugin):
           @property
           def metadata(self):
               return PluginMetadata(
                   name='b', display_name='B', version='1.0.0',
                   description='Plugin B', author='Test',
                   dependencies=['a']
               )
       
       manager = PluginManager(mock_bot)
       
       # Add plugins
       from lib.plugin.manager import PluginInfo, PluginState
       from lib.plugin.errors import PluginDependencyError
       
       info_a = PluginInfo(Path('a.py'))
       info_a.plugin = PluginA(mock_bot)
       info_a.state = PluginState.LOADED
       
       info_b = PluginInfo(Path('b.py'))
       info_b.plugin = PluginB(mock_bot)
       info_b.state = PluginState.LOADED
       
       manager._plugins = {'a': info_a, 'b': info_b}
       
       # Should raise
       with pytest.raises(PluginDependencyError):
           manager._resolve_dependencies()
   ```

10. **Update exports** (10 min)
    ```python
    # lib/plugin/__init__.py
    from .base import Plugin
    from .metadata import PluginMetadata
    from .manager import PluginManager, PluginState, PluginInfo
    # ... errors
    ```

11. **Validation** (30 min)
    ```bash
    mypy lib/plugin/manager.py
    pylint lib/plugin/manager.py
    pytest test/test_plugin_manager.py -v
    ```

## Testing Strategy

### Unit Tests

- ✅ Plugin discovery
- ✅ Plugin loading
- ✅ Dependency resolution (simple, complex, circular)
- ✅ Lifecycle management (setup, enable, disable, teardown)
- ✅ Error isolation
- ✅ Reload functionality
- ✅ Public API methods

### Integration Tests

- ✅ Load multiple real plugins
- ✅ Dependency chain resolution
- ✅ Error in one plugin doesn't affect others

## Dependencies

**Python Packages:**
- None (pure Python)

**Internal Modules:**
- `lib/plugin/base.py` (Sortie 1)
- `lib/plugin/metadata.py` (Sortie 1)
- `lib/plugin/errors.py` (Sortie 1)

## Validation

Before moving to Sortie 3:

1. ✅ PluginManager class complete
2. ✅ Plugin discovery works
3. ✅ Plugin loading works
4. ✅ Dependency resolution works
5. ✅ Lifecycle management works
6. ✅ Error isolation works
7. ✅ All tests pass
8. ✅ Type checking passes

## Risks & Mitigations

**Risk:** Plugin errors crash bot  
**Mitigation:** Try/except around all plugin operations, log errors, mark plugin as FAILED

**Risk:** Dependency resolution too complex  
**Mitigation:** Use proven algorithm (Kahn's), detect circular deps explicitly

**Risk:** Module reload issues  
**Mitigation:** Proper cleanup (disable → teardown → remove), reload from file

**Risk:** Plugin file not found  
**Mitigation:** Check file exists, helpful error messages

## Design Decisions

### Why Topological Sort?

Ensures dependencies loaded before dependents. Standard algorithm, efficient.

### Why Separate States?

Clear tracking of plugin lifecycle. Helps debug issues, enables safe state transitions.

### Why Error Isolation?

One plugin failure shouldn't crash bot or other plugins. Log and continue.

### Why File Tracking?

Enables hot reload - know which file corresponds to which plugin.

## Next Steps

After completion, proceed to:

- **Sortie 3:** Implement hot reload (file watching, auto-reload)
- **Sortie 4:** Implement event bus (inter-plugin communication)

---

**Created:** November 12, 2025  
**Author:** Copilot  
**Sprint:** 8 - Inception
