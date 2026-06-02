' Silent launcher for Start-Pensieve-Server.ps1.
'
' Invoked at logon by the Startup-folder shortcut installed by
' Install-PensieveAutoStart.ps1. WScript.Shell.Run with window style 0
' starts powershell.exe with no visible window at all — no taskbar
' entry, no flash, no console allocation prompt.
'
' This is the right pattern for a long-running foreground process
' (Pensieve's launcher runs `python -m pensieve.cli serve` in the
' foreground of the same powershell.exe), because shell.Run does NOT
' wait for the process to exit (third arg = False) and leaves
' powershell.exe running indefinitely as a hidden background process.
'
' Resolves its own location and derives the .ps1 path + repo root from
' it, so this file stays portable if the repo moves.

Option Explicit

Dim shell, fso, scriptDir, repoRoot, ps1, cmd
Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
repoRoot  = fso.GetParentFolderName(scriptDir)
ps1       = scriptDir & "\Start-Pensieve-Server.ps1"

cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & ps1 & """ -NoBrowser"

shell.CurrentDirectory = repoRoot
' Args: command string, window style (0 = hidden), bWaitOnReturn (False = fire and forget).
shell.Run cmd, 0, False
