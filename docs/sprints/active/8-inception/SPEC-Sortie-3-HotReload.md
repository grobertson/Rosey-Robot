# Sprint 8, Sortie 3: Hot Reload System

**Status:** Planning  
**Estimated Effort:** 6 hours  
**Sprint:** Inception (Sprint 8)  
**Phase:** 1 - Core Plugin Infrastructure  
**Dependencies:** Sortie 2 (PluginManager complete)

## Objective

Implement file system watching and automatic plugin reloading. When a plugin file changes, automatically reload it without restarting the bot. This is the REQUIRED hot reload feature your stakeholder is asking for!

## Background

Developers need fast iteration:
- Edit plugin code
- See changes immediately
- No bot restart
- No manual !plugin reload command

We'll use watchdog library to monitor plugins/ directory and trigger automatic reloads on file changes.

## Success Criteria

- ✅ File system watcher monitors plugins/ directory
- ✅ Detects file modifications
- ✅ Debounces rapid changes (0.5s)
- ✅ Automatically reloads changed plugins
- ✅ Preserves plugin state where possible
- ✅ Can be enabled/disabled
- ✅ Logs reload events

## Technical Design

### Hot Reload Architecture

```
┌──────────────────┐
│  File System     │
│  (plugins/*.py)  │
└────────┬─────────┘
         │ modification detected
         ▼
┌──────────────────┐
│   Watchdog       │  File system observer
│   Observer       │
└────────┬─────────┘
         │ event triggered
         ▼
┌──────────────────┐
│  ReloadHandler   │  Debounce & queue
│                  │
└────────┬─────────┘
         │ 0.5s after last change
         ▼
┌──────────────────┐
│ PluginManager    │  Reload plugin
│  .reload(name)   │
└──────────────────┘
```

### Hot Reload Implementation

```python
"""
lib/plugin/hot_reload.py

File system watching and automatic plugin reloading.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Set
import logging

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from .manager import PluginManager


class ReloadHandler(FileSystemEventHandler):
    """
    Handle file system events for plugin hot reload.
    
    Features:
    - Debouncing (wait 0.5s after last change)
    - Queue reloads (don't reload same plugin twice)
    - Error isolation (reload failure doesn't crash watcher)
    """
    
    def __init__(self, manager: PluginManager, debounce_delay: float = 0.5,
                 logger: Optional[logging.Logger] = None):
        super().__init__()
        self.manager = manager
        self.debounce_delay = debounce_delay
        self.logger = logger or logging.getLogger('plugin.hot_reload')
        
        # Pending reloads: path -> timestamp
        self._pending: Dict[Path, float] = {}
        
        # Currently reloading
        self._reloading: Set[Path] = set()
        
        # Background task
        self._reload_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
    
    def on_modified(self, event):
        """
        Handle file modification event.
        
        Called by watchdog when file changes detected.
        """
        if event.is_directory:
            return
        
        if not event.src_path.endswith('.py'):
            return
        
        if event.src_path.endswith('__init__.py'):
            return
        
        file_path = Path(event.src_path)
        
        # Check if this is a plugin file
        if file_path not in self.manager._file_to_name:
            # New file, not yet loaded
            return
        
        # Queue for reload
        self._pending[file_path] = time.time()
        self.logger.debug(f"Queued for reload: {file_path.name}")
    
    async def start(self):
        """Start background reload task."""
        self._stop_event.clear()
        self._reload_task = asyncio.create_task(self._reload_loop())
        self.logger.info("Hot reload started")
    
    async def stop(self):
        """Stop background reload task."""
        self._stop_event.set()
        if self._reload_task:
            await self._reload_task
        self.logger.info("Hot reload stopped")
    
    async def _reload_loop(self):
        """
        Background task that processes reload queue.
        
        Waits for debounce delay, then reloads plugins.
        """
        while not self._stop_event.is_set():
            # Check pending reloads
            now = time.time()
            ready_to_reload = []
            
            for file_path, queued_time in list(self._pending.items()):
                if now - queued_time >= self.debounce_delay:
                    ready_to_reload.append(file_path)
            
            # Process reloads
            for file_path in ready_to_reload:
                if file_path in self._reloading:
                    # Already reloading, skip
                    continue
                
                # Remove from pending
                del self._pending[file_path]
                
                # Mark as reloading
                self._reloading.add(file_path)
                
                # Reload plugin
                try:
                    plugin_name = self.manager._file_to_name.get(file_path)
                    if plugin_name:
                        self.logger.info(f"Reloading plugin: {plugin_name}")
                        await self.manager.reload(plugin_name)
                        self.logger.info(f"Reloaded: {plugin_name}")
                    else:
                        self.logger.warning(f"Plugin not found for: {file_path}")
                
                except Exception as e:
                    self.logger.error(f"Reload failed for {file_path}: {e}")
                
                finally:
                    # Mark as done
                    self._reloading.discard(file_path)
            
            # Sleep briefly
            await asyncio.sleep(0.1)


class HotReloadWatcher:
    """
    File system watcher for plugin hot reload.
    
    Uses watchdog to monitor plugin directory and trigger
    automatic reloads when files change.
    
    Args:
        manager: PluginManager instance
        enabled: Start watching immediately (default: True)
        debounce_delay: Seconds to wait after last change (default: 0.5)
        logger: Optional logger instance
    """
    
    def __init__(self, manager: PluginManager,
                 enabled: bool = True,
                 debounce_delay: float = 0.5,
                 logger: Optional[logging.Logger] = None):
        self.manager = manager
        self.debounce_delay = debounce_delay
        self.logger = logger or logging.getLogger('plugin.hot_reload')
        
        # Watchdog observer
        self._observer: Optional[Observer] = None
        
        # Reload handler
        self._handler: Optional[ReloadHandler] = None
        
        # State
        self._enabled = False
        
        if enabled:
            self.start()
    
    def start(self):
        """Start watching plugin directory."""
        if self._enabled:
            self.logger.warning("Hot reload already started")
            return
        
        # Create handler
        self._handler = ReloadHandler(
            self.manager,
            debounce_delay=self.debounce_delay,
            logger=self.logger
        )
        
        # Create observer
        self._observer = Observer()
        self._observer.schedule(
            self._handler,
            str(self.manager.plugin_dir),
            recursive=False
        )
        self._observer.start()
        
        # Start handler background task
        asyncio.create_task(self._handler.start())
        
        self._enabled = True
        self.logger.info(f"Watching for changes: {self.manager.plugin_dir}")
    
    def stop(self):
        """Stop watching plugin directory."""
        if not self._enabled:
            return
        
        # Stop observer
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        
        # Stop handler
        if self._handler:
            asyncio.create_task(self._handler.stop())
            self._handler = None
        
        self._enabled = False
        self.logger.info("Hot reload stopped")
    
    @property
    def is_enabled(self) -> bool:
        """Check if hot reload is enabled."""
        return self._enabled
    
    def __del__(self):
        """Cleanup on deletion."""
        if self._enabled:
            self.stop()
```

