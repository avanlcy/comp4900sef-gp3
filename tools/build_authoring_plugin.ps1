<#
.SYNOPSIS
  Builds the DF Blueprint Authoring editor plugin and installs it into the engine's Plugins folder
  (it is a build tool for the machine that runs the automation, not part of the game project).

.DESCRIPTION
  The game project is Blueprint-only, so the plugin is compiled inside a minimal C++ host project
  (created on first run under $HostDir: two Target.cs files and one empty module). The plugin source is
  copied into the host's Plugins folder, built with the engine's Build.bat, and the result (source +
  Binaries) copied to <EnginePath>\Engine\Plugins\DeadFire\DFBlueprintAuthoring. Close the editor first:
  it holds the previous plugin DLL open. Needs Visual Studio 2019/2022 with the C++ workload.

.EXAMPLE
  .\tools\build_authoring_plugin.ps1
#>
param(
    [string]$EnginePath = "D:\UE_4.27",
    [string]$HostDir = (Join-Path $env:LOCALAPPDATA "DFPluginHost"),  # keep this path short: UBT refuses output paths over 260 chars
    [switch]$NoInstall  # build only (the editor must be closed to replace the installed DLL)
)
$ErrorActionPreference = "Stop"
$src = Resolve-Path (Join-Path $PSScriptRoot "DFBlueprintAuthoring")

if (-not (Test-Path (Join-Path $HostDir "DFPluginHost.uproject"))) {
    New-Item -ItemType Directory -Force (Join-Path $HostDir "Source\DFPluginHost") | Out-Null
    Set-Content (Join-Path $HostDir "DFPluginHost.uproject") '{ "FileVersion": 3, "EngineAssociation": "4.27", "Modules": [ { "Name": "DFPluginHost", "Type": "Runtime", "LoadingPhase": "Default" } ] }'
    Set-Content (Join-Path $HostDir "Source\DFPluginHost.Target.cs") "using UnrealBuildTool;`npublic class DFPluginHostTarget : TargetRules { public DFPluginHostTarget(TargetInfo Target) : base(Target) { Type = TargetType.Game; DefaultBuildSettings = BuildSettingsVersion.V2; ExtraModuleNames.Add(`"DFPluginHost`"); } }"
    Set-Content (Join-Path $HostDir "Source\DFPluginHostEditor.Target.cs") "using UnrealBuildTool;`npublic class DFPluginHostEditorTarget : TargetRules { public DFPluginHostEditorTarget(TargetInfo Target) : base(Target) { Type = TargetType.Editor; DefaultBuildSettings = BuildSettingsVersion.V2; ExtraModuleNames.Add(`"DFPluginHost`"); } }"
    Set-Content (Join-Path $HostDir "Source\DFPluginHost\DFPluginHost.Build.cs") "using UnrealBuildTool;`npublic class DFPluginHost : ModuleRules { public DFPluginHost(ReadOnlyTargetRules Target) : base(Target) { PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs; PublicDependencyModuleNames.AddRange(new string[] { `"Core`", `"CoreUObject`", `"Engine`" }); } }"
    Set-Content (Join-Path $HostDir "Source\DFPluginHost\DFPluginHost.cpp") "#include `"Modules/ModuleManager.h`"`nIMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, DFPluginHost, `"DFPluginHost`");"
}

$hostPlugin = Join-Path $HostDir "Plugins\DFBlueprintAuthoring"
if (Test-Path $hostPlugin) { Remove-Item -Recurse -Force $hostPlugin }
New-Item -ItemType Directory -Force (Split-Path $hostPlugin) | Out-Null
Copy-Item -Recurse $src $hostPlugin

& (Join-Path $EnginePath "Engine\Build\BatchFiles\Build.bat") DFPluginHostEditor Win64 Development -Project="$(Join-Path $HostDir 'DFPluginHost.uproject')" -WaitMutex -FromMsBuild
if ($LASTEXITCODE -ne 0) { throw "Build failed with exit code $LASTEXITCODE" }
if ($NoInstall) { Write-Host "Built (not installed): $hostPlugin"; exit 0 }

$dest = Join-Path $EnginePath "Engine\Plugins\DeadFire\DFBlueprintAuthoring"
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
Copy-Item -Recurse $hostPlugin $dest
Remove-Item -Recurse -Force (Join-Path $dest "Intermediate") -ErrorAction SilentlyContinue
Write-Host "Installed to $dest"
Get-ChildItem (Join-Path $dest "Binaries\Win64") | Select-Object Name, Length, LastWriteTime
