"""File watcher for hot-reloading MCP configurations using subprocess isolation."""

import multiprocessing
import time
from multiprocessing import Process, Queue
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..core.logger import get_logger

logger = get_logger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """Handler for configuration file changes."""

    def __init__(self, queue: Queue, debounce_delay: float = 1.0):
        """Initialize handler.

        Args:
            queue: Queue to send events to main process
            debounce_delay: Delay in seconds to debounce rapid changes
        """
        super().__init__()
        self.queue = queue
        self.debounce_delay = debounce_delay
        self._last_modified: dict[str, float] = {}

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        if not event.src_path.endswith("mcp_settings.json"):
            return

        self._handle_change(event.src_path, "modified")

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        if not event.src_path.endswith("mcp_settings.json"):
            return

        self._handle_change(event.src_path, "created")

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        if not event.src_path.endswith("mcp_settings.json"):
            return

        self._handle_change(event.src_path, "deleted")

    def _handle_change(self, path: str, event_type: str) -> None:
        """Handle file change with debouncing.

        Args:
            path: Path to changed file
            event_type: Type of change (created, modified, deleted)
        """
        current_time = time.time()
        last_time = self._last_modified.get(path, 0)

        if current_time - last_time < self.debounce_delay:
            return

        self._last_modified[path] = current_time

        # Send event to main process via queue
        try:
            self.queue.put_nowait({"path": path, "event_type": event_type})
        except Exception:
            pass  # Queue might be full, skip this event


def _watch_process(watch_path: str, queue: Queue, debounce_delay: float):
    """Subprocess function to watch for file changes.

    Args:
        watch_path: Directory path to watch
        queue: Queue to send events to main process
        debounce_delay: Delay in seconds to debounce rapid changes
    """
    # Setup logging in subprocess
    subprocess_logger = get_logger(f"{__name__}.subprocess")
    subprocess_logger.info(f"File watcher subprocess started for: {watch_path}")

    path = Path(watch_path)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    event_handler = ConfigFileHandler(queue, debounce_delay)
    observer = Observer()
    observer.schedule(event_handler, str(path), recursive=True)
    observer.start()

    try:
        # Keep subprocess running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    finally:
        observer.join()
        subprocess_logger.info("File watcher subprocess stopped")


class FileWatcher:
    """Watches for configuration file changes using isolated subprocess."""

    def __init__(
        self,
        watch_path: str = "data",
        debounce_delay: float = 1.0,
    ):
        """Initialize file watcher.

        Args:
            watch_path: Directory path to watch
            debounce_delay: Delay in seconds to debounce rapid changes
        """
        self.watch_path = Path(watch_path)
        self.debounce_delay = debounce_delay
        self._process: Process | None = None
        self._queue: Queue | None = None
        self._running = False

    def start(self) -> Queue:
        """Start watching for file changes in subprocess.

        Returns:
            Queue to receive file change events
        """
        if self._running:
            logger.warning("File watcher already running")
            return self._queue

        if not self.watch_path.exists():
            logger.warning(f"Watch path does not exist: {self.watch_path}")
            self.watch_path.mkdir(parents=True, exist_ok=True)

        # Create queue for inter-process communication
        self._queue = multiprocessing.Queue(maxsize=100)

        # Start watcher in subprocess
        self._process = Process(
            target=_watch_process,
            args=(str(self.watch_path), self._queue, self.debounce_delay),
            daemon=True,  # Daemon process will terminate when main process exits
        )
        self._process.start()
        self._running = True

        logger.info(f"File watcher started in subprocess (PID: {self._process.pid})")

        return self._queue

    def stop(self) -> None:
        """Stop watching for file changes."""
        if not self._running or not self._process:
            return

        logger.info("Stopping file watcher subprocess...")

        # Terminate subprocess
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=5)

            # Force kill if still alive
            if self._process.is_alive():
                self._process.kill()
                self._process.join()

        self._running = False
        self._process = None
        self._queue = None

        logger.info("File watcher stopped")

    def is_running(self) -> bool:
        """Check if watcher is running.

        Returns:
            True if running, False otherwise
        """
        return self._running and self._process is not None and self._process.is_alive()
