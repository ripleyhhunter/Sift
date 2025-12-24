# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Sift** is an intelligent document organization system that automatically monitors a folder, analyzes documents using a local LLM (via LMStudio), and organizes them into appropriate subfolders based on content classification. All processing happens locally—no cloud services, no telemetry.

**Key Technologies**: Python 3.10+, Flask (web dashboard), Watchdog (filesystem monitoring), LMStudio (local LLM inference), SQLite (document history)

## Claude Operating Rules (IMPORTANT)

### Safety & Privacy
- **Do NOT read or summarize any real user documents** (inbox contents, PDFs, doc samples) unless explicitly asked.
- **Never access or print secrets**: `config/settings.yaml`, `.env*` files, keys, tokens, or user paths.
- **Avoid network commands** (`curl`, `wget`, `powershell Invoke-WebRequest`) unless explicitly approved.

### Workflow
- **For any big task**: Start in Plan Mode and produce a written plan + checklist before making edits.
- **Always cite evidence from the codebase** (file paths, functions/classes) for claims about behavior.
- **Prefer producing durable artifacts** in `/docs` rather than long chat output.

### Artifacts to Maintain
The following documentation files should be kept up-to-date:
- `docs/ARCHITECTURE.md` - System diagrams, components, data flow
- `docs/FEATURES.md` - All features with code locations
- `docs/USER_FLOWS.md` - Step-by-step user journeys
- `docs/PRODUCT_BRIEF.md` - Personas, jobs-to-be-done, value proposition
- `docs/GAPS_QOL.md` - Quality-of-life improvements with analysis
- `docs/LATENT_NEEDS.md` - Current, latent, trust, and power user needs
- `ROADMAP.md` - Phased development plan

### Definition of Done (for roadmap sessions)
When working on roadmap planning:
- Feature inventory is complete and mapped to user flows
- Roadmap items include: problem statement, target user, proposed solution, rationale, effort estimate (S/M/L), risks, and "how to verify"

## Development Commands

### Installation from Source

**Windows**:
```cmd
install.bat          # Creates venv, installs dependencies, verifies imports
run.bat              # Activate venv and run application
```

**macOS**:
```bash
chmod +x setup_macos.sh
./setup_macos.sh     # Installs Homebrew deps (poppler, libmagic), creates venv
./run_sift.sh        # Run application
```

### Running the Application

**Development Mode**:
```cmd
# Windows
run.bat                      # Normal console mode
run.bat --check              # Verify config and LMStudio connection
run.bat --verbose            # Enable debug logging
run.bat --scan-only          # Process existing files and exit
run.bat --file "path.pdf"    # Process single file

# macOS
./run_sift.sh [options]      # Same options as Windows
./run_background.sh          # Run with system tray
```

**CLI Options**:
- `--help` - Show all options
- `--check` - Verify configuration and LMStudio connection
- `--verbose` - Enable debug logging
- `--scan-only` - Process existing files and exit
- `--file <path>` - Process a single file
- `--create-folders` - Create folder structure and exit
- `--no-scan` - Start without processing existing files
- `--background` - Run with system tray icon
- `--enable-startup` / `--disable-startup` - Manage auto-start on login

### Building Distributable Packages

**Windows**:
```cmd
pip install pyinstaller
python build_package.py      # Creates dist/Sift_Windows.zip
```

**macOS**:
```bash
python build_macos_package.py  # Creates dist/Sift_macOS.zip (source bundle)
```

### Testing

**No formal test suite exists**. The project uses manual verification:
- `install.bat` includes import verification checks
- `run.bat --check` verifies LMStudio connectivity
- Log-based debugging via `logs/sift.log`

## High-Level Architecture

### Component-Based Design

The application follows a component-based architecture with clear separation of concerns. The `Sift` class in `src/main.py` orchestrates all components:

```
main.py (Sift class - Orchestrator)
    ├── config.py (Config) - YAML configuration management
    ├── watcher.py (DocumentWatcher) - Filesystem monitoring via watchdog
    ├── document_processor.py (DocumentProcessor) - Text/image extraction
    ├── llm_client.py (LMStudioClient) - LMStudio API communication
    ├── classifier.py (DocumentClassifier) - Classification orchestration
    ├── folder_organizer.py (FolderOrganizer) - File movement logic
    ├── database.py (DocumentDatabase) - SQLite document history
    ├── dashboard.py (DashboardServer) - Flask web UI (port 5000)
    ├── tray_icon.py (TrayIcon) - System tray integration
    └── rules_engine.py (RulesEngine) - Custom classification rules
```

