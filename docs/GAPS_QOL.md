# Sift Quality of Life Gaps

This document identifies friction points in the Sift user experience and suggests improvements. Each item includes the problem, why it matters, a suggested solution, effort estimate, and evidence from the codebase.

**Effort Scale**:
- **S (Small)**: < 1 day, localized change, low risk
- **M (Medium)**: 1-3 days, multiple files, moderate testing needed
- **L (Large)**: 1+ week, architectural changes, significant testing needed

---

## 1. Onboarding

### ONB-1: No First-Run Experience

**Problem**: When a user runs Sift for the first time, they're dropped directly into processing mode with no guidance. There's no welcome message, no explanation of what's happening, and no confirmation that setup is correct.

**Why it matters**: Users don't know if Sift is working correctly. They may have misconfigured something and not realize it until documents start going to wrong folders. First impressions determine whether users continue or abandon the tool.

**Suggested solution**: Add a first-run detection that:
1. Checks if `data/documents.db` exists (new user indicator)
2. Shows a welcome message with quick setup checklist
3. Runs `--check` automatically and reports results
4. Offers to process a sample document to demonstrate functionality

**Effort**: M (Medium)
- Detect first run: Check for empty database
- Add welcome flow to `@src/main.py:539-570`
- Create sample document in `assets/` folder

**Evidence**: No first-run logic exists. `@src/main.py` goes directly to configuration loading with no user state awareness.

---

### ONB-2: Configuration Requires Manual Path Editing

**Problem**: The default `settings.yaml` contains placeholder paths like `C:\\Users\\{username}\\Documents\\Sift\\Inbox`. Users must manually replace `{username}` with their actual username before Sift will work.

**Why it matters**: This is an immediate blocker. If a user doesn't notice or understand the placeholder, Sift fails on first run with a confusing "path not found" error. Every user must do this step.

**Suggested solution**:
1. Auto-detect home directory using Python's `Path.home()`
2. Create default paths automatically on first run
3. Offer interactive path selection during setup
4. Or: prompt user to confirm/change paths before first processing

**Effort**: S (Small)
- Modify `@src/config.py` to expand `~` and `{username}` placeholders
- Add `os.path.expanduser()` calls during config loading

**Evidence**: `config/settings.default.yaml:11-15` shows hardcoded placeholders. `@src/config.py` loads paths as-is without expansion.

---

### ONB-3: No Sample Documents for Testing

**Problem**: After setup, users must find their own documents to test with. They don't know what to expect or what "success" looks like. If classification seems wrong, they can't tell if it's misconfiguration or expected behavior.

**Why it matters**: Users need a known-good test case to verify setup. Without it, they're debugging in the dark. A successful first classification builds confidence.

**Suggested solution**:
1. Include 3-5 sample documents (invoice, receipt, medical form, contract, personal letter)
2. Add `--demo` flag that processes samples and shows expected results
3. Dashboard could show "Try with sample documents" button

**Effort**: S (Small)
- Create sample PDFs (can be mock/generated)
- Add to `assets/samples/` folder
- Add `--demo` argument to `@src/main.py`

**Evidence**: No `assets/` or `samples/` directory exists. No demo mode in argument parser (`@src/main.py:455-536`).

---

### ONB-4: LMStudio Setup Not Validated

**Problem**: Sift requires LMStudio running with a model loaded, but there's no clear validation during setup. Users might install everything, run Sift, and wonder why nothing happens (because LMStudio isn't running or has no model loaded).

**Why it matters**: LMStudio is the #1 external dependency. If it's not working, Sift falls back to filename-based classification silently, giving poor results without explaining why.

**Suggested solution**:
1. Add `--setup-check` that specifically validates LMStudio:
   - Is LMStudio running?
   - Is a model loaded?
   - Which model? Is it compatible?
   - What's the expected speed?
2. Show this automatically on first run
3. Provide clear remediation steps for each failure

**Effort**: S (Small)
- Extend `--check` logic in `@src/main.py:572-598`
- Add model listing via `@src/llm_client.py:359-378`
- Improve error messages

