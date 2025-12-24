"""
Thumbnail generation module for Sift.

Generates preview thumbnails for documents to display in the dashboard.
Supports PDFs, images, and Office documents.
"""

import logging
import hashlib
import base64
from pathlib import Path
from typing import Optional, Tuple
from io import BytesIO

logger = logging.getLogger(__name__)

# Optional imports - gracefully degrade if not available
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.debug("PIL not available - thumbnail generation disabled")

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logger.debug("PyMuPDF not available - PDF thumbnails disabled")


class ThumbnailGenerator:
    """
    Generate preview thumbnails for documents.
    
    Thumbnails are cached to disk to avoid regeneration.
    """
    
    # Default thumbnail dimensions
    DEFAULT_SIZE = (200, 280)  # Roughly A4 aspect ratio
    ICON_SIZE = (48, 48)  # For small icons
    
    # Supported file types
    IMAGE_TYPES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
    PDF_TYPES = {'.pdf'}
    
    def __init__(self, cache_dir: Path):
        """
        Initialize the thumbnail generator.
        
        Args:
            cache_dir: Directory to store cached thumbnails
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._enabled = HAS_PIL
    
    @property
    def is_available(self) -> bool:
        """Check if thumbnail generation is available."""
        return self._enabled
    
    def get_thumbnail(
        self, 
        file_path: Path, 
        size: Tuple[int, int] = None
    ) -> Optional[str]:
        """
        Get a thumbnail for a file, generating if needed.
        
        Args:
            file_path: Path to the document
            size: Desired thumbnail size (width, height)
            
        Returns:
            Base64-encoded thumbnail image, or None if generation failed
        """
        if not self._enabled:
            return None
        
        if not file_path.exists():
            return None
        
        size = size or self.DEFAULT_SIZE
        
        # Check cache first
        cache_key = self._get_cache_key(file_path, size)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        # Generate thumbnail based on file type
        thumbnail = None
        suffix = file_path.suffix.lower()
        
        try:
            if suffix in self.IMAGE_TYPES:
                thumbnail = self._thumbnail_from_image(file_path, size)
            elif suffix in self.PDF_TYPES and HAS_PYMUPDF:
                thumbnail = self._thumbnail_from_pdf(file_path, size)
            else:
                # Return a placeholder or generic icon
                thumbnail = self._get_file_type_icon(suffix)
        except Exception as e:
            logger.debug(f"Thumbnail generation failed for {file_path.name}: {e}")
            return None
        
        # Cache the result
        if thumbnail:
            self._cache_thumbnail(cache_key, thumbnail)
        
        return thumbnail
    
    def _get_cache_key(self, file_path: Path, size: Tuple[int, int]) -> str:
        """Generate a unique cache key for a file+size combination."""
        # Include file path, size, and mtime in the hash
        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            mtime = 0
        
        key_data = f"{file_path}|{size[0]}x{size[1]}|{mtime}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached(self, cache_key: str) -> Optional[str]:
        """Retrieve a cached thumbnail."""
        cache_file = self.cache_dir / f"{cache_key}.b64"
        if cache_file.exists():
            try:
                return cache_file.read_text()
            except OSError:
                return None
        return None
    
    def _cache_thumbnail(self, cache_key: str, thumbnail: str) -> None:
        """Save a thumbnail to the cache."""
        cache_file = self.cache_dir / f"{cache_key}.b64"
        try:
            cache_file.write_text(thumbnail)
        except OSError as e:
            logger.debug(f"Failed to cache thumbnail: {e}")
    
    def _thumbnail_from_image(
        self, 
        file_path: Path, 
        size: Tuple[int, int]
    ) -> Optional[str]:
        """Generate thumbnail from an image file."""
        if not HAS_PIL:
            return None
        
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary (for PNG with alpha, etc.)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Create thumbnail (maintains aspect ratio)
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Save to buffer
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=85, optimize=True)
                buffer.seek(0)
                
                # Return as base64 data URL
                b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                return f"data:image/jpeg;base64,{b64}"
                
        except Exception as e:
            logger.debug(f"Image thumbnail failed: {e}")
            return None
    
    def _thumbnail_from_pdf(
        self, 
        file_path: Path, 
        size: Tuple[int, int]
    ) -> Optional[str]:
        """Generate thumbnail from first page of a PDF."""
        if not HAS_PYMUPDF or not HAS_PIL:
            return None
        
        try:
            # Open PDF and get first page
            doc = fitz.open(str(file_path))
            if len(doc) == 0:
                doc.close()
                return None
            
            page = doc[0]
            
            # Calculate zoom to get desired size
            # We'll render larger and then resize for better quality
            zoom = 2.0  # 2x for better quality
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            doc.close()
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            
            # Create thumbnail
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Save to buffer
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85, optimize=True)
            buffer.seek(0)
            
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/jpeg;base64,{b64}"
            
        except Exception as e:
            logger.debug(f"PDF thumbnail failed: {e}")
            return None
    
    def _get_file_type_icon(self, suffix: str) -> Optional[str]:
        """
        Get a simple icon/placeholder for unsupported file types.
        
        Returns a data URL for a simple colored placeholder.
        """
        if not HAS_PIL:
            return None
        
        # Color mapping for file types
        type_colors = {
            '.pdf': (220, 53, 69),      # Red
            '.doc': (0, 123, 255),      # Blue
            '.docx': (0, 123, 255),
            '.xls': (40, 167, 69),      # Green  
            '.xlsx': (40, 167, 69),
            '.ppt': (255, 193, 7),      # Yellow
            '.pptx': (255, 193, 7),
            '.txt': (108, 117, 125),    # Gray
            '.csv': (40, 167, 69),
        }
        
        color = type_colors.get(suffix, (108, 117, 125))  # Default gray
        
        try:
            # Create a simple colored rectangle with text
            img = Image.new('RGB', self.ICON_SIZE, color)
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/png;base64,{b64}"
            
        except Exception:
            return None
    
    def clear_cache(self, older_than_days: int = 30) -> int:
        """
        Clear old cached thumbnails.
        
        Args:
            older_than_days: Remove thumbnails older than this many days
            
        Returns:
            Number of files removed
        """
        import time
        
        cutoff = time.time() - (older_than_days * 24 * 60 * 60)
        removed = 0
        
        try:
            for cache_file in self.cache_dir.glob("*.b64"):
                try:
                    if cache_file.stat().st_mtime < cutoff:
                        cache_file.unlink()
                        removed += 1
                except OSError:
                    continue
        except OSError:
            pass
        
        if removed > 0:
            logger.info(f"Cleared {removed} old thumbnail cache files")
        
        return removed

