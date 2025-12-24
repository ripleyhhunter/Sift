"""
Install Sift to run automatically at Windows startup.

This script:
1. Creates a VBS launcher for silent background execution
2. Adds a shortcut to the Windows Startup folder
3. Creates a desktop shortcut to the dashboard
"""

import os
import sys
import winreg
from pathlib import Path


def get_startup_folder() -> Path:
    """Get the Windows Startup folder path."""
    import winreg
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
    )
    startup_path = winreg.QueryValueEx(key, "Startup")[0]
    winreg.CloseKey(key)
    return Path(startup_path)


def get_desktop_folder() -> Path:
    """Get the Windows Desktop folder path."""
    import winreg
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
    )
    desktop_path = winreg.QueryValueEx(key, "Desktop")[0]
    winreg.CloseKey(key)
    return Path(desktop_path)


def create_vbs_launcher(project_root: Path) -> Path:
    """Create VBS script for silent background execution."""
    vbs_path = project_root / "Sift_Background.vbs"
    
    # VBS script that:
    # 1. Checks if already running (prevents duplicates)
    # 2. Activates virtual environment
    # 3. Runs Python silently
    # 4. Handles paths correctly
    
    vbs_content = f'''
' Sift Background Launcher
' Runs the Smart Document Folder System silently in the background

Option Explicit

Dim objShell, objFSO, objWMI, colProcesses, objProcess
Dim strProjectRoot, strPython, strScript, strCommand
Dim intRunning

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objWMI = GetObject("winmgmts://./root/cimv2")

' Project paths
strProjectRoot = "{str(project_root).replace(chr(92), chr(92) + chr(92))}"
strPython = strProjectRoot & "\\venv\\Scripts\\python.exe"
strScript = strProjectRoot & "\\src\\main.py"

' Check if already running by looking for our specific Python process
intRunning = 0
Set colProcesses = objWMI.ExecQuery("SELECT * FROM Win32_Process WHERE Name = 'python.exe'")
For Each objProcess In colProcesses
    If InStr(objProcess.CommandLine, "main.py") > 0 Then
        If InStr(objProcess.CommandLine, "Sift") > 0 Then
            intRunning = 1
            Exit For
        End If
    End If
Next

If intRunning = 1 Then
    ' Already running, exit silently
    WScript.Quit
End If

' Check if Python exists
If Not objFSO.FileExists(strPython) Then
    MsgBox "Sift Error: Python virtual environment not found." & vbCrLf & _
           "Please run install.bat first.", vbCritical, "Sift"
    WScript.Quit
End If

' Set working directory
objShell.CurrentDirectory = strProjectRoot

' Build command with environment setup and background flag
strCommand = """" & strPython & """ """ & strScript & """ --background"

' Run hidden (0 = hidden, False = don't wait)
objShell.Run strCommand, 0, False
'''
    
    with open(vbs_path, 'w') as f:
        f.write(vbs_content.strip())
    
    print(f"Created: {vbs_path}")
    return vbs_path


def create_startup_shortcut(vbs_path: Path) -> Path:
    """Create shortcut in Windows Startup folder."""
    startup_folder = get_startup_folder()
    shortcut_path = startup_folder / "Sift.lnk"
    
    # Use PowerShell to create shortcut (more reliable than win32com)
    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = '"{vbs_path}"'
$Shortcut.WorkingDirectory = "{vbs_path.parent}"
$Shortcut.Description = "Smart Document Folder System"
$Shortcut.Save()
'''
    
    import subprocess
    subprocess.run(["powershell", "-Command", ps_script], check=True)
    
    print(f"Created startup shortcut: {shortcut_path}")
    return shortcut_path


def create_dashboard_shortcut(project_root: Path) -> Path:
    """Create desktop shortcut to open the dashboard."""
    desktop_folder = get_desktop_folder()
    shortcut_path = desktop_folder / "Sift Dashboard.lnk"
    
    # Create a small batch file that opens the dashboard
    dashboard_bat = project_root / "open_dashboard.bat"
    bat_content = '''@echo off