**Evidence**: `--check` exists (`@src/main.py:572-598`) but only reports pass/fail. Doesn't guide user on what to do if it fails.

---

### ONB-5: No Installation Verification

**Problem**: `install.bat` installs dependencies but doesn't verify the full system works. A user can complete installation successfully but still have a broken setup (missing Poppler, wrong Python version, etc.).

**Why it matters**: Users think installation succeeded, then hit cryptic errors later. The gap between "installed" and "working" is confusing.

**Suggested solution**:
1. Add verification step to `install.bat` that runs `python src/main.py --check`
2. Check for Poppler in PATH
3. Check Python version
4. Report clear pass/fail for each requirement

**Effort**: S (Small)
- Modify `install.bat` to add verification section
- Already have most checks in `@src/document_processor.py:109-159`

**Evidence**: `install.bat` runs pip install and basic import checks, but doesn't verify runtime dependencies like Poppler.

---

## 2. UX Clarity

### UX-1: Confidence Scores Unexplained

**Problem**: Documents show confidence scores like "0.72" or "85%" but users don't know what this means. Is 0.72 good? Why did this score happen? What's the threshold?

**Why it matters**: Users can't make informed decisions about whether to trust classifications or adjust settings. They don't understand why some documents go to Needs_Review.

**Suggested solution**:
1. Add tooltip/help text explaining confidence: "0.7+ = auto-filed, below = needs review"
2. Show confidence as colored indicator (green/yellow/red)
3. Show the threshold setting so users understand the cutoff
4. Add "Why this score?" expandable with AI reasoning

**Effort**: S (Small)
- Update dashboard HTML/CSS in `@src/dashboard.py:27-1760`
- Reasoning already exists in `ClassificationResult.reasoning`

**Evidence**: Dashboard shows raw confidence number (`@src/dashboard.py` templates). `@src/classifier.py:630-632` defines threshold but it's not shown to users.

---

### UX-2: No Real-Time Processing Feedback

**Problem**: When processing a batch of files, users see the dashboard statistics but don't know what's currently happening. Is Sift stuck? Is it processing? Which file is it on?

**Why it matters**: Users feel anxious during batch processing. They might restart Sift thinking it's frozen, potentially causing issues.

**Suggested solution**:
1. Add "Currently processing: filename.pdf" to dashboard
2. Show processing queue depth
3. Add progress bar for batch operations
4. Show estimated time remaining

**Effort**: M (Medium)
- `@src/watcher.py:723-751` already tracks `_current_file` and batch stats
- Need to expose via `/api/status` and update dashboard UI
- Add polling/WebSocket for real-time updates

**Evidence**: `get_batch_status()` at `@src/watcher.py:723-751` tracks this data but dashboard doesn't poll it frequently.

---

### UX-3: Classification Reasoning Hidden

**Problem**: The AI provides reasoning for each classification, but it's not prominently displayed. Users see the category but not *why* that category was chosen.

**Why it matters**: Understanding "why" helps users trust the system and identify when to correct it. It also helps debug misclassifications.

**Suggested solution**:
1. Show reasoning on hover or click in dashboard
2. Add "View AI reasoning" button for each document
3. Include reasoning in Needs_Review view (where it matters most)

**Effort**: S (Small)
- Reasoning stored in database (`@src/database.py:103`)
- Just needs UI exposure in dashboard

**Evidence**: `reasoning` field populated by LLM (`@src/llm_client.py:780-783`) and stored in database, but dashboard doesn't show it prominently.

---

### UX-4: System Tray States Undocumented

**Problem**: The system tray icon changes color (green, yellow, red) but users don't know what each color means. Is yellow "paused" or "warning"?

**Why it matters**: Users can't diagnose issues at a glance. They might ignore a red icon not knowing it indicates a problem.

**Suggested solution**:
1. Add tooltip showing current state ("Running", "Paused", "Error: LMStudio disconnected")
2. Document icon states in help/README
3. Consider adding notification for state changes

**Effort**: S (Small)
- Modify `@src/tray_icon.py:139-141` to set detailed tooltip
- Colors defined at `@src/tray_icon.py:148-178`

