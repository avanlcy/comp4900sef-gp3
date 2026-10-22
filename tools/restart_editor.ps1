<#
.SYNOPSIS
  Saves and quits the running editor, optionally installs the last-built authoring plugin, relaunches the editor
  on the project and waits until Python remote execution answers.

.EXAMPLE
  .\tools\restart_editor.ps1                 # plain restart
  .\tools\restart_editor.ps1 -InstallPlugin  # after .\tools\build_authoring_plugin.ps1 -NoInstall
#>
param(
    [switch]$InstallPlugin,
    [string]$EnginePath = "D:\UE_4.27",
    [string]$HostDir = (Join-Path $env:LOCALAPPDATA "DFPluginHost"),
    [int]$TimeoutSeconds = 300
)
$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$project = Join-Path $repo "comp4900sef\comp4900sef.uproject"
$remote = Join-Path $PSScriptRoot "ue_remote.py"

if (Get-Process UE4Editor -ErrorAction SilentlyContinue) {
    & python $remote --code "import unreal; unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)" 2>&1 | Out-Null
    & python $remote --console "QUIT_EDITOR" 2>&1 | Out-Null
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Process UE4Editor -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
    if (Get-Process UE4Editor -ErrorAction SilentlyContinue) { Stop-Process -Name UE4Editor -Force; Start-Sleep -Seconds 3 }
}

if ($InstallPlugin) {
    $built = Join-Path $HostDir "Plugins\DFBlueprintAuthoring"
    $dest = Join-Path $EnginePath "Engine\Plugins\DeadFire\DFBlueprintAuthoring"
    if (-not (Test-Path (Join-Path $built "Binaries"))) { throw "No built plugin at $built; run build_authoring_plugin.ps1 -NoInstall first" }
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Copy-Item -Recurse $built $dest
    Remove-Item -Recurse -Force (Join-Path $dest "Intermediate") -ErrorAction SilentlyContinue
    Write-Host "Installed plugin to $dest"
}

Start-Process -FilePath (Join-Path $EnginePath "Engine\Binaries\Win64\UE4Editor.exe") -ArgumentList "`"$project`"" | Out-Null
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 10
    $r = & python $remote --code "import unreal; print('EDITOR READY', hasattr(unreal, 'DFBlueprintAuthoringLibrary'))" 2>&1 | Out-String
    if ($r -match "EDITOR READY") { Write-Host ($r.Trim()); exit 0 }
}
Write-Host "TIMEOUT waiting for the editor"
exit 1
