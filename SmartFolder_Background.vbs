' SmartFolder Background Launcher
' Runs the Smart Document Folder System silently in the background

Option Explicit

Dim objShell, objFSO, objWMI, colProcesses, objProcess
Dim strProjectRoot, strPython, strScript, strCommand
Dim intRunning

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objWMI = GetObject("winmgmts://./root/cimv2")

' Project paths
strProjectRoot = "C:\\Users\\Ripley\\OneDrive\\Documents\\Cursor Projects\\SmartFolder"
strPython = strProjectRoot & "\venv\Scripts\python.exe"
strScript = strProjectRoot & "\src\main.py"

' Check if already running by looking for our specific Python process
intRunning = 0
Set colProcesses = objWMI.ExecQuery("SELECT * FROM Win32_Process WHERE Name = 'python.exe'")
For Each objProcess In colProcesses
    If InStr(objProcess.CommandLine, "main.py") > 0 Then
        If InStr(objProcess.CommandLine, "SmartFolder") > 0 Then
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
    MsgBox "SmartFolder Error: Python virtual environment not found." & vbCrLf & _
           "Please run install.bat first.", vbCritical, "SmartFolder"
    WScript.Quit
End If

' Set working directory
objShell.CurrentDirectory = strProjectRoot

' Build command with environment setup and background flag
strCommand = """" & strPython & """ """ & strScript & """ --background"

' Run hidden (0 = hidden, False = don't wait)
objShell.Run strCommand, 0, False