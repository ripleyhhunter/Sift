# Sift User Flows

This document describes step-by-step how to accomplish common tasks in Sift, what happens behind the scenes, and what can go wrong.

---

## Flow 1: Automatic Document Classification

**Goal**: Have a document automatically sorted into the correct folder.

### Steps

1. **You drop a file into your Inbox folder**
   - Example: Drag `invoice_acme_2024.pdf` into `Documents/Sift/Inbox`

2. **Sift detects the new file** (within 1-2 seconds)
   - The file watcher sees the new file appear
   - Evidence: `@src/watcher.py:87` (on_created handler)

3. **Sift waits for the file to finish copying** (2 seconds)
   - Ensures the file isn't still being written
   - Evidence: `@src/watcher.py:298` (delay timer)

4. **File is added to the processing queue**
   - Added to in-memory queue (fast) AND database queue (crash-safe)
   - Evidence: `@src/watcher.py:159-161`, `@src/database.py:897-923`

5. **Processing begins**
   - Queue marks file as "processing"
   - Evidence: `@src/database.py:925-943`

6. **Text is extracted from the document**
   - For PDF: pypdf reads the text
   - If no text found (scanned doc): OCR kicks in
   - Evidence: `@src/document_processor.py:193-233`

7. **Custom rules are checked first**
   - If a rule matches: skip AI, use rule's category
   - Evidence: `@src/classifier.py:62-66`

8. **AI analyzes the document**
   - Text sent to LMStudio with folder context
   - AI returns: category, subcategory, confidence, reasoning
   - Evidence: `@src/llm_client.py:573-667`

9. **Confidence is evaluated**
   - If confidence ≥ 0.7: proceed to filing
   - If confidence < 0.7: route to Needs_Review folder
   - Evidence: `@src/classifier.py:630-632`

10. **File is moved to destination**
    - Example: Moved to `Documents/Sift/Financial/Invoices/invoice_acme_2024.pdf`
    - If filename is generic, it may be renamed
    - Evidence: `@src/folder_organizer.py:108-124`

11. **Database is updated**
    - Records: original path, new path, category, confidence, timestamp
    - Evidence: `@src/database.py:324-373`

12. **Processing queue entry is removed**
    - File successfully processed, no longer needs tracking
    - Evidence: `@src/database.py:945-975`

13. **Notification shown** (if background mode)
    - Toast: "Organized: invoice_acme_2024.pdf → Financial/Invoices"
    - Evidence: `@src/tray_icon.py:207-230`

### Data Changes

| Location | Before | After |
|----------|--------|-------|
| Inbox folder | Contains file | Empty |
| Category folder | - | Contains file |
| `documents` table | No record | New record with metadata |
| `activity_log` table | - | New "processed" entry |
| `processing_queue` table | Has entry | Entry deleted |

### What Can Go Wrong

| Error | What Happens | Recovery |
|-------|--------------|----------|
| **File locked** | Can't read file (still being written) | Retried 3 times, 10 seconds apart (`@src/watcher.py:506-526`) |
| **LMStudio not running** | AI classification fails | Falls back to filename-based classification (`@src/classifier.py:129-141`) |
| **LMStudio timeout** | Request takes too long | Returns fallback result, file goes to Miscellaneous |
| **Invalid JSON from AI** | Can't parse response | 5-layer repair attempted, then filename fallback (`@src/llm_client.py:669-911`) |
| **Sift crashes mid-process** | File stuck in queue | On restart, file re-processed (`@src/database.py:1045-1065`) |
| **Disk full** | Can't move file | Error logged, file stays in Inbox |

---

## Flow 2: Review and Reassign a Document

**Goal**: Correct a document that was misclassified or had low confidence.

### Steps

1. **Open the dashboard**
   - Go to http://localhost:5000 in your browser

2. **Find documents needing review**
   - Look at "Needs Review" section
   - Or search for a specific document
   - Evidence: `@src/dashboard.py:1815-1819`

3. **Click on a document to see details**
   - Shows: current location, confidence, AI reasoning
   - Evidence: Dashboard JavaScript

4. **Click "Reassign" button**
   - Modal opens with category selection

5. **Select the correct category and subcategory**
   - Dropdown shows all available folders
   - Evidence: `@src/dashboard.py:1820-1837`

6. **Confirm the reassignment**
   - POST request sent to `/api/reassign`
   - Evidence: `@src/dashboard.py:1853-1930`

7. **File is physically moved**
   - From old location to new category folder
   - Evidence: `@src/dashboard.py:1889-1894`

8. **Correction is recorded for learning**
   - Stores: original category → corrected category + document info
   - Future similar documents will use this as guidance
   - Evidence: `@src/database.py:1107-1160`

