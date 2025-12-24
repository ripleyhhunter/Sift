"""
LMStudio API client for Sift.

Interfaces with LMStudio's OpenAI-compatible API for document classification.
Supports both text-based (fast) and vision-based (for images) classification.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import requests

from .config import Config

logger = logging.getLogger(__name__)


# ============================================================================
# UNIFIED PROMPT SYSTEM
# ============================================================================
# 
# The prompt system is designed around a clear workflow:
# 1. DOCUMENT METADATA - File information (name, type, size, date)
# 2. FOLDER STRUCTURE - Complete hierarchy of existing folders
# 3. DOCUMENT CONTENT - Extracted text from the document
# 4. CLASSIFICATION TASK - Clear instructions for the LLM
#
# Model size adaptations only affect verbosity, not the structure.
# ============================================================================

# Base system prompt - used for moderate/detailed modes
# Defines the role, workflow, and output format
# NOTE: The actual folder structure is provided DYNAMICALLY in each user prompt
SYSTEM_PROMPT_BASE = """You are Sift, an intelligent document classification assistant. Your task is to analyze documents and classify them into the user's folder structure.

## YOUR WORKFLOW

1. **READ** the document metadata (filename, type, size)
2. **EXAMINE** the existing folder structure provided below - this shows EXACTLY what folders exist
3. **ANALYZE** the document content to understand what it is
4. **CLASSIFY** into the most appropriate EXISTING folder, or create a new one only if needed
5. **RESPOND** with structured JSON

## CLASSIFICATION PRINCIPLES

**ALWAYS prefer existing folders** - The user's folder structure is provided in each request. Use it!

**Create new folders sparingly** - Only when no existing folder fits.

**Match by PURPOSE, not keywords** - Classify based on what the document is FOR:
- Insurance policies/claims → Insurance folder (NOT Health_Fitness)
- Paystubs, tax forms, bank docs → Financial folder
- Doctor visits, prescriptions → Medical folder
- Workout plans, gym, races → Health_Fitness folder
- But always CHECK the user's actual folders first!

## REQUIRED OUTPUT FORMAT

You MUST respond with valid JSON only. No additional text before or after.

```json
{
  "category": "TopLevelFolder",
  "subcategory": "SubfolderName",
  "confidence": 0.85,
  "document_type": "Specific Document Type",
  "summary": "Brief description of document contents",
  "reasoning": "Why this classification is appropriate",
  "suggested_filename": "Descriptive_Filename",
  "extracted_date": "2024-01-15 or null",
  "extracted_org": "Organization name or null"
}
```

**Field Requirements:**
- `category`: MUST be a top-level folder (existing or new)
- `subcategory`: Subfolder within category (can be empty string if none needed)
- `confidence`: 0.0 to 1.0 (use 0.9+ for obvious matches, 0.7-0.8 for good matches, below 0.7 if uncertain)
- `document_type`: Specific type like "Insurance Policy", "Tax Return", "Resume"
- `summary`: 1-2 sentence description of what the document contains
- `reasoning`: Brief explanation of why you chose this classification
- `suggested_filename`: Descriptive name without extension (use underscores, no special chars)
- `extracted_date`: Any date found in document (YYYY-MM-DD format) or null
- `extracted_org`: Any organization/company name found or null"""

# Compact version for small models (<2B) - concise but complete
# Small models work better with direct instructions, not verbose explanations
# NOTE: No hardcoded categories - folder structure is provided dynamically per-document
SYSTEM_PROMPT_COMPACT = """Classify the document into a folder. Reply with JSON only.

RULES:
- Classify by document PURPOSE, not keyword matches
- Read what the document IS ABOUT, not just words it contains
- If your reasoning contradicts the content, RECONSIDER
- Use EXISTING folders from the list provided

JSON format:
{"category":"FOLDER","subcategory":"SUBFOLDER","confidence":0.9,"document_type":"TYPE","summary":"SUMMARY","reasoning":"REASON","suggested_filename":"FILENAME"}