### Integration with PluginManager

```python
# lib/plugin/manager.py

class PluginManager:
    """Plugin manager with hot reload support."""
    
    def __init__(self, bot, plugin_dir: str = 'plugins',
                 hot_reload: bool = True,
                 logger: Optional[logging.Logger] = None):
        # ... existing code ...
        
        # Hot reload watcher
        self._hot_reload: Optional[HotReloadWatcher] = None
        if hot_reload:
            from .hot_reload import HotReloadWatcher
            self._hot_reload = HotReloadWatcher(self, enabled=False)
    
    async def load_all(self) -> None:
        """Load all plugins and start hot reload."""
        # ... existing load logic ...
        
        # Start hot reload after initial load
        if self._hot_reload:
            self._hot_reload.start()
    
    async def unload_all(self) -> None:
        """Unload all plugins and stop hot reload."""
        # Stop hot reload first
        if self._hot_reload:
            self._hot_reload.stop()
        
        # ... existing unload logic ...
```

### Configuration

```python
# config/bot_config.json

{
    "bot": {
        "domain": "cytu.be",
        "channel": "mychannel"
    },
    "plugins": {
        "enabled": true,
        "hot_reload": {
            "enabled": true,
            "debounce_delay": 0.5
        }
    }
}
```

## Implementation Steps

1. **Install watchdog** (5 min)
   ```bash
   pip install watchdog
   # Add to requirements.txt:
   # watchdog>=3.0.0
   ```

2. **Create hot_reload module** (15 min)
   ```bash
   touch lib/plugin/hot_reload.py
   ```

3. **Implement ReloadHandler** (2 hours)
   - Inherit from FileSystemEventHandler
   - Implement on_modified()
   - Add debouncing logic
   - Add reload queue
   - Add background reload task

4. **Implement HotReloadWatcher** (1 hour)
   - Wrap watchdog Observer
   - Integrate with PluginManager
   - Add start/stop methods
   - Add configuration

5. **Integrate with PluginManager** (45 min)
   - Add hot_reload parameter to __init__
   - Start watcher in load_all()
   - Stop watcher in unload_all()

