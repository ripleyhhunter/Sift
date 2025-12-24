# Sift Features

This document describes what Sift can do, where each feature lives in the code, and how to configure it.

---

## Core Features

### 1. Automatic Folder Monitoring

**What it does**: Watches your Inbox folder and automatically processes any file you drop into it.

**How it works**:
- Detects new files within seconds
- Waits briefly to ensure file is fully copied
- Processes files one at a time to avoid overwhelming your computer

**Where it lives**:
- `@src/watcher.py` - Main watching logic
- `@src/watcher.py:87-92` - File detection handler
- `@src/watcher.py:298` - 2-second stabilization delay

**Configuration** (`config/settings.yaml`):
```yaml
folders:
  watch_path: "C:\\Users\\You\\Documents\\Sift\\Inbox"  # Folder to watch

processing:
  processing_delay_seconds: 2  # Wait time before processing
```

**Status**: Fully functional, production-ready

---

### 2. AI-Powered Document Classification

**What it does**: Uses a local AI model to understand what your document is about and choose the best folder for it.

**How it works**:
1. Extracts text from your document
2. Sends text to LMStudio (runs on your computer)
3. AI analyzes content and suggests a category
4. Returns a confidence score (0-100%)

**Where it lives**:
- `@src/classifier.py` - Classification orchestration
- `@src/llm_client.py` - Communication with LMStudio
- `@src/llm_client.py:446-571` - Prompt construction
- `@src/llm_client.py:669-820` - Response parsing

**Configuration** (`config/settings.yaml`):
```yaml
llm:
  base_url: "http://localhost:1234/v1"
  active_profile: "balanced"  # fast, balanced, or accurate

  profiles:
    fast:
      model_identifier: "qwen/qwen3-1.7b"
      description: "Fastest, good for most documents"
    balanced:
      model_identifier: "qwen/qwen3-4b"
      description: "Good balance of speed and accuracy"
    accurate:
      model_identifier: "qwen/qwen2.5-7b-instruct"
      description: "Most accurate, slower"
```

**Status**: Fully functional. Requires LMStudio running with a model loaded.

---

### 3. Multi-Format Document Support

**What it does**: Reads text from many different document types.

**Supported formats**:

| Format | Text Extraction | How |
|--------|-----------------|-----|
| PDF (.pdf) | Yes | pypdf library + OCR fallback |
| Word (.docx) | Yes | python-docx library |
| Word (.doc) | Yes | LibreOffice conversion |
| Excel (.xlsx) | Yes | openpyxl library |
| Excel (.xls) | Yes | LibreOffice conversion |
| CSV/TSV | Yes | Built-in Python |
| PowerPoint (.pptx, .ppt) | No | Filename only |
| Images (.png, .jpg, etc.) | No | Filename only |

**Where it lives**:
- `@src/document_processor.py` - All extraction logic
- `@src/document_processor.py:235-274` - PDF extraction
- `@src/document_processor.py:374-397` - Word extraction
- `@src/document_processor.py:433-499` - Excel extraction

**Configuration** (`config/settings.yaml`):
```yaml
processing:
  supported_extensions:
    - ".pdf"
    - ".docx"
    - ".xlsx"
    # ... add more as needed
  max_pages_to_analyze: 3  # For multi-page documents
```

**Status**: PDF/Word/Excel fully functional. PowerPoint and images use filename-only classification.

---

### 4. Smart Category System

**What it does**: Organizes documents into categories and subcategories.

**Default categories**:
- Financial (Tax_Documents, Bank_Statements, Invoices, Investment, Payroll)
- Medical (Insurance, Records, Prescriptions, Bills)
- Legal (Contracts, Agreements, Correspondence, Court)
- Government (ID_Documents, Licenses, Permits)
- Insurance
- Work
- Education
- Personal
- Home
- Health_Fitness
- Travel
- Receipts
- Needs_Review (for uncertain classifications)
- Miscellaneous (fallback)

