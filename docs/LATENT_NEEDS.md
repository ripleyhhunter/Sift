# Sift Latent Needs Analysis

This document identifies user needs across four dimensions: current needs (validated by existing features), latent needs (emerging as usage scales), trust needs (reliability and security), and power user needs (automation and integration). Each need includes a user story, trigger, proposed feature, effort estimate, and dependencies.

**Personas referenced** (from PRODUCT_BRIEF.md):
- **P1**: Privacy-Conscious Professional (lawyer, accountant, healthcare worker)
- **P2**: Digital Hoarder (knowledge worker with 3,000+ unorganized files)
- **P3**: Small Business Owner (freelancer managing invoices, receipts, contracts)
- **P4**: Local-AI Enthusiast (technical user wanting practical LLM applications)

---

## 1. Current User Needs

These needs are validated by existing features—users already have these problems, and Sift addresses them (to varying degrees).

### CUR-1: Automatic Organization

**User Story**: "As a busy professional, I want my documents automatically filed so I don't spend time on manual organization."

**Trigger**: User receives 5-50 documents per week and spends 20+ minutes manually filing them.

**Current Solution**: Automatic folder monitoring + AI classification (`@src/watcher.py`, `@src/classifier.py`)

**Gap**: Works well, but requires initial setup and LMStudio knowledge.

**Personas**: P1, P2, P3

---

### CUR-2: Privacy-First Processing

**User Story**: "As someone handling confidential documents, I need assurance that my files never leave my computer."

**Trigger**: User has regulatory obligations (HIPAA, attorney-client privilege) or general privacy concerns after cloud breaches.

**Current Solution**: Localhost-only architecture, no telemetry, no cloud dependencies.

**Gap**: No easy way to *verify* nothing is leaving the machine. User must trust the code.

**Personas**: P1, P3

---

### CUR-3: Handling Unpredictable Documents

**User Story**: "As someone who receives diverse document types, I need a system that can understand content, not just filenames."

**Trigger**: Documents arrive with generic names ("scan001.pdf", "document.pdf") that provide no classification hints.

**Current Solution**: Text extraction + LLM classification reads actual content.

**Gap**: PowerPoint and images are classified by filename only.

**Personas**: P2, P3

---

### CUR-4: Control Over Uncertain Decisions

**User Story**: "As someone who needs accurate filing, I want to review documents when the system isn't confident."

**Trigger**: User discovers a document was filed incorrectly because AI was uncertain but filed anyway.

**Current Solution**: Confidence threshold routes low-confidence documents to Needs_Review folder.

**Gap**: Confidence meaning isn't explained. Users don't know what 0.72 means.

**Personas**: P1, P3

---

### CUR-5: Deterministic Classification for Known Patterns

**User Story**: "As someone who receives predictable documents from specific sources, I want guaranteed classification without AI variation."

**Trigger**: User notices that identical-looking bank statements sometimes go to different folders.

**Current Solution**: Custom rules bypass AI entirely for matching patterns.

**Gap**: Creating rules requires YAML editing and regex knowledge.

**Personas**: P1, P3, P4

---

### CUR-6: System Learning from Corrections

**User Story**: "As a user who corrects misclassifications, I expect the system to learn from my corrections over time."

**Trigger**: User corrects the same type of document multiple times and wonders why it keeps happening.

**Current Solution**: Corrections are recorded and injected as few-shot examples in future prompts.

**Gap**: No visibility into what the system has "learned." Can't see or manage corrections.

**Personas**: P1, P2, P3

---

### CUR-7: Finding Documents Later

**User Story**: "As someone with hundreds of organized documents, I need to find specific ones quickly."

**Trigger**: User knows they have a document but can't remember which category it's in.

**Current Solution**: FTS5-powered search across filenames, content, and categories.

**Gap**: Search results don't show why they matched or highlight terms.

**Personas**: All

---

### CUR-8: Recovering from Mistakes

**User Story**: "As a human who makes mistakes, I need to undo recent actions."

**Trigger**: User accidentally reassigns multiple documents to wrong category.