6. **Write unit tests** (1.5 hours)
   ```python
   # test/test_hot_reload.py
   
   import pytest
   import asyncio
   import time
   from pathlib import Path
   from lib.plugin import PluginManager
   from lib.plugin.hot_reload import HotReloadWatcher
   
   
   @pytest.mark.asyncio
   async def test_file_change_triggers_reload(tmp_path, mock_bot):
       """Test file modification triggers reload."""
       plugin_dir = tmp_path / "plugins"
       plugin_dir.mkdir()
       
       # Create plugin file
       plugin_file = plugin_dir / "test_plugin.py"
       plugin_file.write_text('''
from lib.plugin import Plugin, PluginMetadata

class TestPlugin(Plugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name='test', display_name='Test', version='1.0.0',
            description='Test', author='Test'
        )
       ''')
       
       # Create manager and load
       manager = PluginManager(mock_bot, str(plugin_dir), hot_reload=False)
       await manager.load_all()
       
       # Start hot reload
       watcher = HotReloadWatcher(manager)
       
       # Modify file
       plugin_file.write_text(plugin_file.read_text() + "\n# Modified")
       
       # Wait for debounce + reload
       await asyncio.sleep(1.0)
       
       # Plugin should be reloaded
       # (verify via reload count or log inspection)
       
       watcher.stop()
   
   
   @pytest.mark.asyncio
   async def test_debouncing(tmp_path, mock_bot):
       """Test rapid changes are debounced."""
       plugin_dir = tmp_path / "plugins"
       plugin_dir.mkdir()
       
       plugin_file = plugin_dir / "test_plugin.py"
       plugin_file.write_text("# Version 1")
       
       manager = PluginManager(mock_bot, str(plugin_dir), hot_reload=False)
       watcher = HotReloadWatcher(manager, debounce_delay=0.5)
       
       # Rapid modifications
       for i in range(5):
           plugin_file.write_text(f"# Version {i}")
           await asyncio.sleep(0.1)
       
       # Wait for debounce
       await asyncio.sleep(0.6)
       
       # Should only reload once (not 5 times)
       # Verify via reload count
       
       watcher.stop()
   ```

7. **Integration testing** (45 min)
   - Test with real plugin files
   - Test multiple concurrent changes
   - Test error during reload
   - Test enable/disable hot reload

8. **Configuration support** (30 min)
   - Add hot_reload config to bot config
   - Add debounce_delay config
   - Update config loading

9. **Documentation** (30 min)
   - Add hot reload section to README
   - Document configuration options
   - Add troubleshooting guide

10. **Validation** (30 min)
    ```bash
    mypy lib/plugin/hot_reload.py
    pylint lib/plugin/hot_reload.py
    pytest test/test_hot_reload.py -v
    ```

## Testing Strategy

### Unit Tests

- ✅ File modification detected
- ✅ Debouncing works (multiple changes → single reload)
- ✅ Error during reload doesn't crash watcher
- ✅ Start/stop works correctly
- ✅ Non-plugin files ignored

### Integration Tests

- ✅ Real file modifications
- ✅ Multiple plugins changed
- ✅ Plugin with syntax error
- ✅ Plugin with import error
- ✅ Rapid file saves (editor autosave)

### Manual Testing

- ✅ Edit plugin in VS Code
- ✅ Save file
- ✅ Bot logs reload
- ✅ Changes take effect immediately
- ✅ No bot restart needed

## Dependencies

**Python Packages:**
- `watchdog>=3.0.0` - File system monitoring

**Internal Modules:**
- `lib/plugin/manager.py` (Sortie 2)

## Validation

Before moving to Sortie 4:

1. ✅ HotReloadWatcher class complete
2. ✅ File changes trigger reloads
3. ✅ Debouncing works
4. ✅ Integration with PluginManager works
5. ✅ All tests pass
6. ✅ Type checking passes
7. ✅ Documentation complete

## Risks & Mitigations

**Risk:** Reload during plugin operation  
**Mitigation:** Disable before reload, re-enable after. Use locks if needed.

**Risk:** File system event spam  
**Mitigation:** Debouncing (wait 0.5s after last change)

**Risk:** Watchdog platform issues  
**Mitigation:** Test on Windows/Linux/Mac. Fallback to manual reload if watchdog fails.

**Risk:** Memory leaks from reloads  
**Mitigation:** Proper cleanup in teardown(). Monitor memory usage.

**Risk:** Editor temporary files  
**Mitigation:** Only watch .py files, ignore __init__.py, ignore .pyc, etc.

## Design Decisions

### Why Watchdog?

- Cross-platform (Windows, Linux, Mac)
- Well-maintained
- Standard for Python file watching
- Used by pytest-watch, Flask, etc.

### Why Debouncing?

Editors often save multiple times rapidly (autosave, format on save, etc.). Debouncing prevents reload spam.

### Why 0.5s Delay?

Balance between responsiveness and stability. Can be configured.

### Why Background Task?

Reload is async and may take time. Don't block file system events.

## Performance Considerations

- **Watchdog overhead:** Minimal (< 1% CPU)
- **Reload time:** ~100-500ms per plugin
- **Debounce delay:** 0.5s (configurable)
- **Memory:** No accumulation (proper cleanup)

## User Experience

**Developer workflow:**
1. Edit plugin.py in VS Code
2. Save (Ctrl+S)
3. Bot logs: "Reloading plugin: my_plugin"
4. Bot logs: "Reloaded: my_plugin"
5. Test changes immediately (no restart!)

**Fast iteration:**
- Edit → Save → Test (seconds)
- vs. Edit → Restart bot → Test (minutes)

## Next Steps

After completion, proceed to:

- **Sortie 4:** Implement event bus (inter-plugin communication)
- **Sortie 5:** Implement service registry (dependency injection)

---

**Created:** November 12, 2025  
**Author:** Copilot  
**Sprint:** 8 - Inception
