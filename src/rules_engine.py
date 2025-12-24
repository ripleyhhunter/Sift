"""
Custom Rules Engine for Sift.

Allows users to define classification rules that take precedence over
LLM classification. Rules can match on filename patterns, file extensions,
content keywords, or combinations thereof.
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ClassificationRule:
    """
    A single classification rule.
    
    Rules can match on:
    - filename_pattern: Regex pattern to match filename
    - extension: File extension(s) to match
    - content_contains: Keywords that must appear in content
    - content_pattern: Regex pattern to match in content
    
    All specified conditions must match (AND logic).
    """
    name: str
    category: str
    subcategory: str = ''
    priority: int = 100  # Higher = checked first
    enabled: bool = True
    
    # Matching conditions
    filename_pattern: Optional[str] = None
    extension: Optional[List[str]] = None
    content_contains: Optional[List[str]] = None
    content_pattern: Optional[str] = None
    
    # Optional overrides
    document_type: str = ''
    suggested_filename: str = ''
    
    # Compiled patterns (cached)
    _filename_regex: Optional[re.Pattern] = field(default=None, repr=False, compare=False)
    _content_regex: Optional[re.Pattern] = field(default=None, repr=False, compare=False)
    
    def __post_init__(self):
        """Compile regex patterns after initialization."""
        if self.filename_pattern:
            try:
                self._filename_regex = re.compile(self.filename_pattern, re.IGNORECASE)
            except re.error as e:
                logger.warning(f"Invalid filename pattern in rule '{self.name}': {e}")
                self._filename_regex = None
        
        if self.content_pattern:
            try:
                self._content_regex = re.compile(self.content_pattern, re.IGNORECASE)
            except re.error as e:
                logger.warning(f"Invalid content pattern in rule '{self.name}': {e}")
                self._content_regex = None
    
    def matches(self, filename: str, extension: str, content: str = '') -> bool:
        """
        Check if this rule matches the given document.
        
        Args:
            filename: The document filename (without path)
            extension: The file extension (with dot, e.g., '.pdf')
            content: The extracted document content (optional)
            
        Returns:
            True if all specified conditions match
        """
        if not self.enabled:
            return False
        
        # Check filename pattern
        if self.filename_pattern:
            if not self._filename_regex:
                return False
            if not self._filename_regex.search(filename):
                return False
        
        # Check extension
        if self.extension:
            ext_lower = extension.lower()
            # Normalize extensions (handle with/without dot)
            allowed = [e.lower() if e.startswith('.') else f'.{e.lower()}' for e in self.extension]
            if ext_lower not in allowed:
                return False
        
        # Check content contains (all keywords must be present)
        if self.content_contains:
            content_lower = content.lower()
            for keyword in self.content_contains:
                if keyword.lower() not in content_lower:
                    return False
        
        # Check content pattern
        if self.content_pattern:
            if not self._content_regex:
                return False
            if not self._content_regex.search(content):
                return False
        
        return True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClassificationRule':
        """Create a rule from a dictionary (e.g., from YAML config)."""
        return cls(
            name=data.get('name', 'Unnamed Rule'),
            category=data.get('category', 'Miscellaneous'),
            subcategory=data.get('subcategory', ''),
            priority=data.get('priority', 100),
            enabled=data.get('enabled', True),
            filename_pattern=data.get('filename_pattern'),
            extension=data.get('extension'),
            content_contains=data.get('content_contains'),
            content_pattern=data.get('content_pattern'),
            document_type=data.get('document_type', ''),
            suggested_filename=data.get('suggested_filename', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary for serialization."""
        return {
            'name': self.name,
            'category': self.category,
            'subcategory': self.subcategory,
            'priority': self.priority,
            'enabled': self.enabled,
            'filename_pattern': self.filename_pattern,
            'extension': self.extension,
            'content_contains': self.content_contains,
            'content_pattern': self.content_pattern,
            'document_type': self.document_type,
            'suggested_filename': self.suggested_filename
        }


