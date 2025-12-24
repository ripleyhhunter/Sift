# Smart Document Folder System

An intelligent Windows-based document organization system that automatically monitors a designated folder, analyzes documents using a local vision-language model (Qwen2.5-VL via LMStudio), and organizes them into appropriate subfolders based on content classification.

## Features

- 📁 **Automatic Folder Monitoring**: Watches an inbox folder for new documents
- 🤖 **AI-Powered Classification**: Uses Qwen2.5-VL vision model to understand document content
- 📄 **Multi-Format Support**: Handles PDF, Office documents (DOCX, XLSX, PPTX), and images
- 🏷️ **Smart Categorization**: Organizes into categories like Financial, Medical, Legal, etc.
- 🔒 **100% Local Processing**: All analysis happens on your machine - documents never leave your system
- ⚙️ **Highly Configurable**: Customize categories, behavior, and processing options

## Prerequisites

Before installation, ensure you have:

1. **Python 3.10+** - [Download Python](https://www.python.org/downloads/)
2. **LMStudio** - [Download LMStudio](https://lmstudio.ai/)
3. **Qwen2.5-VL 7B Instruct** - Download through LMStudio's model browser
4. **Poppler** (for PDF support) - [Download Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases)
5. **LibreOffice** (optional, for Office documents) - [Download LibreOffice](https://www.libreoffice.org/download/)

### Installing Poppler (Required for PDFs)

1. Download the latest release from [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
2. Extract to `C:\Program Files\poppler`
3. Add `C:\Program Files\poppler\Library\bin` to your system PATH
4. Restart any open terminals

Verify installation:
```cmd
pdftoppm -v
```

## Installation

1. **Clone or download this repository**

2. **Run the installation script**:
   ```cmd
   install.bat
   ```

3. **Configure settings** (optional):
   Edit `config\settings.yaml` to customize:
   - Watch folder location
   - Category definitions
   - Processing options

4. **Start LMStudio**:
   - Open LMStudio
   - Load the Qwen2.5-VL 7B Instruct model
   - Go to Developer tab → Start Server
   - Ensure it's running on `http://localhost:1234`

## Usage

### Start the Service

```cmd
run.bat
```

The system will:
1. Connect to LMStudio
2. Create the folder structure (if needed)
3. Process any existing files in the Inbox
4. Start watching for new files

### Command Line Options

```cmd
run.bat --help              # Show all options
run.bat --check             # Verify configuration and LMStudio connection
run.bat --verbose           # Enable debug logging
run.bat --scan-only         # Process existing files and exit
run.bat --file document.pdf # Process a single file
run.bat --create-folders    # Create folder structure and exit
run.bat --no-scan           # Start without processing existing files
```

### How It Works

1. **Drop a document** into the `Inbox` folder (default: `Documents\SmartFolder\Inbox`)
2. The system **detects** the new file
3. The document is **converted** to images
4. Images are **analyzed** by the Qwen2.5-VL model
5. Based on the analysis, the document is **classified**
6. The file is **moved** to the appropriate category folder

### Folder Structure

After setup, your SmartFolder will look like:
```
SmartFolder/
├── Inbox/              # Drop documents here
├── Financial/
│   ├── Tax_Documents/
│   ├── Bank_Statements/
│   ├── Invoices/
│   └── ...
├── Medical/
│   ├── Insurance/
│   ├── Records/
│   └── ...
├── Legal/
├── Government/
├── Insurance/
├── Work/
├── Education/
├── Personal/
├── Receipts/
├── Needs_Review/       # Low-confidence classifications
└── Miscellaneous/      # Fallback category
```

## Configuration

Edit `config\settings.yaml` to customize the system.

### Key Settings

```yaml
# Watch path - where to drop new documents
folders:
  watch_path: "C:\\Users\\{username}\\Documents\\SmartFolder\\Inbox"

# LMStudio connection
llm:
  base_url: "http://localhost:1234/v1"
  model_identifier: "qwen2.5-vl-7b-instruct"
  timeout_seconds: 120

# Classification behavior
behavior:
  confidence_threshold: 0.7  # Below this → Needs_Review folder
  move_or_copy: "move"       # or "copy"
  preserve_original_filename: true
```

### Adding Custom Categories

```yaml
categories:
  - name: "Recipes"
    subcategories:
      - "Desserts"
      - "Main_Dishes"
      - "Appetizers"
    keywords: ["recipe", "cooking", "ingredients", "instructions"]
```

## Troubleshooting

### LMStudio Not Responding

- Ensure LMStudio is running
- Check that a model is loaded (Model tab)
- Verify the server is started (Developer tab → Start Server)
- Check the port matches your config (default: 1234)

### PDF Processing Fails

- Verify Poppler is installed: `pdftoppm -v`
- Ensure Poppler's bin directory is in PATH
- Restart terminal after adding to PATH

### Office Documents Not Converting

- Install LibreOffice
- Ensure it's the full installation (not just Writer)
- LibreOffice's `soffice.exe` should be accessible

### Low Classification Accuracy

- Increase `max_pages_to_analyze` for multi-page documents
- Increase `image_dpi` for better quality
- Lower `confidence_threshold` if too many items go to review
- Add relevant keywords to category definitions

### Files Stuck in Inbox

- Check logs: `logs\smart_folder.log`
- Ensure LMStudio is running
- Try processing manually: `run.bat --file "path\to\file.pdf"`

## Running at Startup

### Option 1: Startup Shortcut
1. Press `Win + R`, type `shell:startup`
2. Create a shortcut to `run_background.vbs`

### Option 2: Task Scheduler
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: At log on
4. Action: Start a program
5. Program: `wscript.exe`
6. Arguments: `"C:\path\to\run_background.vbs"`

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌────────────┐
│   Inbox     │───▶│  Document    │───▶│  LMStudio  │
│   Folder    │    │  Processor   │    │  (Qwen2.5) │
└─────────────┘    └──────────────┘    └─────┬──────┘
                                             │
                   ┌──────────────┐    ┌─────▼──────┐
                   │   Folder     │◀───│ Classifier │
                   │   Organizer  │    │            │
                   └──────┬───────┘    └────────────┘
                          │
                   ┌──────▼───────┐
                   │  Organized   │
                   │  Folders     │
                   └──────────────┘
```

## Project Structure

```
SmartDocumentFolder/
├── src/
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration management
│   ├── watcher.py           # Folder monitoring
│   ├── document_processor.py # Document conversion
│   ├── llm_client.py        # LMStudio API client
│   ├── classifier.py        # Classification logic
│   ├── folder_organizer.py  # File organization
│   └── utils.py             # Utility functions
├── config/
│   ├── settings.yaml        # User configuration
│   └── settings.default.yaml
├── logs/
│   └── smart_folder.log
├── requirements.txt
├── install.bat
├── run.bat
└── README.md
```

## Requirements

- Windows 10/11
- Python 3.10+
- 8GB+ RAM (16GB recommended for smooth LMStudio operation)
- GPU with 8GB+ VRAM recommended (CPU inference works but is slower)

## Security & Privacy

- **100% Local**: All processing happens on your machine
- **No Cloud Services**: Documents never leave your system
- **No Telemetry**: The application doesn't phone home
- **Open Source**: Review the code yourself

## Performance Tips

- Start with `max_pages_to_analyze: 3` for speed
- Use `image_dpi: 150` for balance of quality and speed
- Process one file at a time (`concurrent_processing: false`)
- Use a GPU for faster LLM inference

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Acknowledgments

- [LMStudio](https://lmstudio.ai/) for local LLM hosting
- [Qwen2.5-VL](https://github.com/QwenLM/Qwen2-VL) for the vision-language model
- [Watchdog](https://github.com/gorakhargosh/watchdog) for file system monitoring
- [pdf2image](https://github.com/Belval/pdf2image) for PDF processing

