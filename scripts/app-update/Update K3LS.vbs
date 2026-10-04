Option Explicit
Dim files, shell, packageRoot, launcher, powershell, arguments
Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
packageRoot = files.GetParentFolderName(WScript.ScriptFullName)
launcher = files.BuildPath(packageRoot, "launch-update.ps1")
If Not files.FileExists(launcher) Then
    MsgBox "Extract the complete update ZIP before opening Update K3LS.vbs.", vbCritical, "K3LS update"
    WScript.Quit 1
End If
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe")
arguments = "-NoExit -NoProfile -ExecutionPolicy Bypass -File """ & launcher & """"
On Error Resume Next
shell.Run """" & powershell & """ " & arguments, 1, False
If Err.Number <> 0 Then
    MsgBox "PowerShell could not open." & vbCrLf & Err.Description, vbExclamation, "K3LS update"
    WScript.Quit 1
End If
