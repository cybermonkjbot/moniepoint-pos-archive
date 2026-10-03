Option Explicit
Dim files, shell, appShell, repairRoot, launcher, powershell, arguments
Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
repairRoot = files.GetParentFolderName(WScript.ScriptFullName)
launcher = files.BuildPath(repairRoot, "resume-setup.ps1")
If Not files.FileExists(launcher) Then
    MsgBox "Extract the complete repair ZIP before opening Resume K3LS.vbs.", vbCritical, "K3LS setup"
    WScript.Quit 1
End If
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe")
arguments = "-NoExit -NoProfile -ExecutionPolicy Bypass -File """ & launcher & """"
On Error Resume Next
Set appShell = CreateObject("Shell.Application")
appShell.ShellExecute powershell, arguments, repairRoot, "runas", 1
If Err.Number <> 0 Then
    MsgBox "PowerShell could not open. Approve the administrator prompt and try again." & vbCrLf & Err.Description, vbExclamation, "K3LS setup"
    WScript.Quit 1
End If