**Current Solution**: 24-hour undo window via activity log.

**Gap**: Undo is not prominently visible in UI. Users might not know it exists.

**Personas**: All

---

### CUR-9: Processing Document Backlogs

**User Story**: "As someone with years of unorganized files, I need to process my backlog without manual effort."

**Trigger**: User has 3,000+ files in Downloads folder accumulated over years.

**Current Solution**: `--scan-only` mode processes existing files.

**Gap**: No progress indication for large batches. Can take hours with no feedback.

**Personas**: P2

---

## 2. Latent Needs

These needs emerge as usage scales—users don't know they need these until they hit scaling walls.

### Volume Scaling (100 → 1,000 → 10,000+ documents)

#### LAT-1: Dashboard Performance at Scale

**User Story**: "As a user with 5,000+ documents, I need the dashboard to stay fast."

**Trigger**: Dashboard becomes slow to load after 6 months of heavy use.

**Feature**: Pagination, virtual scrolling, lazy loading for document lists.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Dashboard UI changes, API pagination support |
| **Evidence** | `@src/database.py:392-404` loads all recent documents |

**Personas**: P1, P2, P3

---

#### LAT-2: Duplicate Detection

**User Story**: "As someone who downloads the same document multiple times, I don't want duplicates cluttering my folders."

**Trigger**: User discovers they have 5 copies of the same bank statement in different locations.

**Feature**: Content hash comparison, duplicate flagging, merge/keep-one options.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Hash computation during processing, database schema change |
| **Evidence** | No duplicate detection exists in codebase |

**Personas**: P2, P3

---

#### LAT-3: Category Management at Scale

**User Story**: "As my document collection grows, I need to reorganize my categories without losing organization."

**Trigger**: User realizes their initial category structure doesn't fit anymore after 2 years.

**Feature**: Category renaming, merging, splitting with automatic file movement.

| Aspect | Detail |
|--------|--------|
| **Effort** | L (Large) |
| **Dependencies** | Bulk file operations, database migrations, rule updates |
| **Evidence** | No category management exists beyond config editing |

**Personas**: P1, P2, P3

---

#### LAT-4: Archiving Old Documents

**User Story**: "As someone with 10 years of documents, I want to archive old files without deleting them."

**Trigger**: User's Sift folder grows to 50GB, slowing down backups and searches.

**Feature**: Archive rules (move documents older than X to archive), archive folder management.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Date-based filtering, archive folder structure |
| **Evidence** | No archiving concept exists |

**Personas**: P1, P2

---

#### LAT-5: Bulk Reclassification

**User Story**: "As someone whose needs changed, I need to reclassify hundreds of documents at once."

**Trigger**: User changes jobs and needs to reorganize work documents into personal categories.

**Feature**: Batch reassignment with filters (by date range, category, content match).

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Dashboard batch UI, filtered selection |
| **Evidence** | Batch operations exist (`@src/dashboard.py:1985-2095`) but limited filtering |

**Personas**: P1, P2

---

### Time Scaling (1 month → 1 year → 5+ years)

#### LAT-6: Historical Reports

**User Story**: "As someone preparing for tax season, I need to see all documents from 2024 in Financial category."

**Trigger**: Annual tax preparation requires gathering documents from specific time period.

**Feature**: Date range filtering, category-specific views, exportable reports.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Dashboard UI filters |
| **Evidence** | No date filtering in current dashboard |

**Personas**: P1, P3

---

#### LAT-7: Classification Accuracy Trends

**User Story**: "As a long-term user, I want to know if the system is getting better or worse over time."

**Trigger**: User suspects classification quality has degraded but has no data to confirm.

**Feature**: Accuracy dashboard showing: corrections over time, confidence trends, category distribution changes.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Analytics queries, trend visualization |
| **Evidence** | Statistics exist (`@src/database.py:470-512`) but no trend analysis |

**Personas**: P1, P4

---

#### LAT-8: Document Retention Policies

**User Story**: "As a professional with record-keeping requirements, I need to know when documents can be safely deleted."

