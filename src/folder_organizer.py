"""
Folder organization module for Smart Document Folder System.

Handles file movement/copying, folder creation, and filename management.
"""

import re
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Set

from .config import Config
from .llm_client import ClassificationResult
from .utils import (
    sanitize_filename,
    sanitize_folder_name,
    generate_unique_path,
    ensure_directory,
    get_date_prefix
)

logger = logging.getLogger(__name__)

# Filename patterns that indicate a useless/generic name
USELESS_FILENAME_PATTERNS: Set[str] = {
    'scan', 'scanned', 'document', 'doc', 'file', 'download', 'downloaded',
    'image', 'img', 'photo', 'picture', 'untitled', 'new', 'copy',
    'attachment', 'fwd', 'fw', 're', 'temp', 'tmp', 'unknown'
}

# Regex for filenames that are just numbers/codes
NUMERIC_PATTERN = re.compile(r'^[\d_\-\.]+$')
RANDOM_PATTERN = re.compile(r'^[a-zA-Z0-9]{1,8}$')  # Very short random strings


class FolderOrganizer:
    """
    Organize files into category folders based on classification.
    
    Handles file operations, folder creation, and naming conventions.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the folder organizer.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.base_path = config.folders.base_path
        self.create_folders = config.behavior.create_missing_folders
        self.preserve_filename = config.behavior.preserve_original_filename
        self.add_date_prefix = config.behavior.add_date_prefix
        self.duplicate_handling = config.behavior.duplicate_handling
        self.move_or_copy = config.behavior.move_or_copy
        self.review_folder = config.behavior.manual_review_folder
    
    def organize_file(
        self,
        source_path: Path,
        classification: ClassificationResult,
        force_review: bool = False
    ) -> Optional[Path]:
        """
        Move/copy file to appropriate folder based on classification.
        
        Args:
            source_path: Path to source file
            classification: Classification result
            force_review: If True, move to review folder regardless of confidence
            
        Returns:
            New file path, or None if operation was skipped
        """
        # Determine target folder
        if force_review:
            target_folder = self.base_path / self.review_folder
        else:
            target_folder = self._get_target_folder(classification)
        
        # Create folder if needed
        if self.create_folders:
            self.create_folder_if_needed(target_folder)
        elif not target_folder.exists():
            logger.warning(f"Target folder doesn't exist and creation disabled: {target_folder}")
            target_folder = self.base_path / "Miscellaneous"
            self.create_folder_if_needed(target_folder)
        
        # Determine target filename (with smart renaming)
        target_filename = self._get_target_filename(
            source_path,
            classification
        )
        
        # Build full target path
        target_path = target_folder / target_filename
        
        # Handle duplicates
        target_path = self._handle_duplicate(target_path)
        
        if target_path is None:
            logger.info(f"Skipping duplicate file: {source_path.name}")
            return None
        
        # Perform file operation
        try:
            if self.move_or_copy == "move":
                shutil.move(str(source_path), str(target_path))
                logger.info(f"Moved: {source_path.name} -> {target_path}")
            else:
                shutil.copy2(str(source_path), str(target_path))
                logger.info(f"Copied: {source_path.name} -> {target_path}")
            
            # Log the operation
            self._log_operation(source_path, target_path, classification)
            
            return target_path
            
        except Exception as e:
            logger.error(f"Failed to move/copy file: {e}")
            raise FileOrganizationError(f"Failed to organize file: {e}")
    
    def _get_target_folder(self, classification: ClassificationResult) -> Path:
        """
        Get target folder path from classification.
        
        Args:
            classification: Classification result
            
        Returns:
            Path to target folder
        """
        # Sanitize folder names
        primary = sanitize_folder_name(classification.primary_category)
        target = self.base_path / primary
        
        if classification.subcategory:
            subcat = sanitize_folder_name(classification.subcategory)
            target = target / subcat
        
        return target
    
    def _is_filename_useful(self, filename_stem: str) -> bool:
        """
        Assess if a filename is useful/descriptive or generic/useless.
        
        Args:
            filename_stem: Filename without extension
            
        Returns:
            True if filename is useful, False if it should be replaced
        """
        stem = filename_stem.lower().strip()
        
        # Very short names are usually useless
        if len(stem) < 4:
            return False
        
        # Pure numbers are useless (e.g., "001", "123456")
        if NUMERIC_PATTERN.match(stem):
            return False
        
        # Check for common useless patterns
        # Split by common separators
        words = re.split(r'[\s_\-\.]+', stem)
        
        # If any word is a useless pattern and file is short, it's probably useless
        if len(words) <= 2:
            for word in words:
                if word in USELESS_FILENAME_PATTERNS:
                    return False
                # Pure numbers as the only meaningful part
                if word.isdigit():
                    continue
        
        # Check for IMG_XXXX, DSC_XXXX, SCAN_XXXX patterns
        if re.match(r'^(img|dsc|scan|doc|file|image|photo)[\s_\-]?\d+', stem):
            return False
        
        # If we have at least 2 meaningful words, it's probably useful
        meaningful_words = [w for w in words if len(w) > 2 and not w.isdigit() and w not in USELESS_FILENAME_PATTERNS]
        if len(meaningful_words) >= 2:
            return True
        
        # Single word but long and not a generic term - might be useful (e.g., company name)
        if len(meaningful_words) == 1 and len(meaningful_words[0]) > 6:
            return True
        
        # Default: if there's some content, keep it
        return len(stem) > 8
    
    def _generate_smart_filename(
        self,
        source_path: Path,
        classification: ClassificationResult
    ) -> str:
        """
        Generate a smart filename based on classification and document info.
        
        Args:
            source_path: Original file path
            classification: Classification result with document info
            
        Returns:
            A descriptive filename (without extension)
        """
        parts = []
        
        # Try to extract/use date
        extracted_date = classification.extracted_info.date if classification.extracted_info else ''
        if extracted_date and len(extracted_date) >= 4:
            # Clean up date format
            date_clean = re.sub(r'[^\d]', '', extracted_date)[:8]  # YYYYMMDD or YYYY
            if len(date_clean) >= 4:
                parts.append(date_clean[:4] if len(date_clean) == 4 else date_clean)
        
        # Add document type (cleaned up)
        if classification.document_type and classification.document_type != 'Unknown':
            doc_type = classification.document_type
            # Simplify document type
            doc_type = doc_type.replace(' ', '_').replace('-', '_')
            doc_type = re.sub(r'[^\w]', '', doc_type)
            if len(doc_type) > 30:
                doc_type = doc_type[:30]
            parts.append(doc_type)
        else:
            # Use subcategory as document type hint
            if classification.subcategory:
                parts.append(classification.subcategory.replace(' ', '_'))
            elif classification.primary_category != 'Miscellaneous':
                parts.append(classification.primary_category)
        
        # Add organization/entity if available
        org = classification.extracted_info.organization if classification.extracted_info else ''
        if org and len(org) > 2:
            org_clean = org.replace(' ', '_').replace('-', '_')
            org_clean = re.sub(r'[^\w]', '', org_clean)
            if len(org_clean) > 25:
                org_clean = org_clean[:25]
            if org_clean and org_clean.lower() not in [p.lower() for p in parts]:
                parts.append(org_clean)
        
        # Build filename
        if parts:
            smart_name = '_'.join(parts)
        else:
            # Fallback: use category and current date
            smart_name = f"{classification.primary_category}_{datetime.now().strftime('%Y%m%d')}"
        
        return smart_name
    
    def _get_target_filename(
        self,
        source_path: Path,
        classification: ClassificationResult
    ) -> str:
        """
        Generate target filename with smart renaming.
        
        Logic:
        1. If preserve_filename is True AND filename is useful → keep original
        2. If LLM provided a good suggested_name → use it
        3. If original filename is useless → generate smart name
        4. Add date prefix if configured
        
        Args:
            source_path: Original file path
            classification: Full classification result
            
        Returns:
            Target filename (with extension)
        """
        extension = source_path.suffix.lower()
        original_stem = source_path.stem
        suggested_name = classification.suggested_filename if classification else None
        
        # Assess original filename quality
        original_is_useful = self._is_filename_useful(original_stem)
        
        # Decide which name to use
        if self.preserve_filename and original_is_useful:
            # Keep original if it's useful and user wants to preserve
            base_name = original_stem
            logger.debug(f"Keeping original filename: {original_stem}")
        elif suggested_name and len(suggested_name) > 3:
            # Use LLM suggestion if available
            base_name = suggested_name
            logger.debug(f"Using LLM suggested filename: {suggested_name}")
        elif not original_is_useful:
            # Generate smart name for useless filenames
            base_name = self._generate_smart_filename(source_path, classification)
            logger.info(f"Generated smart filename: {original_stem} -> {base_name}")
        else:
            # Keep original
            base_name = original_stem
        
        # Sanitize the base name
        base_name = sanitize_filename(base_name)
        
        # Add date prefix if configured and not already present
        if self.add_date_prefix:
            date_prefix = get_date_prefix()
            # Check if already has a date-like prefix
            if not re.match(r'^\d{4}[-_]?\d{0,2}[-_]?\d{0,2}', base_name):
                base_name = f"{date_prefix}_{base_name}"
        
        # Ensure extension is present
        filename = f"{base_name}{extension}"
        
        return sanitize_filename(filename)
    
    def _handle_duplicate(self, target_path: Path) -> Optional[Path]:
        """
        Handle duplicate filename based on configuration.
        
        Args:
            target_path: Desired target path
            
        Returns:
            Final target path, or None if should skip
        """
        if not target_path.exists():
            return target_path
        
        if self.duplicate_handling == "skip":
            return None
        elif self.duplicate_handling == "overwrite":
            return target_path
        else:  # "rename" (default)
            return generate_unique_path(target_path)
    
    def create_folder_if_needed(self, folder_path: Path) -> None:
        """
        Create folder and parent folders if they don't exist.
        
        Args:
            folder_path: Path to folder to create
        """
        if not folder_path.exists():
            ensure_directory(folder_path)
            logger.debug(f"Created folder: {folder_path}")
    
    def create_category_structure(self) -> None:
        """
        Create essential folder structure only.
        
        This ONLY creates:
        - Base SmartFolder path
        - Inbox (watch folder)
        - Needs_Review folder
        - Temp folder
        
        Category folders are NOT created from config - they are either:
        - Already existing on disk (preserved)
        - Created dynamically when a document needs them
        
        This respects any manual folder renames/changes the user has made.
        """
        logger.info("Creating initial folder structure...")
        
        # Create base path
        ensure_directory(self.base_path)
        
        # Create Inbox (essential - where documents are dropped)
        inbox = self.config.folders.watch_path
        ensure_directory(inbox)
        
        # Create review folder (essential - for low-confidence items)
        ensure_directory(self.base_path / self.review_folder)
        
        # Create temp folder (essential - for processing)
        ensure_directory(self.config.folders.temp_path)
        
        # NOTE: We do NOT create category folders from config here.
        # The system will:
        # 1. Discover existing folders from disk
        # 2. Create new folders only when a document is classified into them
        # This preserves any manual folder changes the user has made.
        
        logger.info(f"Created folder structure at: {self.base_path}")
    
    def get_folder_stats(self) -> dict:
        """
        Get statistics about organized folders.
        
        Returns:
            Dictionary with folder statistics
        """
        stats = {
            "total_files": 0,
            "categories": {}
        }
        
        if not self.base_path.exists():
            return stats
        
        for item in self.base_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                if item.name.lower() == 'inbox':
                    continue
                
                cat_stats = {"files": 0, "subcategories": {}}
                
                for subitem in item.rglob('*'):
                    if subitem.is_file():
                        cat_stats["files"] += 1
                        stats["total_files"] += 1
                
                for subdir in item.iterdir():
                    if subdir.is_dir():
                        sub_count = sum(1 for f in subdir.rglob('*') if f.is_file())
                        cat_stats["subcategories"][subdir.name] = sub_count
                
                stats["categories"][item.name] = cat_stats
        
        return stats
    
    def _log_operation(
        self,
        source: Path,
        destination: Path,
        classification: ClassificationResult
    ) -> None:
        """
        Log file organization operation.
        
        Args:
            source: Source file path
            destination: Destination file path
            classification: Classification result
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "source": str(source),
            "destination": str(destination),
            "document_type": classification.document_type,
            "category": classification.primary_category,
            "subcategory": classification.subcategory,
            "confidence": classification.confidence,
            "reasoning": classification.reasoning
        }
        
        logger.debug(f"Operation logged: {log_entry}")


class FileOrganizationError(Exception):
    """Exception raised for file organization errors."""
    pass