**Where it lives**:
- `@src/classifier.py:310-333` - Discovers existing folders
- `@src/folder_organizer.py:126-144` - Creates folder paths
- `config/settings.default.yaml:67-160` - Category definitions

**Configuration** (`config/settings.yaml`):
```yaml
categories:
  - name: "Financial"
    subcategories:
      - "Tax_Documents"
      - "Bank_Statements"
      - "Invoices"
    keywords: ["tax", "W2", "bank", "invoice", "payment"]

  - name: "YourCustomCategory"
    subcategories:
      - "Subcategory1"
      - "Subcategory2"
    keywords: ["keyword1", "keyword2"]
```

**Status**: Fully functional. Add your own categories by editing config.

---

### 5. Custom Classification Rules

**What it does**: Lets you define patterns that bypass AI and always go to a specific folder.

**Example rules**:
- "Any PDF with 'W2' in the filename → Financial/Tax_Documents"
- "Any file containing 'invoice' and 'ACME Corp' → Work/Invoices"

**Rule types**:
| Type | What It Matches |
|------|-----------------|
| Filename pattern | Regex against filename |
| Extension | File type (.pdf, .docx, etc.) |
| Content keywords | Words that must appear in document |
| Content pattern | Regex against document text |

**Where it lives**:
- `@src/rules_engine.py` - Rule matching logic
- `@src/rules_engine.py:67-111` - Match algorithm
- `@src/classifier.py:62-66` - Rule check (highest priority)

**Configuration** (`config/settings.yaml`):
```yaml
advanced:
  custom_rules:
    - name: "Bank Statements"
      category: "Financial"
      subcategory: "Bank_Statements"
      filename_pattern: "(bank|statement|account)"
      extension: [".pdf"]
      content_contains: ["account", "balance"]
      priority: 90  # Higher = checked first
```

**Status**: Fully functional. Rules always have confidence 1.0 (100% certain).

---

### 6. Confidence-Based Review System

**What it does**: When AI isn't sure about a classification, puts the file in a review folder for you to decide.

**How it works**:
- AI returns a confidence score (0.0 to 1.0)
- If score < threshold (default 0.7), file goes to "Needs_Review"
- You can review in the dashboard and reassign

**Where it lives**:
- `@src/classifier.py:630-632` - Confidence check
- `@src/main.py:248-254` - Review decision
- `@src/folder_organizer.py:78-80` - Review folder routing

**Configuration** (`config/settings.yaml`):
```yaml
behavior:
  confidence_threshold: 0.7  # 0.0-1.0, lower = more auto-filing
  manual_review_folder: "Needs_Review"
```

**Status**: Fully functional

---

### 7. Learning from Corrections

**What it does**: When you reassign a document, Sift remembers and uses that to improve future classifications.

**How it works**:
1. You correct a misclassified document
2. Sift records: original category → corrected category + document type
3. Next time a similar document appears, Sift includes your correction as context for the AI

**Where it lives**:
- `@src/database.py:1107-1160` - Records corrections
- `@src/database.py:1162-1238` - Retrieves relevant corrections
- `@src/llm_client.py:523-533` - Injects corrections into AI prompt

**Configuration**: No configuration needed. Automatic.

**Status**: Fully functional. Corrections stored in database permanently.

---

### 8. Smart Filename Generation

**What it does**: Renames generic filenames (like "scan001.pdf") to something meaningful.

**How it works**:
- Detects "useless" filenames (scan, document, IMG_, etc.)
- Generates descriptive name from: date + document type + organization
- Respects your preference to keep original names

**Where it lives**:
- `@src/folder_organizer.py:146-193` - Detects useless names
- `@src/folder_organizer.py:195-253` - Generates smart names
- `@src/folder_organizer.py:255-325` - Final name decision