Replace with actual values. Use "" for subcategory if none. 
suggested_filename: If original filename is non-descriptive (like a person's name), suggest a better one describing the document."""

# Map prompt styles to system prompts
SYSTEM_PROMPTS = {
    "simple": SYSTEM_PROMPT_COMPACT,
    "moderate": SYSTEM_PROMPT_BASE,
    "detailed": SYSTEM_PROMPT_BASE
}

# Legacy aliases for backwards compatibility
PROMPT_TEMPLATES = SYSTEM_PROMPTS
PROMPT_SIMPLE = SYSTEM_PROMPT_COMPACT
PROMPT_MODERATE = SYSTEM_PROMPT_BASE
PROMPT_DETAILED = SYSTEM_PROMPT_BASE
SYSTEM_PROMPT_TEXT = SYSTEM_PROMPT_BASE


# ============================================================================
# DOCUMENT METADATA HELPERS
# ============================================================================

@dataclass
class DocumentMetadata:
    """Structured metadata about a document."""
    filename: str
    extension: str
    file_type: str  # Human-readable type
    size_bytes: int
    size_human: str  # Human-readable size
    modified_date: str
    page_count: Optional[int] = None
    
    @classmethod
    def from_path(cls, file_path: Path) -> 'DocumentMetadata':
        """Extract metadata from a file path."""
        stat = file_path.stat()
        size = stat.st_size
        
        # Human-readable size
        if size < 1024:
            size_human = f"{size} bytes"
        elif size < 1024 * 1024:
            size_human = f"{size / 1024:.1f} KB"
        else:
            size_human = f"{size / (1024 * 1024):.1f} MB"
        
        # File type mapping
        ext = file_path.suffix.lower()
        type_map = {
            '.pdf': 'PDF Document',
            '.docx': 'Word Document',
            '.doc': 'Word Document (Legacy)',
            '.xlsx': 'Excel Spreadsheet',
            '.xls': 'Excel Spreadsheet (Legacy)',
            '.pptx': 'PowerPoint Presentation',
            '.ppt': 'PowerPoint Presentation (Legacy)',
            '.csv': 'CSV Data File',
            '.tsv': 'TSV Data File',
            '.txt': 'Text File',
            '.png': 'PNG Image',
            '.jpg': 'JPEG Image',
            '.jpeg': 'JPEG Image',
            '.gif': 'GIF Image',
            '.bmp': 'Bitmap Image',
            '.tiff': 'TIFF Image',
        }
        
        return cls(
            filename=file_path.name,
            extension=ext,
            file_type=type_map.get(ext, f'{ext.upper()} File'),
            size_bytes=size,
            size_human=size_human,
            modified_date=datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
            page_count=None  # Can be set later for PDFs
        )
    
    def to_prompt_block(self) -> str:
        """Format metadata as a prompt block."""
        lines = [
            "## DOCUMENT METADATA",
            f"- Filename: {self.filename}",
            f"- Type: {self.file_type}",
            f"- Size: {self.size_human}",
            f"- Modified: {self.modified_date}",
        ]
        if self.page_count:
            lines.append(f"- Pages: {self.page_count}")
        return "\n".join(lines)


def format_folder_structure(structure: Dict[str, List[str]], indent: str = "  ") -> str:
    """
    Format folder structure as a hierarchical tree for the prompt.
    
    Args:
        structure: Dict mapping category names to list of subcategories
        indent: Indentation string for subcategories
        
    Returns:
        Formatted string showing the folder tree
    """
    if not structure:
        return "No folders exist yet. You may create new categories as needed."
    
    lines = ["## EXISTING FOLDER STRUCTURE", "```"]
    lines.append("Sift/")
    
    for category in sorted(structure.keys()):
        subcats = structure[category]
        if subcats:
            lines.append(f"├── {category}/")
            for i, subcat in enumerate(sorted(subcats)):
                if i == len(subcats) - 1:
                    lines.append(f"│   └── {subcat}/")
                else:
                    lines.append(f"│   ├── {subcat}/")
        else:
            lines.append(f"├── {category}/")
    
    lines.append("└── [New folders can be created as needed]")
    lines.append("```")
    
    return "\n".join(lines)



@dataclass
class ExtractedInfo:
    """Information extracted from document."""
    date: str = ""
    organization: str = ""
    key_identifiers: List[str] = field(default_factory=list)


@dataclass
class ClassificationResult:
    """Result of document classification."""
    document_type: str
    primary_category: str
    subcategory: str
    confidence: float
    reasoning: str
    extracted_info: ExtractedInfo
    suggested_filename: str
    content_summary: str = ''  # LLM's understanding of the document
    raw_response: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClassificationResult':
        """Create from dictionary."""
        extracted = data.get('extracted_info', {})
        return cls(
            document_type=data.get('document_type', 'Unknown'),
            primary_category=data.get('primary_category', 'Miscellaneous'),
            subcategory=data.get('subcategory', ''),
            confidence=float(data.get('confidence', 0.5)),
            reasoning=data.get('reasoning', ''),
            extracted_info=ExtractedInfo(
                date=extracted.get('date', ''),
                organization=extracted.get('organization', ''),
                key_identifiers=extracted.get('key_identifiers', [])
            ),
            suggested_filename=data.get('suggested_filename', ''),
            content_summary=data.get('content_summary', ''),
            raw_response=data
        )
    
    @classmethod
    def create_fallback(cls, reason: str) -> 'ClassificationResult':
        """Create fallback result for error cases."""
        return cls(
            document_type="Unknown",
            primary_category="Miscellaneous",
            subcategory="",
            confidence=0.0,
            reasoning=f"Fallback classification: {reason}",
            extracted_info=ExtractedInfo(),
            suggested_filename="",
            raw_response=None
        )


class LMStudioClient:
    """
    Client for LMStudio's OpenAI-compatible API.
    
    Supports multiple model profiles with optimized prompts for each.
    """
    
    def __init__(self, config: Config):
        """Initialize the LMStudio client."""
        self.config = config
        self.base_url = config.llm.base_url.rstrip('/')
        self.api_key = config.llm.api_key
        
        # Get the active profile
        self.profile = config.llm.get_active_profile()
        self.model_identifier = self.profile.model_identifier
        self.timeout = self.profile.timeout_seconds
        self.max_tokens = self.profile.max_tokens
        self.temperature = self.profile.temperature
        self.prompt_style = self.profile.prompt_style
        
        # Get the appropriate system prompt for this model size
        self.system_prompt = SYSTEM_PROMPTS.get(self.prompt_style, SYSTEM_PROMPT_BASE)
        
        logger.info(f"LLM Profile: {self.profile.name}")
        logger.info(f"  Model: {self.model_identifier}")
        logger.info(f"  Prompt style: {self.prompt_style}")
        logger.info(f"  Max tokens: {self.max_tokens}")
        logger.info(f"  Timeout: {self.timeout}s")
        
        self._session = requests.Session()
        self._session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })
    
    def switch_profile(self, profile_name: str) -> bool:
        """
        Switch to a different model profile at runtime.
        
        Args:
            profile_name: Name of the profile to switch to (e.g., "fast", "balanced")
            
        Returns:
            True if successful, False otherwise
        """
        if profile_name not in self.config.llm.profiles:
            logger.error(f"Unknown profile: {profile_name}")
            return False
        
        new_profile = self.config.llm.profiles[profile_name]
        
        # Update all profile-related settings
        self.profile = new_profile
        self.model_identifier = new_profile.model_identifier
        self.timeout = new_profile.timeout_seconds
        self.max_tokens = new_profile.max_tokens
        self.temperature = new_profile.temperature
        self.prompt_style = new_profile.prompt_style
        self.system_prompt = SYSTEM_PROMPTS.get(self.prompt_style, SYSTEM_PROMPT_BASE)
        
        # Update config's active profile
        self.config.llm.active_profile = profile_name
        
        logger.info(f"Switched to profile: {profile_name}")
        logger.info(f"  Model: {self.model_identifier}")
        logger.info(f"  Prompt style: {self.prompt_style}")
        
        return True
    
    def get_available_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get all available profiles with their details."""
        profiles = {}
        for name, profile in self.config.llm.profiles.items():
            profiles[name] = {
                "name": name,
                "model": profile.model_identifier,
                "description": profile.description,
                "prompt_style": profile.prompt_style,
                "timeout": profile.timeout_seconds,
                "max_tokens": profile.max_tokens
            }
        return profiles
    
    def get_current_profile(self) -> Dict[str, Any]:
        """Get the current active profile details."""
        return {
            "name": self.profile.name,
            "model": self.model_identifier,
            "description": self.profile.description,
            "prompt_style": self.prompt_style,
            "timeout": self.timeout,
            "max_tokens": self.max_tokens
        }
    
    def is_available(self) -> bool:
        """Check if LMStudio is running and has a model loaded."""
        try:
            response = self._session.get(
                f"{self.base_url}/models",
                timeout=10
            )
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            models = data.get('data', [])
            return len(models) > 0
            
        except Exception as e:
            logger.warning(f"LMStudio not available: {e}")
            return False
    
    def get_loaded_models(self) -> List[str]:
        """Get list of loaded models from LMStudio."""
        try:
            response = self._session.get(f"{self.base_url}/models", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [m.get('id', '') for m in data.get('data', [])]
            return []
        except Exception:
            return []
    
    def _sample_text(self, text: str, max_chars: int = 2000) -> str:
        """
        Intelligently sample text for classification.
        
        Takes beginning (header/title info) + middle sample for context.
        This is more efficient than sending 6000 chars and avoids timeouts.
        
        Args:
            text: Full document text
            max_chars: Maximum characters to return
            
        Returns:
            Sampled text
        """
        text = text.strip()
        
        if len(text) <= max_chars:
            return text
        
        # Take first 1500 chars (headers, titles, key info usually at start)
        beginning = text[:1500]
        
        # Take a sample from the middle for additional context
        if len(text) > 3000:
            middle_start = len(text) // 2 - 250
            middle = text[middle_start:middle_start + 500]
            return f"{beginning}\n\n[...]\n\n{middle}"
        else:
            return beginning
    
    def _build_user_prompt(
        self,
        content: str,
        metadata: Optional[DocumentMetadata] = None,
        category_structure: Optional[Dict[str, List[str]]] = None,
        filename: str = "",
        existing_folders: Optional[List[str]] = None
    ) -> str:
        """
        Build a structured user prompt with document data.
        
        The prompt has three clear sections:
        1. DOCUMENT METADATA - File information
        2. FOLDER STRUCTURE - Existing organization
        3. DOCUMENT CONTENT - Extracted text
        
        Args:
            content: Extracted/sampled document content
            metadata: Structured document metadata (optional)
            category_structure: Dict mapping categories to subcategories
            filename: Fallback filename if no metadata provided
            existing_folders: Fallback folder list if no structure provided
            
        Returns:
            Formatted user prompt
        """
        # For small models, use compact format BUT include full folder structure
        if self.prompt_style == "simple":
            # Build folder tree - include subfolders so model knows what exists
            if category_structure:
                folder_lines = []
                for cat in sorted(category_structure.keys()):
                    subs = category_structure[cat]
                    if subs:
                        folder_lines.append(f"{cat}/: {', '.join(sorted(subs))}")
                    else:
                        folder_lines.append(f"{cat}/")
                folder_tree = "\n".join(folder_lines)
            elif existing_folders:
                folder_tree = "\n".join(f"{f}/" for f in sorted(existing_folders))
            else:
                folder_tree = "(no folders yet)"
            
            return f"""Document: {metadata.filename if metadata else filename}

