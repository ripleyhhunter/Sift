"""
LMStudio API client for Sift.

Interfaces with LMStudio's OpenAI-compatible API for document classification.
Supports both text-based (fast) and vision-based (for images) classification.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import requests

from .config import Config

logger = logging.getLogger(__name__)


# ============================================================================
# PROMPT TEMPLATES - Different prompts for different model sizes
# ============================================================================

# SIMPLE prompt for small models (< 2B parameters)
# Focus on CONTEXTUAL REASONING - what is this document FOR?
PROMPT_SIMPLE = """You classify documents by understanding what they're FOR.

THINK ABOUT THE DOCUMENT'S PURPOSE:
1. What ACTIVITY or AREA OF LIFE is this for?
2. Look at KEYWORDS in content and filename!

MATCH CONTENT TO CATEGORY:
- Insurance policy, coverage, premium, claim, indemnity → Insurance
- Tax, W2, 1099, bank statement, invoice → Financial
- Lease, contract, agreement, legal → Legal
- Running, workout, exercise, race, marathon, gym → Health_Fitness
- Wedding, bride, groom, first dance, reception → Personal/Wedding
- Electronics, circuits, ESP32, Arduino → Hobbies/Electronics
- Resume, CV, job application → Work/Resumes
- Medical, doctor, prescription, diagnosis → Medical
- Passport, license, permit, government → Government
- Receipt, purchase confirmation → Receipts
- Travel, flight, hotel, itinerary → Travel

KEY DISTINCTION:
- Insurance documents (policy, coverage, premium) → Insurance (NOT Health_Fitness!)
- Sports/fitness events (races, marathons) → Health_Fitness
- Life events (weddings, babies) → Personal
- Don't confuse them!

REQUIRED JSON:
{
  "category": "main folder",
  "subcategory": "DESCRIPTIVE name",
  "confidence": 0.0 to 1.0,
  "document_type": "what this document IS",
  "summary": "what it contains",
  "reasoning": "what ACTIVITY/AREA is this for?"
}"""

# MODERATE prompt for medium models (2-4B parameters)
# Focus on CONTEXTUAL REASONING - what is this document FOR?
PROMPT_MODERATE = """You classify documents by understanding their PURPOSE.

MATCH CONTENT TO CATEGORY:
- Insurance policy, coverage, premium, claim, indemnity, liability → Insurance
- Tax, W2, 1099, bank statement, invoice, payment → Financial
- Lease, rental, contract, legal agreement → Legal
- Medical, doctor, hospital, prescription, diagnosis → Medical
- Running, training plan, workout, exercise, race, marathon, gym → Health_Fitness
- Wedding, bride, groom, first dance, reception, ceremony → Personal/Wedding
- Electronics, circuits, datasheets, Arduino, ESP32 → Hobbies
- Resume, CV, job application → Work/Resumes
- Kitchen inventory, home items → Home
- Passport, license, permit, government → Government

CRITICAL DISTINCTIONS:
- Insurance documents (policy, premium, coverage) → Insurance (NOT Health_Fitness!)
- A "training plan" for a RACE/RUN → Health_Fitness (NOT wedding!)
- A "training program" for a JOB → Work
- Sports events (5K, marathon, race) → Health_Fitness
- Life events (wedding, baby shower) → Personal

EXISTING FOLDERS = USER CONTEXT:
- If Hobbies/Electronics exists → electronics docs go there
- Check existing folders first!

JSON FORMAT:
{
  "content_summary": "what this document contains",
  "document_type": "what this document IS",
  "primary_category": "category",
  "subcategory": "descriptive name",
  "confidence": 0.0-1.0,
  "reasoning": "what ACTIVITY is this for?"
}"""

# DETAILED prompt for larger models (4B+ parameters)
# Full instructions with examples and edge cases
PROMPT_DETAILED = """You are a document classification assistant. Your job is to READ and UNDERSTAND document content, then classify it appropriately.

MANDATORY FIRST STEP - CONTENT SUMMARY:
Before classifying, you MUST first write a brief summary of what the document actually contains. This forces you to read it carefully. Ask yourself: "What is this document about? What kind of information does it contain?"

