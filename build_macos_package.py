"""
Build script to create a source distribution package for macOS.

This script creates a ZIP file containing everything needed to run
Sift on macOS.

Usage:
    python build_macos_package.py
"""

import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime


def create_macos_package():
    """Create a source distribution package for macOS."""
    print("=" * 60)
    print("Sift - macOS Package Builder")
    print("=" * 60)
    print()

    # Define what to include
    include_files = [
        # Source code
        "src/__init__.py",
        "src/main.py",
        "src/config.py",
        "src/watcher.py",
        "src/document_processor.py",
        "src/llm_client.py",
        "src/classifier.py",
        "src/folder_organizer.py",
        "src/database.py",
        "src/dashboard.py",
        "src/tray_icon.py",
        "src/utils.py",
        "src/platform_utils.py",
        
        # Configuration
        "config/settings.default.yaml",
        "config/settings.macos.yaml",
        
        # Requirements
        "requirements.txt",
        "requirements-macos.txt",
        
        # Setup and run scripts
        "setup_macos.sh",
        
        # Documentation
        "README.md",
        "SETUP_INSTRUCTIONS_MACOS.md",
    ]
    
    include_dirs = [
        "src/templates",  # If you have Flask templates
        "src/static",     # If you have static files
    ]
    
    # Create package directory
    package_name = "Sift_macOS"
    package_dir = Path("dist") / package_name
    
    print(f"[*] Creating package: {package_dir}")
    
    # Clean existing
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    
    # Copy files
    print("[*] Copying source files...")
    for file_path in include_files:
        src = Path(file_path)
        if src.exists():
            dst = package_dir / file_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"    + {file_path}")
        else:
            print(f"    - {file_path} (not found, skipping)")
    
    # Copy directories
    for dir_path in include_dirs:
        src = Path(dir_path)
        if src.exists() and src.is_dir():
            dst = package_dir / dir_path
            shutil.copytree(src, dst)
            print(f"    + {dir_path}/")
    
    # Create empty directories
    print("[*] Creating directory structure...")
    (package_dir / "logs").mkdir(exist_ok=True)
    (package_dir / "temp").mkdir(exist_ok=True)
    (package_dir / "data").mkdir(exist_ok=True)
    
    # Create .gitkeep files to preserve empty dirs
    (package_dir / "logs" / ".gitkeep").touch()
    (package_dir / "temp" / ".gitkeep").touch()
    (package_dir / "data" / ".gitkeep").touch()
    
    # Create ZIP file
    print("[*] Creating ZIP archive...")
    zip_path = Path("dist") / f"{package_name}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in package_dir.rglob('*'):
            if file.is_file():
                arcname = file.relative_to(package_dir.parent)
                zf.write(file, arcname)
    
    # Calculate size
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    
    print()
    print("=" * 60)
    print("[OK] Package created successfully!")
    print("=" * 60)
    print()
    print(f"    Location: {zip_path.absolute()}")
    print(f"    Size: {size_mb:.1f} MB")
    print()
    print("To share with your Mac friend:")
    print()
    print("  1. Send them the ZIP file")
    print("  2. They extract it and run: ./setup_macos.sh")
    print("  3. Follow the instructions in SETUP_INSTRUCTIONS_MACOS.md")
    print()
    
    return zip_path


if __name__ == "__main__":
    create_macos_package()

