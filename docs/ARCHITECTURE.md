# Sift Architecture

This document explains how Sift is built and how its parts work together. It's written for anyone who wants to understand the system, whether you're a developer or just curious about how your documents get organized.

---

## What Is Sift?

Sift is a **desktop application** that watches a folder on your computer, reads documents you drop into it, uses AI to understand what each document is about, and automatically moves it to the right folder.

**Key Design Principles:**
- **Privacy-first**: Everything runs on your computer. No cloud services, no data sent anywhere.
- **Resilient**: If something fails, Sift recovers gracefully without losing your documents.
- **Local AI**: Uses LMStudio (a free app) to run AI models entirely on your machine.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HOW YOU INTERACT WITH SIFT                          │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│  Command Line   │   System Tray   │  Web Dashboard  │   Drop Files Here     │
│  (run.bat)      │   (icon in      │  (browser at    │   (Inbox folder)      │
│                 │   taskbar)      │  localhost:5000)│                       │
└────────┬────────┴────────┬────────┴────────┬────────┴───────────┬───────────┘
         │                 │                 │                    │
         └─────────────────┴─────────────────┴────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            THE BRAIN (Orchestrator)                         │
│                                                                             │
│  Coordinates everything: starting up, processing files, shutting down       │
│                                                                             │
│  Evidence: @src/main.py (Sift class)                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌─────────────────┐    ┌───────────────────────┐    ┌─────────────────────────┐
│  FILE WATCHER   │    │   CLASSIFICATION      │    │   USER INTERFACE        │
│                 │    │                       │    │                         │
│ Watches your    │    │ Figures out what      │    │ Shows you what's        │
│ Inbox folder    │───▶│ each document is      │    │ happening and lets      │
│ for new files   │    │ and where it goes     │    │ you make changes        │
│                 │    │                       │    │                         │
│ @src/watcher.py │    │ @src/classifier.py    │    │ @src/dashboard.py       │
└─────────────────┘    │ @src/llm_client.py    │    │ @src/tray_icon.py       │
                       │ @src/rules_engine.py  │    └─────────────────────────┘
                       └───────────┬───────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FILE ORGANIZATION                                  │
│                                                                             │
│  Moves files to the right folder, handles duplicates, renames if needed     │
│                                                                             │
│  Evidence: @src/folder_organizer.py                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATABASE                                        │
│                                                                             │
│  Remembers every document processed, supports undo, enables search          │
│                                                                             │
│  Evidence: @src/database.py → data/documents.db                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Entry Points

An "entry point" is how you start or interact with Sift. Here are all the ways:

| Entry Point | What It Does | File |
|-------------|--------------|------|
| **run.bat** (Windows) | Starts Sift in console mode | `run.bat` → `@src/main.py` |
| **run_background.bat** | Starts Sift with system tray icon | `run_background.bat` → `@src/main.py --background` |
| **Web Dashboard** | Browser interface at http://localhost:5000 | `@src/dashboard.py` |
| **System Tray Icon** | Right-click menu in taskbar | `@src/tray_icon.py` |
| **Drop files in Inbox** | Triggers automatic processing | Detected by `@src/watcher.py` |

### Command Line Options

You can customize how Sift starts:

```
python src/main.py [options]

--check           Test if everything is set up correctly
--verbose         Show detailed logs (for troubleshooting)
--scan-only       Process existing files and exit
--file <path>     Process just one specific file
--background      Run with system tray icon
--create-folders  Create folder structure and exit
```

**Evidence**: `@src/main.py:455-536` (argument parser)

---

## Major Subsystems

### 1. File Watcher
**What it does**: Monitors your Inbox folder and detects when new files appear.

