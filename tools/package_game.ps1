<#
.SYNOPSIS
  Packages Dead Fire for Windows (cook, stage, pak, archive), writes README.txt into the build, smoke-tests it and zips it.

.DESCRIPTION
  Calls the engine's AutomationTool.exe directly, by full path, with Engine\Binaries\DotNET as the working directory.
  RunUAT.bat is not used: on an installed engine it runs AutomationTool.exe by bare name from that folder, which fails
  ("'AutomationTool.exe' is not recognized") whenever the environment sets NoDefaultCurrentDirectoryInExePath=1 (some
  shells do, and an editor started from such a shell inherits it, so its own Launch / Package buttons fail the same way).

  Output: Builds\DeadFire-v<ProjectVersion>-Win64-<Config>-<yyyymmdd>-<commit>[-dirty]\ and a .zip of the same name.
  "-dirty" means the build was made from uncommitted changes, so it does not match the named commit exactly.

  Smoke test: starts the packaged game windowed (1280x720) and captures the game's own window (never the rest of the
  screen) to Builds\<name>-smoke.png. Development: passes when the game's log shows the main menu loaded and the save
  system started, with no Blueprint runtime error, script error, fatal error or failed save read (the log is kept as
  Builds\<name>-smoke.log). Shipping (no log): passes when the game is still running after 20 s. Every process started
  from the build folder is closed afterwards, and the Saved folder the run created inside the build is deleted, so the
  zip holds a clean build. The AutomationTool log is kept as Builds\<name>-uat.log.

  It can run while the editor is open (the cook is a separate process), but not while a headless test suite runs.

.EXAMPLE
  .\tools\package_game.ps1                    # Development build + smoke test + zip
  .\tools\package_game.ps1 -Config Shipping   # the hand-in build
  .\tools\package_game.ps1 -NoSmoke -NoZip    # cook, stage and archive only