**Evidence**: Icon created with generic tooltip "Sift - Running" (`@src/tray_icon.py:139`). Colors set but not documented.

---

### UX-5: Search Results Don't Show Match Reason

**Problem**: When searching for documents, results are returned but users don't see *why* each result matched. Did it match the filename? Content? Category?

**Why it matters**: Users can't refine searches effectively. They might think search is broken when it's matching on content they didn't expect.

**Suggested solution**:
1. Highlight matching terms in results
2. Show which field matched (filename, content, category)
3. Show relevance score with explanation

**Effort**: M (Medium)
- FTS5 can return match info but `@src/database.py:706-808` doesn't extract it
- Need to modify search query and result formatting

**Evidence**: `@src/database.py:758-796` uses BM25 ranking but doesn't return match snippets or highlight terms.

---

### UX-6: Needs_Review Purpose Not Clear

**Problem**: Documents appear in "Needs_Review" folder but users don't understand why or what they're supposed to do about it.

**Why it matters**: Users might ignore the folder, defeating its purpose. Or they might be confused about whether these documents were processed at all.

**Suggested solution**:
1. Add explanation banner in dashboard: "These documents need your review because AI confidence was below 70%"
2. Show what the AI's best guess was
3. Add quick actions: "Accept AI suggestion" or "Move to..."

**Effort**: S (Small)
- Add explanatory text to dashboard review section
- Data already available

**Evidence**: Review folder mentioned but not explained in dashboard (`@src/dashboard.py:1815-1819`).

---

## 3. Defaults

### DEF-1: Default Paths Require Editing

**Problem**: Already covered in ONB-2, but specifically: default `settings.yaml` has paths that won't work without editing.

**Why it matters**: Every single user hits this. Zero chance of "just works" out of the box.

**Suggested solution**: Use expandable paths like `~/Documents/Sift/Inbox` and auto-expand on load.

**Effort**: S (Small)

**Evidence**: `config/settings.default.yaml:11-15`

---

### DEF-2: Default Model May Not Be Loaded

**Problem**: Config defaults to `qwen/qwen3-4b` but user may have loaded a different model in LMStudio. Sift tries to use the configured model identifier for prompts but LMStudio uses whatever is loaded.

**Why it matters**: Confusion when model behavior doesn't match profile settings. User thinks they're using "accurate" profile but LMStudio has a different model loaded.

**Suggested solution**:
1. On startup, query LMStudio for loaded model
2. Warn if loaded model doesn't match configured profile
3. Offer to auto-detect and adjust settings

**Effort**: S (Small)
- `@src/llm_client.py:359-378` can get loaded models
- Add comparison in startup check

**Evidence**: `get_loaded_models()` exists but isn't used to validate configuration.

---

### DEF-3: Processing Delay May Be Wrong

**Problem**: Default 2-second delay before processing (`processing_delay_seconds: 2`) assumes files are small and copy quickly. Large files might still be copying when processing starts.

**Why it matters**: Processing a partially-copied file causes errors or incomplete text extraction.

**Suggested solution**:
1. Instead of fixed delay, check file size stability (file size unchanged for 2 seconds)
2. Or: increase default to 5 seconds with explanation
3. Or: add file-size-based delay (larger files = longer wait)

**Effort**: M (Medium)
- Modify `@src/watcher.py:88-92` delay logic
- Add file size monitoring

**Evidence**: Fixed delay at `@src/watcher.py:298`. No file stability check.

---

### DEF-4: Default Categories Too Generic

**Problem**: Default categories (Financial, Medical, Legal, etc.) are comprehensive but may not match user's actual document types. A user who mostly has recipes and hobby documents has no relevant defaults.

**Why it matters**: Users see AI confidently put documents in wrong categories because those were the only options.

**Suggested solution**:
1. Offer category presets: "Professional", "Personal", "Small Business", "Custom"
2. Or: scan user's existing folder structure and suggest matching categories
3. Or: learn categories from first batch of documents

**Effort**: M (Medium)
- Add preset configs in `config/presets/`
- Add selection during first run

**Evidence**: `config/settings.default.yaml:67-160` shows one-size-fits-all categories.

