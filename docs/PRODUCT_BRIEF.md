# Sift Product Brief

This document describes who Sift is for, what problems it solves, and where it excels or falls short.

---

## Target Personas

### Persona 1: The Privacy-Conscious Professional

**Who they are**: Lawyers, accountants, healthcare workers, or anyone handling sensitive documents (client files, medical records, financial statements). They're technically competent—comfortable with command lines and configuration files—but not necessarily developers.

**Their situation**:
- Deals with confidential documents daily
- Has regulatory or ethical obligations around data privacy (HIPAA, attorney-client privilege, financial regulations)
- Distrusts cloud services after hearing about breaches
- Has accumulated years of digital documents across multiple systems
- Currently uses manual folder hierarchies or simple naming conventions

**Their frustrations**:
- "I can't use cloud AI tools because my documents contain client information"
- "I spend 20 minutes a week just filing documents into the right folders"
- "When I need an old document, I waste time searching through nested folders"
- "My current system relies on me remembering my own naming conventions"

**Evidence from codebase**: The privacy-first architecture (`localhost:1234` for LMStudio, `127.0.0.1:5000` for dashboard) and zero telemetry design directly address this persona's core concern.

---

### Persona 2: The Digital Hoarder

**Who they are**: Knowledge workers, researchers, or anyone who downloads, scans, and saves "everything" but never organizes it. They have a Downloads folder with 3,000 files and an "Inbox" folder that's become a graveyard.

**Their situation**:
- Has thousands of unorganized PDFs, receipts, scanned documents
- Periodically tries to "get organized" but gives up after an hour
- Knows important documents exist somewhere but can't find them
- Has tried various apps but found them too rigid or too manual

**Their frustrations**:
- "I know I have that receipt somewhere, but finding it would take longer than just requesting a new one"
- "Every January I panic about finding tax documents"
- "I've tried organizing before but I can never stick with a system"
- "Most tools want me to manually tag everything—I need something automatic"

**Evidence from codebase**: The `--scan-only` mode (`@src/main.py:650-675`) and batch processing capabilities directly address the "catch up" use case. The learning system (`@src/database.py:1107-1238`) means the more they correct, the less they need to correct.

---

### Persona 3: The Small Business Owner

**Who they are**: Freelancers, consultants, or small business owners who handle their own paperwork. They receive invoices, send contracts, collect receipts, and dread tax season.

**Their situation**:
- Receives 10-50 documents per week (invoices, receipts, contracts, statements)
- Needs to find documents for: tax preparation, client disputes, expense reports
- Values time savings but has limited patience for technical setup
- May have an assistant or spouse who also needs access

**Their frustrations**:
- "At tax time, I spend days hunting down receipts and invoices"
- "When a client disputes a contract term, I need to find the original quickly"
- "I lose money because I forget to expense things I can't find"
- "I need something that just works without me thinking about it"

**Evidence from codebase**: The custom rules engine (`@src/rules_engine.py`) can be configured once for common document types (invoices from specific vendors, bank statements with predictable names), then runs hands-off. The search functionality (`@src/database.py:706-808`) with full-text indexing addresses the "find it fast" need.

---

### Persona 4: The Local-AI Enthusiast

**Who they are**: Technical users excited about running AI locally. They've set up LMStudio, Ollama, or similar tools. They want to build personal infrastructure that doesn't depend on cloud services.

**Their situation**:
- Already running LMStudio or similar for other purposes
- Interested in practical applications for local LLMs
- Comfortable with Python, configuration files, and debugging
- May want to customize or extend the tool

**Their frustrations**:
- "I have this powerful local LLM sitting idle most of the time"
- "Most 'AI-powered' tools require cloud APIs and monthly subscriptions"
- "I want to build useful automation without sending my data to OpenAI"
- "I'd like something I can tinker with and improve"

**Evidence from codebase**: The model profiles system (`@src/llm_client.py:325-357`), extensive configuration options (`config/settings.yaml`), and open architecture make this a natural fit. The existing but unused vision model infrastructure (`@src/document_processor.py:553-589`) suggests room for community extension.

---

## Jobs-to-Be-Done

### Persona 1: Privacy-Conscious Professional

| Job | Frequency | Current Solution | Pain Level |
|-----|-----------|------------------|------------|
| File incoming documents without exposing them to cloud | Daily | Manual folder hierarchy | High |
| Find a specific client document quickly | Weekly | Folder browsing, filename search | Medium |
| Maintain organized records for compliance | Ongoing | Manual discipline | High |
| Prepare documents for audits or legal proceedings | Occasional | Time-consuming manual search | High |

