"""
Main application entry point for Sift.

Orchestrates all components and provides CLI interface.
"""

import sys
import time
import signal
import argparse
import logging
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports when running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config, ConfigurationError, setup_logging
from src.watcher import DocumentWatcher
from src.document_processor import DocumentProcessor
from src.llm_client import LMStudioClient
from src.classifier import DocumentClassifier
from src.folder_organizer import FolderOrganizer
from src.database import DocumentDatabase
from src.dashboard import DashboardServer
from src.tray_icon import TrayIcon, create_startup_shortcut_vbs, remove_startup_shortcut, is_startup_enabled

# Initialize colorama for Windows console colors
try:
    import colorama
    colorama.init()
except ImportError:
    pass

logger = logging.getLogger(__name__)


class Sift:
    """
    Main application class for Sift.
    
    Coordinates all components and manages the application lifecycle.
    """
    
    def __init__(self, config: Config, project_root: Path):
        """
        Initialize the application.
        
        Args:
            config: Application configuration
            project_root: Path to project root directory
        """
        self.config = config
        self.project_root = project_root
        self.running = False
        
        # Initialize database
        db_path = project_root / "data" / "documents.db"
        self.database = DocumentDatabase(db_path)
        
        # Initialize components
        self.processor = DocumentProcessor(config)
        self.llm_client = LMStudioClient(config)
        
        # Initialize rules engine if custom rules are defined
        rules_engine = None
        if config.advanced.custom_rules:
            try:
                from .rules_engine import RulesEngine
                rules_engine = RulesEngine.from_config(config.advanced.custom_rules)
                logger.info(f"Loaded {len(config.advanced.custom_rules)} custom classification rules")
            except Exception as e:
                logger.warning(f"Could not load custom rules: {e}")
        
        self.classifier = DocumentClassifier(
            config, self.llm_client, self.processor, 
            database=self.database, rules_engine=rules_engine
        )
        self.organizer = FolderOrganizer(config)
        self.watcher: Optional[DocumentWatcher] = None
        
        # Initialize dashboard
        self.dashboard: Optional[DashboardServer] = None
        if config.dashboard.enabled:
            self.dashboard = DashboardServer(
                config=config,
                database=self.database,
                port=config.dashboard.port
            )
            # Give dashboard access to LLM for search query parsing
            self.dashboard.set_llm_client(self.llm_client)
        
        # Initialize system tray icon
        self.tray_icon: Optional[TrayIcon] = None
        self.background_mode = False
    
    def start(self, scan_existing: bool = True, background: bool = False) -> None:
        """
        Start the application.
        
        Args:
            scan_existing: Whether to process existing files in inbox
            background: Whether running in background mode (with tray icon)
        """
        self.background_mode = background
        
        logger.info("=" * 60)
        logger.info("Sift - Starting")
        if background:
            logger.info("Running in background mode with system tray")
        logger.info("=" * 60)
        
        # Start system tray icon if in background mode
        if background:
            self.tray_icon = TrayIcon(
                on_exit=self.stop,
                dashboard_url=f"http://localhost:{self.config.dashboard.port}",
                inbox_path=self.config.folders.watch_path
            )
            self.tray_icon.start()
            self.tray_icon.update_status("Starting...", "yellow")
        
        # Verify LMStudio is available (with extended retry for background mode)
        max_attempts = 30 if background else 5  # Wait longer at startup
        lmstudio_ok = self._wait_for_lmstudio(max_attempts=max_attempts)
        
        if not lmstudio_ok:
            logger.error("Cannot start without LMStudio. Exiting.")
            if self.tray_icon:
                self.tray_icon.update_status("LMStudio Offline", "red")
                self.tray_icon.notify(
                    "Sift - LMStudio Required",
                    "Please start LMStudio and load a model, then restart Sift.",
                    "error"
                )
            return
        
        # Create folder structure if needed
        if self.config.behavior.create_missing_folders:
            self.organizer.create_category_structure()
        
        # Log capabilities
        caps = self.processor.get_capabilities()
        logger.info(f"Document processing capabilities:")
        logger.info(f"  - Images: {'✓' if caps['images'] else '✗'}")
        logger.info(f"  - PDF: {'✓' if caps['pdf'] else '✗ (install Poppler)'}")
        logger.info(f"  - Office: {'✓' if caps['office'] else '✗ (install LibreOffice)'}")
        
        # Start dashboard if enabled
        if self.dashboard:
            # Clean up any zombie processes on the dashboard port
            self._cleanup_port(self.config.dashboard.port)
            
            self.dashboard.set_status(running=True, lmstudio=lmstudio_ok)
            self.dashboard.start(open_browser=self.config.dashboard.auto_open_browser)
            logger.info(f"Dashboard available at: http://localhost:{self.config.dashboard.port}")
        
        # Create watcher with database for crash recovery
        self.watcher = DocumentWatcher(
            self.config, 
            self._process_file,
            database=self.database
        )
        
        # Connect watcher to dashboard for batch status
        if self.dashboard:
            self.dashboard.set_watcher(self.watcher)
        
        # Process existing files if enabled
        if scan_existing and self.config.advanced.startup_scan:
            logger.info("Scanning for existing files...")
            self.watcher.scan_existing()
        
        # Start watching
        self.watcher.start()
        self.running = True
        
        logger.info(f"Watching folder: {self.config.folders.watch_path}")
        if not self.background_mode:
            logger.info("Press Ctrl+C to stop")
        logger.info("-" * 60)
        
        # Update tray icon to running state
        if self.tray_icon:
            self.tray_icon.update_status("Running", "green")
            self.tray_icon.notify_startup()
        
        # Main loop
        try:
            while self.running:
                time.sleep(1)
                
                # Check if paused via tray icon
                if self.tray_icon and self.tray_icon.is_paused:
                    continue
                    
        except KeyboardInterrupt:
            logger.info("\nShutdown requested...")
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the application."""
        self.running = False
        
        if self.watcher:
            self.watcher.stop()
        
        if self.dashboard:
            self.dashboard.stop()
        
        if self.llm_client:
            self.llm_client.close()
        
        if self.tray_icon:
            self.tray_icon.stop()
        
        logger.info("Sift - Stopped")
    
    def _process_file(self, file_path: Path) -> None:
        """
        Process a single file through the classification pipeline.
        
        Args:
            file_path: Path to file to process
        """
        try:
            # Check file still exists
            if not file_path.exists():
                logger.warning(f"File no longer exists: {file_path}")
                return
            
            # Extract text for search indexing (before classification moves the file)
            content_snippet = ""
            if self.processor.can_extract_text(file_path):
                try:
                    text = self.processor.extract_text(file_path)
                    if text:
                        content_snippet = text[:2000]  # Store first 2000 chars for search
                except Exception as e:
                    logger.debug(f"Could not extract text for search: {e}")
            
            # Classify the document
            result = self.classifier.classify(file_path)
            
            # Determine if manual review is needed
            needs_review = self.classifier.should_review(result)
            
            if needs_review:
                logger.warning(
                    f"Low confidence ({result.confidence:.2f}), "
                    f"moving to review: {file_path.name}"
                )
            
            # Organize the file
            new_path = self.organizer.organize_file(
                file_path,
                result,
                force_review=needs_review
            )
            
            if new_path:
                logger.info(f"✓ Organized: {file_path.name}")
                
                # Log to database with content snippet and LLM analysis
                status = 'needs_review' if needs_review else 'processed'
                self.database.add_document(
                    original_filename=file_path.name,
                    original_path=str(file_path),
                    current_path=str(new_path),
                    category=result.primary_category,
                    subcategory=result.subcategory,
                    document_type=result.document_type,
                    confidence=result.confidence,
                    reasoning=result.reasoning,
                    content_snippet=content_snippet,
                    content_summary=result.content_summary,
                    status=status
                )
                
                # Send notification if in background mode
                if self.tray_icon and self.background_mode:
                    self.tray_icon.notify_document_processed(
                        filename=file_path.name,
                        category=result.primary_category,
                        subcategory=result.subcategory
                    )
            
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)
            
            # Try to move to review folder on error
            try:
                fallback = self.organizer.organize_file(
                    file_path,
                    result if 'result' in locals() else 
                        type('obj', (object,), {
                            'primary_category': 'Miscellaneous',
                            'subcategory': '',
                            'suggested_filename': '',
                            'document_type': 'Unknown',
                            'confidence': 0,
                            'reasoning': f'Error: {str(e)}'
                        })(),
                    force_review=True
                )
            except (OSError, PermissionError) as move_error:
                logger.error(f"Could not move file to review folder: {file_path} - {move_error}")
            except Exception as move_error:
                logger.error(f"Unexpected error moving file to review folder: {file_path} - {move_error}")
    
    def _wait_for_lmstudio(self, max_attempts: int = 5, delay: float = 5.0) -> bool:
        """
        Wait for LMStudio to become available.
        
        Args:
            max_attempts: Maximum number of connection attempts
            delay: Delay between attempts in seconds
            
        Returns:
            True if LMStudio is available, False otherwise
        """
        logger.info(f"Checking LMStudio connection at {self.config.llm.base_url}...")
        
        for attempt in range(max_attempts):
            if self.llm_client.is_available():
                models = self.llm_client.get_loaded_models()
                logger.info(f"LMStudio connected. Loaded models: {models}")
                return True
            
            if attempt < max_attempts - 1:
                logger.warning(
                    f"LMStudio not available (attempt {attempt + 1}/{max_attempts}). "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
        
        logger.error(
            "Could not connect to LMStudio. Please ensure:\n"
            "  1. LMStudio is running\n"
            "  2. A model is loaded (e.g., Qwen2.5-VL 7B)\n"
            "  3. The server is started (Developer tab -> Start Server)\n"
            f"  4. The URL is correct: {self.config.llm.base_url}"
        )
        return False
    
    def _cleanup_port(self, port: int) -> None:
        """
        Kill any existing processes using the specified port.
        
        This prevents zombie Flask processes from blocking startup.
        Works on Windows, macOS, and Linux.
        
        Args:
            port: Port number to clean up
        """
        import subprocess
        import os
        from .platform_utils import IS_WINDOWS, get_subprocess_flags
        
        try:
            if IS_WINDOWS:
                # Find processes using the port
                result = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True, text=True,
                    **get_subprocess_flags()
                )
                
                pids_to_kill = set()
                for line in result.stdout.split('\n'):
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        if parts:
                            try:
                                pid = int(parts[-1])
                                # Don't kill the current process
                                if pid != os.getpid() and pid != 0:
                                    pids_to_kill.add(pid)
                            except ValueError:
                                pass
                
                # Kill the processes
                for pid in pids_to_kill:
                    try:
                        subprocess.run(
                            ['taskkill', '/F', '/PID', str(pid)],
                            capture_output=True,
                            **get_subprocess_flags()
                        )
                        logger.debug(f"Killed zombie process {pid} on port {port}")
                    except Exception:
                        pass
                
                if pids_to_kill:
                    logger.info(f"Cleaned up {len(pids_to_kill)} zombie process(es) on port {port}")
                    time.sleep(1)  # Give OS time to release the port
                    
            else:  # macOS / Linux
                # Use lsof to find processes
                result = subprocess.run(
                    ['lsof', '-i', f':{port}', '-t'],
                    capture_output=True, text=True
                )
                
                pids = [p.strip() for p in result.stdout.split('\n') if p.strip()]
                killed = 0
                
                for pid in pids:
                    try:
                        pid_int = int(pid)
                        if pid_int != os.getpid():
                            os.kill(pid_int, signal.SIGTERM)
                            killed += 1
                    except (ValueError, ProcessLookupError, PermissionError):
                        pass
                
                if killed > 0:
                    logger.info(f"Cleaned up {killed} zombie process(es) on port {port}")
                    time.sleep(1)
                    
        except FileNotFoundError:
            # netstat/lsof not available, skip cleanup
            pass
        except Exception as e:
            logger.debug(f"Port cleanup failed (non-critical): {e}")
    
    def process_single(self, file_path: Path) -> bool:
        """
        Process a single file without starting the watcher.
        
        Args:
            file_path: Path to file to process
            
        Returns:
            True if processing succeeded
        """
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False
        
        if not self.llm_client.is_available():
            logger.error("LMStudio is not available")
            return False
        
        try:
            self._process_file(file_path)
            return True
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            return False


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Sift - AI-powered document organization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    Start watching the inbox folder
  python main.py --config my.yaml   Use custom configuration file
  python main.py --scan-only        Process existing files and exit
  python main.py --file doc.pdf     Process a single file
  python main.py --verbose          Enable debug logging
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=Path,
        help='Path to configuration file (default: config/settings.yaml)'
    )
    
    parser.add_argument(
        '--scan-only',
        action='store_true',
        help='Process existing files in inbox and exit (do not watch for new files)'
    )
    
    parser.add_argument(
        '--file', '-f',
        type=Path,
        help='Process a single file and exit'
    )
    
    parser.add_argument(
        '--no-scan',
        action='store_true',
        help='Skip processing existing files on startup'
    )
    
    parser.add_argument(
        '--create-folders',
        action='store_true',
        help='Create initial folder structure and exit'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (debug) logging'
    )
    
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check configuration and LMStudio connection, then exit'
    )
    
    parser.add_argument(
        '--background',
        action='store_true',
        help='Run in background mode with system tray icon (no console output)'
    )
    
    parser.add_argument(
        '--enable-startup',
        action='store_true',
        help='Enable auto-start when Windows starts'
    )
    
    parser.add_argument(
        '--disable-startup',
        action='store_true',
        help='Disable auto-start when Windows starts'
    )
    
    parser.add_argument(
        '--startup-status',
        action='store_true',
        help='Check if auto-start is enabled'
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    args = parse_args()
    
    # Determine project root
    project_root = Path(__file__).parent.parent
    
    # Load configuration
    try:
        config_path = args.config or (project_root / "config" / "settings.yaml")
        config = Config.load(config_path)
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        return 1
    
    # Override log level if verbose
    if args.verbose:
        config.logging.level = "DEBUG"
    
    # Setup logging
    setup_logging(config, project_root)
    
    # Validate configuration
    issues = config.validate()
    if issues:
        for issue in issues:
            logger.warning(f"Configuration issue: {issue}")
    
    # Check mode - just verify configuration and connection
    if args.check:
        logger.info("Running configuration check...")
        
        # Check config
        if issues:
            logger.error("Configuration has issues")
            return 1
        else:
            logger.info("Configuration OK")
        
        # Check LMStudio
        app = Sift(config, project_root)
        if app.llm_client.is_available():
            models = app.llm_client.get_loaded_models()
            logger.info(f"LMStudio OK. Models: {models}")
        else:
            logger.error("LMStudio not available")
            return 1
        
        # Check document processing
        caps = app.processor.get_capabilities()
        logger.info(f"Poppler (PDF): {'OK' if caps['pdf'] else 'NOT FOUND'}")
        logger.info(f"LibreOffice (Office): {'OK' if caps['office'] else 'NOT FOUND'}")
        
        logger.info("All checks passed!")
        return 0
    
    # Create folders mode
    if args.create_folders:
        organizer = FolderOrganizer(config)
        organizer.create_category_structure()
        logger.info("Folder structure created successfully")
        return 0
    
    # Startup management
    if args.enable_startup:
        if create_startup_shortcut_vbs():
            print("[OK] Auto-start enabled. Sift will start automatically when Windows starts.")
            print("     To disable: python src\\main.py --disable-startup")
        else:
            print("[ERROR] Failed to enable auto-start.")
        return 0
    
    if args.disable_startup:
        if remove_startup_shortcut():
            print("[OK] Auto-start disabled. Sift will no longer start automatically.")
        else:
            print("[ERROR] Failed to disable auto-start.")
        return 0
    
    if args.startup_status:
        if is_startup_enabled():
            print("[ENABLED] Auto-start is enabled")
            print("          Sift will start automatically when Windows starts.")
        else:
            print("[DISABLED] Auto-start is disabled")
            print("           To enable: python src\\main.py --enable-startup")
        return 0
    
    # Create application
    app = Sift(config, project_root)
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("\nReceived interrupt signal, shutting down...")
        app.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Single file mode
    if args.file:
        logger.info(f"Processing single file: {args.file}")
        success = app.process_single(args.file)
        return 0 if success else 1
    
    # Scan only mode
    if args.scan_only:
        logger.info("Running in scan-only mode...")
        
        if not app._wait_for_lmstudio():
            return 1
        
        # Create watcher just for scanning (with database for crash recovery)
        app.watcher = DocumentWatcher(config, app._process_file, database=app.database)
        count = app.watcher.scan_existing()
        
        if count > 0:
            # Start watcher temporarily to process queue
            app.watcher.start()
            
            # Wait for queue to be processed
            while app.watcher.queue_size > 0:
                time.sleep(1)
            
            # Give time for last file to process
            time.sleep(3)
            
            app.watcher.stop()
        
        logger.info("Scan complete")
        return 0
    
    # Normal mode - start watching
    try:
        app.start(
            scan_existing=not args.no_scan,
            background=args.background
        )
        return 0
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