9. **Document status updated**
   - Changed from `needs_review` to `manual_override`
   - Evidence: `@src/dashboard.py:1923`

10. **Activity log entry created**
    - Action: "reassigned"
    - Old path and new path recorded
    - Evidence: `@src/database.py:375-390`

### Data Changes

| Location | Before | After |
|----------|--------|-------|
| Old category folder | Contains file | File removed |
| New category folder | - | Contains file |
| `documents` table | status: `needs_review` | status: `manual_override`, new path |
| `activity_log` table | - | New "reassigned" entry |
| `classification_corrections` table | - | New correction record |

### What Can Go Wrong

| Error | What Happens | Recovery |
|-------|--------------|----------|
| **File was deleted** | Can't find source file | Error shown in dashboard |
| **Target folder doesn't exist** | - | Created automatically (`@src/dashboard.py:2040`) |
| **Filename collision** | File with same name exists | Counter added: `file_1.pdf`, `file_2.pdf` (`@src/dashboard.py:2043-2047`) |
| **Permission denied** | Can't write to folder | Error shown, operation fails |

---

## Flow 3: Search for a Document

**Goal**: Find a specific document by content, name, or category.

### Steps

1. **Open the dashboard**
   - Go to http://localhost:5000

2. **Type your search query**
   - Examples: "tax 2023", "invoice acme", "medical"
   - Evidence: Dashboard search box

3. **Search is processed**
   - Query sent to `/api/search`
   - Evidence: `@src/dashboard.py:2097-2143`

4. **Query is optionally enhanced by AI**
   - If LMStudio available, AI may extract: category hints, search terms
   - Evidence: `@src/dashboard.py:2103-2115`

5. **Database search executes**
   - Three-tier search strategy:
     1. Exact category match (if category hint found)
     2. Full-text search (FTS5 with BM25 ranking)
     3. LIKE fallback (substring matching)
   - Evidence: `@src/database.py:706-808`

6. **Results returned with relevance scores**
   - Higher score = better match
   - Evidence: `@src/database.py:785-796`

7. **Results displayed in dashboard**
   - Shows: filename, category, confidence, date
   - Thumbnails if available

8. **Click a result to see details**
   - Or click "Open Folder" to go to file location

### Data Changes

None - search is read-only.

### What Can Go Wrong

| Error | What Happens | Recovery |
|-------|--------------|----------|
| **No results** | Nothing matches query | Try broader terms |
| **FTS5 error** | Full-text search fails | Falls back to LIKE search (`@src/database.py:810-845`) |
| **Slow search** | Many documents to scan | Consider: FTS index may need rebuilding |

---

## Flow 4: Undo a Recent Action

**Goal**: Reverse a classification you made by mistake.

### Steps

1. **Open the dashboard**
   - Go to http://localhost:5000

2. **Click "Undo" button**
   - Or use the "Undo Last" option
   - Evidence: `@src/dashboard.py:1974-1983`

3. **System finds the most recent undoable action**
   - Looks for `processed` or `reassigned` actions
   - Must be within 24 hours
   - Evidence: `@src/database.py:660-697`

4. **Action is validated**
   - Checks if original file path is still valid
   - Evidence: `@src/database.py:600-658`

5. **File is moved back to original location**
   - Physical file move
   - Evidence: `@src/database.py:637-644`

6. **Document status updated**
   - Changed to `undone`
   - Path restored to original
   - Evidence: `@src/database.py:648-650`

7. **Activity log entry created**
   - Action: "undone"
   - Evidence: `@src/database.py:652-655`

8. **Dashboard refreshes**
   - Shows success message

### Data Changes

| Location | Before | After |
|----------|--------|-------|
| Category folder | Contains file | File removed |
| Original location | - | File restored |
| `documents` table | Current status | status: `undone`, original path |
| `activity_log` table | - | New "undone" entry |

### What Can Go Wrong

| Error | What Happens | Recovery |
|-------|--------------|----------|
| **Nothing to undo** | No recent actions found | Check if actions are >24 hours old |
| **Original location doesn't exist** | Folder was deleted | May need manual intervention |
| **File was modified** | Content changed since processing | Undo still works on location |
| **Action already undone** | Can't undo twice | Skip to next action |

---

## Flow 5: Pause and Resume Processing

**Goal**: Temporarily stop Sift from processing files.

### Steps

1. **Right-click the system tray icon**
   - Sift icon in your taskbar (Windows) or menu bar (macOS)

2. **Click "Pause Processing"**
   - Evidence: `@src/tray_icon.py:127-129`

3. **Processing pauses**
   - `_paused` flag set to `True`
   - Icon color changes to yellow
   - Evidence: `@src/tray_icon.py:195-200`

4. **Main loop respects pause**
   - Processing continues but files queue up
   - Evidence: `@src/main.py:193`

