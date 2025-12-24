' Smart Document Folder - Background Runner
' ==========================================
' This script runs the Smart Document Folder System in the background
' without a visible console window. Useful for startup.

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Get the script's directory
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' Build the command
pythonPath = scriptDir & "\venv\Scripts\pythonw.exe"
mainScript = scriptDir & "\src\main.py"

' Check if virtual environment exists
If Not FSO.FileExists(pythonPath) Then
    MsgBox "Virtual environment not found!" & vbCrLf & _
           "Please run install.bat first.", vbExclamation, "Smart Document Folder"
    WScript.Quit 1
End If

' Run the application in the background
WshShell.CurrentDirectory = scriptDir
WshShell.Run """" & pythonPath & """ """ & mainScript & """", 0, False