COMMON MISTAKES TO AVOID:
- A "Personal Profile" with height/weight/clothing sizes is about FASHION or LIFESTYLE, NOT fitness
- A "Kitchen Inventory" or food list is about HOME/COOKING, NOT exercise
- A "Wardrobe" or clothing list is about FASHION/LIFESTYLE, NOT fitness  
- Body measurements for clothing purposes are NOT medical or fitness documents
- Lists of possessions (clothes, food, items) are INVENTORY documents, not fitness

AVAILABLE CATEGORIES (use these or create new ones):
- Financial: taxes, banking, investments, bills, invoices, receipts
- Medical: doctor visits, prescriptions, health insurance claims, medical records
- Legal: contracts, agreements, legal correspondence
- Government: IDs, licenses, permits
- Insurance: policies, claims, coverage
- Work: EMPLOYMENT-related only - job documents, professional projects, HR, resumes
- Education: academic transcripts, degrees, courses
- Personal: identity documents, personal records, fashion/style profiles, lifestyle documents
- Home: household inventory, kitchen/cooking, home maintenance, furniture, appliances
- Health_Fitness: ACTUAL exercise programs, gym memberships, workout plans, race registrations
- Hobbies: recreational activities, crafts, collections, cooking recipes
- Travel: trips, itineraries, bookings
- Receipts: purchase confirmations

CLASSIFICATION RULES:
1. Health_Fitness is ONLY for actual exercise/workout content (gym routines, running plans, etc.)
2. Personal measurements (height, weight) for CLOTHING purposes → Personal/Fashion or Lifestyle
3. Food/kitchen lists → Home/Kitchen or Hobbies/Cooking
4. Clothing/wardrobe lists → Personal/Fashion or Lifestyle/Wardrobe
5. If unsure, choose Personal or Home over Health_Fitness
6. Create new categories/subcategories when needed (Fashion, Lifestyle, Kitchen, Wardrobe, etc.)

JSON FORMAT - ALL FIELDS REQUIRED:
{
  "content_summary": "2-3 sentence description of what this document ACTUALLY contains",
  "document_type": "specific type (e.g., 'Wardrobe Inventory', 'Kitchen Inventory', 'Personal Style Profile')",
  "primary_category": "category name",
  "subcategory": "subcategory name (create new one if needed)",
  "confidence": 0.0 to 1.0,
  "reasoning": "explain WHY this category based on the content summary above",
  "suggested_filename": "descriptive name without extension",
  "extracted_info": {
    "date": "date if found",
    "organization": "organization if found"
  }
}"""

# Map prompt styles to templates
PROMPT_TEMPLATES = {
    "simple": PROMPT_SIMPLE,
    "moderate": PROMPT_MODERATE,
    "detailed": PROMPT_DETAILED
}

# Legacy alias
SYSTEM_PROMPT_TEXT = PROMPT_DETAILED



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
        
        # Get the appropriate prompt template
        self.system_prompt = PROMPT_TEMPLATES.get(self.prompt_style, PROMPT_MODERATE)
        
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
        self.system_prompt = PROMPT_TEMPLATES.get(self.prompt_style, PROMPT_MODERATE)
        
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
        sampled_text: str,
        filename: str,
        existing_folders: List[str],
        category_structure: Optional[Dict[str, List[str]]] = None
    ) -> str:
        """
        Build the user prompt based on the prompt style.
        
        Different prompts for different model sizes:
        - simple: Minimal instructions for small models
        - moderate: Balanced for medium models
        - detailed: Full instructions for large models
        
        ALL styles now receive the full folder structure so the LLM can
        see existing folders and subfolders, and create new ones if needed.
        """
        # Build category list - ALWAYS include full structure with subfolders
        if category_structure:
            category_lines = []
            for cat, subcats in sorted(category_structure.items()):
                if subcats:
                    subcat_str = ", ".join(sorted(subcats))  # Show ALL subcategories
                    category_lines.append(f"- {cat}/: [{subcat_str}]")
                else:
                    category_lines.append(f"- {cat}/")
            category_info = "\n".join(category_lines) if category_lines else "No folders yet - create as needed"
        elif existing_folders:
            category_info = "\n".join(f"- {f}/" for f in sorted(existing_folders))
        else:
            category_info = "No folders yet - create as needed (e.g., Financial, Insurance, Medical, Legal, Work, Personal)"
        
        if self.prompt_style == "simple":
            # Simple prompt with full folder structure visibility
            return f"""Classify this document into a folder.