**Trigger**: User needs to comply with 7-year retention policy but also wants to clean up old documents.

**Feature**: Retention rules (keep for X years), expiration warnings, compliance reports.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Date tracking, policy configuration, notification system |
| **Evidence** | No retention concept exists |

**Personas**: P1

---

#### LAT-9: Category Evolution History

**User Story**: "As someone who reorganized categories, I need to know where documents were before reorganization."

**Trigger**: User can't find a document because they don't remember which old category it was in.

**Feature**: Full path history for each document showing all previous locations.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | `activity_log` already tracks moves; needs UI exposure |
| **Evidence** | Activity log exists (`@src/database.py:121-132`) but history not surfaced |

**Personas**: P1, P2

---

### Complexity Scaling (simple → complex workflows)

#### LAT-10: Multiple Watch Folders

**User Story**: "As someone who receives documents from multiple sources, I want to watch different folders with different rules."

**Trigger**: User has work documents in one location and personal documents in another, with different category needs.

**Feature**: Multiple inbox folders with per-folder rule sets and category destinations.

| Aspect | Detail |
|--------|--------|
| **Effort** | L (Large) |
| **Dependencies** | Config restructuring, watcher modifications, rule scoping |
| **Evidence** | Single `watch_path` in config (`config/settings.default.yaml:11`) |

**Personas**: P1, P3

---

#### LAT-11: Tagging Beyond Folders

**User Story**: "As someone whose documents don't fit neatly into one category, I want to tag documents with multiple labels."

**Trigger**: User has a document that's both "Financial" and "Work" but must choose one folder.

**Feature**: Multi-tag support alongside folder organization, tag-based search and filtering.

| Aspect | Detail |
|--------|--------|
| **Effort** | L (Large) |
| **Dependencies** | Database schema for tags, UI for tag management, search integration |
| **Evidence** | Single category/subcategory model only |

**Personas**: P1, P2

---

#### LAT-12: Document Relationships

**User Story**: "As someone tracking related documents, I want to link a contract to its amendments."

**Trigger**: User needs to find all documents related to a specific project or client.

**Feature**: Document linking, project/client grouping, relationship visualization.

| Aspect | Detail |
|--------|--------|
| **Effort** | L (Large) |
| **Dependencies** | Relationship model, UI for linking, search by relationships |
| **Evidence** | No relationship concept exists |

**Personas**: P1, P3

---

#### LAT-13: Conditional Processing Rules

**User Story**: "As someone with complex filing needs, I want rules that chain: if X then Y, else Z."

**Trigger**: User needs: "If invoice from Acme and over $1000, put in Financial/Large_Invoices, else Financial/Invoices."

**Feature**: Conditional rule logic, content-based conditions, chained actions.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Rule engine enhancements, content analysis |
| **Evidence** | Current rules are simple match → action (`@src/rules_engine.py:67-111`) |

**Personas**: P1, P3, P4

---

## 3. Trust Needs

These needs relate to reliability, auditability, privacy, and data protection—especially important for P1 (Privacy-Conscious Professional).

### Privacy Needs

#### TRU-1: Network Activity Verification

**User Story**: "As someone handling confidential documents, I need proof that Sift never contacts external servers."

**Trigger**: User's compliance team asks for evidence that no data leaves the machine.

**Feature**: Network activity log, offline mode verification, audit report showing all network calls.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Network call logging, report generation |
| **Evidence** | No network monitoring; trust is based on code inspection |

**Personas**: P1

---

#### TRU-2: Data Inventory

**User Story**: "As someone subject to data audits, I need to know exactly what data Sift stores about my documents."

**Trigger**: User receives data subject access request and needs to know what metadata is stored.

**Feature**: Data inventory report showing: what's in database, what's in logs, what's cached.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Documentation + export functionality |
| **Evidence** | Database schema documented in `@src/database.py:85-242` |

**Personas**: P1

---

#### TRU-3: Complete Data Purge

**User Story**: "As someone leaving the organization, I need to completely remove all traces of my documents."

**Trigger**: User needs to prove all document data was deleted for compliance.

