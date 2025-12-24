"""
Utility functions for Sift.

Contains helper functions for file operations, string manipulation,
and other common tasks.
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Optional, Callable, TypeVar, Any
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


# Invalid characters for Windows filenames
INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\x00-\x1f]'
INVALID_FOLDER_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

# Reserved Windows filenames
RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
}

# Temporary/incomplete file extensions to ignore
TEMP_EXTENSIONS = {'.tmp', '.temp', '.part', '.crdownload', '.partial', '.download'}


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize a filename for Windows compatibility.
    
    Args:
        filename: The original filename
        replacement: Character to replace invalid characters with
        
    Returns:
        Sanitized filename safe for Windows file system
    """
    if not filename:
        return "unnamed"
    
    # Remove invalid characters
    sanitized = re.sub(INVALID_FILENAME_CHARS, replacement, filename)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    
    # Handle reserved names
    name_without_ext = Path(sanitized).stem.upper()
    if name_without_ext in RESERVED_NAMES:
        sanitized = f"_{sanitized}"
    
    # Ensure not empty
    if not sanitized:
        sanitized = "unnamed"
    
    # Limit length (Windows MAX_PATH consideration)
    max_length = 200  # Leave room for path
    if len(sanitized) > max_length:
        stem = Path(sanitized).stem[:max_length - 10]
        suffix = Path(sanitized).suffix
        sanitized = f"{stem}{suffix}"
    
    return sanitized


def sanitize_folder_name(folder_name: str, replacement: str = "_") -> str:
    """
    Sanitize a folder name for Windows compatibility.
    
    Args:
        folder_name: The original folder name
        replacement: Character to replace invalid characters with
        
    Returns:
        Sanitized folder name safe for Windows file system
    """
    if not folder_name:
        return "Unnamed"
    
    # Remove invalid characters
    sanitized = re.sub(INVALID_FOLDER_CHARS, replacement, folder_name)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    
    # Handle reserved names
    if sanitized.upper() in RESERVED_NAMES:
        sanitized = f"_{sanitized}"
    
    # Ensure not empty
    if not sanitized:
        sanitized = "Unnamed"
    
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    
    return sanitized


def is_file_ready(file_path: Path, max_attempts: int = 30, delay: float = 1.0) -> bool:
    """
    Check if a file is ready for processing (not locked by another process).
    
    Args:
        file_path: Path to the file to check
        max_attempts: Maximum number of attempts
        delay: Delay between attempts in seconds
        
    Returns:
        True if file is ready, False otherwise
    """
    for attempt in range(max_attempts):
        try:
            # Try to open file with exclusive access
            with open(file_path, 'rb') as f:
                # Try to read a small portion to verify access
                f.read(1024)
            return True
        except (IOError, OSError, PermissionError) as e:
            if attempt < max_attempts - 1:
                logger.debug(f"File not ready (attempt {attempt + 1}/{max_attempts}): {file_path}")
                time.sleep(delay)
            else:
                logger.warning(f"File still locked after {max_attempts} attempts: {file_path}")
                return False
    return False


def is_temp_file(file_path: Path) -> bool:
    """
    Check if a file is a temporary or incomplete file.
    
    Args:
        file_path: Path to check
        
    Returns:
        True if file appears to be temporary/incomplete
    """
    name = file_path.name
    suffix = file_path.suffix.lower()
    
    # Check extension
    if suffix in TEMP_EXTENSIONS:
        return True
    
    # Check for hidden files (starting with . or ~)
    if name.startswith('.') or name.startswith('~'):
        return True
    
    # Check for Office temp files
    if name.startswith('~$'):
        return True
    
    return False


def is_supported_extension(file_path: Path, supported_extensions: list) -> bool:
    """
    Check if file has a supported extension.
    
    Args:
        file_path: Path to check
        supported_extensions: List of supported extensions (with dots)
        
    Returns:
        True if extension is supported
    """
    suffix = file_path.suffix.lower()
    return suffix in [ext.lower() for ext in supported_extensions]


def get_date_prefix() -> str:
    """
    Get current date as prefix string.
    
    Returns:
        Date string in YYYY-MM-DD format
    """
    return datetime.now().strftime("%Y-%m-%d")


def generate_unique_path(target_path: Path) -> Path:
    """
    Generate a unique file path by appending a counter if file exists.
    
    Args:
        target_path: Desired target path
        
    Returns:
        Unique path (original if doesn't exist, or with counter appended)
    """
    if not target_path.exists():
        return target_path
    
    counter = 1
    stem = target_path.stem
    suffix = target_path.suffix
    parent = target_path.parent
    
    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1
        
        # Safety limit
        if counter > 10000:
            raise RuntimeError(f"Could not generate unique path for {target_path}")


def ensure_directory(dir_path: Path) -> None:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        dir_path: Path to directory
    """
    dir_path.mkdir(parents=True, exist_ok=True)


def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in megabytes.
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in MB
    """
    try:
        return file_path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def retry_with_backoff(
    func: Callable[..., T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
) -> Callable[..., T]:
    """
    Decorator to retry a function with exponential backoff.
    
    Args:
        func: Function to wrap
        max_attempts: Maximum number of attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Tuple of exceptions to catch
        
    Returns:
        Wrapped function with retry logic
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_attempts} attempts failed: {e}")
        
        raise last_exception
    
    return wrapper


class Timer:
    """Simple context manager for timing operations."""
    
    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time: Optional[float] = None
        self.elapsed: Optional[float] = None
    
    def __enter__(self) -> 'Timer':
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args) -> None:
        self.elapsed = time.time() - self.start_time
        logger.debug(f"{self.name} completed in {self.elapsed:.2f}s")


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def normalize_path(path: Path) -> Path:
    """
    Normalize a path for consistent comparison.
    
    Args:
        path: Path to normalize
        
    Returns:
        Normalized absolute path
    """
    return Path(os.path.normpath(os.path.abspath(path)))


def paths_equal(path1: Path, path2: Path) -> bool:
    """
    Check if two paths point to the same location.
    
    Args:
        path1: First path
        path2: Second path
        
    Returns:
        True if paths are equivalent
    """
    return normalize_path(path1) == normalize_path(path2)

