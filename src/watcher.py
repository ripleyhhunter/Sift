"""
Folder monitoring module for Sift.

Uses watchdog library to monitor the inbox folder for new files
and trigger the document processing pipeline.
"""

import time
import logging
import threading
from pathlib import Path
from queue import Queue, Empty
from typing import Callable, Optional, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, DirCreatedEvent

from .config import Config
from .utils import is_file_ready, is_temp_file, is_supported_extension

logger = logging.getLogger(__name__)


class DocumentEventHandler(FileSystemEventHandler):
    """
    Handle file system events for new documents.
    
    Filters events and queues valid files for processing.
    Supports both individual files and folders (recursively processed).
    """
    
    # Delay for folder processing (wait for copy to complete)
    FOLDER_PROCESSING_DELAY = 5.0
    
    def __init__(
        self,
        config: Config,
        file_queue: Queue,
        processing_delay: float = 2.0,
        on_folder_queued: Optional[Callable[[int], None]] = None
    ):
        """
        Initialize the event handler.
        
        Args:
            config: Application configuration
            file_queue: Queue to add files for processing
            processing_delay: Seconds to wait before processing new files
            on_folder_queued: Callback when folder files are queued (receives count)
        """
        super().__init__()
        self.config = config
        self.file_queue = file_queue
        self.processing_delay = processing_delay
        self.on_folder_queued = on_folder_queued
        self.supported_extensions = [
            ext.lower() for ext in config.processing.supported_extensions
        ]
        self._pending_files = set()
        self._pending_folders = set()
        self._lock = threading.Lock()
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """
        Handle file/folder creation events.
        
        Args:
            event: The file system event
        """
        path = Path(event.src_path)
        
        # Handle folders - process contents recursively
        if event.is_directory:
            self._handle_folder_drop(path)
            return
        
        # Handle individual files
        if not self._should_process(path):
            return
        
        # Avoid duplicate processing
        with self._lock:
            if path in self._pending_files:
                return
            self._pending_files.add(path)
        
        # Schedule delayed processing
        logger.info(f"New file detected: {path.name}")
        threading.Thread(
            target=self._delayed_queue,
            args=(path,),
            daemon=True
        ).start()
    
    def _handle_folder_drop(self, folder_path: Path) -> None:
        """
        Handle a folder being dropped into the Inbox.
        
        Recursively finds all supported files and queues them for processing.
        
        Args:
            folder_path: Path to the dropped folder
        """
        # Avoid duplicate folder processing
        with self._lock:
            if folder_path in self._pending_folders:
                return
            self._pending_folders.add(folder_path)
        
        logger.info(f"Folder detected: {folder_path.name} - scanning for files...")
        
        # Process in background thread
        threading.Thread(
            target=self._process_folder,
            args=(folder_path,),
            daemon=True
        ).start()
    
    def _process_folder(self, folder_path: Path) -> None:
        """
        Process a dropped folder - find all files and queue them.
        
        Args:
            folder_path: Path to the folder
        """
        try:
            # Wait for folder copy to complete
            time.sleep(self.FOLDER_PROCESSING_DELAY)
            
            if not folder_path.exists():
                logger.debug(f"Folder no longer exists: {folder_path}")
                return
            
            # Wait until folder size stabilizes (copy complete)
            if not self._wait_for_folder_stable(folder_path):
                logger.warning(f"Folder still changing, processing anyway: {folder_path.name}")
            
            # Recursively find all supported files
            files_found = []
            for file_path in folder_path.rglob('*'):
                if file_path.is_file():
                    if is_temp_file(file_path):
                        continue
                    if not is_supported_extension(file_path, self.supported_extensions):
                        continue
                    files_found.append(file_path)
            
            if not files_found:
                logger.info(f"No supported files found in folder: {folder_path.name}")
                # Clean up empty folder
                self._cleanup_empty_folder(folder_path)
                return
            
            logger.info(f"Found {len(files_found)} file(s) in folder '{folder_path.name}'")
            
            # Queue all files
            for file_path in files_found:
                with self._lock:
                    if file_path not in self._pending_files:
                        self._pending_files.add(file_path)
                        self.file_queue.put(file_path)
                        logger.debug(f"Queued from folder: {file_path.name}")
            
            # Notify about queued files
            if self.on_folder_queued:
                self.on_folder_queued(len(files_found))
            
            # Schedule folder cleanup after files are processed
            # The cleanup will happen when the folder becomes empty
            threading.Thread(
                target=self._delayed_folder_cleanup,
                args=(folder_path, len(files_found)),
                daemon=True
            ).start()
            
        except Exception as e:
            logger.error(f"Error processing folder {folder_path.name}: {e}")
        finally:
            with self._lock:
                self._pending_folders.discard(folder_path)
    
    def _wait_for_folder_stable(self, folder_path: Path, timeout: float = 30.0) -> bool:
        """
        Wait until folder contents stop changing (copy complete).
        
        Args:
            folder_path: Path to folder
            timeout: Maximum wait time
            
        Returns:
            True if folder stabilized, False if timeout
        """
        start_time = time.time()
        last_size = -1
        stable_count = 0
        
        while time.time() - start_time < timeout:
            try:
                # Count total size of all files
                current_size = sum(
                    f.stat().st_size for f in folder_path.rglob('*') if f.is_file()
                )
                
                if current_size == last_size:
                    stable_count += 1
                    if stable_count >= 3:  # Stable for 3 checks
                        return True
                else:
                    stable_count = 0
                    last_size = current_size
                
                time.sleep(1.0)
                
            except (OSError, PermissionError) as e:
                # Folder may be locked during copy - wait and retry
                logger.debug(f"Error checking folder size (retrying): {e}")
                time.sleep(1.0)
        
        return False
    
    def _delayed_folder_cleanup(self, folder_path: Path, expected_files: int) -> None:
        """
        Wait for files to be processed, then clean up empty folder.
        
        Args:
            folder_path: Path to folder to clean up
            expected_files: Number of files that were queued
        """
        # Wait an estimated time for processing (15 sec per file + buffer)
        wait_time = min(expected_files * 20 + 60, 600)  # Cap at 10 minutes
        time.sleep(wait_time)
        
        # Clean up if folder is now empty
        self._cleanup_empty_folder(folder_path)
    
    def _cleanup_empty_folder(self, folder_path: Path) -> None:
        """
        Remove a folder if it's empty (including empty subfolders).
        
        Args:
            folder_path: Path to folder
        """
        if not folder_path.exists():
            return
        
        try:
            # First, clean up any empty subfolders (bottom-up)
            for subfolder in sorted(folder_path.rglob('*'), reverse=True):
                if subfolder.is_dir():
                    try:
                        subfolder.rmdir()  # Only removes if empty
                        logger.debug(f"Removed empty subfolder: {subfolder.name}")
                    except OSError:
                        pass  # Not empty, skip
            
            # Then try to remove the main folder
            folder_path.rmdir()
            logger.info(f"Cleaned up empty folder: {folder_path.name}")
            
        except OSError:
            # Folder not empty - some files weren't processed
            remaining = list(folder_path.rglob('*'))
            if remaining:
                logger.debug(f"Folder not empty, {len(remaining)} items remaining: {folder_path.name}")
        except Exception as e:
            logger.debug(f"Could not clean up folder {folder_path.name}: {e}")
    
    def _should_process(self, file_path: Path) -> bool:
        """
        Check if file should be processed.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file should be processed
        """
        # Check if temp file
        if is_temp_file(file_path):
            logger.debug(f"Ignoring temp file: {file_path.name}")
            return False
        
        # Check extension
        if not is_supported_extension(file_path, self.supported_extensions):
            logger.debug(f"Ignoring unsupported extension: {file_path.name}")
            return False
        
        return True
    
    def _delayed_queue(self, file_path: Path) -> None:
        """
        Wait for file to be ready, then queue for processing.
        
        Args:
            file_path: Path to the file
        """
        try:
            # Initial delay for file copy completion
            time.sleep(self.processing_delay)
            
            # Check file still exists
            if not file_path.exists():
                logger.debug(f"File no longer exists: {file_path.name}")
                return
            
            # Check file is ready (not locked)
            if not is_file_ready(file_path):
                logger.warning(f"File locked, skipping: {file_path.name}")
                return
            
            # Add to processing queue
            self.file_queue.put(file_path)
            logger.debug(f"Queued for processing: {file_path.name}")
            
        except Exception as e:
            logger.error(f"Error queuing file {file_path.name}: {e}")
        finally:
            with self._lock:
                self._pending_files.discard(file_path)