FILENAME: {filename}

YOUR EXISTING FOLDER STRUCTURE:
{category_info}

CONTENT:
{sampled_text}

INSTRUCTIONS:
1. USE an existing folder/subfolder if it matches
2. Or CREATE a new folder if nothing fits
3. For insurance documents → Insurance/ folder
4. For tax/bank/financial → Financial/
5. For medical/health records → Medical/
6. For fitness/exercise → Health_Fitness/

Respond with JSON: {{"category": "folder", "subcategory": "subfolder", "confidence": 0.9, "document_type": "type", "summary": "brief", "reasoning": "why"}} /no_think"""
        
        elif self.prompt_style == "moderate":
            # Moderate prompt with clear folder structure
            return f"""Classify this document into an appropriate folder.

FILENAME: {filename}

YOUR EXISTING FOLDER STRUCTURE:
{category_info}

CONTENT:
---
{sampled_text}
---

RULES:
1. PREFER existing folders/subfolders when they match
2. CREATE new folders only if nothing fits
3. Insurance/policy/coverage → Insurance/ (NOT Health_Fitness!)
4. Tax/bank/financial → Financial/
5. Medical/doctor/prescription → Medical/
6. Running/workout/exercise → Health_Fitness/
7. Wedding/personal events → Personal/

Reply with JSON only. /no_think"""
        
        else:  # detailed
            # Full prompt for large models (4B+)
            return f"""READ the document content below and classify it into an appropriate folder.

STEP 1: First, write a "content_summary" describing what this document actually contains.
STEP 2: Then classify based on that summary using an EXISTING folder or creating a NEW one.

YOUR EXISTING FOLDER STRUCTURE:
{category_info}

RULES:
1. PREFER existing folders/subfolders when they match the document content
2. CREATE new folders/subfolders only if no existing folder fits
3. Insurance documents (policy, coverage, premium) → Insurance/ folder
4. Financial documents (tax, bank, invoice) → Financial/ folder
5. Medical documents (doctor, prescription) → Medical/ folder
6. Clothing/wardrobe/fashion → Personal/Fashion or create new subfolder
7. Kitchen/food inventory → Home/Kitchen
8. Health_Fitness is ONLY for actual workout/exercise content (NOT insurance!)

Filename (for reference): {filename}

DOCUMENT CONTENT - READ THIS CAREFULLY:
---
{sampled_text}
---

What does this document contain? Write content_summary first, then classify.
Respond with JSON only. /no_think"""
    
    def classify_document_text(
        self,
        text: str,
        filename: str,
        existing_folders: List[str],
        category_structure: Optional[Dict[str, List[str]]] = None
    ) -> ClassificationResult:
        """
        Classify a document based on its text content (fast mode).
        
        Args:
            text: Extracted text from the document
            filename: Original filename for context
            existing_folders: List of existing category folder names
            category_structure: Dict mapping category names to their subcategories
            
        Returns:
            Classification result
        """
        if not text:
            return ClassificationResult.create_fallback("No text provided")
        
        try:
            # Adjust text sample size based on prompt style
            # Smaller models work better with less text
            sample_sizes = {"simple": 1000, "moderate": 1500, "detailed": 2000}
            max_chars = sample_sizes.get(self.prompt_style, 1500)
            sampled_text = self._sample_text(text, max_chars=max_chars)
            
            # Build the user prompt based on prompt style
            user_prompt = self._build_user_prompt(
                sampled_text, filename, existing_folders, category_structure
            )

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
