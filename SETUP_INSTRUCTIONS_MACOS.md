# Smart Document Folder System - macOS Setup Guide

Welcome! This guide will help you set up Smart Folder on your Mac.

## What is Smart Folder?

Smart Folder is an AI-powered document organization system that:
- Watches your Inbox folder for new documents
- Uses a local AI model to understand what each document is about
- Automatically moves documents to the appropriate category folder

**100% Private**: All processing happens on your Mac. Documents never leave your computer.

---

## Prerequisites

Before starting, you need:

1. **macOS 11 (Big Sur) or later**
2. **At least 8GB RAM** (16GB recommended for smooth AI operation)
3. **~10GB free disk space** (for LMStudio and AI models)

---

## Installation Steps

### Step 1: Extract the Files

1. Extract the ZIP file you received
2. Move the `SmartFolder` folder to a convenient location (e.g., your home folder or Applications)
3. Open Terminal (press `Cmd + Space`, type "Terminal", press Enter)
4. Navigate to the SmartFolder folder:
   ```bash
   cd ~/SmartFolder  # or wherever you placed it
   ```

### Step 2: Run the Setup Script

Make the setup script executable and run it:

```bash
chmod +x setup_macos.sh
./setup_macos.sh
```

This will automatically:
- Install Homebrew (if needed)
- Install Poppler for PDF processing
- Install libmagic for file type detection
- Create a Python virtual environment
- Install all dependencies
- Create your SmartFolder directory structure

### Step 3: Install LMStudio

LMStudio is a free application that runs AI models locally on your Mac.

1. Download LMStudio from: **https://lmstudio.ai**
2. Install it like any other Mac app (drag to Applications)
3. Open LMStudio

### Step 4: Download an AI Model

1. In LMStudio, click the **Search** icon (magnifying glass) in the left sidebar
2. Search for: `qwen3-1.7b`
3. Download the model (about 1.5GB)
4. Wait for the download to complete

### Step 5: Start the LMStudio Server

1. In LMStudio, click the **Developer** tab (< > icon) in the left sidebar
2. Select your downloaded model from the dropdown
3. Click **Start Server**
4. You should see "Server running on port 1234" message

### Step 6: Run Smart Folder

In Terminal, from the SmartFolder directory:

```bash
./run_smartfolder.sh
```

You should see:
```
Smart Document Folder System - Starting
LMStudio connected.
Watching folder: /Users/yourname/Documents/SmartFolder/Inbox
```

### Step 7: Test It!

1. Find any document (PDF, Word doc, image, etc.)
2. Copy or move it to `~/Documents/SmartFolder/Inbox`
3. Watch Smart Folder automatically classify and organize it!

---

## Daily Usage

### Starting Smart Folder

```bash
./run_smartfolder.sh
```

### Running in Background (with menu bar icon)

```bash
./run_background.sh
```

### Accessing the Dashboard

Open your browser to: **http://localhost:5000**

The dashboard shows:
- Recently processed documents
- Classification statistics
- Search functionality

---

## Folder Structure

After running, your SmartFolder will look like:

```
~/Documents/SmartFolder/
├── Inbox/              ← Drop documents here
├── Financial/
│   ├── Tax_Documents/
│   ├── Bank_Statements/
│   └── Invoices/
├── Medical/
├── Legal/
├── Work/
├── Personal/
├── Needs_Review/       ← Low-confidence items
└── Miscellaneous/      ← Uncategorized items
```

---

## Configuration

Edit `config/settings.yaml` to customize:
- Category names and subcategories
- Confidence threshold
- Which model to use

After editing, restart Smart Folder for changes to take effect.

---

## Troubleshooting

### "LMStudio not available"

- Make sure LMStudio is running
- Check that you've started the server (Developer tab → Start Server)
- Verify the model is loaded

### PDF processing not working

Run in Terminal:
```bash
pdftoppm -v
```

If not found, install Poppler:
```bash
brew install poppler
```

### "Permission denied" errors

Make sure scripts are executable:
```bash
chmod +x setup_macos.sh run_smartfolder.sh run_background.sh
```

### App won't start

Check logs in `logs/smart_folder.log` for error details.

---

## Uninstalling

To remove Smart Folder:

1. Delete the SmartFolder application folder
2. Optionally delete `~/Documents/SmartFolder` (contains your organized documents)
3. Uninstall LMStudio if no longer needed

---

## Need Help?

Check the logs: `logs/smart_folder.log`

Common issues:
- LMStudio server not started
- Wrong model loaded
- Poppler not installed

---

Enjoy your automatically organized documents! 📁✨