**Configuration** (`config/settings.yaml`):
```yaml
behavior:
  preserve_original_filename: true  # false = always rename
  add_date_prefix: false  # true = prepend YYYY-MM-DD
```

**Status**: Fully functional

---

### 9. Crash Recovery

**What it does**: If Sift crashes or your computer restarts, no files are lost.

**How it works**:
- Before processing, file is added to a "processing queue" in the database
- If crash happens, file stays in queue with status "processing"
- On restart, Sift finds these files and re-processes them

**Where it lives**:
- `@src/database.py:137-148` - Processing queue table
- `@src/database.py:1045-1065` - Reset interrupted items
- `@src/watcher.py:407-448` - Recovery on startup

**Configuration**: No configuration needed. Always active.

**Status**: Fully functional

---

## Dashboard Features

### 10. Document History View

**What it does**: Shows all documents that have been processed, most recent first.

**Where it lives**:
- `@src/dashboard.py:1810-1814` - API endpoint
- `@src/database.py:392-404` - Database query

**Access**: http://localhost:5000 (main view)

**Status**: Fully functional

---

### 11. Full-Text Search

**What it does**: Search across all your documents by content, filename, or category.

**How it works**:
- Uses FTS5 (SQLite full-text search) for fast results
- BM25 ranking for relevance
- Can optionally use AI to understand search intent

**Where it lives**:
- `@src/dashboard.py:2097-2143` - Search endpoint
- `@src/database.py:706-808` - Search query with ranking
- `@src/database.py:195-207` - FTS5 index definition

**Configuration**: No configuration needed.

**Status**: Fully functional

---

### 12. Review Queue

**What it does**: Shows documents that need your attention (low confidence classifications).

**Where it lives**:
- `@src/dashboard.py:1815-1819` - Review endpoint
- `@src/database.py:406-418` - Query for review items

**Access**: http://localhost:5000 → "Needs Review" section

**Status**: Fully functional

---

### 13. Document Reassignment

**What it does**: Move a document to a different category (single or batch).

**Where it lives**:
- `@src/dashboard.py:1853-1930` - Single reassign
- `@src/dashboard.py:2017-2069` - Batch reassign

**Status**: Fully functional. Records corrections for learning.

---

### 14. Undo/Redo Actions

**What it does**: Reverse recent classifications or reassignments.

**Time limit**: Can undo actions from the last 24 hours.

**Where it lives**:
- `@src/dashboard.py:1955-1983` - Undo endpoints
- `@src/database.py:563-697` - Undo logic
- `@src/database.py:121-132` - Activity log table

**Status**: Fully functional

---

### 15. Statistics Dashboard

**What it does**: Shows overview of your document collection.

**Metrics shown**:
- Total documents processed
- Documents by category
- Documents needing review
- Recent activity

**Where it lives**:
- `@src/dashboard.py:1805-1809` - Stats endpoint
- `@src/database.py:470-512` - Statistics queries

**Status**: Fully functional

---

### 16. Model Profile Switching

**What it does**: Switch between fast/balanced/accurate AI models without restarting.

**Where it lives**:
- `@src/dashboard.py:2212-2245` - Profile endpoints
- `@src/llm_client.py:325-357` - Profile switching logic

**Status**: Fully functional

---

## System Tray Features

### 17. Background Operation

**What it does**: Run Sift in the background with just a tray icon.

**How to use**: `run_background.bat` or `python src/main.py --background`

**Where it lives**:
- `@src/tray_icon.py:61-263`
- `@src/main.py:98-187` - Background mode startup

**Status**: Fully functional on Windows. macOS support varies.

---

### 18. Pause/Resume Processing

**What it does**: Temporarily stop processing without exiting Sift.

**Where it lives**:
- `@src/tray_icon.py:127-129` - Menu item
- `@src/tray_icon.py:195-200` - Toggle logic
- `@src/main.py:193` - Pause check in main loop

**Status**: Fully functional

---

### 19. Toast Notifications