---

## 4. Error Messages

### ERR-1: LMStudio Connection Failure Unhelpful

**Problem**: When LMStudio isn't running, error message says "Could not connect to LMStudio" but doesn't explain what to do.

**Why it matters**: Users don't know: Is LMStudio installed? Did I start it? Do I need to load a model? What port should it be on?

**Suggested solution**:
Improve error message to:
```
Could not connect to LMStudio at localhost:1234.

To fix this:
1. Open LMStudio application
2. Load a model (Recommended: qwen/qwen3-4b)
3. Go to Developer tab → Start Server
4. Ensure it's running on port 1234

Then run: python src/main.py --check
```

**Effort**: S (Small)
- Modify `@src/main.py:336-346`

**Evidence**: Current error at `@src/main.py:338-346` is technical, not actionable.

---

### ERR-2: JSON Parsing Failures Silent

**Problem**: When LLM returns malformed JSON, Sift tries 5 repair strategies then falls back silently. Users don't know this happened.

**Why it matters**: Users see documents going to Miscellaneous and don't know why. They can't tell if it's a model problem, prompt problem, or expected behavior.

**Suggested solution**:
1. Log a clear warning when JSON repair is needed
2. In dashboard, show "Classification method: AI" vs "Classification method: Fallback"
3. Consider showing "AI response was unclear, used filename-based classification"

**Effort**: S (Small)
- Add logging in `@src/llm_client.py:669-911`
- Modify `ClassificationResult` to include classification method

**Evidence**: Silent fallback at `@src/llm_client.py:905-911`. No user-facing indication.

---

### ERR-3: Timeout Errors Don't Suggest Solutions

**Problem**: When LLM times out, error says "Request timed out after 90s" but doesn't suggest switching to faster model or increasing timeout.

**Why it matters**: Users don't know they can switch profiles or adjust settings. They might think Sift is broken.

**Suggested solution**:
```
LLM request timed out after 90 seconds.

Suggestions:
- Switch to "fast" profile for quicker responses
- Or increase timeout in config: llm.timeout_seconds
- Large documents may need "accurate" profile with higher timeout
```

**Effort**: S (Small)
- Modify error handling at `@src/llm_client.py:662-667`

**Evidence**: Timeout error at `@src/llm_client.py:662-663` has no remediation suggestions.

---

### ERR-4: Permission Errors Not Actionable

**Problem**: File permission errors (can't move file, can't write to folder) show Python exception but don't explain what to do.

**Why it matters**: Users might have antivirus blocking, folder permissions wrong, or file open in another program. They need specific guidance.

**Suggested solution**:
Improve error messages:
- "Permission denied" → "Cannot move file. Check: Is it open in another program? Does Sift have write access to the destination folder?"
- "File in use" → "File is locked by another program. Close it and try again, or wait for automatic retry."

**Effort**: S (Small)
- Catch specific exceptions in `@src/folder_organizer.py:122-124`

**Evidence**: Generic exception handling at `@src/folder_organizer.py:122-124` and `@src/main.py:290-311`.

---

### ERR-5: Config Validation Errors Vague

**Problem**: Invalid YAML configuration shows parser errors that are hard to understand ("expected mapping for merge, found scalar" means nothing to most users).

**Why it matters**: Users edit YAML, make a typo, and get a wall of text that doesn't point to the problem.

**Suggested solution**:
1. Catch YAML errors and translate to user-friendly messages
2. Show line number and what was expected
3. Offer to validate config: `python src/main.py --validate-config`

**Effort**: S (Small)
- Add YAML validation with better error messages in `@src/config.py:311-318`

**Evidence**: Raw exception at `@src/config.py:317-318`.

---

## 5. Config

### CFG-1: No GUI for Configuration

**Problem**: All configuration requires editing YAML files. Users can't change settings from the dashboard.

**Why it matters**: Non-technical users (Persona 3 from Product Brief) can't customize Sift. Even technical users find it tedious.

**Suggested solution**:
Add Settings page to dashboard with:
- Path configuration (with folder browser)
- Confidence threshold slider
- Model profile selector (already exists as dropdown)
- Category management (add/edit/delete)
- Custom rule builder (visual, not YAML)

