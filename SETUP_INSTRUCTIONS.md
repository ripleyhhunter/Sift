# Smart Document Folder System - Setup Guide

An AI-powered document organizer that automatically sorts your files into categorized folders.

## What You'll Need

1. **This package** (you have it!)
2. **LMStudio** - Free AI model hosting software
3. **~10 minutes** for setup

## Step 1: Install LMStudio

1. Go to **https://lmstudio.ai**
2. Download LMStudio for Windows
3. Install it (just run the installer, defaults are fine)

## Step 2: Download the AI Model

1. Open **LMStudio**
2. Click the **Search** icon (magnifying glass) on the left
3. Search for: `qwen/qwen3-4b`
4. Click **Download** on the Qwen3-4B model (~2.5 GB download)
5. Wait for the download to complete

## Step 3: Start the LMStudio Server

1. In LMStudio, click the **Developer** tab (looks like `</>`)
2. Select the **qwen/qwen3-4b** model from the dropdown
3. Click **Start Server**
4. You should see "Server started on port 1234"
5. **Keep LMStudio running** while using Smart Folder

## Step 4: Run the Setup Script

1. Open this folder in File Explorer
2. **Double-click `setup_friend.bat`**
3. Follow any prompts

This will:
- Install Poppler (for PDF processing)
- Create your SmartFolder directory structure
- Set up the configuration

## Step 5: Start Using Smart Folder

1. Make sure LMStudio is running with the server started
2. **Double-click `run_smartfolder.bat`**
3. The system will start watching your Inbox folder

## How to Use

1. Drop any document into: `Documents\SmartFolder\Inbox`
2. Wait a few seconds (the AI analyzes the document)
3. The document will be automatically moved to the appropriate folder!

### Supported File Types
- PDF documents
- Word documents (.docx, .doc)
- Excel spreadsheets (.xlsx, .xls, .csv)
- Images (.png, .jpg, .jpeg)

### Default Folder Categories
- **Financial** - Tax forms, bank statements, invoices
- **Medical** - Medical records, insurance, prescriptions
- **Legal** - Contracts, agreements, legal documents
- **Work** - Employment docs, reports, projects
- **Education** - Transcripts, certificates, applications
- **Personal** - Birth certificates, personal correspondence
- **Receipts** - Purchase receipts, order confirmations
- And more...

## Customization

Edit `SmartFolder\config\settings.yaml` to:
- Change folder locations
- Add/modify categories and subcategories
- Adjust AI settings

## Troubleshooting

### "LMStudio not available" error
- Make sure LMStudio is running
- Make sure the server is started (Developer tab → Start Server)
- Check that port 1234 is not blocked

### Documents not being processed
- Check the `logs\smart_folder.log` file for errors
- Make sure the file type is supported
- Try restarting the application

### Slow classification
- This is normal - the AI takes 30-90 seconds per document
- You can load a faster model in LMStudio if needed

## Need Help?

Check the log file at `SmartFolder\logs\smart_folder.log` for detailed information about what's happening.

---

Enjoy your automatically organized documents! 📁✨

