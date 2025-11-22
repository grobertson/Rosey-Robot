"""
lib/plugin/hot_reload.py

File system watching and automatic plugin reloading.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Set

try:
    from watchdog.events import FileModifiedEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object

from .manager import PluginManager


class ReloadHandler(FileSystemEventHandler):
    """
    Handle file system events for plugin hot reload.
    
    Features:
        - Debouncing (wait for quiet period after changes)
        - Queue reloads (avoid duplicate reloads)
        - Error isolation (reload failure doesn't crash watcher)
    
    Args:
        manager: PluginManager instance
        debounce_delay: Seconds to wait after last change (default: 0.5)
        logger: Optional logger instance
    
    Example:
        handler = ReloadHandler(manager, debounce_delay=0.5)
        await handler.start()
        # ... file changes detected automatically ...
        await handler.stop()
    """

    def __init__(
        self,
        manager: PluginManager,
        debounce_delay: float = 0.5,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize reload handler.
        
        Args:
            manager: PluginManager to reload plugins
            debounce_delay: Seconds to wait after last change
            logger: Optional logger
        """
        super().__init__()
        self.manager = manager
        self.debounce_delay = debounce_delay
        self.logger = logger or logging.getLogger("plugin.hot_reload")

        # Pending reloads: path -> timestamp of last change
        self._pending: Dict[Path, float] = {}

        # Currently reloading (prevent duplicate reloads)
        self._reloading: Set[Path] = set()

        # Background task
        self._reload_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def on_modified(self, event):
        """
        Handle file modification event.
        
        Called by watchdog when file changes detected.
        Queues plugin for reload after debounce delay.
        
        Args:
            event: FileSystemEvent from watchdog
        """
        # Ignore directories
        if event.is_directory:
            return

        # Only watch .py files
        if not event.src_path.endswith(".py"):
            return

        # Ignore __init__.py
        if event.src_path.endswith("__init__.py"):
            return

        file_path = Path(event.src_path)

        # Check if this is a loaded plugin file
        if file_path not in self.manager._file_to_name:
            # Not a loaded plugin (might be new file)
            self.logger.debug(f"Ignoring unloaded file: {file_path.name}")
            return

        # Queue for reload
        self._pending[file_path] = time.time()
        self.logger.debug(f"Queued for reload: {file_path.name}")

    async def start(self):
        """
        Start background reload task.
        
        Begins processing the reload queue with debouncing.
        """
        if self._reload_task and not self._reload_task.done():
            self.logger.warning("Reload task already running")
            return

        self._stop_event.clear()
        self._reload_task = asyncio.create_task(self._reload_loop())
        self.logger.info("Hot reload handler started")

    async def stop(self):
        """
        Stop background reload task.
        
        Waits for current reloads to complete.
        """
        self._stop_event.set()
        if self._reload_task:
            await self._reload_task
            self._reload_task = None
        self.logger.info("Hot reload handler stopped")

    async def _reload_loop(self):
        """
        Background task that processes reload queue.
        
        Waits for debounce delay after last change,
        then reloads the plugin.
        """
        while not self._stop_event.is_set():
            # Check pending reloads
            now = time.time()
            ready_to_reload = []

            for file_path, queued_time in list(self._pending.items()):
                # Check if enough time has passed since last change
                if now - queued_time >= self.debounce_delay:
                    ready_to_reload.append(file_path)

            # Process ready reloads
            for file_path in ready_to_reload:
                # Skip if already reloading
                if file_path in self._reloading:
                    continue

                # Remove from pending
                del self._pending[file_path]

                # Mark as reloading
                self._reloading.add(file_path)

                # Reload plugin
                try:
                    plugin_name = self.manager._file_to_name.get(file_path)
                    if plugin_name:
                        self.logger.info(f"🔄 Reloading plugin: {plugin_name}")
                        await self.manager.reload(plugin_name)
                        self.logger.info(f"✅ Reloaded: {plugin_name}")
                    else:
                        self.logger.warning(f"Plugin not found for: {file_path}")

                except Exception as e:
                    self.logger.error(f"❌ Reload failed for {file_path}: {e}")

                finally:
                    # Mark as done
                    self._reloading.discard(file_path)

            # Sleep briefly before next check
            await asyncio.sleep(0.1)


class HotReloadWatcher:
    """
    File system watcher for plugin hot reload.
    
    Uses watchdog to monitor plugin directory and trigger
    automatic reloads when files change.
    
    Features:
        - Automatic plugin reload on file save
        - Debouncing (wait for quiet period)
        - Can be enabled/disabled
        - Error isolation
    
    Args:
        manager: PluginManager instance
        enabled: Start watching immediately (default: False)
        debounce_delay: Seconds to wait after last change (default: 0.5)
        logger: Optional logger instance
    
    Example:
        watcher = HotReloadWatcher(manager)
        watcher.start()
        # ... plugins reload automatically on file changes ...
        watcher.stop()
    
    Note:
        Requires watchdog package: pip install watchdog
    """

    def __init__(
        self,
        manager: PluginManager,
        enabled: bool = False,
        debounce_delay: float = 0.5,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize hot reload watcher.
        
        Args:
            manager: PluginManager to reload plugins
            enabled: Start immediately (default: False)
            debounce_delay: Seconds to wait after changes
            logger: Optional logger
        
        Raises:
            ImportError: If watchdog not installed
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError(
                "watchdog package required for hot reload. "
                "Install with: pip install watchdog"
            )

        self.manager = manager
        self.debounce_delay = debounce_delay
        self.logger = logger or logging.getLogger("plugin.hot_reload")

        # Watchdog observer
        self._observer: Optional[Observer] = None

        # Reload handler
        self._handler: Optional[ReloadHandler] = None

        # State
        self._enabled = False

        if enabled:
            self.start()

    def start(self):
        """
        Start watching plugin directory.
        
        Begins monitoring for file changes and automatic reloads.
        
        Raises:
            RuntimeError: If already started
        """
        if self._enabled:
            self.logger.warning("Hot reload already started")
            return

        # Check plugin directory exists
        if not self.manager.plugin_dir.exists():
            self.logger.warning(
                f"Plugin directory not found: {self.manager.plugin_dir}"
            )
            return

        # Create handler
        self._handler = ReloadHandler(
            self.manager, debounce_delay=self.debounce_delay, logger=self.logger
        )

        # Create observer
        self._observer = Observer()
        self._observer.schedule(
            self._handler, str(self.manager.plugin_dir), recursive=False
        )
        self._observer.start()

        # Start handler background task
        asyncio.create_task(self._handler.start())

        self._enabled = True
        self.logger.info(f"🔥 Hot reload enabled: {self.manager.plugin_dir}")

    def stop(self):
        """
        Stop watching plugin directory.
        
        Stops monitoring for file changes.
        """
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
        self.logger.info("Hot reload disabled")

    @property
    def is_enabled(self) -> bool:
        """
        Check if hot reload is enabled.
        
        Returns:
            True if watching for changes, False otherwise
        """
        return self._enabled

    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, "_enabled") and self._enabled:
            self.stop()

    def __repr__(self) -> str:
        """Developer representation."""
        status = "enabled" if self._enabled else "disabled"
        return f"<HotReloadWatcher: {status}, dir={self.manager.plugin_dir}>"