5. **Files dropped in Inbox are queued**
   - Detection continues, processing waits
   - Evidence: Queues still accept files

6. **Right-click tray icon again**

7. **Click "Resume Processing"**
   - Menu label changes dynamically
   - Evidence: `@src/tray_icon.py:128`

8. **Processing resumes**
   - `_paused` flag set to `False`
   - Icon returns to green
   - Queued files start processing

### Data Changes

| State | Before Pause | During Pause | After Resume |
|-------|--------------|--------------|--------------|
| `_paused` flag | `False` | `True` | `False` |
| Icon color | Green | Yellow | Green |
| Queue | Processing | Growing | Processing |

### What Can Go Wrong

| Error | What Happens | Recovery |
|-------|--------------|----------|
| **Tray icon crashed** | Can't access menu | Restart Sift |
| **Long pause with many files** | Large queue builds up | Resume will process all, may take time |

---

## Flow 6: Process a Single File Manually

**Goal**: Classify one specific file without using the Inbox.

### Steps

1. **Open command line**
   - Windows: Command Prompt or PowerShell
   - Navigate to Sift folder

2. **Run with --file option**
   ```
   python src/main.py --file "C:\path\to\document.pdf"
   ```
   - Evidence: `@src/main.py:644-648`

3. **Sift initializes**
   - Loads config, connects to LMStudio
   - Evidence: `@src/main.py:539-570`

4. **Single file is processed**
   - Same pipeline as automatic processing
   - Evidence: `@src/main.py:429-452`

5. **Result displayed in console**
   - Shows: category, confidence, destination

6. **Sift exits**
   - No watcher started, just one-shot processing

### Data Changes

Same as Flow 1 (Automatic Classification).

### What Can Go Wrong

| Error | What Happens | Recovery |
|-------|--------------|----------|
| **File not found** | Error message | Check path is correct |
| **Unsupported format** | Classification by filename only | Expected for some formats |
| **LMStudio not running** | Fallback classification | Start LMStudio first |

---

## Flow 7: Batch Process Existing Files

**Goal**: Process all files currently in your Inbox.

### Steps

1. **Place files in Inbox**
   - Copy/move multiple documents to your Inbox folder

2. **Run with --scan-only option**
   ```
   python src/main.py --scan-only
   ```
   - Evidence: `@src/main.py:650-675`

3. **Sift scans Inbox**
   - Finds all supported files
   - Evidence: `@src/watcher.py:627-679`

4. **Files queued for processing**
   - All files added to queue

5. **Processing begins**
   - Files processed one at a time
   - Progress shown in console

6. **Each file classified and moved**
   - Same pipeline as automatic processing

7. **Sift exits when done**
   - All files processed, no watcher started

### Data Changes

Same as Flow 1, but for multiple files.

### What Can Go Wrong

| Error | What Happens | Recovery |
|-------|--------------|----------|
| **LMStudio overwhelmed** | Timeouts increase | Sift adds delays between files (`@src/watcher.py:573-580`) |
| **Many failures** | Multiple fallback classifications | Review in dashboard later |

---

## Flow 8: Batch Reassign Multiple Documents

**Goal**: Move several documents to a new category at once.

### Steps

1. **Open the dashboard**
   - Go to http://localhost:5000

2. **Select multiple documents**
   - Use checkboxes or select-all

3. **Click "Batch Actions"**

4. **Choose "Reassign"**

5. **Select target category**
   - Pick category and optionally subcategory
   - Evidence: `@src/dashboard.py:2017-2069`

6. **Confirm batch operation**
   - POST to `/api/batch` with action: "reassign"
   - Evidence: `@src/dashboard.py:1985-2095`

7. **Each document processed**
   - Files moved one by one
   - Corrections recorded for each
   - Evidence: `@src/dashboard.py:2025-2066`

8. **Results displayed**
   - Success count, failure count, any errors

### Data Changes

For each document:
| Location | Before | After |
|----------|--------|-------|
| Old folder | Contains file | File removed |
| New folder | - | Contains file |
| `documents` table | Old category | New category, `manual_override` |
| `classification_corrections` table | - | New correction (if category changed) |

### What Can Go Wrong

| Error | What Happens | Recovery |
|-------|--------------|----------|
| **Some files missing** | Those fail, others succeed | Check error list in results |
| **Permission issues** | Some moves fail | May need admin rights |
| **Category doesn't exist** | Created automatically | Works as expected |

---

## Flow 9: Check System Health

**Goal**: Verify Sift is properly configured and can connect to LMStudio.

### Steps

1. **Open command line**

2. **Run with --check option**
   ```
   python src/main.py --check
   ```
   - Evidence: `@src/main.py:572-598`

3. **Configuration is validated**
   - Checks if settings.yaml exists and is valid
   - Evidence: `@src/main.py:552-557`