**How it works**:
- Uses a library called "Watchdog" to get notified of file changes
- Waits 2 seconds after a file appears (to make sure it's fully copied)
- Adds files to a processing queue
- Runs in the background so Sift can do other things

**Evidence**: `@src/watcher.py:321-760`

---

### 2. Document Processor
**What it does**: Reads the content from documents so the AI can understand them.

**Supported formats**:
| Format | How It's Read | Requirements |
|--------|---------------|--------------|
| PDF | Text extraction with pypdf, OCR fallback | Poppler (for OCR) |
| Word (.docx) | python-docx library | None |
| Word (.doc) | Converted via LibreOffice | LibreOffice |
| Excel (.xlsx) | openpyxl library | None |
| Excel (.xls) | Converted via LibreOffice | LibreOffice |
| CSV/TSV | Built-in Python | None |
| Images | Filename only (no content analysis) | None |
| PowerPoint | Filename only (not implemented) | None |

**Evidence**: `@src/document_processor.py:43-530`

---

### 3. Classification System
**What it does**: Decides what category each document belongs to.

**Three-tier decision process**:

```
1. CUSTOM RULES (highest priority)
   ↓ If filename matches a pattern you defined, use that category

2. AI CLASSIFICATION
   ↓ Send document text to LMStudio, get AI's recommendation

3. FILENAME FALLBACK (lowest priority)
   ↓ If AI fails, guess based on keywords in the filename
```

**Components**:
- `@src/rules_engine.py` - Your custom rules (patterns, keywords)
- `@src/classifier.py` - Orchestrates the decision process
- `@src/llm_client.py` - Talks to LMStudio AI

---

### 4. Folder Organizer
**What it does**: Actually moves files to their destination folders.

**Features**:
- Creates folders if they don't exist
- Handles duplicate filenames (adds _1, _2, etc.)
- Can rename generic filenames (like "scan001.pdf") to something meaningful
- Moves files to "Needs_Review" if AI isn't confident

**Evidence**: `@src/folder_organizer.py:38-463`

---

### 5. Database
**What it does**: Remembers everything that's happened.

**Tables**:
| Table | Purpose |
|-------|---------|
| `documents` | Every file that's been processed |
| `activity_log` | History of actions (for undo) |
| `processing_queue` | Files being processed (crash recovery) |
| `classification_corrections` | Your corrections (helps AI learn) |
| `documents_fts` | Search index (fast full-text search) |

**Evidence**: `@src/database.py:85-242` (schema), `data/documents.db` (file)

---

### 6. Dashboard
**What it does**: Web interface to see and manage your documents.

**Features**:
- View recent documents
- Search across all documents
- Review uncertain classifications
- Reassign documents to different folders
- Undo recent actions

**Evidence**: `@src/dashboard.py:1-2350`, accessible at http://localhost:5000

---

### 7. System Tray
**What it does**: Lets you control Sift from your taskbar.

**Menu options**:
- Open Dashboard
- Open Inbox Folder
- Pause/Resume Processing
- Exit

**Evidence**: `@src/tray_icon.py:61-263`

---

## Storage

### Files on Disk

| Location | What's There |
|----------|--------------|
| `config/settings.yaml` | Your configuration (folders, categories, etc.) |
| `data/documents.db` | SQLite database with all document history |
| `logs/sift.log` | Application logs |
| `{your Sift folder}/Inbox/` | Where you drop documents |
| `{your Sift folder}/{Category}/` | Where documents get organized |

### Database Details

**Type**: SQLite with WAL mode (allows reading while writing)

**Location**: `data/documents.db`

**Key characteristics**:
- Single file, no server needed
- Survives crashes (write-ahead logging)
- Full-text search built-in

**Evidence**: `@src/database.py:247-255` (connection setup)

---

## Integrations

### LMStudio (Required)
**What it is**: Free app that runs AI models on your computer.

**How Sift connects**:
- Sift sends document text to http://localhost:1234
- LMStudio processes it with your chosen AI model
- LMStudio returns a classification decision

**Evidence**: `@src/llm_client.py:644-667` (API call)

### Poppler (Optional but Recommended)
**What it is**: Tools for reading PDF files.

**Why needed**: Extracts text from PDFs, converts pages to images for OCR.

**Evidence**: `@src/document_processor.py:109-124`

### LibreOffice (Optional)
**What it is**: Free office suite.

**Why needed**: Converts old .doc and .xls files to modern formats.

**Evidence**: `@src/document_processor.py:126-138`

### Tesseract (Optional)
**What it is**: OCR (Optical Character Recognition) tool.

**Why needed**: Reads text from scanned documents that don't have selectable text.

**Evidence**: `@src/document_processor.py:140-159`

---

## Observability

### Logging

**Log file**: `logs/sift.log`

**Log levels**:
- `INFO` (default): Important events, processing results
- `DEBUG` (with `--verbose`): Detailed step-by-step information

**What's logged**:
- Every file detected and processed
- Classification decisions with confidence scores
- Errors and recovery actions
- LMStudio communication

**Evidence**: Logging setup in `@src/config.py`, used throughout all modules

### Health Check

Run `python src/main.py --check` to verify:
- Configuration is valid
- LMStudio is running and accessible
- Required folders exist

**Evidence**: `@src/main.py:572-598`

---

## How Data Flows Through the System

```
1. FILE ARRIVES
   You drop "invoice.pdf" into your Inbox folder

2. DETECTION (within seconds)
   Watcher sees new file, waits 2 seconds for it to finish copying
   Evidence: @src/watcher.py:87-92

3. QUEUE FOR PROCESSING
   File added to in-memory queue AND database queue (crash safety)
   Evidence: @src/database.py:897-923

4. TEXT EXTRACTION
   Document Processor reads the PDF text
   Evidence: @src/document_processor.py:235-274

5. AI CLASSIFICATION
   Text sent to LMStudio: "What kind of document is this?"
   LMStudio responds: "Financial/Invoices, confidence: 0.85"
   Evidence: @src/llm_client.py:573-667

6. DECISION
   Confidence 0.85 > threshold 0.70, so auto-file (no review needed)
   Evidence: @src/classifier.py:630-632

7. FILE MOVE
   invoice.pdf moved to Financial/Invoices/invoice.pdf
   Evidence: @src/folder_organizer.py:108-124

8. RECORD KEEPING
   Database updated: file path, category, confidence, timestamp
   Evidence: @src/database.py:324-373

9. NOTIFICATION (if background mode)
   Toast notification: "Organized: invoice.pdf → Financial/Invoices"
   Evidence: @src/tray_icon.py:207-230
```

---

## Threading Model

Sift runs multiple things at once using "threads" (parallel workers):

| Thread | What It Does | Type |
|--------|--------------|------|
| Main Thread | Runs the main loop, handles signals | Primary |
| Watcher Thread | Monitors Inbox for new files | Daemon |
| Processing Thread | Works through the file queue | Daemon |
| Dashboard Thread | Runs the web server | Daemon |
| Tray Icon Thread | Manages system tray | Daemon |

**"Daemon" threads** automatically stop when Sift exits.

**Evidence**:
- `@src/watcher.py:398-403` (processing thread)
- `@src/dashboard.py:2306` (dashboard thread)
- `@src/tray_icon.py:101-102` (tray thread)

---

## Error Handling Philosophy

Sift is designed to **never lose your files**. Here's how:

### 1. Crash Recovery
If Sift crashes while processing a file:
- The file stays in a "processing" state in the database
- On restart, Sift finds interrupted files and re-processes them

**Evidence**: `@src/database.py:1045-1065`, `@src/watcher.py:407-448`

### 2. Retry Queue
If a file is locked (still being written):
- Sift puts it in a retry queue
- Tries again up to 3 times, 10 seconds apart

**Evidence**: `@src/watcher.py:506-526`

### 3. Fallback Chain
If AI classification fails:
1. Try filename-based classification
2. If that fails, move to Miscellaneous
3. Never throw away the file

**Evidence**: `@src/classifier.py:129-141`

### 4. Safe "Delete"
Even batch delete doesn't actually delete:
- Files are moved to Needs_Review folder
- You can recover them

**Evidence**: `@src/dashboard.py:2071-2090`

---

## Known Unknowns / Questions

Things we discovered during analysis that might need attention:

| Question | Context | Where to Look |
|----------|---------|---------------|
| Why no test suite? | No automated tests exist | Consider adding `tests/` directory |
| Vision model code unused? | Infrastructure exists but isn't wired up | `@src/document_processor.py:553-589` |
| PowerPoint text extraction? | PPTX files classified by filename only | `@src/document_processor.py:40` |
| What happens with huge files? | No explicit size limits documented | `@src/document_processor.py` |
| Multi-language support? | Tesseract defaults to English | `@src/document_processor.py:329-332` |

---

## Quick Reference

| Component | File | Port/Path |
|-----------|------|-----------|
| Main app | `@src/main.py` | - |
| Dashboard | `@src/dashboard.py` | http://localhost:5000 |
| LMStudio | External | http://localhost:1234 |
| Database | `@src/database.py` | `data/documents.db` |
| Logs | - | `logs/sift.log` |
| Config | - | `config/settings.yaml` |