### Classification Pipeline

The document classification pipeline follows this flow:

1. **File Detection**: `DocumentWatcher` detects new files in the inbox folder
2. **Custom Rules Check** (highest priority): `RulesEngine` checks pattern-based rules first
3. **Content Extraction**:
   - For documents (PDF, DOCX, XLSX, CSV): `DocumentProcessor.extract_text()`
   - For images: Fallback to filename-based classification
4. **LLM Classification**: `DocumentClassifier` sends extracted text to LMStudio via `LMStudioClient`
5. **Confidence Check**: If confidence < threshold → move to "Needs_Review" folder
6. **Organization**: `FolderOrganizer` moves file to category/subcategory folder
7. **Tracking**: `DocumentDatabase` logs the classification in SQLite
8. **Notification**: System tray notification (if background mode)

### Key Architectural Decisions

1. **Local-First Privacy**: All processing happens on localhost. LMStudio runs on `localhost:1234`, dashboard binds to `127.0.0.1:5000` (not accessible from network).

2. **Configuration-Driven**: Extensive YAML configuration (`config/settings.yaml`) allows customization without code changes:
   - Custom categories and subcategories
   - Multiple LLM model profiles (fast/balanced/accurate)
   - Confidence thresholds
   - Custom classification rules

3. **Dual Processing Modes**:
   - **Text Mode** (fast): Extract text from documents → classify with text-only model
   - **Fallback Mode**: If text extraction fails → filename-based classification

4. **Learning from Corrections**: `DocumentDatabase` tracks user corrections to classification, allowing future instances to learn from feedback.

5. **Custom Rules Priority**: Pattern-based rules (in `rules_engine.py`) bypass LLM entirely for deterministic classification (e.g., "W2" → Financial/Tax_Documents).

## Configuration System

The application uses a hierarchical YAML configuration system:

- `config/settings.default.yaml` - Template with all options documented
- `config/settings.yaml` - User configuration (gitignored)
- `config/settings.macos.yaml` - macOS-specific template

**Key Configuration Sections**:
- `folders`: Paths for inbox, base, and temp directories
- `llm`: LMStudio connection settings, model profiles
- `processing`: File types, page limits, image settings
- `categories`: Category/subcategory definitions with keywords
- `behavior`: Confidence threshold, move vs copy, filename handling
- `dashboard`: Web UI settings
- `advanced`: Custom classification rules, file type overrides

**Model Profiles** (`llm.profiles`): The config supports multiple model profiles for different speed/accuracy tradeoffs:
- `fast`: qwen3-1.7b (~1.5GB, fastest)
- `balanced`: qwen3-4b (~3GB)
- `accurate`: qwen2.5-7b-instruct (~5GB, most accurate)

Switch profiles by changing `llm.active_profile`.

## Component Responsibilities

### `src/main.py` (Sift Class)
**Purpose**: Application orchestrator and lifecycle manager
**Key Methods**:
- `start()` - Initialize components, start watcher, launch dashboard
- `_process_file()` - Main processing pipeline for each detected file
- `stop()` - Graceful shutdown of all components

### `src/classifier.py` (DocumentClassifier)
**Purpose**: Orchestrates classification logic
**Key Flow**:
1. Check custom rules first (`_check_custom_rules()`)
2. Extract text if possible (`processor.extract_text()`)
3. Call LLM via `llm_client.classify_text()`
4. Fuzzy match LLM response to known folders
5. Return `ClassificationResult` with category, subcategory, confidence

### `src/llm_client.py` (LMStudioClient)
**Purpose**: OpenAI-compatible API client for LMStudio
**Key Methods**:
- `classify_text()` - Send text to LLM, parse JSON response
- `is_available()` - Health check for LMStudio connection
- Handles retries, timeouts, JSON parsing

### `src/document_processor.py` (DocumentProcessor)
**Purpose**: Extract text/images from various file formats
**Supported Formats**:
- PDF: `pypdf` + `pdf2image` (requires Poppler)
- Office: `python-docx` (DOCX), `openpyxl` (XLSX)
- CSV/TSV: Built-in CSV parsing
- Images: Filename-based classification only

### `src/folder_organizer.py` (FolderOrganizer)
**Purpose**: File movement with collision handling
**Features**:
- Move or copy files based on config
- Handle filename collisions (append counter)
- Preserve or normalize filenames
- Create category folders on-demand