start "" "http://localhost:5000"
'''
    with open(dashboard_bat, 'w') as f:
        f.write(bat_content)
    
    # Create shortcut
    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{dashboard_bat}"
$Shortcut.WorkingDirectory = "{project_root}"
$Shortcut.Description = "Open Sift Dashboard"
$Shortcut.IconLocation = "shell32.dll,21"
$Shortcut.Save()
'''
    
    import subprocess
    subprocess.run(["powershell", "-Command", ps_script], check=True)
    
    print(f"Created desktop shortcut: {shortcut_path}")
    return shortcut_path


def create_inbox_shortcut(config_path: Path) -> Path:
    """Create desktop shortcut to the Inbox folder."""
    import yaml
    
    # Load config to get inbox path
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    inbox_path = config.get('folders', {}).get('watch_path', '')
    inbox_path = inbox_path.replace('{username}', os.environ.get('USERNAME', ''))
    inbox_path = Path(inbox_path)
    
    if not inbox_path.exists():
        inbox_path.mkdir(parents=True, exist_ok=True)
    
    desktop_folder = get_desktop_folder()
    shortcut_path = desktop_folder / "Sift Inbox.lnk"
    
    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{inbox_path}"
$Shortcut.Description = "Drop documents here for automatic organization"
$Shortcut.IconLocation = "shell32.dll,3"
$Shortcut.Save()
'''
    
    import subprocess
    subprocess.run(["powershell", "-Command", ps_script], check=True)
    
    print(f"Created inbox shortcut: {shortcut_path}")
    return shortcut_path


def remove_startup():
    """Remove Sift from Windows startup."""
    startup_folder = get_startup_folder()
    shortcut_path = startup_folder / "Sift.lnk"
    
    if shortcut_path.exists():
        shortcut_path.unlink()
        print(f"Removed: {shortcut_path}")
        return True
    else:
        print("Sift is not configured to run at startup.")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Sift Startup Installer")
    parser.add_argument('--remove', action='store_true', help='Remove from startup')
    parser.add_argument('--no-desktop', action='store_true', help='Skip desktop shortcuts')
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.absolute()
    config_path = project_root / "config" / "settings.yaml"
    
    if args.remove:
        remove_startup()
        return
    
    print("=" * 50)
    print("Sift Startup Installer")
    print("=" * 50)
    print()
    
    # Check prerequisites
    venv_python = project_root / "venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        print("ERROR: Virtual environment not found!")
        print("Please run install.bat first.")
        return 1
    
    if not config_path.exists():
        print("ERROR: Configuration file not found!")
        print("Please ensure config/settings.yaml exists.")
        return 1
    
    # Create VBS launcher
    print("1. Creating background launcher...")
    vbs_path = create_vbs_launcher(project_root)
    
    # Add to startup
    print("2. Adding to Windows startup...")
    create_startup_shortcut(vbs_path)
    
    if not args.no_desktop:
        # Create desktop shortcuts
        print("3. Creating desktop shortcuts...")
        create_dashboard_shortcut(project_root)
        create_inbox_shortcut(config_path)
    
    print()
    print("=" * 50)
    print("Installation complete!")
    print("=" * 50)
    print()
    print("Sift will now start automatically when you log in.")
    print()
    print("Desktop shortcuts created:")
    print("  - 'Sift Dashboard' - Opens the web dashboard")
    print("  - 'Sift Inbox' - Drop documents here")
    print()
    print("To start Sift now, run:")
    print(f"  wscript \"{vbs_path}\"")
    print()
    print("To remove from startup, run:")
    print("  python install_startup.py --remove")
    print()
    
    # Offer to start now (handle non-interactive mode)
    try:
        response = input("Start Sift now? [Y/n]: ").strip().lower()
        if response != 'n':
            import subprocess
            subprocess.Popen(["wscript", str(vbs_path)])
            print("Sift started! Check the dashboard at http://localhost:5000")
    except EOFError:
        # Non-interactive mode, start automatically
        import subprocess
        subprocess.Popen(["wscript", str(vbs_path)])
        print("Sift started in background!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

