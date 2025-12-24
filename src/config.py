"""
Configuration management for Sift.

Handles loading, validation, and access to configuration settings from YAML files.
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import yaml

logger = logging.getLogger(__name__)


@dataclass
class FoldersConfig:
    """Folder path configuration."""
    watch_path: Path
    base_path: Path
    temp_path: Path

    @classmethod
    def from_dict(cls, data: Dict[str, Any], username: str) -> 'FoldersConfig':
        """Create from dictionary, expanding {username} placeholders."""
        def expand_path(path_str: str) -> Path:
            expanded = path_str.replace("{username}", username)
            return Path(expanded)
        
        return cls(
            watch_path=expand_path(data.get('watch_path', '')),
            base_path=expand_path(data.get('base_path', '')),
            temp_path=expand_path(data.get('temp_path', ''))
        )


@dataclass
class ModelProfile:
    """Configuration for a specific model profile."""
    name: str
    model_identifier: str
    max_tokens: int
    temperature: float
    timeout_seconds: int
    prompt_style: str  # "simple", "moderate", "detailed"
    description: str = ""

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'ModelProfile':
        """Create from dictionary."""
        return cls(
            name=name,
            model_identifier=data.get('model_identifier', ''),
            max_tokens=data.get('max_tokens', 512),
            temperature=data.get('temperature', 0.1),
            timeout_seconds=data.get('timeout_seconds', 60),
            prompt_style=data.get('prompt_style', 'simple'),
            description=data.get('description', '')
        )


# Default model profiles
DEFAULT_PROFILES = {
    "fast": ModelProfile(
        name="fast",
        model_identifier="qwen/qwen3-1.7b",
        max_tokens=512,
        temperature=0.1,
        timeout_seconds=60,
        prompt_style="simple",
        description="Fastest - Qwen3 1.7B with simple prompts"
    ),
    "balanced": ModelProfile(
        name="balanced",
        model_identifier="qwen/qwen3-4b",
        max_tokens=2048,
        temperature=0.1,
        timeout_seconds=180,
        prompt_style="detailed",
        description="Balanced - Qwen3 4B with detailed prompts (original setup)"
    ),
    "accurate": ModelProfile(
        name="accurate",
        model_identifier="qwen/qwen2.5-7b-instruct",
        max_tokens=2048,
        temperature=0.1,
        timeout_seconds=180,
        prompt_style="detailed",
        description="Most accurate - Qwen2.5 7B with detailed prompts"
    )
}


@dataclass
class LLMConfig:
    """LMStudio API configuration with model profiles."""
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "lm-studio"
    active_profile: str = "fast"  # Which profile to use
    profiles: Dict[str, ModelProfile] = field(default_factory=lambda: DEFAULT_PROFILES.copy())
    
    # Legacy direct settings (used if no profile matches)
    model_identifier: str = "qwen/qwen3-1.7b"
    timeout_seconds: int = 60
    max_tokens: int = 512
    temperature: float = 0.1

    def get_active_profile(self) -> ModelProfile:
        """Get the currently active model profile."""
        if self.active_profile in self.profiles:
            return self.profiles[self.active_profile]
        # Fallback: create profile from legacy settings
        return ModelProfile(
            name="custom",
            model_identifier=self.model_identifier,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            timeout_seconds=self.timeout_seconds,
            prompt_style="moderate",
            description="Custom configuration"
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLMConfig':
        """Create from dictionary."""
        # Parse profiles if present
        profiles = DEFAULT_PROFILES.copy()
        profiles_data = data.get('profiles', {})
        for profile_name, profile_data in profiles_data.items():
            profiles[profile_name] = ModelProfile.from_dict(profile_name, profile_data)
        
        return cls(
            base_url=data.get('base_url', cls.base_url),
            api_key=data.get('api_key', cls.api_key),
            active_profile=data.get('active_profile', 'fast'),
            profiles=profiles,
            # Legacy settings for backwards compatibility
            model_identifier=data.get('model_identifier', 'qwen/qwen3-1.7b'),
            timeout_seconds=data.get('timeout_seconds', 60),
            max_tokens=data.get('max_tokens', 512),
            temperature=data.get('temperature', 0.1)
        )


@dataclass
class ProcessingConfig:
    """Document processing configuration."""
    supported_extensions: List[str] = field(default_factory=lambda: [
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
        ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"
    ])
    max_pages_to_analyze: int = 3
    image_dpi: int = 150
    max_image_dimension: int = 1024
    processing_delay_seconds: float = 2.0
    ocr_enabled: bool = True  # Enable OCR for scanned PDFs (requires Tesseract)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessingConfig':
        """Create from dictionary."""
        default_extensions = [
            ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
            ".csv", ".tsv", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"
        ]
        return cls(
            supported_extensions=data.get('supported_extensions', default_extensions),
            max_pages_to_analyze=data.get('max_pages_to_analyze', 3),
            image_dpi=data.get('image_dpi', 150),
            max_image_dimension=data.get('max_image_dimension', 1024),
            processing_delay_seconds=data.get('processing_delay_seconds', 2.0),
            ocr_enabled=data.get('ocr_enabled', True)
        )


@dataclass
class CategoryConfig:
    """Category configuration."""
    name: str
    subcategories: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CategoryConfig':
        """Create from dictionary."""
        return cls(
            name=data.get('name', ''),
            subcategories=data.get('subcategories', []),
            keywords=data.get('keywords', [])
        )


@dataclass
class BehaviorConfig:
    """Behavior settings configuration."""
    create_missing_folders: bool = True
    preserve_original_filename: bool = True
    add_date_prefix: bool = False
    duplicate_handling: str = "rename"  # rename, skip, overwrite
    move_or_copy: str = "move"  # move, copy
    enable_subcategory_classification: bool = True
    confidence_threshold: float = 0.7
    manual_review_folder: str = "Needs_Review"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BehaviorConfig':
        """Create from dictionary."""
        return cls(
            create_missing_folders=data.get('create_missing_folders', True),
            preserve_original_filename=data.get('preserve_original_filename', True),
            add_date_prefix=data.get('add_date_prefix', False),
            duplicate_handling=data.get('duplicate_handling', 'rename'),
            move_or_copy=data.get('move_or_copy', 'move'),
            enable_subcategory_classification=data.get('enable_subcategory_classification', True),
            confidence_threshold=data.get('confidence_threshold', 0.7),
            manual_review_folder=data.get('manual_review_folder', 'Needs_Review')
        )


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    log_file: str = "logs/sift.log"
    max_log_size_mb: int = 10
    backup_count: int = 5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoggingConfig':
        """Create from dictionary."""
        return cls(
            level=data.get('level', 'INFO'),
            log_file=data.get('log_file', 'logs/sift.log'),
            max_log_size_mb=data.get('max_log_size_mb', 10),
            backup_count=data.get('backup_count', 5)
        )


@dataclass
class DashboardConfig:
    """Dashboard configuration settings."""
    enabled: bool = True
    port: int = 5000
    auto_open_browser: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DashboardConfig':
        """Create from dictionary."""
        return cls(
            enabled=data.get('enabled', True),
            port=data.get('port', 5000),
            auto_open_browser=data.get('auto_open_browser', True)
        )


@dataclass
class AdvancedConfig:
    """Advanced configuration settings."""
    retry_attempts: int = 3
    retry_delay_seconds: float = 5.0
    concurrent_processing: bool = False
    startup_scan: bool = True
    custom_rules: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AdvancedConfig':
        """Create from dictionary."""
        return cls(
            retry_attempts=data.get('retry_attempts', 3),
            retry_delay_seconds=data.get('retry_delay_seconds', 5.0),
            concurrent_processing=data.get('concurrent_processing', False),
            startup_scan=data.get('startup_scan', True),
            custom_rules=data.get('custom_rules', [])
        )


@dataclass
class Config:
    """Main configuration class holding all settings."""
    folders: FoldersConfig
    llm: LLMConfig
    processing: ProcessingConfig
    categories: List[CategoryConfig]
    behavior: BehaviorConfig
    logging: LoggingConfig
    dashboard: DashboardConfig
    advanced: AdvancedConfig

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> 'Config':
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to configuration file. If None, uses default location.
            
        Returns:
            Config object with all settings loaded.
        """
        if config_path is None:
            # Default to config/settings.yaml relative to project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "settings.yaml"
        
        config_path = Path(config_path)
        
        if not config_path.exists():
            logger.warning(f"Configuration file not found at {config_path}, using defaults")
            return cls._create_default()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            return cls._from_dict(data)
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise ConfigurationError(f"Failed to load configuration from {config_path}: {e}")

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create Config from dictionary."""
        username = os.environ.get('USERNAME', os.environ.get('USER', 'User'))
        
        folders_data = data.get('folders', {})
        llm_data = data.get('llm', {})
        processing_data = data.get('processing', {})
        categories_data = data.get('categories', [])
        behavior_data = data.get('behavior', {})
        logging_data = data.get('logging', {})
        dashboard_data = data.get('dashboard', {})
        advanced_data = data.get('advanced', {})
        
        # Parse categories
        categories = [CategoryConfig.from_dict(cat) for cat in categories_data]
        
        # Ensure Miscellaneous category exists
        if not any(cat.name == "Miscellaneous" for cat in categories):
            categories.append(CategoryConfig(name="Miscellaneous", subcategories=[], keywords=[]))
        
        return cls(
            folders=FoldersConfig.from_dict(folders_data, username),
            llm=LLMConfig.from_dict(llm_data),
            processing=ProcessingConfig.from_dict(processing_data),
            categories=categories,
            behavior=BehaviorConfig.from_dict(behavior_data),
            logging=LoggingConfig.from_dict(logging_data),
            dashboard=DashboardConfig.from_dict(dashboard_data),
            advanced=AdvancedConfig.from_dict(advanced_data)
        )

    @classmethod
    def _create_default(cls) -> 'Config':
        """Create default configuration."""
        username = os.environ.get('USERNAME', os.environ.get('USER', 'User'))
        base_path = Path.home() / "Documents" / "Sift"
        
        return cls(
            folders=FoldersConfig(
                watch_path=base_path / "Inbox",
                base_path=base_path,
                temp_path=base_path / ".temp"
            ),
            llm=LLMConfig(),
            processing=ProcessingConfig(),
            categories=cls._default_categories(),
            behavior=BehaviorConfig(),
            logging=LoggingConfig(),
            dashboard=DashboardConfig(),
            advanced=AdvancedConfig()
        )

    @staticmethod
    def _default_categories() -> List[CategoryConfig]:
        """Return default category configurations."""
        return [
            CategoryConfig(
                name="Financial",
                subcategories=["Tax_Documents", "Bank_Statements", "Invoices", "Investment", "Payroll"],
                keywords=["tax", "W2", "1099", "bank", "statement", "invoice", "receipt", "payment"]
            ),
            CategoryConfig(
                name="Medical",
                subcategories=["Insurance", "Records", "Prescriptions", "Bills"],
                keywords=["medical", "health", "doctor", "hospital", "prescription", "diagnosis"]
            ),
            CategoryConfig(
                name="Legal",
                subcategories=["Contracts", "Agreements", "Correspondence", "Court"],
                keywords=["contract", "agreement", "legal", "attorney", "court", "lawsuit"]
            ),
            CategoryConfig(
                name="Government",
                subcategories=["ID_Documents", "Licenses", "Permits", "Correspondence"],
                keywords=["government", "dmv", "passport", "social security", "license", "permit"]
            ),
            CategoryConfig(
                name="Insurance",
                subcategories=["Auto", "Home", "Life", "Claims"],
                keywords=["insurance", "policy", "claim", "premium", "coverage"]
            ),
            CategoryConfig(
                name="Work",
                subcategories=["Reports", "Correspondence", "Projects", "HR"],
                keywords=["work", "employment", "project", "report", "memo", "meeting"]
            ),
            CategoryConfig(
                name="Education",
                subcategories=["Transcripts", "Certificates", "Applications"],
                keywords=["education", "school", "university", "degree", "transcript", "diploma"]
            ),
            CategoryConfig(
                name="Personal",
                subcategories=["Identity", "Certificates", "Correspondence"],
                keywords=["personal", "birth", "marriage", "certificate"]
            ),
            CategoryConfig(
                name="Receipts",
                subcategories=["Shopping", "Services", "Utilities"],
                keywords=["receipt", "purchase", "order", "confirmation"]
            ),
            CategoryConfig(
                name="Miscellaneous",
                subcategories=[],
                keywords=[]
            )
        ]

    def get_category_by_name(self, name: str) -> Optional[CategoryConfig]:
        """Get category configuration by name (case-insensitive)."""
        name_lower = name.lower()
        for category in self.categories:
            if category.name.lower() == name_lower:
                return category
        return None

    def get_all_category_names(self) -> List[str]:
        """Get list of all category names."""
        return [cat.name for cat in self.categories]

    def validate(self) -> List[str]:
        """
        Validate configuration and return list of issues.
        
        Returns:
            List of validation error messages. Empty if valid.
        """
        issues = []
        
        # Validate paths
        if not self.folders.base_path:
            issues.append("Base path is not configured")
        
        if not self.folders.watch_path:
            issues.append("Watch path is not configured")
        
        # Validate LLM settings
        if not self.llm.base_url:
            issues.append("LLM base URL is not configured")
        
        if self.llm.timeout_seconds < 10:
            issues.append("LLM timeout should be at least 10 seconds")
        
        # Validate processing settings
        if self.processing.max_pages_to_analyze < 1:
            issues.append("max_pages_to_analyze must be at least 1")
        
        if self.processing.image_dpi < 72:
            issues.append("image_dpi should be at least 72")
        
        # Validate behavior settings
        if self.behavior.duplicate_handling not in ["rename", "skip", "overwrite"]:
            issues.append(f"Invalid duplicate_handling: {self.behavior.duplicate_handling}")
        
        if self.behavior.move_or_copy not in ["move", "copy"]:
            issues.append(f"Invalid move_or_copy: {self.behavior.move_or_copy}")
        
        if not 0 <= self.behavior.confidence_threshold <= 1:
            issues.append("confidence_threshold must be between 0 and 1")
        
        return issues


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass


def setup_logging(config: Config, project_root: Path) -> None:
    """
    Setup logging based on configuration.
    
    Args:
        config: Configuration object
        project_root: Path to project root directory
    """
    from logging.handlers import RotatingFileHandler
    
    # Determine log file path
    log_file = project_root / config.logging.log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Get log level
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # Add rotating file handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=config.logging.max_log_size_mb * 1024 * 1024,
        backupCount=config.logging.backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)
    
    logger.info(f"Logging initialized. Level: {config.logging.level}, File: {log_file}")