class DocumentWatcher:
    """
    Monitor a folder for new documents and dispatch for processing.
    
    Designed for robust batch processing with:
    - Rate limiting between LLM requests
    - Retry logic for locked/failed files
    - Progress tracking
    - Health monitoring
    - Crash recovery via persistent queue
    """
    
    # Processing delays (in seconds)
    DELAY_BETWEEN_FILES = 1.0  # Pause between LLM requests
    DELAY_AFTER_TIMEOUT = 5.0  # Longer pause after a timeout
    MAX_RETRY_ATTEMPTS = 3     # Retries for locked files
    RETRY_DELAY = 10.0         # Delay between retries
    
    def __init__(self, config: Config, on_file: Callable[[Path], None], 
                 database=None):
        """
        Initialize the document watcher.
        
        Args:
            config: Application configuration
            on_file: Callback function to process each file
            database: Optional DocumentDatabase for crash recovery
        """
        self.config = config
        self.on_file = on_file
        self.watch_path = config.folders.watch_path
        self.file_queue: Queue = Queue()
        self.retry_queue: Queue = Queue()  # Files that need retry
        self.observer: Optional[Observer] = None
        self._running = False
        self._processing_thread: Optional[threading.Thread] = None
        self._database = database  # For crash recovery
        
        # Progress tracking
        self._total_queued = 0
        self._processed_count = 0
        self._failed_count = 0
        self._current_file: Optional[str] = None
        self._last_timeout = False  # Track if last request timed out
        self._stats_lock = threading.Lock()
    
    def start(self) -> None:
        """Start watching the folder."""
        if self._running:
            logger.warning("Watcher already running")
            return
        
        # Ensure watch folder exists
        if not self.watch_path.exists():
            logger.info(f"Creating watch folder: {self.watch_path}")
            self.watch_path.mkdir(parents=True, exist_ok=True)
        
        # Recover any interrupted items from previous crash
        self._recover_interrupted_items()
        
        # Create event handler
        event_handler = DocumentEventHandler(
            self.config,
            self.file_queue,
            self.config.processing.processing_delay_seconds
        )
        
        # Create and start observer
        self.observer = Observer()
        self.observer.schedule(
            event_handler,
            str(self.watch_path),
            recursive=False  # Only watch inbox, not subfolders
        )
        self.observer.start()
        
        # Start processing thread
        self._running = True
        self._processing_thread = threading.Thread(
            target=self._process_queue,
            daemon=True
        )
        self._processing_thread.start()
        
        logger.info(f"Started watching folder: {self.watch_path}")
    
    def _recover_interrupted_items(self) -> int:
        """
        Recover items that were being processed when the app crashed.
        
        Returns:
            Number of items recovered
        """
        if not self._database:
            return 0
        
        try:
            # Reset any items that were mid-processing
            reset_count = self._database.reset_interrupted_items()
            
            # Get all pending items (including just-reset ones)
            pending_items = self._database.get_pending_queue_items(include_failed=False)
            
            recovered = 0
            for item in pending_items:
                file_path = Path(item['file_path'])
                if file_path.exists():
                    self.file_queue.put(file_path)
                    recovered += 1
                    logger.debug(f"Recovered from queue: {file_path.name}")
                else:
                    # File no longer exists, clean up queue entry
                    self._database.mark_processing_completed(
                        str(file_path), 
                        success=False, 
                        error_message="File no longer exists"
                    )
            
            if recovered > 0:
                logger.info(f"Recovered {recovered} items from previous session")
                with self._stats_lock:
                    self._total_queued += recovered
            
            return recovered
            
        except Exception as e:
            logger.warning(f"Could not recover interrupted items: {e}")
            return 0
    
    def stop(self) -> None:
        """Stop watching and cleanup."""
        logger.info("Stopping folder watcher...")
        self._running = False
        
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None
        
        if self._processing_thread:
            self._processing_thread.join(timeout=5)
            self._processing_thread = None
        
        logger.info("Folder watcher stopped")
    
    def _process_queue(self) -> None:
        """
        Process files from the queue with rate limiting and retry logic.
        
        Features:
        - Delays between LLM requests to prevent overwhelming
        - Longer delays after timeouts (backoff)
        - Retry logic for locked files
        - Progress tracking
        """
        while self._running:
            try:
                # First check retry queue for files that failed previously
                file_path = None
                is_retry = False
                
                try:
                    file_path = self.retry_queue.get_nowait()
                    is_retry = True
                except Empty:
                    pass
                
                # If no retry files, check main queue
                if file_path is None:
                    try:
                        file_path = self.file_queue.get(timeout=1.0)
                    except Empty:
                        continue
                
                # Double-check file still exists
                if not file_path.exists():
                    logger.debug(f"File no longer exists: {file_path}")
                    if self._database:
                        self._database.mark_processing_completed(
                            str(file_path), success=False, 
                            error_message="File no longer exists"
                        )
                    self._increment_processed()
                    continue
                
                # Check if file is ready (not locked by OneDrive/other process)
                if not is_file_ready(file_path):
                    # File is locked - queue for retry
                    retry_count = getattr(file_path, '_retry_count', 0)
                    if retry_count < self.MAX_RETRY_ATTEMPTS:
                        file_path._retry_count = retry_count + 1
                        logger.warning(
                            f"File locked, will retry ({retry_count + 1}/{self.MAX_RETRY_ATTEMPTS}): "
                            f"{file_path.name}"
                        )
                        self.retry_queue.put(file_path)
                        time.sleep(self.RETRY_DELAY)
                    else:
                        logger.error(f"File still locked after {self.MAX_RETRY_ATTEMPTS} retries: {file_path.name}")
                        if self._database:
                            self._database.mark_processing_completed(
                                str(file_path), success=False,
                                error_message=f"File locked after {self.MAX_RETRY_ATTEMPTS} retries"
                            )
                        self._increment_failed()
                    continue
                
                # Update current file for progress tracking
                with self._stats_lock:
                    self._current_file = file_path.name
                
                # Mark as processing in database (for crash recovery)
                if self._database:
                    self._database.mark_processing_started(str(file_path))
                
                # Log progress
                progress = self._get_progress_string()
                retry_tag = " [RETRY]" if is_retry else ""
                logger.info(f"Processing{retry_tag}: {file_path.name} {progress}")
                
                # Process the file
                try:
                    start_time = time.time()
                    self.on_file(file_path)
                    elapsed = time.time() - start_time
                    
                    # Check if this was likely a timeout (took close to timeout limit)
                    timeout_limit = self.config.llm.timeout_seconds
                    if elapsed > timeout_limit * 0.9:
                        logger.warning(f"Processing took {elapsed:.1f}s (near timeout), adding extra delay")
                        self._last_timeout = True
                    else:
                        self._last_timeout = False
                    
                    # Mark completed successfully in database
                    if self._database:
                        self._database.mark_processing_completed(str(file_path), success=True)
                    
                    self._increment_processed()
                    
                except Exception as e:
                    logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)
                    if self._database:
                        self._database.mark_processing_completed(
                            str(file_path), success=False, error_message=str(e)
                        )
                    self._increment_failed()
                
                # Clear current file
                with self._stats_lock:
                    self._current_file = None
                
                # Rate limiting: pause between files
                if self._last_timeout:
                    # Longer pause after a timeout to let LMStudio recover
                    logger.debug(f"Post-timeout delay: {self.DELAY_AFTER_TIMEOUT}s")
                    time.sleep(self.DELAY_AFTER_TIMEOUT)
                else:
                    # Normal delay between files
                    time.sleep(self.DELAY_BETWEEN_FILES)
                    
            except Exception as e:
                logger.error(f"Error in processing queue: {e}", exc_info=True)
    
    def scan_existing(self, recursive: bool = True) -> int:
        """
        Scan and process existing files in the watch folder.
        
        Args:
            recursive: If True, scan subfolders too (for dropped folders)
        
        Returns:
            Number of files queued for processing
        """
        if not self.watch_path.exists():
            return 0
        
        count = 0
        folders_found = 0
        supported_extensions = [
            ext.lower() for ext in self.config.processing.supported_extensions
        ]
        
        logger.info(f"Scanning for existing files in: {self.watch_path}")
        
        # Reset batch statistics for this batch
        self.reset_batch_stats()
        
        # Use rglob for recursive scanning, iterdir for non-recursive
        if recursive:
            items = list(self.watch_path.rglob('*'))
        else:
            items = list(self.watch_path.iterdir())
        
        for item_path in items:
            if item_path.is_file():
                if is_temp_file(item_path):
                    continue
                if not is_supported_extension(item_path, supported_extensions):
                    continue
                
                # Queue to in-memory queue
                self.file_queue.put(item_path)
                
                # Also persist to database for crash recovery
                if self._database:
                    self._database.queue_file_for_processing(str(item_path))
                
                count += 1
                logger.debug(f"Queued existing file: {item_path.name}")
            elif item_path.is_dir() and item_path.parent == self.watch_path:
                # Count top-level folders (not subfolders)
                folders_found += 1
        
        # Update total for progress tracking
        with self._stats_lock:
            self._total_queued = count
        
        if count > 0:
            if folders_found > 0:
                logger.info(f"Found {folders_found} folder(s) containing {count} file(s)")
            else:
                logger.info(f"Queued {count} existing file(s) for processing")
            
            # Estimate processing time
            estimated_minutes = (count * 15) / 60  # Assume ~15 sec per file average
            logger.info(f"Estimated processing time: {estimated_minutes:.0f}-{estimated_minutes*2:.0f} minutes")
        else:
            logger.info("No existing files to process")
        
        # Schedule cleanup for any folders after processing
        if folders_found > 0 and count > 0:
            for item in self.watch_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    threading.Thread(
                        target=self._delayed_folder_cleanup,
                        args=(item, count),
                        daemon=True
                    ).start()
        
        return count
    
    def _delayed_folder_cleanup(self, folder_path: Path, file_count: int) -> None:
        """
        Clean up folder after processing is likely complete.
        
        Args:
            folder_path: Folder to clean up
            file_count: Number of files being processed
        """
        # Wait for estimated processing time
        wait_time = min(file_count * 20 + 60, 600)
        time.sleep(wait_time)
        
        if not folder_path.exists():
            return
        
        try:
            # Clean up empty subfolders first (bottom-up)
            for subfolder in sorted(folder_path.rglob('*'), reverse=True):
                if subfolder.is_dir():
                    try:
                        subfolder.rmdir()
                    except OSError:
                        pass
            
            # Try to remove main folder
            folder_path.rmdir()
            logger.info(f"Cleaned up empty folder: {folder_path.name}")
        except OSError:
            pass  # Not empty
        except Exception as e:
            logger.debug(f"Folder cleanup error: {e}")
    
    @property
    def is_running(self) -> bool:
        """Check if watcher is currently running."""
        return self._running
    
    @property
    def queue_size(self) -> int:
        """Get current number of files in queue."""
        return self.file_queue.qsize() + self.retry_queue.qsize()
    
    def _increment_processed(self) -> None:
        """Increment the processed counter."""
        with self._stats_lock:
            self._processed_count += 1
    
    def _increment_failed(self) -> None:
        """Increment the failed counter."""
        with self._stats_lock:
            self._failed_count += 1
    
    def _get_progress_string(self) -> str:
        """Get a progress string like '[5/100]'."""
        with self._stats_lock:
            if self._total_queued > 0:
                done = self._processed_count + self._failed_count
                return f"[{done + 1}/{self._total_queued}]"
            return ""
    
    def get_batch_status(self) -> dict:
        """
        Get current batch processing status for dashboard.
        
        Returns:
            Dict with processing statistics
        """
        with self._stats_lock:
            return {
                'total_queued': self._total_queued,
                'processed': self._processed_count,
                'failed': self._failed_count,
                'pending': self.file_queue.qsize(),
                'retry_pending': self.retry_queue.qsize(),
                'current_file': self._current_file,
                'is_processing': self._current_file is not None
            }
    
    def reset_batch_stats(self) -> None:
        """Reset batch statistics for a new batch."""
        with self._stats_lock:
            self._total_queued = 0
            self._processed_count = 0
            self._failed_count = 0
            self._current_file = None