4. **LMStudio connection tested**
   - Pings http://localhost:1234
   - Checks if a model is loaded
   - Evidence: `@src/main.py:313-346`

5. **Results displayed**
   - Success: "Configuration valid, LMStudio connected"
   - Failure: Specific error message

6. **Exit code returned**
   - 0 = success
   - 1 = failure

### Data Changes

None - check is read-only.

### What Can Go Wrong

| Error | What Happens | Message |
|-------|--------------|---------|
| **Config missing** | Can't find settings.yaml | "Configuration error: Failed to load..." |
| **Config invalid** | YAML syntax error | "Configuration error: ..." |
| **LMStudio not running** | Can't connect | "Could not connect to LMStudio" |
| **No model loaded** | LMStudio running but empty | "No models loaded in LMStudio" |

---

## Flow 10: Create Folder Structure

**Goal**: Set up the initial folder structure without processing files.

### Steps

1. **Open command line**

2. **Run with --create-folders option**
   ```
   python src/main.py --create-folders
   ```
   - Evidence: `@src/main.py:600-605`

3. **Essential folders created**
   - Base Sift folder
   - Inbox folder
   - Needs_Review folder
   - Temp folder
   - Evidence: `@src/folder_organizer.py:358-395`

4. **Category folders NOT created**
   - Only created when needed (when a document is classified into them)
   - This respects any manual changes you've made

5. **Sift exits**

### Data Changes

| Location | Before | After |
|----------|--------|-------|
| Base folder | May not exist | Created |
| Inbox folder | May not exist | Created |
| Needs_Review folder | May not exist | Created |
| Temp folder | May not exist | Created |

### What Can Go Wrong

| Error | What Happens | Recovery |
|-------|--------------|----------|
| **No write permission** | Folder creation fails | Run as admin or change base path |
| **Path too long** | Windows path limit | Use shorter path in config |

---

## Flow 11: Enable/Disable Auto-Start (Windows)

**Goal**: Have Sift start automatically when you log in.

### Steps (Enable)

1. **Open command line**

2. **Run with --enable-startup option**
   ```
   python src/main.py --enable-startup
   ```
   - Evidence: `@src/main.py:607-618`

3. **Startup shortcut created**
   - VBS script created in Windows Startup folder
   - Evidence: `@src/tray_icon.py:269-330`

4. **Confirmation displayed**
   - "Startup enabled"

### Steps (Disable)

1. **Run with --disable-startup option**
   ```
   python src/main.py --disable-startup
   ```
   - Evidence: `@src/main.py:619-625`

2. **Startup shortcut removed**
   - Evidence: `@src/tray_icon.py:333-350`

### Steps (Check Status)

1. **Run with --startup-status option**
   ```
   python src/main.py --startup-status
   ```
   - Evidence: `@src/main.py:626-630`

### Data Changes

| Action | Windows Startup Folder |
|--------|------------------------|
| Enable | VBS script added |
| Disable | VBS script removed |

### What Can Go Wrong

| Error | What Happens | Recovery |
|-------|--------------|----------|
| **Not Windows** | Feature not available | Only works on Windows |
| **Permission denied** | Can't write to Startup folder | Run as admin |

---

## Flow Summary Table

| Flow | Trigger | Key Files | Data Modified |
|------|---------|-----------|---------------|
| 1. Auto Classification | Drop file in Inbox | watcher, classifier, organizer | documents, activity_log |
| 2. Reassign Document | Dashboard click | dashboard, database | documents, corrections |
| 3. Search | Dashboard search | dashboard, database | None (read-only) |
| 4. Undo Action | Dashboard click | dashboard, database | documents, activity_log |
| 5. Pause/Resume | Tray icon click | tray_icon, main | In-memory flag |
| 6. Single File | CLI --file | main, classifier | documents, activity_log |
| 7. Batch Scan | CLI --scan-only | main, watcher | documents, activity_log |
| 8. Batch Reassign | Dashboard batch | dashboard | documents, corrections |
| 9. Health Check | CLI --check | main, llm_client | None (read-only) |
| 10. Create Folders | CLI --create-folders | main, organizer | Filesystem |
| 11. Auto-Start | CLI --enable-startup | main, tray_icon | Windows Startup |

---

## Error Recovery Quick Reference

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Files stuck in Inbox | LMStudio not running | Start LMStudio, load a model |
| All files going to Miscellaneous | AI returning errors | Check `--verbose` logs, verify LMStudio |
| Dashboard not loading | Port 5000 in use | Restart Sift (port cleanup built-in) |
| Slow processing | Large files or weak hardware | Use "fast" model profile |
| Can't undo | Action >24 hours old | Manual file move required |
| Tray icon missing | pystray not installed | Install with `pip install pystray` |