**Effort**: L (Large)
- New dashboard route and HTML
- Config update API endpoints
- File writing from dashboard
- Validation logic

**Evidence**: No `/settings` route in `@src/dashboard.py`. All config in YAML files.

---

### CFG-2: Custom Rules Require Regex Knowledge

**Problem**: Creating custom rules requires writing regex patterns. Most users don't know regex.

**Why it matters**: The rules engine is powerful but inaccessible. Users who would benefit can't use it.

**Suggested solution**:
1. Add visual rule builder: "If filename contains [___] then move to [dropdown]"
2. Provide common pattern templates: "Bank statements from Chase", "Invoices from Vendor"
3. Test rule against existing documents before enabling

**Effort**: M (Medium)
- Visual rule builder in dashboard
- Pattern templates
- Rule testing endpoint

**Evidence**: Rules at `@src/rules_engine.py:67-111` support regex but no UI exists.

---

### CFG-3: No Config Validation Before Run

**Problem**: Sift loads config and fails later if something is wrong. No upfront validation that all paths exist, all settings are valid ranges, etc.

**Why it matters**: Users run Sift, process some files, then hit an error because a path was wrong. Should fail fast with clear message.

**Suggested solution**:
1. Add comprehensive validation in `Config.load()`
2. Check: paths exist or can be created, threshold in 0-1 range, extensions have dots, etc.
3. Add `--validate-config` command

**Effort**: S (Small)
- Add validation methods to `@src/config.py`
- List all checks with clear error messages

**Evidence**: Minimal validation in `@src/config.py`. Paths not checked until accessed.

---

### CFG-4: Can't Test Rules Without Enabling

**Problem**: Users create a rule but can't test it without processing real documents. If the rule is wrong, documents might be misclassified.

**Why it matters**: Fear of misconfiguration prevents users from using rules. No safe way to experiment.

**Suggested solution**:
1. Add `--test-rules "filename.pdf"` command that shows what rules would match
2. Dashboard: "Test this rule" button that shows matching historical documents
3. "Dry run" mode that shows where files would go without moving them

**Effort**: S (Small)
- Add test endpoint to `@src/rules_engine.py`
- Add CLI argument

**Evidence**: No rule testing capability exists.

---

## 6. Performance

### PERF-1: No Progress Indication for OCR

**Problem**: OCR processing can take 30+ seconds per page. Users see no progress and may think Sift is frozen.

**Why it matters**: OCR is common for scanned documents. Users need feedback that something is happening.

**Suggested solution**:
1. Log "OCR processing page 1/3..." messages
2. Update dashboard status during OCR
3. Show estimated time for OCR documents

**Effort**: S (Small)
- Add progress logging to `@src/document_processor.py:276-310`

**Evidence**: OCR at `@src/document_processor.py:276-310` has no progress output.

---

### PERF-2: No Parallel Processing Option

**Problem**: Documents are processed one at a time. A batch of 100 documents takes 100x single-document time, even if CPU/GPU could handle more.

**Why it matters**: Initial "catch up" processing of existing documents is painfully slow. Users with large backlogs may give up.

**Suggested solution**:
1. Add `--parallel N` option for batch processing
2. Use thread pool for document extraction (CPU-bound)
3. Note: LLM calls may need to stay serial due to LMStudio limitations

**Effort**: M (Medium)
- Modify `@src/watcher.py:466-583` queue processing
- Add thread pool for extraction
- Handle concurrent database writes

**Evidence**: Serial processing in `@src/watcher.py:466-583` with explicit delays between files.

---

### PERF-3: Large Documents May Timeout

**Problem**: Default timeout (90s) may not be enough for large documents with "accurate" profile. Document gets fallback classification without explanation.

**Why it matters**: Users trying to classify complex documents get poor results without understanding why.

**Suggested solution**:
1. Estimate document complexity before processing (page count, text length)
2. Adjust timeout dynamically based on document size
3. Warn user if document seems too large for current profile

**Effort**: S (Small)
- Add timeout scaling based on page count
- Modify `@src/llm_client.py:644-667`

