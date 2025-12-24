"""
System tray icon module for Sift.

Provides:
- System tray icon with status indicator
- Right-click menu for control
- Cross-platform toast notifications
- Background operation support
"""

import os
import sys
import logging
import threading
import webbrowser
import subprocess
from pathlib import Path
from typing import Optional, Callable
from PIL import Image, ImageDraw

from .platform_utils import (
    IS_WINDOWS, IS_MACOS, IS_LINUX,
    open_file_or_folder, show_notification
)

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import pystray
    from pystray import MenuItem as Item
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    logger.warning("pystray not available - system tray disabled")

# Platform-specific notification support
NOTIFICATIONS_AVAILABLE = False
if IS_WINDOWS:
    try:
        from winotify import Notification, audio
        NOTIFICATIONS_AVAILABLE = True
    except ImportError:
        logger.debug("winotify not available")
elif IS_MACOS:
    try:
        import pync
        NOTIFICATIONS_AVAILABLE = True
    except ImportError:
        logger.debug("pync not available, will try osascript fallback")
        NOTIFICATIONS_AVAILABLE = True  # osascript fallback
else:
    # Linux - check for notify-send
    try:
        subprocess.run(['which', 'notify-send'], capture_output=True, check=True)
        NOTIFICATIONS_AVAILABLE = True
    except Exception:
        logger.debug("notify-send not available")