**Feature**: Full purge command that removes: database, logs, cache, thumbnails, with verification.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | File enumeration, secure deletion |
| **Evidence** | No purge functionality exists |

**Personas**: P1

---

#### TRU-4: Prompt Transparency

**User Story**: "As someone who needs to know what AI sees, I want to view the exact prompts sent to LMStudio."

**Trigger**: User wants to verify no sensitive content is included in prompts beyond what's necessary.

**Feature**: Prompt logging mode, prompt preview before sending, prompt history in database.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Logging enhancement |
| **Evidence** | Prompts constructed in `@src/llm_client.py:446-571` but not logged by default |

**Personas**: P1, P4

---

### Reliability Needs

#### TRU-5: File Integrity Verification

**User Story**: "As someone who can't afford data corruption, I need to verify my documents haven't been altered."

**Trigger**: User suspects a document was corrupted during processing and wants to verify.

**Feature**: Hash verification on move, integrity check command, corruption detection.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Hash storage in database, verification CLI |
| **Evidence** | No integrity checking exists |

**Personas**: P1

---

#### TRU-6: Orphan Detection

**User Story**: "As someone who needs to trust the system, I want to know if database and filesystem are in sync."

**Trigger**: User notices database shows documents that no longer exist on disk.

**Feature**: Orphan detection command, automatic sync, repair recommendations.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Filesystem scan, database comparison |
| **Evidence** | No sync verification exists |

**Personas**: P1, P4

---

#### TRU-7: Graceful Degradation

**User Story**: "As someone who depends on Sift, I need it to keep working even when LMStudio is unavailable."

**Trigger**: LMStudio crashes and user's documents start piling up unprocessed.

**Feature**: Enhanced fallback modes, queuing during outages, automatic retry when LMStudio returns.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Fallback logic enhancement, outage detection |
| **Evidence** | Basic fallback exists (`@src/classifier.py:129-141`) but could be smarter |

**Personas**: P1, P3

---

#### TRU-8: Health Monitoring

**User Story**: "As someone running Sift continuously, I need alerts when something goes wrong."

**Trigger**: User doesn't notice LMStudio stopped until a week of documents are unprocessed.

**Feature**: Health dashboard, configurable alerts (email, desktop notification), status API.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Health check expansion, notification system |
| **Evidence** | Basic `--check` exists (`@src/main.py:572-598`) but no continuous monitoring |

**Personas**: P1, P3, P4

---

### Auditability Needs

#### TRU-9: Complete Activity Log

**User Story**: "As someone who may need to explain document handling, I need a complete history of all actions."

**Trigger**: Legal discovery requires showing how a document was handled from arrival to current location.

**Feature**: Comprehensive activity log with: who, what, when, why for every action.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Enhanced logging, log export |
| **Evidence** | Activity log exists (`@src/database.py:121-132`) but limited detail |

**Personas**: P1

---

#### TRU-10: Classification Reasoning Archive

**User Story**: "As someone who may be audited, I need to show why each document was classified a certain way."

**Trigger**: Auditor asks why a specific document was filed under "Medical" instead of "Personal."

**Feature**: Stored reasoning for every classification decision, exportable audit trail.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Already captured; needs better storage and export |
| **Evidence** | Reasoning captured (`@src/llm_client.py:780-783`) but not permanently archived |

**Personas**: P1

---

#### TRU-11: Compliance Reporting

**User Story**: "As someone with regulatory requirements, I need pre-built reports for compliance audits."

**Trigger**: Annual compliance review requires evidence of proper document handling.

**Feature**: Compliance report templates: processing summary, retention compliance, access log.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Report generation, template system |
| **Evidence** | No reporting functionality exists |

**Personas**: P1

---

### Backup Needs

#### TRU-12: Automated Backups

**User Story**: "As someone who can't afford data loss, I need automatic backups of Sift's configuration and history."

**Trigger**: Database corruption causes loss of all classification history.

**Feature**: Scheduled database backups, config backups, backup rotation.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Backup scheduler, storage management |
| **Evidence** | `.corrupt` file shows recovery has happened (`data/documents.db.corrupt`) but no proactive backup |