**Evidence**: Fixed timeout at `@src/llm_client.py:647`. No document-based adjustment.

---

### PERF-4: No Hardware Guidance for Model Selection

**Problem**: Users don't know which model profile to choose based on their hardware. Someone with 8GB RAM might load a 7B model and have terrible performance.

**Why it matters**: Wrong model choice = bad experience. Users blame Sift when it's a model/hardware mismatch.

**Suggested solution**:
1. Document hardware requirements for each profile
2. Add `--recommend-profile` that checks available RAM/GPU
3. Show model memory requirements in dashboard profile selector

**Effort**: S (Small)
- Add documentation
- System memory check is easy to add

**Evidence**: Profiles at `@src/llm_client.py` don't document hardware requirements. No system capability detection.

---

## 7. Reliability

### REL-1: No Automated Test Suite

**Problem**: Zero automated tests exist. All verification is manual.

**Why it matters**:
- Refactoring is risky (might break things unknowingly)
- Contributors can't verify their changes
- Regressions can ship undetected
- Complex code (JSON parsing, crash recovery) has no safety net

**Suggested solution**:
1. Add pytest as dev dependency
2. Priority test targets:
   - `@src/llm_client.py:669-911` (JSON parsing - complex)
   - `@src/database.py` (crash recovery)
   - `@src/rules_engine.py` (rule matching)
3. Add CI test run in GitHub Actions

**Effort**: L (Large)
- Create `tests/` structure
- Write tests for critical paths
- Set up CI integration

**Evidence**: No `tests/` directory, no `pytest.ini`, no test files.

---

### REL-2: Database Migrations Ad-Hoc

**Problem**: Database schema changes use try/except ALTER TABLE statements. If migration fails partially, database could be in inconsistent state.

**Why it matters**: Users upgrading Sift might hit database errors. No way to rollback.

**Suggested solution**:
1. Add proper migration system (alembic or simple version table)
2. Track schema version in database
3. Run migrations on startup with rollback capability

**Effort**: M (Medium)
- Add migration framework
- Convert existing ALTER statements to versioned migrations

**Evidence**: Ad-hoc migrations at `@src/database.py:112-118`.

---

### REL-3: Orphaned Vision Model Code

**Problem**: `@src/document_processor.py:553-689` has complete vision model infrastructure (image conversion, base64 encoding) that's never called. It could rot without anyone noticing.

**Why it matters**: Dead code is technical debt. If someone tries to use it, they'll find it doesn't work with current architecture.

**Suggested solution**:
1. Either: Remove the code if vision isn't planned
2. Or: Wire it up and test it
3. Or: Mark clearly as "experimental/incomplete" with TODO

**Effort**: S (Small) to remove, M (Medium) to complete

**Evidence**: `process_document()` at `@src/document_processor.py:555-588` never called from `@src/classifier.py` or `@src/main.py`.

---

### REL-4: Port Cleanup May Fail Silently

**Problem**: Port cleanup (`@src/main.py:348-427`) uses subprocess calls to `netstat` and `taskkill`. If these fail, the error is logged as debug and ignored.

**Why it matters**: User might have zombie dashboard processes and not know why port 5000 isn't working.

**Suggested solution**:
1. Warn user if port cleanup fails
2. Suggest manual cleanup: "Port 5000 in use. Run: netstat -ano | findstr 5000"
3. Offer alternative port

**Effort**: S (Small)
- Improve error handling at `@src/main.py:348-427`

**Evidence**: Silent `except` blocks at `@src/main.py:404, 424`.

---

## 8. Docs

### DOC-1: README Too Long

**Problem**: README.md is 450+ lines covering everything from installation to troubleshooting. Users struggle to find what they need.

**Why it matters**: First-time users are overwhelmed. Experienced users can't find specific info quickly.

**Suggested solution**:
1. Shorten README to quick-start only
2. Move detailed content to `docs/`:
   - `docs/INSTALLATION.md`
   - `docs/CONFIGURATION.md`
   - `docs/TROUBLESHOOTING.md`
3. Link from README to detailed docs