FOLDERS (use existing when possible):
{folder_tree}

Content:
{content}

TASK: What is this document ABOUT? Classify by its purpose.
Reply with JSON only. /no_think"""
        
        # For moderate/detailed models, use full structured format
        sections = []
        
        # === SECTION 1: DOCUMENT METADATA ===
        if metadata:
            sections.append(metadata.to_prompt_block())
        elif filename:
            # Fallback: minimal metadata from filename
            sections.append(f"## DOCUMENT METADATA\n- Filename: {filename}")
        
        # === SECTION 2: FOLDER STRUCTURE ===
        if category_structure:
            sections.append(format_folder_structure(category_structure))
        elif existing_folders:
            # Fallback: simple list format
            folder_list = "\n".join(f"- {f}/" for f in sorted(existing_folders))
            sections.append(f"## EXISTING FOLDERS\n{folder_list}")
        else:
            sections.append("## EXISTING FOLDERS\nNo folders exist yet. Create categories as needed.")
        
        # === SECTION 3: DOCUMENT CONTENT ===
        sections.append(f"## DOCUMENT CONTENT\n```\n{content}\n```")
        
        # === SECTION 4: TASK (varies by model size) ===
        if self.prompt_style == "moderate":
            task = """## TASK
Classify this document into the most appropriate folder.

