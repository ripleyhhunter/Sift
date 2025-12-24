# Sift

An intelligent cross-platform document organization system that automatically monitors your inbox folder, analyzes documents using a local LLM (via LMStudio), and sifts them into appropriate subfolders based on content classification.

[![Build Sift](https://github.com/ripleyhhunter/Sift/actions/workflows/build.yml/badge.svg)](https://github.com/ripleyhhunter/Sift/actions/workflows/build.yml)

## Features

- 📁 **Automatic Folder Monitoring** - Watches an inbox folder for new documents
- 🤖 **AI-Powered Classification** - Uses local LLMs (Qwen3, Qwen2.5) to understand document content
- 📄 **Multi-Format Support** - Handles PDF, Office documents (DOCX, XLSX, PPTX), CSV, and images
- 🏷️ **Smart Categorization** - Organizes into categories like Financial, Medical, Legal, Travel, and more
- 🔒 **100% Local & Private** - All processing happens on your machine—documents never leave your system
- 🖥️ **Cross-Platform** - Works on Windows and macOS
- 🌐 **Web Dashboard** - View processed documents, search, and manage from your browser
- 🔔 **System Tray** - Background operation with notifications
- ⚙️ **Highly Configurable** - Customize categories, model profiles, and processing options

## Quick Start

### Download Pre-Built Releases

The easiest way to get started is to download a pre-built release:

**[📥 Download Latest Release](https://github.com/ripleyhhunter/Sift/releases)**

Or grab build artifacts from [GitHub Actions](https://github.com/ripleyhhunter/Sift/actions).

| Platform | Download |
|----------|----------|
| Windows | `Sift-Windows.zip` |
| macOS | `Sift-macOS.zip` |
| Source | `Sift-Source.zip` |

### Prerequisites

1. **LMStudio** - [Download LMStudio](https://lmstudio.ai/) (free, runs local AI models)
2. **A compatible model** - Download one of these in LMStudio:
   - `qwen/qwen3-1.7b` (fastest, ~1.5GB)
   - `qwen/qwen3-4b` (balanced, ~3GB)
   - `qwen/qwen2.5-7b-instruct` (most accurate, ~5GB)

### Windows Installation

1. Extract the downloaded ZIP
2. Install [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases) for PDF support
3. Run `run_sift.bat`

### macOS Installation

1. Extract the downloaded ZIP
2. Run `./install_dependencies.sh` (installs Poppler via Homebrew)
3. Run `./run_sift.sh`

---

## Installation from Source

### Windows

```cmd
# Clone the repository
git clone https://github.com/ripleyhhunter/Sift.git
cd SmartFolder

# Run the installer
install.bat

# Start the application
run.bat
```

### macOS

```bash
# Clone the repository
git clone https://github.com/ripleyhhunter/Sift.git
cd SmartFolder

# Run the setup script (installs all dependencies)
chmod +x setup_macos.sh
./setup_macos.sh

# Start the application
./run_sift.sh
```

---

## Usage

### Starting Sift

**Windows:**
```cmd
run.bat                    # Normal mode with console
run_background.bat         # Background mode with system tray
```

**macOS:**
```bash
./run_sift.sh              # Normal mode
./run_background.sh        # Background mode
```

### Command Line Options

```
--help              Show all options
--check             Verify configuration and LMStudio connection
--verbose           Enable debug logging
--scan-only         Process existing files and exit
--file <path>       Process a single file
--create-folders    Create folder structure and exit
--no-scan           Start without processing existing files
--background        Run with system tray icon
--enable-startup    Enable auto-start on login
--disable-startup   Disable auto-start
```

### Web Dashboard

When running, access the dashboard at: **http://localhost:5000**

The dashboard provides:
- 📊 Overview of processed documents
- 🔍 Search functionality
- 📈 Classification statistics
- 📝 Recent activity log

### How It Works

1. **Drop a document** into the `Inbox` folder (`Documents/Sift/Inbox`)
2. Sift **detects** the new file
3. Text is **extracted** from the document (or images for visual documents)
4. Content is **analyzed** by your local LLM via LMStudio
5. The document is **classified** into a category
6. The file is **moved** to the appropriate folder

### Folder Structure

```
Sift/
├── Inbox/              ← Drop documents here
├── Financial/
│   ├── Tax_Documents/
│   ├── Bank_Statements/
│   ├── Invoices/
│   └── Investment/
├── Medical/
│   ├── Insurance/
│   ├── Records/
│   └── Prescriptions/
├── Legal/
├── Government/
├── Insurance/
├── Work/
├── Education/
├── Personal/
├── Home/
├── Health_Fitness/
├── Travel/
├── Receipts/
├── Needs_Review/       ← Low-confidence classifications
└── Miscellaneous/      ← Fallback category
```

---

## Configuration

Edit `config/settings.yaml` to customize Sift.

### Model Profiles

Sift supports multiple model profiles for different speed/accuracy tradeoffs:

```yaml
llm:
  active_profile: "fast"  # Options: fast, balanced, accurate
  
  profiles:
    fast:
      model_identifier: "qwen/qwen3-1.7b"
      description: "Fastest - good for most documents"
    
    balanced:
      model_identifier: "qwen/qwen3-4b"
      description: "Balanced speed and accuracy"
    
    accurate:
      model_identifier: "qwen/qwen2.5-7b-instruct"
      description: "Most accurate - for complex documents"
```

### Custom Categories

Add your own categories:

```yaml
categories:
  - name: "Recipes"
    subcategories:
      - "Desserts"
      - "Main_Dishes"
      - "Appetizers"
    keywords: ["recipe", "cooking", "ingredients", "instructions"]
```

### Key Settings

```yaml
folders:
  watch_path: "/Users/you/Documents/Sift/Inbox"
  base_path: "/Users/you/Documents/Sift"

behavior:
  confidence_threshold: 0.7  # Below this → Needs_Review
  move_or_copy: "move"       # or "copy"
  preserve_original_filename: true

dashboard:
  enabled: true
  port: 5000
  auto_open_browser: true
```

---

## Troubleshooting

### LMStudio Not Responding

- Ensure LMStudio is running
- Check that a model is loaded (click on a model in LMStudio)
- Go to **Developer** tab → **Start Server**
- Verify the server is running on port 1234

### PDF Processing Fails

**Windows:**
1. Download [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases)
2. Extract to `C:\Program Files\poppler`
3. Add `C:\Program Files\poppler\Library\bin` to your system PATH

**macOS:**
```bash
brew install poppler
```

### Office Documents Not Converting

Install LibreOffice for full Office document support:
- **Windows:** [Download LibreOffice](https://www.libreoffice.org/download/)
- **macOS:** `brew install --cask libreoffice`

### Files Stuck in Inbox

1. Check logs: `logs/sift.log`
2. Verify LMStudio is running with a model loaded
3. Try processing manually: `run.bat --file "path/to/file.pdf"`

---

## Project Structure

```
Sift/
├── src/
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration management
│   ├── watcher.py           # Folder monitoring
│   ├── document_processor.py # Document text/image extraction
│   ├── llm_client.py        # LMStudio API client
│   ├── classifier.py        # Classification logic
│   ├── folder_organizer.py  # File organization
│   ├── database.py          # Document history database
│   ├── dashboard.py         # Web dashboard server
│   ├── tray_icon.py         # System tray integration
│   ├── platform_utils.py    # Cross-platform utilities
│   └── utils.py             # Helper functions
├── config/
│   ├── settings.yaml        # Your configuration
│   ├── settings.default.yaml
│   └── settings.macos.yaml  # macOS template
├── .github/
│   └── workflows/
│       └── build.yml        # CI/CD pipeline
├── logs/
├── data/
├── requirements.txt         # Windows dependencies
├── requirements-macos.txt   # macOS dependencies
└── README.md
```

---

## System Requirements

| | Minimum | Recommended |
|---|---------|-------------|
| **OS** | Windows 10 / macOS 11 | Windows 11 / macOS 13+ |
| **Python** | 3.10 | 3.11+ |
| **RAM** | 8GB | 16GB+ |
| **GPU** | None (CPU works) | 8GB+ VRAM for faster inference |
| **Storage** | 2GB + model size | 10GB+ |

---

## Security & Privacy

- **100% Local Processing** - Documents never leave your computer
- **No Cloud Services** - Everything runs locally via LMStudio
- **No Telemetry** - The application doesn't collect or send any data
- **Open Source** - Review the code yourself

---

## Building from Source

### Create Windows Executable

```cmd
pip install pyinstaller
python build_package.py
```

### Create macOS Package

```bash
pip install pyinstaller
python build_macos_package.py
```

### GitHub Actions

The repository includes a CI/CD pipeline that automatically builds for:
- Windows (`.exe` bundle)
- macOS (executable bundle)
- Source distribution

Builds are triggered on every push to `main`/`master`. Tagged releases (e.g., `v1.0.0`) automatically create GitHub Releases with downloadable assets.

---

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## License

MIT License - See LICENSE file for details.

---

## Acknowledgments

- [LMStudio](https://lmstudio.ai/) - Local LLM hosting made easy
- [Qwen](https://github.com/QwenLM/Qwen) - Excellent open-source language models
- [Watchdog](https://github.com/gorakhargosh/watchdog) - File system monitoring
- [pdf2image](https://github.com/Belval/pdf2image) - PDF processing
- [Flask](https://flask.palletsprojects.com/) - Web dashboard
- [pystray](https://github.com/moses-palmer/pystray) - System tray integration