### `src/database.py` (DocumentDatabase)
**Purpose**: SQLite tracking of document history
**Tables**:
- `documents` - Processed files with classification results
- `activity_log` - Action history for undo functionality
- `processing_queue` - Crash recovery for interrupted operations
- `classification_corrections` - User feedback for learning
- `documents_fts` - FTS5 full-text search index

### `src/dashboard.py` (DashboardServer)
**Purpose**: Flask web UI on port 5000
**Features**:
- Document history view
- Search functionality (with LLM query parsing)
- Classification statistics
- Low-confidence document review

### `src/rules_engine.py` (RulesEngine)
**Purpose**: Pattern-based classification rules
**Rule Types**:
- Filename patterns (regex)
- File extension matching
- Content keyword detection
- Bypasses LLM for deterministic classification

## External Dependencies

**Critical Runtime Requirements**:
1. **LMStudio** - Must be running on `localhost:1234` with a model loaded
2. **Poppler** - Required for PDF text extraction (`pdf2image` dependency)
   - Windows: Add `poppler/Library/bin` to PATH
   - macOS: `brew install poppler`
3. **LibreOffice** (optional) - Only needed for legacy `.doc`/`.xls` or PowerPoint files

**Python Dependencies** (see `requirements.txt`):
- `watchdog` - Filesystem monitoring
- `flask` - Web dashboard
- `openai` - LMStudio API client
- `pypdf`, `python-docx`, `openpyxl` - Document parsing
- `pdf2image` - PDF to image conversion
- `Pillow` - Image processing
- `rapidfuzz` - Fuzzy string matching for folder names
- `pystray` - System tray icon

## CI/CD

The repository includes GitHub Actions workflow (`.github/workflows/build.yml`):
- **Triggers**: Push to main/master, PRs, manual dispatch, version tags (`v*`)
- **Builds**: Windows (PyInstaller .exe), macOS (source bundle), Source distribution
- **Release**: Auto-creates GitHub Release for tagged versions with all artifacts

## Logging and Debugging

**Log Location**: `logs/sift.log`
**Log Levels**: INFO (default), DEBUG (with `--verbose`)

**Common Debugging Steps**:
1. Check LMStudio connection: `run.bat --check`
2. Enable verbose logging: `run.bat --verbose`
3. Test single file: `run.bat --file "path/to/document.pdf"`
4. Check database state: `data/documents.db` (SQLite)
5. Review crash recovery queue in database

## Important Paths

- **Entry Point**: `src/main.py`
- **Configuration**: `config/settings.yaml` (user), `config/settings.default.yaml` (template)
- **Database**: `data/documents.db` (SQLite)
- **Logs**: `logs/sift.log`
- **Temp Files**: Configured in `config/settings.yaml` (`folders.temp_path`)
- **Dashboard**: `http://localhost:5000` when running

## Working with the Codebase

When making changes to Sift:

1. **Configuration Changes**: Edit `config/settings.yaml`, restart application
2. **Adding Categories**: Update `categories` section in config, restart
3. **Custom Rules**: Add rules to `advanced.custom_rules` in config
4. **Component Modifications**: Each component is self-contained in `src/` - changes to one component typically don't require changes to others
5. **Database Schema Changes**: Update `database.py`, consider migration for existing users
6. **New File Type Support**: Update `document_processor.py` and `config/settings.default.yaml` (`processing.supported_extensions`)

## Detailed Documentation

For deeper understanding, see the `/docs` folder:
- `docs/ARCHITECTURE.md` - System diagrams, data flow, threading model
- `docs/FEATURES.md` - All 24 features with code locations and config options
- `docs/USER_FLOWS.md` - Step-by-step flows with error scenarios
- `docs/PRODUCT_BRIEF.md` - Target personas, jobs-to-be-done, strengths and gaps
- `docs/GAPS_QOL.md` - 40 identified quality-of-life improvements with analysis
- `docs/LATENT_NEEDS.md` - 43 user needs across current, latent, trust, and power user dimensions
- `ROADMAP.md` - Phased development plan (Now/Next/Later)

## Known Limitations

| Gap | Status | Workaround |
|-----|--------|------------|
| **No test suite** | No automated tests | Use `--check` and manual verification |
| **PowerPoint (.pptx)** | Filename-only classification | Text extraction not implemented |
| **Standalone images** | Filename-only classification | No OCR/vision model for images |
| **Vision model infrastructure** | Code exists but unused | `@src/document_processor.py:553-589` not wired up |
