"""
Build script to create a distributable package of Sift.

This script:
1. Uses PyInstaller to create a standalone executable
2. Bundles Poppler for PDF processing
3. Creates a ZIP package ready for distribution

Requirements:
    pip install pyinstaller

Usage:
    python build_package.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_pyinstaller():
    """Check if PyInstaller is installed."""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def install_pyinstaller():
    """Install PyInstaller."""
    print("Installing PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build_executable():
    """Build the executable using PyInstaller."""
    print("\n" + "="*60)
    print("Building executable with PyInstaller...")
    print("="*60 + "\n")
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "Sift",
        "--onedir",  # Create a folder with exe and dependencies (more reliable)
        "--console",  # Keep console for logging (can change to --windowed later)
        "--noconfirm",  # Overwrite without asking
        "--clean",  # Clean cache
        # Add hidden imports that PyInstaller might miss
        "--hidden-import", "watchdog.observers",
        "--hidden-import", "watchdog.events",
        "--hidden-import", "rapidfuzz",
        "--hidden-import", "yaml",
        "--hidden-import", "pypdf",
        "--hidden-import", "openpyxl",
        # Entry point
        "src/main.py"
    ]
    
    subprocess.check_call(cmd)
    print("\n[OK] Executable built successfully!")


def create_distribution_package():
    """Create the final distribution package."""
    print("\n" + "="*60)
    print("Creating distribution package...")
    print("="*60 + "\n")
    
    dist_dir = Path("dist/Sift")
    package_dir = Path("dist/Sift_Package")
    
    # Clean and create package directory
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    
    # Copy the built executable folder
    print("Copying executable...")
    shutil.copytree(dist_dir, package_dir / "Sift")
    
    # Copy config folder
    print("Copying configuration...")
    config_src = Path("config")
    config_dst = package_dir / "Sift" / "config"
    if config_src.exists():
        shutil.copytree(config_src, config_dst)
    
    # Create logs and temp directories
    (package_dir / "Sift" / "logs").mkdir(exist_ok=True)
    (package_dir / "Sift" / "temp").mkdir(exist_ok=True)
    
    # Copy setup files
    print("Copying setup files...")
    setup_files = ["SETUP_INSTRUCTIONS.md", "setup_friend.bat", "run_smartfolder.bat"]
    for f in setup_files:
        if Path(f).exists():
            shutil.copy(f, package_dir)
    
    # Check if Poppler exists and copy it
    poppler_path = Path("C:/Program Files/poppler")
    if poppler_path.exists():
        print("Bundling Poppler...")
        shutil.copytree(poppler_path, package_dir / "poppler")
    else:
        print("[!] Poppler not found - friend will need to install separately")
    
    # Create the ZIP file
    print("\nCreating ZIP archive...")
    zip_path = Path("dist/Sift_Windows")
    shutil.make_archive(str(zip_path), 'zip', package_dir)
    
    print(f"\n[OK] Package created: {zip_path}.zip")
    print(f"  Size: {(zip_path.with_suffix('.zip').stat().st_size / 1024 / 1024):.1f} MB")
    
    return zip_path.with_suffix('.zip')


def main():
    print("="*60)
    print("Sift - Build Package")
    print("="*60)
    
    # Check/install PyInstaller
    if not check_pyinstaller():
        install_pyinstaller()
    
    # Build executable
    build_executable()
    
    # Create distribution package
    zip_file = create_distribution_package()
    
    print("\n" + "="*60)
    print("BUILD COMPLETE!")
    print("="*60)
    print(f"\nDistribution package: {zip_file}")
    print("\nShare this ZIP file with your friend along with the")
    print("SETUP_INSTRUCTIONS.md file (included in the ZIP).")
    print("\nYour friend will need to:")
    print("1. Extract the ZIP")
    print("2. Install LMStudio from https://lmstudio.ai")
    print("3. Run setup_friend.bat")
    print("4. Start LMStudio and load qwen/qwen3-4b model")
    print("5. Run run_smartfolder.bat")


if __name__ == "__main__":
    main()