**Personas**: P1, P3

---

#### TRU-13: Backup Verification

**User Story**: "As someone who relies on backups, I need to know my backups are actually restorable."

**Trigger**: User tries to restore from backup and discovers it's corrupted.

**Feature**: Backup verification on creation, periodic backup testing, integrity reports.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Backup system (TRU-12) |
| **Evidence** | No backup verification exists |

**Personas**: P1

---

#### TRU-14: Point-in-Time Recovery

**User Story**: "As someone who made a mistake days ago, I need to restore to a specific point in time."

**Trigger**: User discovers a week-old batch reassignment was wrong and wants to undo it all.

**Feature**: Versioned backups, restore to date, rollback capabilities.

| Aspect | Detail |
|--------|--------|
| **Effort** | L (Large) |
| **Dependencies** | Backup versioning, state restoration logic |
| **Evidence** | No point-in-time recovery exists |

**Personas**: P1

---

#### TRU-15: External Backup Export

**User Story**: "As someone with existing backup infrastructure, I want to export Sift data to my backup system."

**Trigger**: User wants Sift data included in their regular off-site backups.

**Feature**: Export command that creates portable backup package, documentation of what to backup.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Export format design, documentation |
| **Evidence** | No export functionality exists |

**Personas**: P1, P3

---

## 4. Power User Needs

These needs come from technical users (P4) and advanced users who want automation, integration, and extensibility.

### Automation Needs

#### PWR-1: CLI for Scripting

**User Story**: "As a power user, I want to script Sift operations from the command line."

**Trigger**: User wants to integrate Sift into their backup scripts or automation workflows.

**Feature**: Full CLI for: classify single file, search, get stats, manage rules.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | CLI argument expansion |
| **Evidence** | Basic CLI exists (`@src/main.py:455-536`) but limited to startup options |

**Personas**: P4

---

#### PWR-2: Headless Mode

**User Story**: "As a server operator, I want to run Sift without any GUI or tray icon."

**Trigger**: User wants to run Sift on a NAS or headless server.

**Feature**: True headless mode, systemd/Windows service support, log-only feedback.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Optional GUI components |
| **Evidence** | Current requires tray icon or console; no pure daemon mode |

**Personas**: P4

---

#### PWR-3: Scheduled Processing

**User Story**: "As a user who wants to control resource usage, I want Sift to only process at certain times."

**Trigger**: User wants processing to happen overnight to avoid slowing down work computer.

**Feature**: Processing schedule (active hours), pause/resume API, scheduled batch runs.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Scheduler integration, configuration |
| **Evidence** | Pause/resume exists (`@src/tray_icon.py:195-200`) but no scheduling |

**Personas**: P4

---

#### PWR-4: Webhook Triggers

**User Story**: "As someone integrating Sift with other tools, I want to trigger processing via HTTP."

**Trigger**: User wants their scanner software to trigger Sift when a scan completes.

**Feature**: Webhook endpoint for: process file, reprocess folder, get status.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | API authentication, endpoint design |
| **Evidence** | Dashboard has internal API but no external trigger endpoints |

**Personas**: P4

---

#### PWR-5: Event Hooks

**User Story**: "As a power user, I want to run custom scripts when documents are classified."

**Trigger**: User wants to automatically upload tax documents to their accountant's portal.

**Feature**: Configurable hooks: on_classify, on_error, on_review_needed with script execution.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Hook system design, subprocess management |
| **Evidence** | No hook system exists |

**Personas**: P4

---

### Export/Import Needs

#### PWR-6: Full System Export

**User Story**: "As someone migrating to a new computer, I want to export everything and restore on new machine."

**Trigger**: User gets new computer and needs to migrate Sift with all history and settings.

**Feature**: Complete export (config, rules, database, corrections) and import commands.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Export format design, path remapping on import |
| **Evidence** | No export/import functionality exists |

**Personas**: P1, P4

---

#### PWR-7: Rule Export/Import

