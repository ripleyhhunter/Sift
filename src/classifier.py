"""
Classification module for Smart Document Folder System.

Orchestrates the classification process using text extraction (fast) for documents
and vision model (slower) for image files.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from rapidfuzz import fuzz, process

from .config import Config, CategoryConfig
from .document_processor import DocumentProcessor
from .llm_client import LMStudioClient, ClassificationResult

logger = logging.getLogger(__name__)


class DocumentClassifier:
    """
    Orchestrate document classification.
    
    Uses text extraction for PDFs, Word docs, Excel files (fast).
    Falls back to vision model for image files.
    """
    
    def __init__(
        self,
        config: Config,
        llm_client: LMStudioClient,
        processor: DocumentProcessor
    ):
        """Initialize the classifier."""
        self.config = config
        self.llm_client = llm_client
        self.processor = processor
        self.base_path = config.folders.base_path
        self.confidence_threshold = config.behavior.confidence_threshold
    
    def classify(self, file_path: Path) -> ClassificationResult:
        """
        Classify a document using text extraction (fast, text-only model).
        
        Args:
            file_path: Path to the document
            
        Returns:
            Classification result
        """
        logger.info(f"Classifying: {file_path.name}")
        
        # Get existing folders for context
        existing_folders = self.get_existing_folders()
        
        # For image files, create a basic classification based on filename
        if self.processor.is_image_file(file_path):
            logger.debug("Image file detected, classifying by filename")
            return self._classify_image_by_name(file_path, existing_folders)
        
        # Try text extraction (fast mode)
        text = None
        if self.processor.can_extract_text(file_path):
            logger.debug("Extracting text from document...")
            text = self.processor.extract_text(file_path)
        
        if text and len(text.strip()) > 20:
            logger.debug(f"Extracted {len(text)} chars, classifying with text model")
            result = self._classify_with_text(file_path, text, existing_folders)
            result = self._post_process_result(result)
            self._log_result(result)
            return result
        
        # If no text could be extracted, classify based on filename/extension
        logger.debug("No text extracted, classifying by filename")
        return self._classify_by_filename(file_path, existing_folders)
    
    def _classify_with_text(
        self,
        file_path: Path,
        text: str,
        existing_folders: List[str]
    ) -> ClassificationResult:
        """Classify using extracted text (fast)."""
        try:
            # Get full category structure with subcategories
            category_structure = self.get_category_structure()
            
            result = self.llm_client.classify_document_text(
                text=text,
                filename=file_path.name,
                existing_folders=existing_folders,
                category_structure=category_structure
            )
            
            # If LLM returned a fallback (timeout, error), try filename-based classification
            if result.confidence == 0.0 or result.primary_category == 'Miscellaneous':
                logger.info("LLM classification failed, falling back to filename-based classification")
                fallback = self._classify_by_filename(file_path, existing_folders)
                # Use fallback if it has better confidence
                if fallback.confidence > result.confidence:
                    return fallback
            
            return result
        except Exception as e:
            logger.error(f"Text classification failed: {e}")
            # Fall back to filename-based classification instead of giving up
            return self._classify_by_filename(file_path, existing_folders)
    
    def _classify_by_filename(
        self,
        file_path: Path,
        existing_folders: List[str]
    ) -> ClassificationResult:
        """Classify based on filename when text extraction fails or LLM times out."""
        filename = file_path.stem.lower()
        extension = file_path.suffix.lower()
        
        # Simple keyword matching for common document types
        # Confidence 0.75 ensures keyword matches bypass review (threshold is 0.7)
        if any(kw in filename for kw in ['invoice', 'bill', 'receipt', 'payment']):
            return ClassificationResult.from_dict({
                'document_type': 'Invoice/Receipt',
                'primary_category': 'Financial',
                'subcategory': 'Invoices',
                'confidence': 0.75,
                'reasoning': 'Classified by filename keywords (LLM fallback)',
                'suggested_filename': file_path.stem
            })
        elif any(kw in filename for kw in ['tax', 'w2', '1099', 'w-2', 'taxreturn', 'tax_return']):
            return ClassificationResult.from_dict({
                'document_type': 'Tax Document',
                'primary_category': 'Financial',
                'subcategory': 'Tax_Documents',
                'confidence': 0.75,
                'reasoning': 'Classified by filename keywords (LLM fallback)',
                'suggested_filename': file_path.stem
            })
        elif any(kw in filename for kw in ['contract', 'agreement', 'legal']):
            return ClassificationResult.from_dict({
                'document_type': 'Legal Document',
                'primary_category': 'Legal',
                'subcategory': 'Contracts',
                'confidence': 0.75,
                'reasoning': 'Classified by filename keywords (LLM fallback)',
                'suggested_filename': file_path.stem
            })
        elif any(kw in filename for kw in ['medical', 'health', 'doctor', 'hospital', 'eob', 'claim']):
            return ClassificationResult.from_dict({
                'document_type': 'Medical Document',
                'primary_category': 'Medical',
                'subcategory': 'Insurance',
                'confidence': 0.75,
                'reasoning': 'Classified by filename keywords (LLM fallback)',
                'suggested_filename': file_path.stem
            })
        elif any(kw in filename for kw in ['resume', 'cv', 'curriculum']):
            return ClassificationResult.from_dict({
                'document_type': 'Resume',
                'primary_category': 'Work',
                'subcategory': 'Resumes',
                'confidence': 0.75,
                'reasoning': 'Classified by filename keywords (LLM fallback)',
                'suggested_filename': file_path.stem
            })
        elif any(kw in filename for kw in ['bank', 'statement', 'account']):
            return ClassificationResult.from_dict({
                'document_type': 'Bank Statement',
                'primary_category': 'Financial',
                'subcategory': 'Bank_Statements',
                'confidence': 0.75,
                'reasoning': 'Classified by filename keywords (LLM fallback)',
                'suggested_filename': file_path.stem
            })
        elif any(kw in filename for kw in ['insurance', 'policy', 'coverage']):
            return ClassificationResult.from_dict({
                'document_type': 'Insurance Document',
                'primary_category': 'Insurance',
                'subcategory': '',
                'confidence': 0.75,
                'reasoning': 'Classified by filename keywords (LLM fallback)',
                'suggested_filename': file_path.stem
            })
        else:
            # Default to Miscellaneous with low confidence
            return ClassificationResult.from_dict({
                'document_type': 'Unknown Document',
                'primary_category': 'Miscellaneous',
                'subcategory': '',
                'confidence': 0.3,
                'reasoning': f'No keyword match, classified by extension: {extension}',
                'suggested_filename': file_path.stem
            })
    
    def _classify_image_by_name(
        self,
        file_path: Path,
        existing_folders: List[str]
    ) -> ClassificationResult:
        """Classify image files based on filename."""
        # For images, use the same filename logic but note it's an image
        result = self._classify_by_filename(file_path, existing_folders)
        if result.primary_category == 'Miscellaneous':
            result.document_type = 'Image File'
            result.reasoning = 'Image file - classified by filename'
        return result
    
    def _log_result(self, result: ClassificationResult) -> None:
        """Log final classification result."""
        # Just log a brief summary - detailed info already logged by LLM client
        subcat_info = f"/{result.subcategory}" if result.subcategory else ""
        logger.info(f"  Final destination: {result.primary_category}{subcat_info}")
    
    def get_existing_folders(self) -> List[str]:
        """
        Get list of existing category folders from disk ONLY.
        
        No fallback to config - returns only what actually exists.
        This respects user's folder structure.
        """
        excluded = {'inbox', '.temp', 'temp', 'needs_review'}
        folders = []
        
        if not self.base_path.exists():
            return []
        
        try:
            for item in self.base_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    if item.name.lower() in excluded:
                        continue
                    folders.append(item.name)
        except Exception as e:
            logger.warning(f"Error scanning folders: {e}")
            return []
        
        return sorted(folders)
    
    def get_category_structure(self) -> Dict[str, List[str]]:
        """
        Get full category structure by scanning the ACTUAL folder structure on disk.
        
        NO fallback to config - only shows what actually exists.
        This ensures the LLM sees the user's actual folder organization.
        
        Includes:
        - All top-level folders in SmartFolder (except Inbox, .temp, Needs_Review)
        - All subfolders within each category
        
        Returns:
            Dict mapping category names to list of subcategories
        """
        structure = {}
        
        # Folders to exclude from the category list
        excluded_folders = {'inbox', '.temp', 'temp', 'needs_review', '.ds_store'}
        
        if not self.base_path.exists():
            # No base path yet - return empty structure
            # The LLM will create folders as needed
            logger.debug("Base path doesn't exist yet - no categories to show")
            return structure
        
        # Scan actual disk structure
        try:
            for category_folder in self.base_path.iterdir():
                if not category_folder.is_dir():
                    continue
                if category_folder.name.lower() in excluded_folders:
                    continue
                if category_folder.name.startswith('.'):
                    continue
                
                # Get subcategories by scanning this folder
                subcats = []
                try:
                    for subfolder in category_folder.iterdir():
                        if subfolder.is_dir() and not subfolder.name.startswith('.'):
                            subcats.append(subfolder.name)
                except Exception as e:
                    logger.debug(f"Error scanning subcategories for {category_folder.name}: {e}")
                
                structure[category_folder.name] = sorted(subcats)
                
        except Exception as e:
            logger.warning(f"Error scanning folder structure: {e}")
            # Return empty - don't use config as fallback
        
        # Log what we found for debugging
        total_folders = len(structure)
        total_subfolders = sum(len(subs) for subs in structure.values())
        logger.debug(f"Found {total_folders} categories with {total_subfolders} total subcategories on disk")
        
        return structure
    
    def _post_process_result(self, result: ClassificationResult) -> ClassificationResult:
        """
        Post-process classification result to match existing folders.
        
        Uses ONLY actual disk folders - no hardcoded config categories.
        This respects any manual folder changes the user has made.
        """
        # First, fix common misclassifications based on document_type
        result = self._fix_common_misclassifications(result)
        
        # Get actual folder structure from disk ONLY
        disk_structure = self.get_category_structure()
        existing_categories = list(disk_structure.keys())
        
        # Match primary category against EXISTING folders only
        matched_category = self._match_category(result.primary_category, existing_categories)
        
        if matched_category:
            result.primary_category = matched_category
            
            # Match subcategory against existing subfolders for this category
            if self.config.behavior.enable_subcategory_classification and result.subcategory:
                existing_subcats = disk_structure.get(matched_category, [])
                
                if existing_subcats:
                    matched_subcat = self._match_category(result.subcategory, existing_subcats)
                    if matched_subcat:
                        result.subcategory = matched_subcat
                    # If no match but create_missing_folders is True, keep the LLM's suggestion
                    elif not self.config.behavior.create_missing_folders:
                        result.subcategory = ""
                # If no existing subcats, keep the LLM's suggestion (it will create the folder)
        else:
            # No match found in existing folders
            if self.config.behavior.create_missing_folders:
                # Keep the LLM's suggested category - it will be created on disk
                logger.info(f"New category will be created: {result.primary_category}")
            else:
                result.primary_category = "Miscellaneous"
                result.subcategory = ""
        
        return result
    
    def _fix_common_misclassifications(self, result: ClassificationResult) -> ClassificationResult:
        """
        Multi-layer safety net:
        0. Check for strong contextual signals (wedding, etc.) that override other classification
        1. Fix mismatched document_type vs subcategory (small model anchoring problem)
        2. Fix specific document types that should go to specific folders
        3. Rescue from Miscellaneous by inferring from content
        """
        doc_type_lower = (result.document_type or '').lower()
        summary_lower = (result.content_summary or '').lower()
        combined_text = f"{doc_type_lower} {summary_lower}"
        
        
        # LAYER 0: Fix subcategory if it doesn't match document_type at all
        # This catches the "anchoring" problem where small models copy example subcategories
        if result.subcategory and result.document_type:
            subcat_lower = result.subcategory.lower().replace('_', ' ')
            # Check if subcategory seems completely unrelated to document_type
            doc_type_words = set(doc_type_lower.split())
            subcat_words = set(subcat_lower.split())
            
            # If no overlap and document_type is specific, regenerate subcategory
            if not doc_type_words.intersection(subcat_words):
                # Check for obvious mismatches
                mismatches = [
                    ('lease', 'wedding'),
                    ('rental', 'wedding'),
                    ('contract', 'wedding'),
                    ('agreement', 'wedding'),
                    ('resume', 'wedding'),
                    ('tax', 'wedding'),
                ]
                for doc_word, wrong_subcat in mismatches:
                    if doc_word in doc_type_lower and wrong_subcat in subcat_lower:
                        new_subcat = self._generate_subcategory(result.document_type)
                        logger.info(f"Fixed mismatched subcategory: {result.subcategory} → {new_subcat} (document was: {result.document_type})")
                        result.subcategory = new_subcat
                        break
        
        # Get existing folders
        disk_structure = self.get_category_structure()
        
        # LAYER 1: Check if document topic matches an existing Hobbies subfolder
        # This uses the user's folder structure as context about their life
        if 'Hobbies' in disk_structure:
            hobbies_subfolders = disk_structure.get('Hobbies', [])
            
            # Check if document topic matches a hobby subfolder (fuzzy match)
            for subfolder in hobbies_subfolders:
                subfolder_words = set(subfolder.lower().replace('_', ' ').split())
                
                # Check if any word from the subfolder appears in document content
                # e.g., "Electronic Makers Stuff" - check if "electronic" is in the doc
                for word in subfolder_words:
                    if len(word) > 3 and word in combined_text:  # Skip short words
                        # Found a match! This topic is a hobby
                        if result.primary_category == 'Work':
                            logger.info(f"Topic matches Hobbies/{subfolder} (word: '{word}') → redirecting from Work")
                            result.primary_category = 'Hobbies'
                            result.subcategory = subfolder
                            return result
                        # Also fix if going to Hobbies but wrong subfolder
                        elif result.primary_category == 'Hobbies' and result.subcategory != subfolder:
                            # Check if our suggested subcategory is similar to existing one
                            suggested_lower = (result.subcategory or '').lower()
                            if word in suggested_lower or suggested_lower in subfolder.lower():
                                logger.info(f"Matching to existing Hobbies/{subfolder} instead of creating new")
                                result.subcategory = subfolder
                                return result
        
        # LAYER 2: Explicit mappings for user's common document types
        # These ensure consistency for frequently-used categories
        explicit_mappings = [
            (['resume', 'cv', 'curriculum vitae'], 'Work', 'Resumes'),
            (['tax return', 'w-2', 'w2', '1099', 'tax form'], 'Financial', 'Tax_Documents'),
            (['eob', 'explanation of benefits', 'medical claim'], 'Medical', 'Insurance'),
            (['bank statement', 'account statement'], 'Financial', 'Bank_Statements'),
            (['lease', 'rental agreement', 'lease renewal', 'tenancy'], 'Legal', 'Leases'),
        ]
        
        for keywords, correct_cat, correct_subcat in explicit_mappings:
            if any(kw in doc_type_lower for kw in keywords):
                if correct_cat in disk_structure:
                    if result.primary_category.lower() != correct_cat.lower():
                        logger.info(f"Explicit mapping: {result.primary_category} → {correct_cat}/{correct_subcat}")
                        result.primary_category = correct_cat
                        result.subcategory = correct_subcat
                        return result
        
        # LAYER 2: Rescue from Miscellaneous by inferring from content
        if result.primary_category.lower() == 'miscellaneous':
            area_keywords = {
                'Work': ['resume', 'cv', 'employment', 'job', 'career', 'professional'],
                'Financial': ['tax', 'bank', 'invoice', 'payment', 'financial', 'money', 'bill'],
                'Medical': ['medical', 'health', 'doctor', 'prescription', 'hospital', 'eob'],
                'Legal': ['contract', 'agreement', 'legal', 'attorney', 'court'],
                'Personal': ['wedding', 'baby', 'personal', 'family', 'birthday', 'anniversary', 
                            'moving', 'wardrobe', 'clothing', 'fashion', 'style'],
                'Home': ['kitchen', 'house', 'apartment', 'home', 'furniture', 'appliance', 'inventory'],
                'Travel': ['travel', 'trip', 'vacation', 'flight', 'hotel', 'itinerary'],
                'Education': ['school', 'university', 'course', 'degree', 'transcript'],
                'Hobbies': ['hobby', 'collection', 'craft', 'recipe', 'cooking'],
            }
            
            best_category = None
            best_score = 0
            
            for category, keywords in area_keywords.items():
                score = sum(1 for kw in keywords if kw in combined_text)
                if score > best_score:
                    best_score = score
                    best_category = category
            
            if best_category and best_score > 0:
                subcategory = self._generate_subcategory(result.document_type)
                logger.info(f"Rescued from Miscellaneous → {best_category}/{subcategory}")
                result.primary_category = best_category
                result.subcategory = subcategory
        
        return result
    
    def _generate_subcategory(self, document_type: str) -> str:
        """Generate a reasonable subcategory name from document type."""
        if not document_type:
            return ""
        
        # Clean up the document type to make it a valid folder name
        subcategory = document_type.strip()
        subcategory = subcategory.replace(' ', '_')
        subcategory = ''.join(c for c in subcategory if c.isalnum() or c == '_')
        subcategory = '_'.join(word.capitalize() for word in subcategory.split('_') if word)
        
        return subcategory if len(subcategory) <= 50 else subcategory[:50]
    
    def _match_category(self, query: str, candidates: List[str], threshold: int = 70) -> Optional[str]:
        """
        Smart match a category/subcategory name against candidates.
        
        Uses multiple strategies:
        1. Exact match (case-insensitive)
        2. Word overlap (e.g., "Electronics" matches "Electronic Makers Stuff")
        3. Substring match (e.g., "Electronic" in "Electronic_Makers_Stuff")
        4. Fuzzy match
        """
        if not query or not candidates:
            return None
        
        query_lower = query.lower().replace('_', ' ')
        query_words = set(query_lower.split())
        
        # Strategy 1: Exact match (case-insensitive)
        for candidate in candidates:
            if candidate.lower().replace('_', ' ') == query_lower:
                return candidate
        
        # Strategy 2: Word overlap - if main word matches
        # e.g., "Electronics" should match "Electronic Makers Stuff"
        for candidate in candidates:
            candidate_lower = candidate.lower().replace('_', ' ')
            candidate_words = set(candidate_lower.split())
            
            # Check if query word appears at start of any candidate word (stem matching)
            for qword in query_words:
                if len(qword) >= 4:  # Only for meaningful words
                    for cword in candidate_words:
                        # "electronic" matches "electronics" or vice versa
                        if qword.startswith(cword[:4]) or cword.startswith(qword[:4]):
                            logger.debug(f"Word stem match: '{query}' → '{candidate}' (via {qword}/{cword})")
                            return candidate
        
        # Strategy 3: Substring match
        for candidate in candidates:
            candidate_lower = candidate.lower().replace('_', ' ')
            if query_lower in candidate_lower or candidate_lower in query_lower:
                logger.debug(f"Substring match: '{query}' → '{candidate}'")
                return candidate
        
        # Strategy 4: Fuzzy match (lowered threshold)
        result = process.extractOne(query, candidates, scorer=fuzz.ratio)
        
        if result and result[1] >= threshold:
            logger.debug(f"Fuzzy match: '{query}' → '{result[0]}' ({result[1]}%)")
            return result[0]
        
        return None
    
    def get_target_folder(self, result: ClassificationResult) -> Path:
        """Get the target folder path for a classification result."""
        target = self.base_path / result.primary_category
        
        if result.subcategory:
            target = target / result.subcategory
        
        return target
    
    def should_review(self, result: ClassificationResult) -> bool:
        """Check if classification result should be sent for manual review."""
        return result.confidence < self.confidence_threshold


class ClassificationError(Exception):
    """Exception raised for classification errors."""
    pass
