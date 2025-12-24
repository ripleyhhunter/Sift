#!/bin/bash
# ============================================================
# Sift - macOS Setup Script
# ============================================================
# This script sets up the Sift application on macOS
#
# Prerequisites:
#   - macOS 11 (Big Sur) or later
#   - Homebrew (will be installed if missing)
#
# Usage:
#   chmod +x setup_macos.sh
#   ./setup_macos.sh
# ============================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "============================================================"
echo "   Sift - macOS Setup"
echo "============================================================"
echo ""

# Function to print status
print_status() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check for Homebrew
print_status "Checking for Homebrew..."
if command -v brew &> /dev/null; then
    print_success "Homebrew is installed"
else
    print_warning "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    print_success "Homebrew installed"
fi

# Check for Python 3.10+
print_status "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
        print_success "Python $PYTHON_VERSION found"
    else
        print_warning "Python $PYTHON_VERSION is too old. Installing Python 3.12..."
        brew install python@3.12
        print_success "Python 3.12 installed"
    fi
else
    print_warning "Python 3 not found. Installing..."
    brew install python@3.12
    print_success "Python installed"
fi

# Install Poppler (required for PDF processing)
print_status "Checking for Poppler (PDF support)..."
if command -v pdftoppm &> /dev/null; then
    print_success "Poppler is installed"
else
    print_warning "Installing Poppler..."
    brew install poppler
    print_success "Poppler installed"
fi

# Install libmagic (required for file type detection)
print_status "Checking for libmagic (file detection)..."
if brew list libmagic &> /dev/null 2>&1; then
    print_success "libmagic is installed"
else
    print_warning "Installing libmagic..."
    brew install libmagic
    print_success "libmagic installed"
fi

# Create virtual environment
print_status "Creating Python virtual environment..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    print_warning "Virtual environment already exists"
else
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements-macos.txt
print_success "Python dependencies installed"

# Setup configuration
print_status "Setting up configuration..."
if [ ! -f "config/settings.yaml" ]; then
    # Get current username
    USERNAME=$(whoami)
    
    # Copy macOS template and substitute username
    sed "s/{username}/$USERNAME/g" config/settings.macos.yaml > config/settings.yaml
    print_success "Configuration created at config/settings.yaml"
else
    print_warning "Configuration already exists, skipping..."
fi

# Create Sift directory structure
print_status "Creating Sift directories..."
SMARTFOLDER_BASE="$HOME/Documents/Sift"
mkdir -p "$SMARTFOLDER_BASE/Inbox"
mkdir -p "$SMARTFOLDER_BASE/.temp"
print_success "Created $SMARTFOLDER_BASE"

# Create logs directory
mkdir -p logs
mkdir -p temp
mkdir -p data

# Check for LibreOffice (optional)
print_status "Checking for LibreOffice (optional, for Office docs)..."
if [ -d "/Applications/LibreOffice.app" ]; then
    print_success "LibreOffice found"
else
    print_warning "LibreOffice not found. Office document conversion will be limited."
    print_warning "Install from: https://www.libreoffice.org/download/download/"
fi

# Create run script
print_status "Creating run script..."
cat > run_sift.sh << 'EOF'
#!/bin/bash
# Run Sift
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
source venv/bin/activate
python -m src.main "$@"
EOF
chmod +x run_sift.sh
print_success "Created run_sift.sh"

# Create background run script
cat > run_background.sh << 'EOF'
#!/bin/bash
# Run Sift in background with system tray
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
source venv/bin/activate
python -m src.main --background "$@" &
disown
EOF
chmod +x run_background.sh
print_success "Created run_background.sh"

echo ""
echo "============================================================"
echo -e "${GREEN}   Setup Complete!${NC}"
echo "============================================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Install LMStudio from: https://lmstudio.ai"
echo "  2. In LMStudio, download a model (e.g., qwen/qwen3-1.7b)"
echo "  3. Go to Developer tab → Start Server"
echo "  4. Run Sift:"
echo ""
echo "     ./run_sift.sh"
echo ""
echo "  5. Drop documents in: ~/Documents/Sift/Inbox"
echo ""
echo "Optional: Edit config/settings.yaml to customize categories"
echo ""