### Persona 2: Digital Hoarder

| Job | Frequency | Current Solution | Pain Level |
|-----|-----------|------------------|------------|
| Process the backlog of unorganized files | One-time (then maintenance) | Procrastination | Very High |
| Stop new files from piling up | Daily | Downloads folder grows forever | High |
| Find "that document I know I saved" | Weekly | Frustrated searching | High |
| Feel in control of digital life | Ongoing | Anxiety and avoidance | Medium |

### Persona 3: Small Business Owner

| Job | Frequency | Current Solution | Pain Level |
|-----|-----------|------------------|------------|
| Auto-file invoices and receipts | Daily/Weekly | Manual or nothing | High |
| Gather documents for tax preparation | Annually | Multi-day hunting expedition | Very High |
| Find a contract or invoice for a client | As needed | Search through folders | Medium |
| Track what's been processed vs. pending | Ongoing | Mental tracking or paper lists | Medium |

### Persona 4: Local-AI Enthusiast

| Job | Frequency | Current Solution | Pain Level |
|-----|-----------|------------------|------------|
| Put local LLM to practical use | Ongoing | Chat interfaces, experiments | Low |
| Build privacy-respecting automation | Project-based | Custom scripts | Medium |
| Learn how others integrate LLMs into tools | Ongoing | Reading code, tutorials | Low |
| Contribute or extend open-source AI tools | Occasional | Finding suitable projects | Low |

---

## Current Value Proposition

Sift is a **privacy-first document organizer** that runs entirely on your computer, using local AI (via LMStudio) to automatically classify and file documents without ever sending your data to the cloud. Drop a PDF, Word document, or spreadsheet into your Inbox folder, and Sift reads the content, understands what it is, and moves it to the right category—all in seconds, all locally. When it's uncertain, it asks for your input, then learns from your corrections to get smarter over time. For power users, custom rules provide deterministic overrides that bypass AI entirely for predictable document types.

---

## What's Uniquely Strong

### 1. True Local Privacy
**Not just "privacy-focused"—genuinely local.**

Unlike tools that claim privacy but still phone home, Sift:
- Binds the dashboard to `127.0.0.1` only (not accessible from network)
- Communicates with LMStudio on `localhost:1234`
- Has zero telemetry, zero analytics, zero cloud dependencies
- All processing happens on your machine with your hardware

**Evidence**: `@src/dashboard.py:2298` (localhost binding), `@src/llm_client.py:644-653` (localhost API calls), no analytics code anywhere in codebase.

---

### 2. Exceptional Resilience
**Designed to never lose your documents.**

The codebase shows paranoid-level protection:
- **5-layer JSON parsing** for LLM responses (`@src/llm_client.py:669-911`)
- **Database-backed crash recovery** survives mid-processing crashes (`@src/database.py:1045-1065`)
- **Retry queue** for locked files with exponential backoff (`@src/watcher.py:506-526`)
- **Fallback chain**: Custom rules → LLM → Filename keywords → Miscellaneous
- **Safe delete** moves to review folder, never actually deletes (`@src/dashboard.py:2071-2090`)

**Evidence**: The `documents.db.corrupt` file in the actual `data/` folder shows crash recovery has been tested in production.

---

### 3. Learning System
**Gets smarter from your corrections.**

When you reassign a misclassified document:
1. Correction is recorded with document type and content snippet
2. Filename is generalized to a pattern (`Invoice_2024-01-15` → `Invoice_DATE`)
3. Future similar documents receive this correction as context
4. AI sees "the user previously corrected this type" in its prompt

**Evidence**: `@src/database.py:1107-1160` (record correction), `@src/llm_client.py:523-533` (inject into prompt)

---

### 4. Flexible Model Profiles
**Speed vs. accuracy on demand.**

Three built-in profiles with different tradeoffs:
| Profile | Model | Speed | Accuracy | Use Case |
|---------|-------|-------|----------|----------|
| Fast | qwen3-1.7b | ~2-3 sec | Good | Daily processing |
| Balanced | qwen3-4b | ~5-8 sec | Better | Default |
| Accurate | qwen2.5-7b | ~10-15 sec | Best | Complex documents |

Switchable from dashboard without restart.

**Evidence**: `@src/llm_client.py:325-357`, `@src/dashboard.py:2212-2245`

---

### 5. Custom Rules Override
**Deterministic when you need it.**

For documents with predictable patterns, rules bypass AI entirely:
```yaml
custom_rules:
  - name: "Bank Statements"
    filename_pattern: "(chase|wellsfargo).*statement"
    category: "Financial"
    subcategory: "Bank_Statements"
    priority: 90
```