REMEMBER:
- Insurance policies → Insurance/
- Paystubs, tax docs → Financial/
- Medical records → Medical/
- Prefer existing folders when they match

Respond with JSON only. /no_think"""
        else:
            # Detailed task for larger models
            task = """## TASK
Carefully read the document content above and classify it appropriately.

STEPS:
1. Identify what type of document this is (invoice, policy, paystub, etc.)
2. Determine its PURPOSE - what area of life is this for?
3. Find the best matching existing folder, or create a new one
4. Generate a descriptive filename if the original is generic

CRITICAL REMINDERS:
- Insurance documents (policies, claims, coverage) → Insurance/
- Financial documents (tax, bank, invoices, paystubs) → Financial/
- Health_Fitness is ONLY for actual workout/exercise content
- Prefer existing folders and subcategories when they match

Respond with valid JSON only. No other text. /no_think"""
        
        sections.append(task)
        
        return "\n\n".join(sections)
    
    def classify_document_text(
        self,
        text: str,
        filename: str,
        existing_folders: List[str],
        category_structure: Optional[Dict[str, List[str]]] = None,
        file_path: Optional[Path] = None
    ) -> ClassificationResult:
        """
        Classify a document based on its text content.
        
        This is the main classification method. It:
        1. Extracts metadata from the file (if path provided)
        2. Samples the document content appropriately for the model size
        3. Builds a structured prompt with metadata, folder structure, and content
        4. Sends to the LLM and parses the response
        
        Args:
            text: Extracted text from the document
            filename: Original filename for context
            existing_folders: List of existing category folder names
            category_structure: Dict mapping category names to their subcategories
            file_path: Optional path to file for metadata extraction
            
        Returns:
            Classification result
        """
        if not text:
            return ClassificationResult.create_fallback("No text provided")
        
        try:
            # === STEP 1: Extract document metadata ===
            metadata = None
            if file_path and file_path.exists():
                try:
                    metadata = DocumentMetadata.from_path(file_path)
                    logger.debug(f"Extracted metadata: {metadata.file_type}, {metadata.size_human}")
                except Exception as e:
                    logger.debug(f"Could not extract metadata: {e}")
            
            # === STEP 2: Sample content based on model size ===
            # Smaller models work better with less text
            sample_sizes = {"simple": 1200, "moderate": 1800, "detailed": 2500}
            max_chars = sample_sizes.get(self.prompt_style, 1500)
            sampled_text = self._sample_text(text, max_chars=max_chars)
            
            # === STEP 3: Build structured prompt ===
            user_prompt = self._build_user_prompt(
                content=sampled_text,
                metadata=metadata,
                category_structure=category_structure,
                filename=filename,
                existing_folders=existing_folders
            )

            # === STEP 4: Prepare messages with system prompt ===
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Log what we're analyzing
            logger.info(f"Analyzing document: {filename}")
            logger.info(f"  Content preview: {sampled_text[:200].replace(chr(10), ' ')}...")
            
            # Make API request
            logger.debug(f"Requesting classification from model: {self.model_identifier}")
            response = self._session.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model_identifier,
                    "messages": messages,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                error_msg = f"LMStudio returned status {response.status_code}"
                logger.error(error_msg)
                return ClassificationResult.create_fallback(error_msg)
            
            return self._parse_response(response.json())
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timed out after {self.timeout}s")
            return ClassificationResult.create_fallback("Request timed out")
        except Exception as e:
            logger.error(f"Error classifying document: {e}")
            return ClassificationResult.create_fallback(str(e))
    
    def _parse_response(self, response: Dict[str, Any]) -> ClassificationResult:
        """Parse LLM response into ClassificationResult."""
        try:
            choices = response.get('choices', [])
            if not choices:
                return ClassificationResult.create_fallback("No choices in response")
            
            message = choices[0].get('message', {})
            content = message.get('content', '')
            
            # Debug: Log raw LLM response
            logger.info(f"LLM raw response: {content[:500]}...")
            
            if not content:
                return ClassificationResult.create_fallback("Empty response content")
            
            # Strip Qwen3's <think>...</think> tags
            content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
            
            # Fix common JSON malformations from small models
            # Pattern: "field":"value":"/" -> "field":"value"  (model confused folder paths)
            # Example: {"category":"Government":"/","sub... -> {"category":"Government","sub...
            content = re.sub(r'":"([^"]+)":"/",', r'":"\1",', content)
            
            # Try to parse JSON from response
            data = None
            try:
                # First try direct parse
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON object from the response
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group()
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        # JSON might be truncated - try to repair it
                        data = self._repair_truncated_json(json_str)
            
            if data is None:
                # Last resort: try to extract fields manually
                data = self._extract_fields_manually(content)
            
            if data is None:
                logger.warning(f"No JSON found in response: {content[:200]}")
                return ClassificationResult.create_fallback("No JSON found in response")
            
            # Normalize field names (handle both simple and detailed formats)
            # Simple format: category, summary
            # Detailed format: primary_category, content_summary
            if 'category' in data and 'primary_category' not in data:
                data['primary_category'] = data['category']
            if 'summary' in data and 'content_summary' not in data:
                data['content_summary'] = data['summary']
            
            # Handle extracted info fields (new unified format)
            if 'extracted_date' in data or 'extracted_org' in data:
                if 'extracted_info' not in data:
                    data['extracted_info'] = {}
                if 'extracted_date' in data and data['extracted_date']:
                    data['extracted_info']['date'] = data['extracted_date']
                if 'extracted_org' in data and data['extracted_org']:
                    data['extracted_info']['organization'] = data['extracted_org']
            
            # ============================================================
            # CRITICAL: Detect when LLM copied placeholder values literally
            # This happens when small models don't understand to replace them
            # ============================================================
            placeholder_values = {'folder', 'sub', 'type', 'brief', 'why', 'foldername', 'subfoldername', 
                                  'documenttype', 'one sentence description', '<folder name>', '<subfolder or empty>',
                                  'summary', 'reason', 'subfolder'}
            category_val = str(data.get('category', data.get('primary_category', ''))).lower().strip()
            doc_type_val = str(data.get('document_type', '')).lower().strip()
            summary_val = str(data.get('summary', data.get('content_summary', ''))).lower().strip()
            subcat_val = str(data.get('subcategory', '')).lower().strip()
            
            # Check for placeholder values in category, doc_type, or summary
            if category_val in placeholder_values or doc_type_val in placeholder_values or summary_val in placeholder_values:
                logger.warning(f"LLM copied placeholder values (category='{category_val}', doc_type='{doc_type_val}', summary='{summary_val}') - falling back to filename classification")
                return ClassificationResult.create_fallback("LLM copied placeholder values - needs filename fallback")
            
            # Special check: "Empty" as subcategory is invalid - should be empty string
            if subcat_val == 'empty':
                logger.info("Correcting subcategory 'Empty' to empty string")
                data['subcategory'] = ''
            
            # Validate and fill defaults
            if 'primary_category' not in data:
                data['primary_category'] = 'Miscellaneous'
            if 'confidence' not in data:
                data['confidence'] = 0.5
            if 'document_type' not in data:
                data['document_type'] = 'Document'
            if 'content_summary' not in data:
                data['content_summary'] = ''
            
            # Fix document_type if it's just a file format
            file_formats = {'pdf', 'docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt', 
                           'csv', 'txt', 'png', 'jpg', 'jpeg', 'gif'}
            if data['document_type'].lower().strip() in file_formats:
                # Model returned file format instead of semantic type
                # Try to infer from category/subcategory
                cat = data.get('primary_category', '')
                subcat = data.get('subcategory', '')
                if subcat:
                    data['document_type'] = f"{cat} - {subcat}".replace('_', ' ')
                elif cat:
                    data['document_type'] = f"{cat} Document".replace('_', ' ')
                else:
                    data['document_type'] = 'Document'
                logger.debug(f"Fixed document_type from file format to: {data['document_type']}")
            
            # Generate reasoning if missing or empty
            if not data.get('reasoning') or data.get('reasoning') == 'Not available':
                cat = data.get('primary_category', 'Unknown')
                subcat = data.get('subcategory', '')
                summary = data.get('content_summary', '')[:100]
                if summary:
                    data['reasoning'] = f"Classified as {cat}" + (f"/{subcat}" if subcat else "") + f" based on content: {summary}..."
                else:
                    data['reasoning'] = f"Classified as {cat}" + (f"/{subcat}" if subcat else "")
            
            try:
                data['confidence'] = max(0.0, min(1.0, float(data['confidence'])))
            except (ValueError, TypeError):
                data['confidence'] = 0.5
            
            # Log the classification decision in detail
            content_summary = data.get('content_summary', 'N/A') or 'N/A'
            category = data.get('primary_category', 'Unknown')
            subcategory = data.get('subcategory', '')
            confidence = data.get('confidence', 0)
            reasoning = data.get('reasoning', '') or 'Classified by LLM'
            doc_type = data.get('document_type', 'Unknown')
            
            logger.info(f"  LLM Analysis:")
            logger.info(f"    Summary: {content_summary}")
            logger.info(f"    Document Type: {doc_type}")
            logger.info(f"  Classification Decision:")
            if subcategory:
                logger.info(f"    Category: {category}/{subcategory}")
            else:
                logger.info(f"    Category: {category}")
            logger.info(f"    Confidence: {confidence:.0%}")
            logger.info(f"    Reasoning: {reasoning}")
            
            return ClassificationResult.from_dict(data)
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return ClassificationResult.create_fallback(f"Parse error: {e}")
    
    def _repair_truncated_json(self, json_str: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to repair truncated JSON by completing it.
        
        Common truncation patterns:
        - Missing closing braces
        - String cut off mid-value
        """
        try:
            # Try progressively more aggressive repairs
            repairs = [
                json_str + '"}',  # Missing closing quote and braces
                json_str + '"}',
                json_str + '"}',
                json_str + '"}}',
                json_str + '" }',
                json_str + '"}',
            ]
            
            # Also try adding just closing braces
            open_braces = json_str.count('{') - json_str.count('}')
            if open_braces > 0:
                # Check if we're in a string
                if json_str.rstrip().endswith('"') or json_str.count('"') % 2 == 0:
                    repairs.append(json_str + ('}' * open_braces))
                else:
                    repairs.append(json_str + '"' + ('}' * open_braces))
            
            for repair in repairs:
                try:
                    data = json.loads(repair)
                    if isinstance(data, dict) and 'primary_category' in data:
                        logger.info("Repaired truncated JSON successfully")
                        return data
                except:
                    continue
            
            return None
        except:
            return None
    
    def _extract_fields_manually(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extract classification fields from partially formatted response.
        
        Handles cases where JSON is badly truncated but fields are visible.
        """
        try:
            result = {}
            
            # Extract content_summary
            summary_match = re.search(r'"content_summary"\s*:\s*"([^"]*)', content)
            if summary_match:
                result['content_summary'] = summary_match.group(1)
            
            # Extract primary_category
            cat_match = re.search(r'"primary_category"\s*:\s*"([^"]*)"', content)
            if cat_match:
                result['primary_category'] = cat_match.group(1)
            
            # Extract subcategory
            subcat_match = re.search(r'"subcategory"\s*:\s*"([^"]*)"', content)
            if subcat_match:
                result['subcategory'] = subcat_match.group(1)
            
            # Extract confidence
            conf_match = re.search(r'"confidence"\s*:\s*([\d.]+)', content)
            if conf_match:
                result['confidence'] = float(conf_match.group(1))
            
            # Extract document_type
            doctype_match = re.search(r'"document_type"\s*:\s*"([^"]*)"', content)
            if doctype_match:
                result['document_type'] = doctype_match.group(1)
            
            # Extract reasoning
            reason_match = re.search(r'"reasoning"\s*:\s*"([^"]*)"', content)
            if reason_match:
                result['reasoning'] = reason_match.group(1)
            
            # Only return if we got at least primary_category
            if 'primary_category' in result:
                logger.info(f"Extracted fields manually: {list(result.keys())}")
                return result
            
            return None
        except Exception as e:
            logger.debug(f"Manual field extraction failed: {e}")
            return None
    
    def parse_search_query(self, query: str) -> Dict[str, Any]:
        """
        Parse a natural language search query with intelligent conceptual expansion.
        
        This doesn't just extract keywords - it thinks about what KIND of document
        would be relevant and what terms would appear in such a document.
        
        Args:
            query: Natural language query like "where's my autonomous ground vehicle stuff?"
            
        Returns:
            Dict with search_terms, expanded_terms, category_hint, document_type_hint
        """
        try:
            prompt = f"""You are helping find a document. The user's search query is:

"{query}"

Think step by step:
1. What is the user actually looking for? (intent)
2. What KIND of document would contain this information?
3. What category/folder would it likely be in?
4. What words and terms would APPEAR IN such a document, even if not in the query?

For example, if someone searches "autonomous ground vehicle project":
- They're looking for robotics/electronics project materials
- Such a document might contain: motors, wheels, sensors, Arduino, servo, battery, chassis, RC, robot, electronics, components, parts, gear, tools
- It would be in Hobbies or Electronics/Maker category
- It could be an inventory, parts list, or project notes

IMPORTANT: Generate terms that would be IN THE DOCUMENT, not just synonyms of the query.

Return JSON:
{{
  "intent": "brief description of what user is looking for",
  "search_terms": ["direct", "keywords", "from", "query"],
  "expanded_terms": ["terms", "that", "would", "appear", "in", "such", "a", "document"],
  "category_hint": "likely category or null",
  "document_type_hint": "inventory/list/manual/report/etc or null"
}}

Respond with JSON only. /no_think"""

            response = self._session.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model_identifier,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 512,
                    "temperature": 0.3  # Slightly higher for creative expansion
                },
                timeout=30
            )
            
            if response.status_code != 200:
                return self._fallback_query_parse(query)
            
            data = response.json()
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # Try to parse JSON
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    return self._fallback_query_parse(query)
            
            # Extract all search terms
            search_terms = result.get('search_terms', [])
            expanded_terms = result.get('expanded_terms', [])
            
            # Combine all terms, prioritizing direct terms
            all_terms = list(set(search_terms + expanded_terms))
            
            # Log the expansion for debugging
            logger.info(f"Search query expansion:")
            logger.info(f"  Original: {query}")
            logger.info(f"  Intent: {result.get('intent', 'N/A')}")
            logger.info(f"  Direct terms: {search_terms}")
            logger.info(f"  Expanded terms: {expanded_terms}")
            logger.info(f"  Category hint: {result.get('category_hint')}")
            
            return {
                'search_terms': all_terms,
                'direct_terms': search_terms,
                'expanded_terms': expanded_terms,
                'category_hint': result.get('category_hint'),
                'document_type_hint': result.get('document_type_hint'),
                'intent': result.get('intent', ''),
                'original_query': query
            }
            
        except Exception as e:
            logger.warning(f"LLM query parsing failed: {e}")
            return self._fallback_query_parse(query)
    
    def _fallback_query_parse(self, query: str) -> Dict[str, Any]:
        """Enhanced fallback for query parsing without LLM."""
        # Remove common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'my', 'your', 
                      'where', 'what', 'when', 'how', 'find', 'show', 'get', 'pull',
                      'up', 'me', 'i', 'need', 'want', 'looking', 'for', 'from',
                      'document', 'file', 'that', 'has', 'all', 'stuff', 'thing',
                      'about', 'with', 'have', 'had', 'does', 'did', 'can', 'could'}
        
        words = query.lower().replace('?', '').replace("'s", '').replace("'", '').split()
        search_terms = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Category detection with expanded keywords
        category_hint = None
        query_lower = query.lower()
        
        if any(w in query_lower for w in ['medical', 'doctor', 'health', 'dental', 'claim', 'eob', 'hospital', 'prescription']):
            category_hint = 'Medical'
        elif any(w in query_lower for w in ['tax', 'financial', 'invoice', 'receipt', 'bank', 'money', 'payment', 'w2', '1099']):
            category_hint = 'Financial'
        elif any(w in query_lower for w in ['resume', 'job', 'work', 'employment', 'salary', 'offer']):
            category_hint = 'Work'
        elif any(w in query_lower for w in ['legal', 'contract', 'agreement', 'lawyer', 'attorney']):
            category_hint = 'Legal'
        elif any(w in query_lower for w in ['hobby', 'project', 'maker', 'electronics', 'craft', 'diy', 'robot', 'arduino']):
            category_hint = 'Hobbies'
        elif any(w in query_lower for w in ['kitchen', 'food', 'recipe', 'cooking', 'home', 'house', 'furniture']):
            category_hint = 'Home'
        elif any(w in query_lower for w in ['travel', 'trip', 'flight', 'hotel', 'vacation', 'booking']):
            category_hint = 'Travel'
        elif any(w in query_lower for w in ['fitness', 'workout', 'exercise', 'gym', 'running', 'training']):
            category_hint = 'Health_Fitness'
        elif any(w in query_lower for w in ['clothes', 'clothing', 'wardrobe', 'fashion', 'outfit', 'style']):
            category_hint = 'Personal'
        
        return {
            'search_terms': search_terms,
            'direct_terms': search_terms,
            'expanded_terms': [],
            'category_hint': category_hint,
            'document_type_hint': None,
            'intent': '',
            'original_query': query
        }
    
    def close(self) -> None:
        """Close the client session."""
        self._session.close()


class LMStudioError(Exception):
    """Exception raised for LMStudio-related errors."""
    pass
