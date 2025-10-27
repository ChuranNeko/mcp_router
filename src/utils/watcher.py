"""File watcher for hot-reloading MCP configurations."""

import asyncio
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from ..core.logger import get_logger

logger = get_logger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """Handler for configuration file changes."""
    
    def __init__(self, callback: Callable, debounce_delay: float = 1.0):
        """Initialize handler.
        
        Args:
            callback: Function to call when files change
            debounce_delay: Delay in seconds to debounce rapid changes
        """
        super().__init__()
        self.callback = callback
        self.debounce_delay = debounce_delay
        self._last_modified: Dict[str, float] = {}
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification event.
        
        Args:
            event: File system event
        """
        if event.is_directory:
            return
        
        if not event.src_path.endswith('mcp_settings.json'):
            return
        
        self._handle_change(event.src_path, 'modified')
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation event.
        
        Args:
            event: File system event
        """
        if event.is_directory:
            return
        
        if not event.src_path.endswith('mcp_settings.json'):
            return
        
        self._handle_change(event.src_path, 'created')
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion event.
        
        Args:
            event: File system event
        """
        if event.is_directory:
            return
        
        if not event.src_path.endswith('mcp_settings.json'):
            return
        
        self._handle_change(event.src_path, 'deleted')
    
    def _handle_change(self, path: str, event_type: str) -> None:
        """Handle file change with debouncing.
        
        Args:
            path: Path to changed file
            event_type: Type of change (created, modified, deleted)
        """
        current_time = time.time()
        last_time = self._last_modified.get(path, 0)
        
        if current_time - last_time < self.debounce_delay:
            logger.debug(f"Debouncing change for {path}")
            return
        
        self._last_modified[path] = current_time
        logger.info(f"Configuration file {event_type}: {path}")
        
        try:
            asyncio.create_task(self.callback(path, event_type))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.callback(path, event_type))


class FileWatcher:
    """Watches for configuration file changes and triggers reloads."""
    
    def __init__(
        self,
        watch_path: str = "data",
        callback: Optional[Callable] = None,
        debounce_delay: float = 1.0
    ):
        """Initialize file watcher.
        
        Args:
            watch_path: Directory path to watch
            callback: Callback function for file changes
            debounce_delay: Delay in seconds to debounce rapid changes
        """
        self.watch_path = Path(watch_path)
        self.callback = callback
        self.debounce_delay = debounce_delay
        self.observer: Optional[Observer] = None
        self._running = False
    
    def start(self) -> None:
        """Start watching for file changes."""
        if self._running:
            logger.warning("File watcher already running")
            return
        
        if not self.watch_path.exists():
            logger.warning(f"Watch path does not exist: {self.watch_path}")
            self.watch_path.mkdir(parents=True, exist_ok=True)
        
        if not self.callback:
            logger.warning("No callback provided, watcher will not do anything")
            return
        
        event_handler = ConfigFileHandler(self.callback, self.debounce_delay)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.watch_path), recursive=True)
        self.observer.start()
        self._running = True
        
        logger.info(f"File watcher started for: {self.watch_path}")
    
    def stop(self) -> None:
        """Stop watching for file changes."""
        if not self._running or not self.observer:
            return
        
        self.observer.stop()
        self.observer.join()
        self._running = False
        
        logger.info("File watcher stopped")
    
    def is_running(self) -> bool:
        """Check if watcher is running.
        
        Returns:
            True if running, False otherwise
        """
        return self._running