class TrayIcon:
    """
    System tray icon for Sift.
    
    Provides visual status indicator and control menu.
    """
    
    APP_NAME = "Sift"
    
    def __init__(
        self,
        on_exit: Optional[Callable] = None,
        dashboard_url: str = "http://localhost:5000",
        inbox_path: Optional[Path] = None
    ):
        """
        Initialize the system tray icon.
        
        Args:
            on_exit: Callback when user clicks Exit
            dashboard_url: URL to open for dashboard
            inbox_path: Path to inbox folder
        """
        self.on_exit_callback = on_exit
        self.dashboard_url = dashboard_url
        self.inbox_path = inbox_path
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self._paused = False
        self._status = "Starting..."
        self._processed_count = 0
        
        if not PYSTRAY_AVAILABLE:
            logger.warning("System tray not available")
    
    def start(self) -> None:
        """Start the system tray icon in a background thread."""
        if not PYSTRAY_AVAILABLE:
            return
        
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("System tray icon started")
    
    def stop(self) -> None:
        """Stop and remove the system tray icon."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception as e:
                logger.debug(f"Error stopping tray icon: {e}")
        logger.info("System tray icon stopped")
    
    def _run(self) -> None:
        """Run the system tray icon (blocking)."""
        try:
            # Create icon image
            image = self._create_icon_image("green")
            
            # Create menu
            menu = pystray.Menu(
                Item("Sift", None, enabled=False),
                Item("─────────────", None, enabled=False),
                Item("Open Dashboard", self._open_dashboard),
                Item("Open Inbox Folder", self._open_inbox),
                Item("─────────────", None, enabled=False),
                Item(
                    lambda item: "Resume Processing" if self._paused else "Pause Processing",
                    self._toggle_pause
                ),
                Item("─────────────", None, enabled=False),
                Item("Exit", self._exit)
            )
            
            # Create and run icon
            self._icon = pystray.Icon(
                "sift",
                image,
                "Sift - Running",
                menu
            )
            
            self._icon.run()
            
        except Exception as e:
            logger.error(f"Error running system tray: {e}")
    
    def _create_icon_image(self, color: str = "green") -> Image.Image:
        """
        Create a simple folder icon with status indicator.
        
        Args:
            color: Status color (green, yellow, red, gray)
        
        Returns:
            PIL Image for the icon
        """
        # Create a 64x64 image
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw folder shape
        folder_color = (70, 130, 180)  # Steel blue
        
        # Folder back
        draw.rectangle([4, 16, 60, 56], fill=folder_color)
        
        # Folder tab
        draw.polygon([4, 16, 4, 8, 24, 8, 28, 16], fill=folder_color)
        
        # Folder front (slightly lighter)
        front_color = (100, 160, 210)
        draw.rectangle([4, 24, 60, 56], fill=front_color)
        
        # Status indicator dot
        color_map = {
            "green": (52, 211, 153),   # Success green
            "yellow": (251, 191, 36),  # Warning yellow
            "red": (248, 113, 113),    # Error red
            "gray": (156, 163, 175)    # Offline gray
        }
        dot_color = color_map.get(color, color_map["gray"])
        
        # Draw status dot in corner
        draw.ellipse([44, 4, 60, 20], fill=dot_color)
        draw.ellipse([45, 5, 59, 19], fill=dot_color)  # Slight inner for depth
        
        return image
    
    def update_status(self, status: str, color: str = "green") -> None:
        """
        Update the tray icon status.
        
        Args:
            status: Status text for tooltip
            color: Icon color (green, yellow, red, gray)
        """
        self._status = status
        
        if self._icon:
            try:
                self._icon.icon = self._create_icon_image(color)
                self._icon.title = f"Sift - {status}"
            except Exception as e:
                logger.debug(f"Error updating tray icon: {e}")
    
    def notify(
        self,
        title: str,
        message: str,
        icon_type: str = "info"
    ) -> None:
        """
        Show a system notification (cross-platform).
        
        Args:
            title: Notification title
            message: Notification body
            icon_type: Type of icon (info, success, warning, error)
        """
        if not NOTIFICATIONS_AVAILABLE:
            logger.info(f"Notification: {title} - {message}")
            return
        
        # Use the cross-platform notification function
        if not show_notification(title, message, self.APP_NAME):
            logger.info(f"Notification: {title} - {message}")
    
    def notify_document_processed(
        self,
        filename: str,
        category: str,
        subcategory: str = ""
    ) -> None:
        """
        Show notification for a processed document.
        
        Args:
            filename: Name of processed file
            category: Category it was sorted into
            subcategory: Subcategory if any
        """
        self._processed_count += 1
        
        location = f"{category}/{subcategory}" if subcategory else category
        
        self.notify(
            title="Document Organized",
            message=f"'{filename}' → {location}",
            icon_type="success"
        )
    
    def notify_startup(self) -> None:
        """Show startup notification."""
        self.notify(
            title="Sift Started",
            message="Drop documents in the Inbox folder to organize them automatically.",
            icon_type="info"
        )
    
    def _open_dashboard(self, icon=None, item=None) -> None:
        """Open the dashboard in browser."""
        try:
            webbrowser.open(self.dashboard_url)
        except Exception as e:
            logger.error(f"Error opening dashboard: {e}")
    
    def _open_inbox(self, icon=None, item=None) -> None:
        """Open the inbox folder in the system file manager."""
        if self.inbox_path and self.inbox_path.exists():
            if not open_file_or_folder(self.inbox_path):
                logger.error(f"Could not open inbox folder")
    
    def _toggle_pause(self, icon=None, item=None) -> None:
        """Toggle pause state."""
        self._paused = not self._paused
        
        if self._paused:
            self.update_status("Paused", "yellow")
            self.notify("Sift Paused", "Document processing is paused.")
        else:
            self.update_status("Running", "green")
            self.notify("Sift Resumed", "Document processing resumed.")
    
    @property
    def is_paused(self) -> bool:
        """Check if processing is paused."""
        return self._paused
    
    def _exit(self, icon=None, item=None) -> None:
        """Handle exit from tray menu."""
        logger.info("Exit requested from tray menu")
        
        if self.on_exit_callback:
            self.on_exit_callback()
        
        self.stop()


def create_startup_shortcut() -> bool:
    """
    Create a startup entry (cross-platform).
    
    Returns:
        True if successful
    """
    if IS_WINDOWS:
        return _create_startup_windows()
    elif IS_MACOS:
        return _create_startup_macos()
    elif IS_LINUX:
        return _create_startup_linux()
    return False


def _create_startup_windows() -> bool:
    """Create startup shortcut on Windows."""
    try:
        try:
            import winshell
            from win32com.client import Dispatch
            
            startup_folder = winshell.startup()
            shortcut_path = os.path.join(startup_folder, "Sift.lnk")
            
            project_root = Path(__file__).parent.parent
            pythonw = project_root / "venv" / "Scripts" / "pythonw.exe"
            main_script = project_root / "src" / "main.py"
            icon_path = project_root / "assets" / "icon.ico"
            
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = str(pythonw)
            shortcut.Arguments = f'"{main_script}" --background'
            shortcut.WorkingDirectory = str(project_root)
            shortcut.Description = "Sift - AI Document Organization"
            
            if icon_path.exists():
                shortcut.IconLocation = str(icon_path)
            
            shortcut.save()
            logger.info(f"Created startup shortcut: {shortcut_path}")
            return True
            
        except ImportError:
            return create_startup_shortcut_vbs()
    except Exception as e:
        logger.error(f"Error creating startup shortcut: {e}")
        return False


def create_startup_shortcut_vbs() -> bool:
    """Create startup shortcut using VBScript (Windows fallback)."""
    try:
        startup_folder = Path(os.environ.get('APPDATA', '')) / \
            "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        
        project_root = Path(__file__).parent.parent
        vbs_path = startup_folder / "Sift.vbs"
        
        pythonw = project_root / "venv" / "Scripts" / "pythonw.exe"
        main_script = project_root / "src" / "main.py"
        
        vbs_content = f'''
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{project_root}"
WshShell.Run """{pythonw}"" ""{main_script}"" --background", 0, False
'''
        
        vbs_path.write_text(vbs_content.strip())
        logger.info(f"Created startup VBS script: {vbs_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating startup VBS: {e}")
        return False


def _create_startup_macos() -> bool:
    """Create LaunchAgent for macOS auto-start."""
    try:
        launch_agents = Path.home() / "Library" / "LaunchAgents"
        launch_agents.mkdir(parents=True, exist_ok=True)
        
        plist_path = launch_agents / "com.sift.app.plist"
        project_root = Path(__file__).parent.parent
        python_path = project_root / "venv" / "bin" / "python"
        main_script = project_root / "src" / "main.py"
        
        plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sift.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{main_script}</string>
        <string>--background</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{project_root}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
'''
        
        plist_path.write_text(plist_content)
        logger.info(f"Created LaunchAgent: {plist_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating LaunchAgent: {e}")
        return False