**User Story**: "As someone who created good rules, I want to share them with others."

**Trigger**: User creates rules for common vendors (Chase, Amazon, IRS) and wants to share.

**Feature**: Rule export to JSON/YAML, rule import, rule repository concept.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Rule serialization |
| **Evidence** | Rules in config but no sharing mechanism |

**Personas**: P4

---

#### PWR-8: History Export

**User Story**: "As someone who wants to analyze my documents, I want to export classification history."

**Trigger**: User wants to build custom reports or analyze patterns outside Sift.

**Feature**: Export to CSV/JSON: all documents with metadata, activity log, statistics.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Export format, database query |
| **Evidence** | No export functionality; data only accessible via dashboard |

**Personas**: P1, P4

---

#### PWR-9: Import from Folder Structure

**User Story**: "As someone with existing organization, I want Sift to learn from my current folders."

**Trigger**: User has 10,000 documents already organized and wants Sift to manage them going forward.

**Feature**: Import existing folder structure, infer categories from folders, bulk database population.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Folder scanning, category inference |
| **Evidence** | No import from existing structure |

**Personas**: P2, P4

---

### Integration Needs

#### PWR-10: Alternative LLM Backends

**User Story**: "As someone who prefers Ollama (or other backends), I want to use my preferred LLM system."

**Trigger**: User has Ollama running and doesn't want to also run LMStudio.

**Feature**: Pluggable LLM backend: Ollama, llama.cpp direct, OpenAI-compatible APIs.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Backend abstraction, configuration |
| **Evidence** | Hardcoded LMStudio in `@src/llm_client.py`; OpenAI-compatible but not flexible |

**Personas**: P4

---

#### PWR-11: Cloud Backup Sync (Optional)

**User Story**: "As someone who wants off-site backup, I want to optionally sync to cloud storage."

**Trigger**: User wants encrypted backup of Sift data (not documents) to cloud.

**Feature**: Optional encrypted sync of database/config to: Dropbox, Google Drive, S3.

| Aspect | Detail |
|--------|--------|
| **Effort** | L (Large) |
| **Dependencies** | Cloud APIs, encryption, user consent |
| **Evidence** | No cloud features exist (privacy-first) |

**Personas**: P3

---

#### PWR-12: Email Attachment Processing

**User Story**: "As someone who receives documents via email, I want attachments automatically processed."

**Trigger**: User receives invoices as email attachments and manually saves them to Inbox.

**Feature**: Email monitoring (IMAP), attachment extraction, automatic processing.

| Aspect | Detail |
|--------|--------|
| **Effort** | L (Large) |
| **Dependencies** | Email credentials, attachment handling, security |
| **Evidence** | No email integration exists |

**Personas**: P3

---

#### PWR-13: Scanner Integration

**User Story**: "As someone who scans documents, I want my scanner to feed directly into Sift."

**Trigger**: User scans documents and manually moves them from scanner output to Inbox.

**Feature**: Watch scanner output folder, handle scanner naming patterns, batch scan support.

| Aspect | Detail |
|--------|--------|
| **Effort** | S (Small) |
| **Dependencies** | Multiple watch folders (LAT-10) |
| **Evidence** | Single watch folder; scanner output usually separate |

**Personas**: P1, P3

---

#### PWR-14: Mobile Companion (View-Only)

**User Story**: "As someone who works across devices, I want to view my documents from my phone."

**Trigger**: User needs to find a document while away from computer.

**Feature**: Mobile-friendly dashboard view, optional remote access with authentication.

| Aspect | Detail |
|--------|--------|
| **Effort** | L (Large) |
| **Dependencies** | Authentication, HTTPS, responsive UI |
| **Evidence** | Dashboard binds to localhost only (`@src/dashboard.py:2298`) |

**Personas**: P3

---

### Extensibility Needs

#### PWR-15: Plugin Architecture

**User Story**: "As a developer, I want to extend Sift with custom functionality."

**Trigger**: User wants to add custom document type support or integration.

**Feature**: Plugin system with: custom extractors, custom classifiers, custom post-processors.

