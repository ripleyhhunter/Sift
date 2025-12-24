# Sift Development Roadmap

This roadmap uses a **Now / Next / Later** framework to prioritize development based on user impact, risk mitigation, and strategic value. Each item is fully specified with user problem, solution, urgency rationale, dependencies, effort, and success metrics.

**Personas** (from PRODUCT_BRIEF.md):
- **P1**: Privacy-Conscious Professional (lawyer, accountant, healthcare)
- **P2**: Digital Hoarder (3,000+ unorganized files)
- **P3**: Small Business Owner (invoices, receipts, tax prep)
- **P4**: Local-AI Enthusiast (technical, wants to tinker)

**Current State**: Functional core with excellent privacy architecture, but ~45-minute time-to-first-success and rough edges that lose P2/P3 users during setup.

---

## NOW (0-4 weeks)

Critical items that block adoption, create data risk, or cause immediate user confusion. These must ship before any feature work.

---

### NOW-1: Auto-Expand Configuration Paths

**User Problem**: Every user must manually edit `config/settings.yaml` to replace `{username}` placeholders before Sift will work. This is a 100% hit rate blocker.

**Proposed Solution**:
- Auto-expand `~`, `{username}`, and `$HOME` in path configuration
- Use Python's `Path.home()` and `os.path.expanduser()`
- Create default folders if they don't exist

**Why Now**:
- **Urgency**: Every single user hits this on first run
- **Adoption**: #1 cause of failed first attempts
- **Risk**: Users blame Sift for "not working" when it's config issue

**Dependencies**: None

**Effort**: S (Small) - Modify `@src/config.py` path loading

**Success Metric**: User can run Sift immediately after install without editing config files

**Refs**: ONB-2, DEF-1

---

### NOW-2: Actionable LMStudio Error Messages

**User Problem**: When LMStudio isn't running, error says "Could not connect to LMStudio" with no guidance on what to do.

**Proposed Solution**:
Replace generic errors with step-by-step remediation:
```
Could not connect to LMStudio at localhost:1234.

To fix this:
1. Open LMStudio application
2. Load a model (Recommended: qwen3-4b)
3. Go to Developer tab → Start Server
4. Ensure it's running on port 1234

Then run: python src/main.py --check
```

**Why Now**:
- **Urgency**: Most common support question
- **Adoption**: Users give up when they can't diagnose
- **Risk**: P2/P3 users lack technical background to debug

**Dependencies**: None

**Effort**: S (Small) - Modify error handling in `@src/main.py:336-346`

**Success Metric**: Users can self-diagnose and fix LMStudio issues without external help

**Refs**: ERR-1

---

### NOW-3: Enhanced Health Check

**User Problem**: `--check` reports pass/fail but doesn't tell users how to fix failures or what each component does.

**Proposed Solution**:
Expand `--check` to show:
- LMStudio: Connected? Model loaded? Which model?
- Paths: Exist? Writable? Correct permissions?
- Dependencies: Poppler? LibreOffice? Tesseract?
- For each failure: specific remediation steps

**Why Now**:
- **Urgency**: Critical for troubleshooting
- **Adoption**: Single command should validate entire setup
- **Risk**: Without this, users debug blindly

**Dependencies**: NOW-2 (error message patterns)

**Effort**: S (Small) - Expand `@src/main.py:572-598`

**Success Metric**: `--check` provides actionable fix for every failure type

**Refs**: ONB-4

---

### NOW-4: Troubleshooting FAQ

**User Problem**: Common problems (LMStudio connection, PDF extraction, files going to Miscellaneous) aren't documented in an easy-to-find location.

**Proposed Solution**:
Create `docs/TROUBLESHOOTING.md` covering:
- "LMStudio won't connect" - checklist
- "All files going to Miscellaneous" - common causes
- "PDF text extraction not working" - Poppler setup
- "Dashboard won't open" - port conflict resolution
- "Documents not being detected" - watcher issues

**Why Now**:
- **Urgency**: Reduces support burden immediately
- **Adoption**: Users can self-serve before giving up
- **Risk**: Low effort, high impact

