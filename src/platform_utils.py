"""
Platform-specific utilities for Smart Document Folder System.

Provides cross-platform abstractions for Windows, macOS, and Linux.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Platform detection
IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')


def get_subprocess_flags() -> dict:
    """
    Get platform-appropriate subprocess flags.
    
    Returns:
        Dict of subprocess flags to use
    """
    if IS_WINDOWS:
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def open_file_or_folder(path: Path) -> bool:
    """
    Open a file or folder in the system's default application.
    
    Args:
        path: Path to open
        
    Returns:
        True if successful
    """
    try:
        if IS_WINDOWS:
            os.startfile(str(path))
        elif IS_MACOS:
            subprocess.run(['open', str(path)], check=True)
        else:  # Linux
            subprocess.run(['xdg-open', str(path)], check=True)
        return True
    except Exception as e:
        logger.error(f"Failed to open {path}: {e}")
        return False


def get_libreoffice_path() -> Optional[str]:
    """
    Find LibreOffice executable path.
    
    Returns:
        Path to soffice executable, or None if not found
    """
    if IS_WINDOWS:
        paths = [
            r'C:\Program Files\LibreOffice\program\soffice.exe',
            r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        ]
        for path in paths:
            if Path(path).exists():
                return path
    elif IS_MACOS:
        paths = [
            '/Applications/LibreOffice.app/Contents/MacOS/soffice',
            '/usr/local/bin/soffice',
            os.path.expanduser('~/Applications/LibreOffice.app/Contents/MacOS/soffice'),
        ]
        for path in paths:
            if Path(path).exists():
                return path
        # Try which
        try:
            result = subprocess.run(['which', 'soffice'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
    else:  # Linux
        try:
            result = subprocess.run(['which', 'soffice'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        # Common Linux paths
        paths = ['/usr/bin/soffice', '/usr/local/bin/soffice']
        for path in paths:
            if Path(path).exists():
                return path
    
    return None


def get_default_base_path() -> Path:
    """
    Get the default base path for SmartFolder data.
    
    Returns:
        Platform-appropriate documents path
    """
    if IS_WINDOWS:
        # Use OneDrive Documents if available, otherwise regular Documents
        onedrive = os.environ.get('OneDrive')
        if onedrive:
            return Path(onedrive) / 'Documents' / 'SmartFolder'
        return Path.home() / 'Documents' / 'SmartFolder'
    elif IS_MACOS:
        return Path.home() / 'Documents' / 'SmartFolder'
    else:  # Linux
        return Path.home() / 'Documents' / 'SmartFolder'


def get_startup_folder() -> Optional[Path]:
    """
    Get the OS-specific startup/autostart folder.
    
    Returns:
        Path to startup folder, or None if not applicable
    """
    if IS_WINDOWS:
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            return Path(appdata) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
    elif IS_MACOS:
        return Path.home() / 'Library' / 'LaunchAgents'
    else:  # Linux
        config_home = os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))
        return Path(config_home) / 'autostart'
    
    return None


def get_config_path() -> Path:
    """
    Get the platform-appropriate config directory.
    
    Returns:
        Path to config directory
    """
    if IS_WINDOWS:
        return Path(os.environ.get('APPDATA', Path.home())) / 'SmartFolder'
    elif IS_MACOS:
        return Path.home() / 'Library' / 'Application Support' / 'SmartFolder'
    else:  # Linux
        config_home = os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))
        return Path(config_home) / 'smartfolder'


def check_poppler_available() -> bool:
    """
    Check if Poppler is available for PDF processing.
    
    Returns:
        True if Poppler is installed and accessible
    """
    try:
        cmd = ['pdftoppm', '-v']
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            **get_subprocess_flags()
        )
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def show_notification(title: str, message: str, app_name: str = "Smart Folder") -> bool:
    """
    Show a system notification.
    
    Args:
        title: Notification title
        message: Notification body
        app_name: Application name
        
    Returns:
        True if notification was shown successfully
    """
    try:
        if IS_WINDOWS:
            try:
                from winotify import Notification
                toast = Notification(
                    app_id=app_name,
                    title=title,
                    msg=message,
                    duration="short"
                )
                toast.show()
                return True
            except ImportError:
                logger.debug("winotify not available")
                return False
        elif IS_MACOS:
            try:
                import pync
                pync.notify(message, title=title, appIcon='', sound='default')
                return True
            except ImportError:
                # Fallback to osascript
                try:
                    script = f'display notification "{message}" with title "{title}"'
                    subprocess.run(['osascript', '-e', script], check=True)
                    return True
                except Exception:
                    logger.debug("macOS notification failed")
                    return False
        else:  # Linux
            try:
                subprocess.run([
                    'notify-send',
                    '-a', app_name,
                    title,
                    message
                ], check=True)
                return True
            except Exception:
                logger.debug("notify-send not available")
                return False
    except Exception as e:
        logger.debug(f"Notification failed: {e}")
        return False