| Aspect | Detail |
|--------|--------|
| **Effort** | L (Large) |
| **Dependencies** | Architecture changes, plugin API design |
| **Evidence** | Monolithic architecture; no plugin concept |

**Personas**: P4

---

#### PWR-16: Custom Document Extractors

**User Story**: "As someone with proprietary document formats, I want to add extraction support."

**Trigger**: User has custom CAD files or proprietary formats that Sift can't read.

**Feature**: Extractor registration, custom extraction scripts, format metadata.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | Extractor interface, registration mechanism |
| **Evidence** | Extractors hardcoded in `@src/document_processor.py` |

**Personas**: P4

---

#### PWR-17: External API

**User Story**: "As a developer, I want to build tools that query Sift's data."

**Trigger**: User wants to build a custom dashboard or integrate with other tools.

**Feature**: Documented REST API with authentication, OpenAPI spec.

| Aspect | Detail |
|--------|--------|
| **Effort** | M (Medium) |
| **Dependencies** | API documentation, authentication |
| **Evidence** | Internal API exists (`@src/dashboard.py`) but undocumented |

**Personas**: P4

---

## Summary Matrix

### By Priority (Impact × Frequency)

| Priority | Needs | Rationale |
|----------|-------|-----------|
| **Critical** | CUR-1, CUR-2, CUR-4, TRU-5, TRU-12 | Core value proposition and data safety |
| **High** | LAT-1, LAT-2, LAT-6, TRU-6, TRU-8, PWR-6 | Scaling blockers and migration |
| **Medium** | LAT-3, LAT-5, LAT-10, TRU-1, TRU-9, PWR-1, PWR-8 | Power user and enterprise features |
| **Low** | LAT-11, LAT-12, PWR-11, PWR-12, PWR-14, PWR-15 | Nice-to-have, long-term vision |

### By Persona

| Persona | Critical Needs | Growth Needs |
|---------|---------------|--------------|
| **P1 (Professional)** | TRU-1, TRU-5, TRU-9, TRU-12 | TRU-11, LAT-8, LAT-10 |
| **P2 (Hoarder)** | CUR-9, LAT-1, LAT-2 | LAT-4, LAT-5, PWR-9 |
| **P3 (Business)** | CUR-1, LAT-6, TRU-7 | PWR-12, PWR-13, LAT-10 |
| **P4 (Enthusiast)** | PWR-1, PWR-2, PWR-10 | PWR-5, PWR-15, PWR-17 |

### By Effort

| Effort | Count | Examples |
|--------|-------|----------|
| **Small** | 14 | TRU-2, TRU-3, TRU-4, TRU-6, PWR-2, PWR-7, PWR-8 |
| **Medium** | 20 | LAT-1, LAT-2, LAT-4, TRU-1, TRU-7, PWR-1, PWR-6 |
| **Large** | 9 | LAT-3, LAT-10, LAT-11, TRU-14, PWR-11, PWR-15 |

---

## Recommended Development Sequence

### Phase 1: Trust Foundation (1-2 months)
Build trust features that enable mission-critical use:
1. TRU-12: Automated backups
2. TRU-6: Orphan detection
3. TRU-5: File integrity verification
4. TRU-9: Complete activity log

### Phase 2: Scale Readiness (2-3 months)
Enable growth without hitting walls:
1. LAT-1: Dashboard pagination
2. LAT-2: Duplicate detection
3. LAT-6: Historical reports
4. PWR-8: History export

### Phase 3: Power User Enablement (2-3 months)
Attract and retain technical users:
1. PWR-1: CLI for scripting
2. PWR-2: Headless mode
3. PWR-10: Alternative LLM backends
4. PWR-6: Full system export

### Phase 4: Enterprise Features (3-6 months)
Enable professional/compliance use:
1. TRU-1: Network activity verification
2. TRU-11: Compliance reporting
3. LAT-10: Multiple watch folders
4. LAT-8: Document retention policies

---

## Changelog

| Date | Change |
|------|--------|
| 2025-12-24 | Initial latent needs analysis |