**Effort**: S (Small)
- Reorganize existing content
- Create new files

**Evidence**: README.md is comprehensive but monolithic.

---

### DOC-2: No Troubleshooting FAQ

**Problem**: Common problems (LMStudio won't connect, PDFs not extracting, files going to Miscellaneous) aren't addressed in an easy-to-find FAQ.

**Why it matters**: Users hit the same issues repeatedly. Without FAQ, they either search issues or give up.

**Suggested solution**:
Create `docs/TROUBLESHOOTING.md` with:
- "LMStudio won't connect" → check steps
- "All files going to Miscellaneous" → common causes
- "PDF text extraction not working" → Poppler setup
- "Dashboard won't open" → port conflict resolution

**Effort**: S (Small)
- Document common issues from experience
- Link from README and dashboard

**Evidence**: Troubleshooting section in README exists but is brief.

---

### DOC-3: CLI Help Not Discoverable

**Problem**: `--help` shows all options but users don't know it exists. They might not think to try it.

**Why it matters**: Users miss features like `--scan-only`, `--file`, `--check` that would solve their problems.

**Suggested solution**:
1. Mention `--help` prominently in README and dashboard
2. Add "Available commands" section to dashboard
3. Show example commands in first-run experience

**Effort**: S (Small)
- Add documentation
- Add to dashboard help section

**Evidence**: Comprehensive argparse at `@src/main.py:455-536` but not promoted.

---

### DOC-4: No Video Walkthrough

**Problem**: Text documentation only. Visual learners have no resources.

**Why it matters**: Many users prefer watching to reading. A 5-minute video could replace 30 minutes of documentation reading.

**Suggested solution**:
1. Record quick-start video (5 min)
2. Record troubleshooting video (3 min)
3. Host on YouTube, link from README

**Effort**: M (Medium)
- Recording and editing time
- Hosting and linking

**Evidence**: No video content exists or is referenced.

---

## 9. Time-to-First-Success

### TFS-1: Current Time-to-First-Success ~45 minutes

**Problem**: From "I want to try Sift" to "I've successfully organized my first document" takes approximately:
- Download/clone Sift: 2 min
- Install Python (if needed): 10 min
- Install LMStudio: 5 min
- Download model in LMStudio: 10 min
- Install Poppler: 5 min
- Edit config file: 5 min
- Run and troubleshoot: 5-10 min

**Why it matters**: High friction = low adoption. Users who would love the product never get to experience it.

**Evidence**: Measured from README prerequisites and typical user journey.

---

### TFS-2: No One-Click Installer

**Problem**: Installation requires multiple manual steps across different applications and tools.

**Why it matters**: Every manual step is a dropout point.

**Suggested solution**:
1. **Windows**: Create installer (NSIS or WiX) that bundles:
   - Python runtime (embedded)
   - Poppler binaries
   - Sift code
   - Creates shortcuts
2. **Cross-platform**: Docker container with everything pre-configured
3. **Alternative**: Downloadable VM image

**Effort**: L (Large)
- Significant packaging work
- Testing on clean systems
- Update process for new versions

**Evidence**: Current installation is multi-step manual process.

---

### TFS-3: LMStudio Must Be Installed Separately

**Problem**: LMStudio is a required external dependency that can't be bundled. Users must understand what it is, why they need it, and how to configure it.

**Why it matters**: For non-technical users, "install a separate AI app and load a model" is a significant barrier.

**Suggested solution**:
1. Create detailed "LMStudio Setup for Sift" guide with screenshots
2. Consider supporting Ollama as alternative (simpler CLI-based setup)
3. Long-term: Embed a small model directly (no external LLM needed)

**Effort**: S (docs) to L (embedded model)

**Evidence**: LMStudio is required dependency per README and `@src/llm_client.py`.

---

### TFS-4: First Run May Fail Silently

**Problem**: If setup is incomplete, first run might:
- Start but do nothing (LMStudio not running)
- Process files poorly (model not loaded)
- Error out cryptically (paths not configured)

**Why it matters**: Users don't get the "aha moment" of seeing their first document classified. They might not realize Sift isn't working properly.

**Suggested solution**:
1. First-run wizard that validates everything before processing
2. "Getting Started" checklist in dashboard that shows status of each component
3. Sample document processing to confirm end-to-end works

**Effort**: M (Medium)
- Add validation and wizard flow
- Integrate with existing `--check` logic

**Evidence**: No first-run validation. Sift starts directly into watch mode.

---

## Summary Table

| ID | Category | Problem | Effort | Impact |
|----|----------|---------|--------|--------|
| ONB-1 | Onboarding | No first-run experience | M | High |
| ONB-2 | Onboarding | Paths require manual editing | S | High |
| ONB-3 | Onboarding | No sample documents | S | Medium |
| ONB-4 | Onboarding | LMStudio setup not validated | S | High |
| ONB-5 | Onboarding | No installation verification | S | Medium |
| UX-1 | UX Clarity | Confidence scores unexplained | S | Medium |
| UX-2 | UX Clarity | No real-time processing feedback | M | Medium |
| UX-3 | UX Clarity | Classification reasoning hidden | S | Medium |
| UX-4 | UX Clarity | System tray states undocumented | S | Low |
| UX-5 | UX Clarity | Search results don't show match reason | M | Low |
| UX-6 | UX Clarity | Needs_Review purpose not clear | S | Medium |
| DEF-1 | Defaults | Default paths require editing | S | High |
| DEF-2 | Defaults | Default model may not match | S | Medium |
| DEF-3 | Defaults | Processing delay may be wrong | M | Medium |
| DEF-4 | Defaults | Default categories too generic | M | Medium |
| ERR-1 | Errors | LMStudio error unhelpful | S | High |
| ERR-2 | Errors | JSON parsing failures silent | S | Medium |
| ERR-3 | Errors | Timeout errors don't suggest solutions | S | Medium |
| ERR-4 | Errors | Permission errors not actionable | S | Medium |
| ERR-5 | Errors | Config validation errors vague | S | Medium |
| CFG-1 | Config | No GUI for configuration | L | High |
| CFG-2 | Config | Rules require regex knowledge | M | Medium |
| CFG-3 | Config | No config validation before run | S | Medium |
| CFG-4 | Config | Can't test rules without enabling | S | Medium |
| PERF-1 | Performance | No OCR progress indication | S | Low |
| PERF-2 | Performance | No parallel processing | M | Medium |
| PERF-3 | Performance | Large documents may timeout | S | Medium |
| PERF-4 | Performance | No hardware guidance for models | S | Medium |
| REL-1 | Reliability | No automated test suite | L | High |
| REL-2 | Reliability | Database migrations ad-hoc | M | Medium |
| REL-3 | Reliability | Orphaned vision model code | S | Low |
| REL-4 | Reliability | Port cleanup may fail silently | S | Low |
| DOC-1 | Docs | README too long | S | Medium |
| DOC-2 | Docs | No troubleshooting FAQ | S | High |
| DOC-3 | Docs | CLI help not discoverable | S | Low |
| DOC-4 | Docs | No video walkthrough | M | Medium |
| TFS-1 | Time-to-Success | ~45 minutes to first success | - | Critical |
| TFS-2 | Time-to-Success | No one-click installer | L | High |
| TFS-3 | Time-to-Success | LMStudio separate install | S-L | High |
| TFS-4 | Time-to-Success | First run may fail silently | M | High |

---

## Recommended Priority

**Quick Wins (High Impact, Small Effort)**:
1. ONB-2/DEF-1: Auto-expand path placeholders
2. ERR-1: Improve LMStudio connection error message
3. ONB-4: Enhance `--check` with remediation steps
4. DOC-2: Create troubleshooting FAQ
5. UX-1: Add confidence score explanation to dashboard

**Medium Priority**:
1. ONB-1: First-run wizard
2. UX-2: Real-time processing feedback
3. TFS-4: First-run validation
4. CFG-3: Config validation
5. ONB-3: Sample documents

**Long-term Investments**:
1. REL-1: Test suite
2. CFG-1: GUI configuration
3. TFS-2: One-click installer
4. PERF-2: Parallel processing