**What it does**: Shows a notification when a document is processed.

**Where it lives**:
- `@src/tray_icon.py:207-230` - Notification logic
- `@src/platform_utils.py` - Platform-specific implementation

**Platform support**:
- Windows: Uses winotify library
- macOS: Uses pync or osascript
- Linux: Uses notify-send

**Status**: Fully functional on Windows

---

## Advanced Features

### 20. OCR for Scanned Documents

**What it does**: Reads text from scanned PDFs that don't have selectable text.

**How it works**:
1. Tries normal text extraction first
2. If <50 characters extracted, assumes it's scanned
3. Converts PDF pages to images
4. Runs Tesseract OCR on images

**Where it lives**:
- `@src/document_processor.py:258-274` - OCR decision
- `@src/document_processor.py:276-310` - PDF OCR
- `@src/document_processor.py:312-372` - Image OCR

**Requirements**: Tesseract must be installed

**Configuration** (`config/settings.yaml`):
```yaml
processing:
  ocr_enabled: true  # Set false to disable
```

**Status**: Functional when Tesseract is installed

---

### 21. Multiple Model Profiles

**What it does**: Different AI configurations for speed vs accuracy trade-offs.

**Profiles**:
| Profile | Model | Speed | Accuracy | Token Limit |
|---------|-------|-------|----------|-------------|
| Fast | qwen3-1.7b | Fastest | Good | 512 |
| Balanced | qwen3-4b | Medium | Better | 2048 |
| Accurate | qwen2.5-7b | Slower | Best | 2048 |

**Where it lives**:
- `@src/llm_client.py:325-357` - Profile management
- `@src/llm_client.py:416-444` - Content sampling by profile

**Status**: Fully functional

---

### 22. Batch Operations

**What it does**: Approve, reassign, or delete multiple documents at once.

**Supported actions**:
- `approve` - Mark multiple documents as processed
- `reassign` - Move multiple documents to a category
- `delete` - Move multiple documents to Needs_Review (safe delete)

**Where it lives**:
- `@src/dashboard.py:1985-2095` - Batch endpoint

**Status**: Fully functional

---

### 23. Thumbnail Generation

**What it does**: Creates preview images for documents in the dashboard.

**Supported formats**:
- Images: Direct resize
- PDFs: Renders first page (requires PyMuPDF)
- Other: Color-coded placeholder

**Where it lives**:
- `@src/thumbnail.py:33-263`
- `@src/dashboard.py:2145-2170` - Thumbnail endpoint

**Configuration**: No configuration needed. Thumbnails cached automatically.

**Status**: Functional when PyMuPDF is installed

---

### 24. Windows Auto-Start

**What it does**: Start Sift automatically when you log into Windows.

**How to use**:
```
python src/main.py --enable-startup   # Enable
python src/main.py --disable-startup  # Disable
python src/main.py --startup-status   # Check status
```

**Where it lives**:
- `@src/main.py:607-630` - Startup management
- `@src/tray_icon.py:269-330` - Creates startup shortcut

**Status**: Windows only. Fully functional.

---

## Feature Status Summary

| Feature | Status | Notes |
|---------|--------|-------|
| Folder Monitoring | Production | Stable |
| AI Classification | Production | Requires LMStudio |
| PDF Text Extraction | Production | Stable |
| Word Text Extraction | Production | Stable |
| Excel Text Extraction | Production | Stable |
| PowerPoint Extraction | Not Implemented | Filename only |
| Image Classification | Limited | Filename only, no OCR |
| Custom Rules | Production | Stable |
| Learning from Corrections | Production | Stable |
| Dashboard | Production | Stable |
| Search | Production | FTS5-powered |
| Undo | Production | 24-hour window |
| System Tray | Production | Windows primary |
| OCR | Optional | Requires Tesseract |
| Crash Recovery | Production | Always active |
| Test Suite | Not Implemented | No automated tests |