Rules have confidence 1.0—no uncertainty, no review needed.

**Evidence**: `@src/rules_engine.py:67-111`, `@src/classifier.py:62-66`

---

## What's Missing or Confusing

### 1. Setup Complexity
**The cold-start problem.**

To use Sift, a user must:
1. Install Python 3.10+
2. Install and configure LMStudio
3. Download and load an appropriate model
4. Install Poppler (for PDF support)
5. Optionally install LibreOffice, Tesseract
6. Edit a YAML configuration file
7. Run batch scripts

**Impact**: Personas 2 (Digital Hoarder) and 3 (Small Business Owner) may abandon setup before experiencing value. Only Personas 1 and 4 are likely to complete it.

**Evidence**: README.md prerequisites section, `install.bat` complexity

---

### 2. No Onboarding Experience
**Dropped into the deep end.**

After installation, there's no:
- First-run wizard
- Sample documents to practice with
- Guided tour of the dashboard
- Explanation of confidence scores
- Help understanding why something was classified a certain way

**Impact**: Users don't understand what "confidence 0.72" means or why a document went to Needs_Review.

**Evidence**: No onboarding code exists in `@src/dashboard.py` or `@src/main.py`

---

### 3. Configuration is Code-Like
**YAML isn't user-friendly.**

All customization requires editing `config/settings.yaml`:
- Adding categories
- Creating custom rules
- Changing confidence thresholds
- Adjusting model profiles

There's no GUI for configuration.

**Impact**: Non-technical users (Persona 3) can't customize without help.

**Evidence**: `config/settings.default.yaml` is 160+ lines of YAML

---

### 4. PowerPoint and Images Are Second-Class
**Incomplete format support.**

| Format | Text Extraction | Classification Quality |
|--------|-----------------|------------------------|
| PDF | Full | High |
| Word | Full | High |
| Excel | Full | High |
| CSV | Full | High |
| **PowerPoint** | **None** | **Low (filename only)** |
| **Images** | **None** | **Low (filename only)** |

Users with many presentations or image-based documents will see poor results.

**Evidence**: `@src/document_processor.py:40` (TEXT_EXTRACTABLE excludes PPTX), `@src/classifier.py:72-74` (images bypass LLM)

---

### 5. No Mobile or Remote Access
**Desktop-only experience.**

The dashboard binds to localhost—this is a privacy feature, but it means:
- Can't check Sift from your phone
- Can't process documents from a laptop while desktop runs Sift
- Can't share the dashboard with a spouse or assistant

**Impact**: Persona 3 (Small Business Owner) who works across devices is limited.

**Evidence**: `@src/dashboard.py:2298` (explicit `127.0.0.1` binding)

---

### 6. No Test Suite
**Confidence in changes is manual.**

The codebase has no automated tests:
- No unit tests for the complex JSON parsing
- No integration tests for the classification pipeline
- No regression tests for crash recovery

**Impact**: Contributors (Persona 4) must manually verify changes. Refactoring is risky.

**Evidence**: No `tests/` directory, no `pytest.ini`, no test files in `src/`

---

### 7. Unclear Feedback Loop
**How do I know it's working?**

After initial setup, users may wonder:
- Is Sift actually watching my folder?
- Why did this document get classified this way?
- Is LMStudio responding slowly or has something failed?
- How many documents have been processed today?

The dashboard shows statistics, but real-time feedback during processing is limited to log files.

**Evidence**: Status shown in tray icon and dashboard, but no processing explanation UI

---

## Summary: Fit by Persona

| Persona | Fit | Why |
|---------|-----|-----|
| **Privacy-Conscious Professional** | Excellent | Core value prop aligns perfectly; technical enough for setup |
| **Digital Hoarder** | Good | Solves their problem, but setup friction may cause abandonment |
| **Small Business Owner** | Fair | Value is there, but setup/config complexity is a barrier |
| **Local-AI Enthusiast** | Excellent | Technically aligned; may contribute improvements |

---

## Opportunities

Based on this analysis, the highest-impact improvements would be:

1. **Reduce setup friction** - One-click installer, bundled dependencies, or Docker container
2. **Add onboarding** - First-run wizard, sample documents, guided tour
3. **GUI configuration** - Dashboard settings page for categories, rules, thresholds
4. **PowerPoint/Image support** - Add python-pptx and image OCR
5. **Real-time processing feedback** - Show what's happening in dashboard during processing

These would expand Sift from a tool for technical users (Personas 1 & 4) to one accessible to broader audiences (Personas 2 & 3).