class RulesEngine:
    """
    Manage and apply custom classification rules.
    
    Rules are checked in priority order (highest first).
    The first matching rule wins.
    """
    
    def __init__(self, rules: List[ClassificationRule] = None):
        """
        Initialize the rules engine.
        
        Args:
            rules: Optional list of rules to load
        """
        self._rules: List[ClassificationRule] = []
        
        if rules:
            for rule in rules:
                self.add_rule(rule)
    
    def add_rule(self, rule: ClassificationRule) -> None:
        """Add a rule and maintain priority ordering."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)  # Descending by priority
    
    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        original_count = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < original_count
    
    def get_rules(self) -> List[ClassificationRule]:
        """Get all rules, ordered by priority."""
        return list(self._rules)
    
    def get_rule(self, name: str) -> Optional[ClassificationRule]:
        """Get a specific rule by name."""
        for rule in self._rules:
            if rule.name == name:
                return rule
        return None
    
    def apply(
        self, 
        filename: str, 
        content: str = ''
    ) -> Optional[Dict[str, Any]]:
        """
        Apply rules to a document and return the classification if matched.
        
        Args:
            filename: Document filename
            content: Extracted document content
            
        Returns:
            Classification dict if a rule matched, None otherwise
        """
        if not self._rules:
            return None
        
        # Parse extension from filename
        path = Path(filename)
        extension = path.suffix
        
        for rule in self._rules:
            if rule.matches(filename, extension, content):
                logger.info(f"Rule '{rule.name}' matched document: {filename}")
                
                return {
                    'primary_category': rule.category,
                    'subcategory': rule.subcategory,
                    'document_type': rule.document_type or 'Custom Rule Match',
                    'suggested_filename': rule.suggested_filename,
                    'confidence': 1.0,  # Rules are authoritative
                    'reasoning': f"Matched rule: {rule.name}",
                    'content_summary': '',
                    'matched_rule': rule.name
                }
        
        return None
    
    @classmethod
    def from_config(cls, rules_data: List[Dict[str, Any]]) -> 'RulesEngine':
        """
        Create a RulesEngine from configuration data.
        
        Args:
            rules_data: List of rule dictionaries from config
            
        Returns:
            Configured RulesEngine instance
        """
        rules = [ClassificationRule.from_dict(r) for r in rules_data]
        return cls(rules)
    
    def to_config(self) -> List[Dict[str, Any]]:
        """Export rules to configuration format."""
        return [rule.to_dict() for rule in self._rules]


# Example rules that can be included by default
DEFAULT_RULES = [
    {
        'name': 'Bank Statements',
        'category': 'Financial',
        'subcategory': 'Bank_Statements',
        'priority': 90,
        'filename_pattern': r'(bank|statement|account)',
        'extension': ['.pdf'],
        'content_contains': ['account', 'balance']
    },
    {
        'name': 'Tax Forms W2',
        'category': 'Financial',
        'subcategory': 'Tax_Documents',
        'priority': 95,
        'filename_pattern': r'w[-_]?2',
        'extension': ['.pdf'],
        'document_type': 'W-2 Tax Form'
    },
    {
        'name': 'Invoices',
        'category': 'Financial',
        'subcategory': 'Invoices',
        'priority': 85,
        'filename_pattern': r'(invoice|inv[-_]?\d+)',
        'document_type': 'Invoice'
    },
    {
        'name': 'Resumes',
        'category': 'Career',
        'subcategory': 'Resumes',
        'priority': 80,
        'filename_pattern': r'(resume|cv|curriculum)',
        'document_type': 'Resume/CV'
    },
    {
        'name': 'Insurance Documents',
        'category': 'Financial',
        'subcategory': 'Insurance',
        'priority': 75,
        'content_contains': ['policy', 'insured', 'premium'],
        'document_type': 'Insurance Policy'
    }
]