**Dependencies**: None

**Effort**: S (Small) - Documentation only

**Success Metric**: Top 10 user questions answered in docs; reduced repeat questions

**Refs**: DOC-2

---

### NOW-5: Critical Code Safety Fixes

**User Problem**: Silent exceptions hide errors (users don't know something failed); file paths from database aren't validated (potential security/corruption issue).

**Proposed Solution**:
1. **CRIT-1**: Replace silent `except: pass` with logged warnings
2. **CRIT-2**: Validate all file paths are within expected directories before operations

**Why Now**:
- **Urgency**: Data safety is foundational
- **Adoption**: Hidden errors erode trust
- **Risk**: Silent failures cause confusion; unvalidated paths are security risk

**Dependencies**: None

**Effort**: S (Small) - Targeted fixes in `@src/main.py:404,424` and `@src/dashboard.py`

**Success Metric**: No silent exception swallowing; all file operations validate paths

**Refs**: CRIT-1, CRIT-2

---

### NOW-6: Automated Database Backups

**User Problem**: If database is corrupted, user loses all classification history and corrections. No recovery possible.

**Proposed Solution**:
- Daily automatic backup of `documents.db`
- Keep last 7 daily backups (rotation)
- Backup before risky operations (migrations, bulk actions)
- `--restore-backup` command for recovery

**Why Now**:
- **Urgency**: Data loss destroys user trust
- **Adoption**: Enterprise/professional users require backup
- **Risk**: Evidence of corruption already exists (`documents.db.corrupt`)

**Dependencies**: None

**Effort**: M (Medium) - New backup module, startup integration

**Success Metric**: Backups exist; user can restore from backup; zero data loss incidents

**Refs**: TRU-12

---

### NOW-7: Confidence Score Explanation

**User Problem**: Dashboard shows "0.72" confidence but users don't know what this means, what's good/bad, or why documents go to Needs_Review.

**Proposed Solution**:
- Add tooltip: "Confidence shows how certain AI is. Above 70% = auto-filed. Below = needs your review."
- Color code: Green (>0.8), Yellow (0.7-0.8), Red (<0.7)
- Show current threshold setting

**Why Now**:
- **Urgency**: Core feature is confusing
- **Adoption**: Users ignore review queue because they don't understand it
- **Risk**: Low effort, improves comprehension significantly

**Dependencies**: None

**Effort**: S (Small) - Dashboard HTML/CSS in `@src/dashboard.py`

**Success Metric**: Users understand why documents need review; review queue engagement increases

**Refs**: UX-1

---

### NOW-8: Needs_Review Explanation Banner

**User Problem**: Documents appear in Needs_Review folder but users don't know why they're there or what to do.

**Proposed Solution**:
Add explanatory banner to review section:
```
These documents need your review because AI confidence was below 70%.

For each document, you can:
• Accept the AI's suggestion (if it looks right)
• Reassign to a different category
• The system learns from your corrections
```

**Why Now**:
- **Urgency**: Review queue is underutilized
- **Adoption**: Users either ignore it or are confused
- **Risk**: Very low effort, high comprehension gain

**Dependencies**: NOW-7 (confidence explanation)

**Effort**: S (Small) - Dashboard text addition

**Success Metric**: Users take action on review queue items instead of ignoring them

**Refs**: UX-6

---

### NOW-9: Installation Verification

**User Problem**: `install.bat` completes successfully but user may still have broken setup (missing Poppler, wrong Python version, LMStudio not configured).

**Proposed Solution**:
- Add verification step at end of install script
- Run `python src/main.py --check`
- Clear pass/fail summary with next steps

**Why Now**:
- **Urgency**: Gap between "installed" and "working" is confusing
- **Adoption**: Users think they're done when they're not
- **Risk**: Low effort addition to existing scripts

**Dependencies**: NOW-3 (enhanced health check)

**Effort**: S (Small) - Script modification

**Success Metric**: Install script tells user if setup is complete or what's missing

**Refs**: ONB-5

---

## NEXT (1-3 months)

Items that improve daily experience, enable scaling, and expand to P2/P3 personas. Ship these after NOW items are complete.

---

### NEXT-1: First-Run Wizard

**User Problem**: After installation, users are dropped directly into watch mode with no guidance, no verification, and no explanation.

**Proposed Solution**:
First-run detection and guided setup:
1. Detect first run (empty database)
2. Welcome message with what Sift does
3. Verify LMStudio connection
4. Confirm/set watch paths
5. Offer to process a sample document
6. Success confirmation before entering watch mode

**Why Now (Next)**:
- **Urgency**: Critical for P2/P3 adoption after NOW items
- **Adoption**: Reduces time-to-first-success from 45 min to <15 min
- **Risk**: Medium effort but high impact

**Dependencies**: NOW-1, NOW-2, NOW-3 (path expansion, errors, health check)

**Effort**: M (Medium) - New flow in `@src/main.py`

**Success Metric**: Time-to-first-success < 15 minutes for users with LMStudio installed

**Refs**: ONB-1, TFS-4

---

### NEXT-2: Sample Documents

**User Problem**: Users can't verify their setup works without finding their own documents. They don't know what "success" looks like.

**Proposed Solution**:
- Bundle 3-5 sample documents: invoice, receipt, medical form, contract, personal letter
- Store in `assets/samples/`
- Add `--demo` flag that processes samples and shows results
- Dashboard "Try with samples" button

**Why Now (Next)**:
- **Urgency**: Enables immediate verification after install
- **Adoption**: "Try before you commit" experience
- **Risk**: Low effort, creates confidence

**Dependencies**: NEXT-1 (first-run wizard uses samples)

**Effort**: S (Small) - Create samples, add `--demo` flag

**Success Metric**: Users can verify setup works immediately; demo shows expected classifications

**Refs**: ONB-3

---

### NEXT-3: Real-Time Processing Status

**User Problem**: During batch processing, users don't know if Sift is working, stuck, or finished. They see static dashboard and wonder.

**Proposed Solution**:
- Dashboard shows: "Currently processing: filename.pdf"
- Queue depth indicator: "3 files remaining"
- Processing history: last 5 files processed with results
- Auto-refresh every 5 seconds during active processing

**Why Now (Next)**:
- **Urgency**: Batch processing (P2's main use case) is anxiety-inducing
- **Adoption**: Users need feedback during long operations
- **Risk**: Medium effort, significant UX improvement

**Dependencies**: None (uses existing `get_batch_status()`)

**Effort**: M (Medium) - Dashboard polling, new UI components

**Success Metric**: Users always know what Sift is doing; zero "is it stuck?" confusion

**Refs**: UX-2

---

### NEXT-4: Dashboard Pagination

**User Problem**: Dashboard becomes slow when user has thousands of documents. Current implementation loads all recent documents.

**Proposed Solution**:
- Paginate document lists (50 per page default)
- Add page navigation controls
- Lazy load thumbnails
- API supports `?page=N&per_page=M`

**Why Now (Next)**:
- **Urgency**: P2 users hit this quickly with backlog processing
- **Adoption**: Scale blocker for heavy users
- **Risk**: Performance degrades silently until it's unusable

**Dependencies**: None

**Effort**: M (Medium) - API changes, dashboard UI

**Success Metric**: Dashboard stays responsive at 10,000+ documents; load time < 2 seconds

**Refs**: LAT-1, PERF-1

---

### NEXT-5: Duplicate Detection

**User Problem**: User downloads the same document multiple times, ending up with duplicates in different locations or multiple copies in same folder.

**Proposed Solution**:
- Calculate content hash during processing
- Check hash against existing documents
- If duplicate found: offer skip, replace, or keep both
- Dashboard shows duplicate count in stats

**Why Now (Next)**:
- **Urgency**: Common pain point for P2
- **Adoption**: Saves disk space, reduces clutter
- **Risk**: Medium effort, clear value

**Dependencies**: Database schema change for hash storage

**Effort**: M (Medium) - Hash calculation, duplicate checking, UI

**Success Metric**: Duplicates detected before filing; user chooses handling

**Refs**: LAT-2

---

### NEXT-6: Historical Reports / Date Filtering

**User Problem**: User preparing for tax season needs to see "all Financial documents from 2024" but has no way to filter by date.

**Proposed Solution**:
- Date range filter in dashboard
- Category filter
- Combined filters: "Financial documents from Jan-Dec 2024"
- Export filtered results to CSV

**Why Now (Next)**:
- **Urgency**: P3's primary use case (tax prep) depends on this
- **Adoption**: Annual need creates loyalty
- **Risk**: Small effort, high value for P3

**Dependencies**: NEXT-4 (pagination for large result sets)

**Effort**: S (Small) - Filter UI, query parameters

**Success Metric**: Users can filter by date range; tax prep time reduced

**Refs**: LAT-6

---

### NEXT-7: Config Validation on Startup

**User Problem**: Invalid configuration (bad path, out-of-range threshold, missing field) causes failures during operation instead of at startup.

**Proposed Solution**:
Comprehensive validation at startup:
- Paths exist or can be created
- Threshold in 0.0-1.0 range
- Extensions start with dot
- Model profile exists
- Required fields present

**Why Now (Next)**:
- **Urgency**: Late failures confuse users
- **Adoption**: Fail fast with clear message
- **Risk**: Low effort, prevents debugging headaches

**Dependencies**: NOW-1 (path expansion)

**Effort**: S (Small) - Validation in `@src/config.py`

**Success Metric**: Invalid config caught at startup with specific error; zero late config failures

**Refs**: CFG-3

---

### NEXT-8: File Integrity Verification

**User Problem**: User has no way to verify documents weren't corrupted during processing. For compliance-conscious users (P1), this is a trust issue.

**Proposed Solution**:
- Calculate and store SHA-256 hash when file is moved
- `--verify` command checks all files against stored hashes
- Report any mismatches
- Dashboard shows verification status

**Why Now (Next)**:
- **Urgency**: Trust foundation for P1
- **Adoption**: Required for professional/compliance use
- **Risk**: Medium effort, essential for enterprise

**Dependencies**: Database schema for hash storage (can share with NEXT-5)

**Effort**: M (Medium) - Hash storage, verification command

**Success Metric**: Users can verify document integrity; zero undetected corruptions

**Refs**: TRU-5

---

### NEXT-9: Orphan Detection

**User Problem**: Database records can get out of sync with filesystem (files moved externally, deleted, renamed). User doesn't know this happened.

**Proposed Solution**:
- `--check-sync` command compares database to filesystem
- Reports: orphan records (no file), untracked files (no record)
- `--repair-sync` offers to fix issues
- Dashboard warning if orphans detected

**Why Now (Next)**:
- **Urgency**: Data consistency is trust foundation
- **Adoption**: P1 needs assurance of accuracy
- **Risk**: Low effort, high trust impact

**Dependencies**: None

**Effort**: S (Small) - Filesystem scan, comparison

**Success Metric**: Users can detect sync issues; dashboard shows sync status

**Refs**: TRU-6

---

### NEXT-10: Core Test Suite (Phase 1)

**User Problem**: No automated tests means refactoring is risky, regressions ship undetected, and contributors can't verify changes.

**Proposed Solution**:
Phase 1 - Critical path coverage:
- `llm_client.py` JSON parsing (5-layer defense)
- `rules_engine.py` pattern matching
- `database.py` crash recovery logic
- Basic classification pipeline integration test

**Why Now (Next)**:
- **Urgency**: Enables safe development of LATER items
- **Adoption**: Contributors (P4) need confidence
- **Risk**: Large effort but essential for long-term velocity

**Dependencies**: None

**Effort**: L (Large) - Ongoing, start now

**Success Metric**: CI passes on every PR; 80%+ coverage on critical paths

**Refs**: REL-1, HIGH-1

---

### NEXT-11: Classification Reasoning Display

**User Problem**: AI provides reasoning for classifications, but it's not visible. Users can't understand *why* a document was classified.

**Proposed Solution**:
- "Why this category?" expandable in dashboard
- Show AI reasoning for each document
- Especially prominent in Needs_Review (where it matters most)

**Why Now (Next)**:
- **Urgency**: Builds trust in AI decisions
- **Adoption**: Users correct more accurately when they understand reasoning
- **Risk**: Data already captured; just needs UI exposure

**Dependencies**: None (reasoning already stored)

**Effort**: S (Small) - Dashboard UI only

**Success Metric**: Users can see classification reasoning; correction accuracy improves

**Refs**: UX-3

---

## LATER (3-6+ months)

Strategic investments that expand to new use cases, enable enterprise adoption, and build competitive differentiation. Ship after NEXT items establish solid foundation.

---

### LATER-1: GUI Configuration

**User Problem**: All configuration requires editing YAML files. P3 users can't customize categories, thresholds, or rules without technical help.

**Proposed Solution**:
Dashboard Settings page:
- Path configuration (with folder browser)
- Confidence threshold slider
- Category management (add/edit/delete)
- Model profile selector
- All changes saved to settings.yaml

**Why Now (Later)**:
- **Urgency**: Gates P3 adoption at scale
- **Adoption**: Non-technical users can customize
- **Risk**: Large effort, but opens new market

**Dependencies**: NEXT-7 (config validation)

**Effort**: L (Large) - New dashboard routes, config write logic

**Success Metric**: Settings changed without editing files; P3 can customize independently

**Refs**: CFG-1

---

### LATER-2: Visual Rule Builder

**User Problem**: Creating custom rules requires YAML editing and regex knowledge. Most users don't know regex.

**Proposed Solution**:
Rule builder UI:
- "If filename contains [___] then move to [dropdown]"
- "If content includes [___] then move to [dropdown]"
- Test rule against existing documents before saving
- Common pattern templates (bank statements, invoices, etc.)

**Why Now (Later)**:
- **Urgency**: Rules are powerful but inaccessible
- **Adoption**: Makes rules usable for non-technical
- **Risk**: Medium effort, significant accessibility gain

**Dependencies**: LATER-1 (settings page framework)

**Effort**: M (Medium) - Rule UI, test functionality

**Success Metric**: Rules created without regex knowledge; rule usage increases

**Refs**: CFG-2, CFG-4

---

### LATER-3: Multiple Watch Folders

**User Problem**: User receives documents from multiple sources (work inbox, personal inbox, scanner output) but can only watch one folder.

**Proposed Solution**:
- Configure multiple inbox folders
- Per-folder rule sets
- Per-folder category destinations
- Dashboard shows which folder document came from

**Why Now (Later)**:
- **Urgency**: Common request from P1, P3
- **Adoption**: Enables multi-context use
- **Risk**: Large effort (config restructure, watcher changes)

**Dependencies**: LATER-1 (GUI config for folder management)

**Effort**: L (Large) - Config restructure, watcher multi-instance

**Success Metric**: Multiple folders monitored independently; per-folder rules work

**Refs**: LAT-10

---

### LATER-4: Alternative LLM Backends

**User Problem**: Sift only works with LMStudio. Users who prefer Ollama, llama.cpp, or other backends can't use Sift.

**Proposed Solution**:
Pluggable backend system:
- LMStudio (current, default)
- Ollama support
- OpenAI-compatible API (generic)
- Backend selection in config

**Why Now (Later)**:
- **Urgency**: Expands addressable market
- **Adoption**: Ollama users are large segment of P4
- **Risk**: Medium effort, significant reach expansion

**Dependencies**: None (clean abstraction)

**Effort**: M (Medium) - Backend abstraction, Ollama adapter

**Success Metric**: Works with Ollama out of box; backend switchable via config

**Refs**: PWR-10

---

### LATER-5: CLI for Scripting

**User Problem**: Power users can't automate Sift operations. No way to script classification, search, or batch operations.

**Proposed Solution**:
Full CLI:
- `sift classify <file>` - Classify single file
- `sift search <query>` - Search documents
- `sift stats` - Show statistics
- `sift rules test <file>` - Test rules against file
- JSON output option for scripting

**Why Now (Later)**:
- **Urgency**: Power user enablement
- **Adoption**: P4 wants scriptability
- **Risk**: Medium effort, attracts technical users

**Dependencies**: None

**Effort**: M (Medium) - CLI argument expansion, JSON output

**Success Metric**: Sift operations scriptable; P4 builds integrations

**Refs**: PWR-1

---

### LATER-6: Headless Mode

**User Problem**: Can't run Sift on server, NAS, or headless system. Current implementation requires tray icon or console.

**Proposed Solution**:
- True daemon mode with no GUI dependencies
- systemd service file for Linux
- Windows Service support
- Log-only feedback, status via API

**Why Now (Later)**:
- **Urgency**: Server/NAS deployment
- **Adoption**: P4 wants to run on home servers
- **Risk**: Small effort, enables new deployment scenarios

**Dependencies**: LATER-5 (CLI for control)

**Effort**: S (Small) - Optional GUI, service files

**Success Metric**: Runs as systemd/Windows service; no display required

**Refs**: PWR-2

---

### LATER-7: Full System Export/Import

**User Problem**: User can't migrate Sift to new computer. No way to export configuration, rules, history, and corrections.

**Proposed Solution**:
- `sift export` creates complete archive (config, database, corrections)
- `sift import <archive>` restores on new machine
- Path remapping during import (old paths → new paths)
- Verification of import success

**Why Now (Later)**:
- **Urgency**: User retention on hardware change
- **Adoption**: Long-term users need migration path
- **Risk**: Medium effort, prevents user loss

**Dependencies**: LATER-5 (CLI framework)

**Effort**: M (Medium) - Export format, path remapping

**Success Metric**: Full migration works; zero history loss on machine change

**Refs**: PWR-6

---

### LATER-8: Network Activity Verification

**User Problem**: P1 users need to prove to compliance/legal that no data leaves the machine. Current proof is "trust the code."

**Proposed Solution**:
- Network activity log (all connections made)
- Offline mode (disable all network, fail if LMStudio not local)
- Audit report showing: all network calls, destinations, timestamps
- Export for compliance review

**Why Now (Later)**:
- **Urgency**: Enterprise/compliance requirement
- **Adoption**: Gates enterprise P1 adoption
- **Risk**: Medium effort, required for regulated industries

**Dependencies**: None

**Effort**: M (Medium) - Network logging, audit report

**Success Metric**: Audit report proves no external data transmission

**Refs**: TRU-1

---

### LATER-9: Compliance Reporting

**User Problem**: Professionals need pre-built reports for compliance audits—processing summary, retention compliance, audit trail.

**Proposed Solution**:
Report templates:
- Processing summary (period, counts, categories)
- Document inventory (all files with metadata)
- Activity audit trail (all actions taken)
- Retention compliance (documents by age)
- Export to PDF/CSV

**Why Now (Later)**:
- **Urgency**: Enterprise feature
- **Adoption**: P1 compliance requirements
- **Risk**: Medium effort, gates regulated industry adoption

**Dependencies**: LATER-8 (network audit), NEXT-8 (integrity)

**Effort**: M (Medium) - Report generation, templates

**Success Metric**: Compliance reports exportable; accepted by auditors

**Refs**: TRU-11

---

### LATER-10: Event Hooks

**User Problem**: Power users want to run custom scripts when documents are classified (e.g., upload tax docs to accountant portal).

**Proposed Solution**:
Configurable hooks:
- `on_classify`: Run script after successful classification
- `on_review_needed`: Run script when document needs review
- `on_error`: Run script on processing error
- Pass document info as arguments/environment

**Why Now (Later)**:
- **Urgency**: Advanced automation for P4
- **Adoption**: Enables custom workflows
- **Risk**: Medium effort, differentiator for power users

**Dependencies**: LATER-5 (CLI for testing hooks)

**Effort**: M (Medium) - Hook system, subprocess management

**Success Metric**: Custom scripts execute on classification events

**Refs**: PWR-5

---

### LATER-11: Plugin Architecture

**User Problem**: Users with custom document formats or specialized needs can't extend Sift without forking the codebase.

**Proposed Solution**:
Plugin system:
- Custom extractors (for proprietary formats)
- Custom classifiers (alternative to LLM)
- Custom post-processors (after classification)
- Plugin discovery and loading
- Plugin API documentation

**Why Now (Later)**:
- **Urgency**: Community growth
- **Adoption**: P4 wants to contribute without forking
- **Risk**: Large effort, but enables ecosystem

**Dependencies**: LATER-4 (backend abstraction patterns)

**Effort**: L (Large) - Plugin API, loading system, docs

**Success Metric**: Third-party plugins possible; community contributions

**Refs**: PWR-15

---

## Top Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **LMStudio API changes** | Medium | High | Abstract backend (LATER-4); support alternatives |
| **Performance at scale** | Medium | Medium | Early pagination (NEXT-4); monitor real-world usage |
| **Silent failures erode trust** | High | High | NOW-5 fixes critical issues; comprehensive error handling |
| **Setup friction loses P2/P3** | High | High | NOW items + NEXT-1 wizard reduce friction |
| **Database corruption** | Low | Critical | NOW-6 backups; integrity verification (NEXT-8) |
| **Threading bugs at load** | Medium | Medium | NEXT-10 tests; careful review of concurrent code |
| **Scope creep delays NOW items** | Medium | High | Strict NOW-first discipline; no features until NOW complete |
| **P4 contributors break things** | Low | Medium | NEXT-10 test suite gates contributions |
| **LLM quality degrades** | Low | Medium | Model profiles; user can switch models |

---

## Assumptions

These assumptions underpin the roadmap. If invalidated, priorities should be revisited.

| Assumption | Confidence | Validation |
|------------|------------|------------|
| Users have or will install LMStudio | High | Core dependency; no alternative until LATER-4 |
| Users have 8GB+ RAM for local LLM | High | Minimum for smallest useful model |
| Python 3.10+ available or installable | High | Standard on modern systems |
| Users can handle basic troubleshooting with guidance | Medium | NOW items provide guidance; may need more |
| Local-first privacy > remote access for target personas | High | P1 explicitly needs this; others accept it |
| Document volumes typically <50,000 per user | Medium | Need monitoring; NEXT-4 handles if wrong |
| Most documents are PDF, Word, Excel | High | Match user research; images/PPTX are edge cases |
| Users prefer automatic filing over manual tagging | High | Core value proposition validation |
| 45-minute setup is primary adoption blocker | High | Strong signal from architecture analysis |
| P2/P3 will adopt if setup friction is reduced | Medium | Hypothesis to validate post-NOW |

---

## Success Criteria by Phase

### After NOW (4 weeks)
- [ ] First run works without config file editing
- [ ] Users can self-diagnose LMStudio issues
- [ ] `--check` provides actionable guidance for every failure
- [ ] Database backups exist and are restorable
- [ ] Zero silent exception swallowing
- [ ] Confidence scores explained in dashboard

### After NEXT (3 months)
- [ ] Time-to-first-success < 15 minutes
- [ ] Dashboard stays responsive at 10,000+ documents
- [ ] Duplicates detected before filing
- [ ] Date filtering enables tax prep workflow
- [ ] Core test suite passes in CI
- [ ] Users can verify document integrity

### After LATER (6+ months)
- [ ] P3 can customize without editing files
- [ ] Works with Ollama as alternative to LMStudio
- [ ] Sift operations scriptable via CLI
- [ ] Compliance reports exportable
- [ ] Plugin ecosystem emerging

---

## Changelog

| Date | Change |
|------|--------|
| 2025-12-24 | Complete rewrite with Now/Next/Later framework |