#>
param(
    [ValidateSet("Development", "Shipping")] [string]$Config = "Development",
    [switch]$NoSmoke,
    [switch]$NoZip,
    [string]$EnginePath = "D:\UE_4.27",
    [string]$OutRoot = (Join-Path $PSScriptRoot "..\Builds")
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$project = Join-Path $repo "comp4900sef\comp4900sef.uproject"
$dotnet = Join-Path $EnginePath "Engine\Binaries\DotNET"
$uat = Join-Path $dotnet "AutomationTool.exe"
$maps = "/Game/DeadFire/Maps/L_MainMenu+/Game/DeadFire/Maps/L_TestTrack+/Game/DeadFire/Maps/L_Switchback"

function Fail([string]$Reason, [string[]]$Lines = @()) {
    $Lines | Select-Object -First 30 | ForEach-Object { Write-Host "  $_" }
    Write-Host "PACKAGE FAILED: $Reason" -ForegroundColor Red
    exit 1
}

. (Join-Path $PSScriptRoot "package\smoke.ps1")  # Test-StagedBuild, Invoke-Smoke, Save-GameWindow, Stop-BuildProcesses

# ---- version, commit, names ----
if (-not (Test-Path $uat)) { Fail "AutomationTool.exe not found at $uat" }
$gameIni = Join-Path $repo "comp4900sef\Config\DefaultGame.ini"
$version = (Select-String -Path $gameIni -Pattern "^ProjectVersion=(.+)$" | Select-Object -First 1).Matches.Groups[1].Value
if (-not $version) { $version = "0.0.0" }
Push-Location $repo
$commit = (git rev-parse --short HEAD).Trim()
if (git status --porcelain) { $commit = "$commit-dirty" }
Pop-Location
$date = Get-Date -Format "yyyyMMdd"
$name = "DeadFire-v$version-Win64-$Config-$date-$commit"
New-Item -ItemType Directory -Force $OutRoot | Out-Null
$OutRoot = (Resolve-Path $OutRoot).Path
$stage = Join-Path $OutRoot "_stage"
$folder = Join-Path $OutRoot $name
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force $stage | Out-Null
if (Test-Path $folder) { Stop-BuildProcesses $folder; Remove-Item -Recurse -Force $folder }

# ---- cook, stage, pak, archive ----
$uatLog = Join-Path $stage "uat.log"
$uatArgs = @("BuildCookRun", "-nop4", "-project=`"$project`"", "-cook", "-stage", "-archive", "-archivedirectory=`"$stage`"",
             "-package", "-ue4exe=UE4Editor-Cmd.exe", "-pak", "-prereqs", "-nodebuginfo", "-targetplatform=Win64", "-build",
             "-clientconfig=$Config", "-utf8output", "-nocompile", "-nocompileeditor", "-map=$maps")
Write-Host "Packaging $name ..."
$started = Get-Date
$p = Start-Process -FilePath $uat -ArgumentList $uatArgs -WorkingDirectory $dotnet -RedirectStandardOutput $uatLog `
        -RedirectStandardError (Join-Path $stage "uat.err") -PassThru -WindowStyle Hidden -Wait
$minutes = [Math]::Round(((Get-Date) - $started).TotalMinutes, 1)
$uatText = Get-Content $uatLog
if ($p.ExitCode -ne 0 -or -not ($uatText | Where-Object { $_ -match "BUILD SUCCESSFUL" })) {
    Fail "AutomationTool exited $($p.ExitCode) after $minutes min (log: $uatLog)" ($uatText | Select-Object -Last 20)
}
$cookWarnings = $uatText | Where-Object { $_ -match "LogUObjectGlobals: Warning|LogBlueprint: Warning" -and $_ -notmatch "Warning/Error Summary" } | Sort-Object -Unique
if ($cookWarnings) { Fail "the cook logged asset warnings (log: $uatLog)" $cookWarnings }
$staged = Join-Path $stage "WindowsNoEditor"
if (-not (Test-Path $staged)) { Fail "no WindowsNoEditor folder in $stage" }
Move-Item $staged $folder
$missing = Test-StagedBuild $folder
if ($missing.Count -gt 0) { Fail "the build is missing files a player needs" $missing }
# the build log, the smoke screenshot and the smoke run's game log stay beside the build, never inside the shipped folder
$sideLog = Join-Path $OutRoot "$name-uat.log"
Move-Item $uatLog $sideLog -Force
Remove-Item -Recurse -Force $stage

# ---- README.txt ----
$template = Get-Content (Join-Path $PSScriptRoot "package\README.template.txt") -Raw -Encoding UTF8  # the title has CJK; Windows PowerShell would read ANSI
$readme = $template.Replace("{{VERSION}}", $version).Replace("{{COMMIT}}", $commit).Replace("{{DATE}}", (Get-Date -Format "yyyy-MM-dd")).Replace("{{CONFIG}}", $Config)
Set-Content -Path (Join-Path $folder "README.txt") -Value $readme -Encoding UTF8

# ---- smoke test ----
$smoke = "skipped"
$shot = Join-Path $OutRoot "$name-smoke.png"
if (-not $NoSmoke) {
    if (Test-Path $shot) { Remove-Item -Force $shot }
    $result = Invoke-Smoke $folder $Config $shot (Join-Path $OutRoot "$name-smoke.log")
    # the run created the game's Saved folder (log, config) inside the build: a fresh build ships without it
    foreach ($runSaved in @((Join-Path $folder "comp4900sef\Saved"), (Join-Path $folder "Engine\Saved"))) {
        if (Test-Path $runSaved) { Remove-Item -Recurse -Force $runSaved }
    }
    if (-not $result.Pass) { Fail "smoke test failed (window capture: $shot)" $result.Lines }
    $smoke = "PASS (window: $shot; look at it)"
}

# ---- zip ----
$zip = "$folder.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }  # an older build's zip under the same name is stale either way
if (-not $NoZip) {
    Compress-Archive -Path $folder -DestinationPath $zip -CompressionLevel Optimal
}
$mb = [Math]::Round((Get-ChildItem $folder -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
$zipNote = if (Test-Path $zip) { ", zip $([Math]::Round((Get-Item $zip).Length / 1MB)) MB" } else { "" }
Write-Host "PACKAGE OK: $folder ($mb MB$zipNote, $minutes min), smoke $smoke" -ForegroundColor Green
exit 0