def _create_startup_linux() -> bool:
    """Create desktop entry for Linux auto-start."""
    try:
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        
        desktop_path = autostart_dir / "sift.desktop"
        project_root = Path(__file__).parent.parent
        
        desktop_content = f'''[Desktop Entry]
Type=Application
Name=Sift
Comment=AI-powered document organization
Exec={project_root}/run_background.sh
Path={project_root}
Terminal=false
StartupNotify=false
'''
        
        desktop_path.write_text(desktop_content)
        logger.info(f"Created autostart entry: {desktop_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating autostart entry: {e}")
        return False


def remove_startup_shortcut() -> bool:
    """
    Remove the startup entry (cross-platform).
    
    Returns:
        True if successful
    """
    try:
        if IS_WINDOWS:
            startup_folder = Path(os.environ.get('APPDATA', '')) / \
                "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            for filename in ["Sift.lnk", "Sift.vbs"]:
                path = startup_folder / filename
                if path.exists():
                    path.unlink()
                    logger.info(f"Removed startup file: {path}")
        elif IS_MACOS:
            plist_path = Path.home() / "Library" / "LaunchAgents" / "com.sift.app.plist"
            if plist_path.exists():
                plist_path.unlink()
                logger.info(f"Removed LaunchAgent: {plist_path}")
        elif IS_LINUX:
            desktop_path = Path.home() / ".config" / "autostart" / "sift.desktop"
            if desktop_path.exists():
                desktop_path.unlink()
                logger.info(f"Removed autostart entry: {desktop_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error removing startup shortcut: {e}")
        return False


def is_startup_enabled() -> bool:
    """
    Check if startup is enabled (cross-platform).
    
    Returns:
        True if startup is enabled
    """
    if IS_WINDOWS:
        startup_folder = Path(os.environ.get('APPDATA', '')) / \
            "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        return (startup_folder / "Sift.lnk").exists() or \
               (startup_folder / "Sift.vbs").exists()
    elif IS_MACOS:
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.sift.app.plist"
        return plist_path.exists()
    elif IS_LINUX:
        desktop_path = Path.home() / ".config" / "autostart" / "sift.desktop"
        return desktop_path.exists()
    return False

