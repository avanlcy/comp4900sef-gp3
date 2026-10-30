# Tests for tools/package/smoke.ps1 (the packaging script's build-folder check and smoke verdict). Plain asserts, no
# Pester needed:  powershell -NoProfile -ExecutionPolicy Bypass -File tools/package/smoke.Tests.ps1
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "smoke.ps1")

$failures = 0
function Check([bool]$Condition, [string]$What) {
    if ($Condition) { Write-Host "  ok    $What" } else { Write-Host "  FAIL  $What" -ForegroundColor Red; $script:failures++ }
}

# ---- Test-StagedBuild: every file a player needs is in the folder ----
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("df-smoke-test-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $tmp "comp4900sef\Content\Paks") | Out-Null
Set-Content (Join-Path $tmp "comp4900sef.exe") "x"
Set-Content (Join-Path $tmp "comp4900sef\Content\Paks\comp4900sef-WindowsNoEditor.pak") "x"
$missing = @(Test-StagedBuild $tmp)
Check ($missing.Count -eq 1 -and $missing[0] -like "*UE4PrereqSetup_x64.exe") "a build without the UE4 prerequisites installer is reported ($($missing -join ', '))"
New-Item -ItemType Directory -Force (Join-Path $tmp "Engine\Extras\Redist\en-us") | Out-Null
Set-Content (Join-Path $tmp "Engine\Extras\Redist\en-us\UE4PrereqSetup_x64.exe") "x"
Check (@(Test-StagedBuild $tmp).Count -eq 0) "a complete build reports nothing missing"
Remove-Item (Join-Path $tmp "comp4900sef\Content\Paks\comp4900sef-WindowsNoEditor.pak")
Check (@(Test-StagedBuild $tmp) -like "*comp4900sef-WindowsNoEditor.pak").Count -eq 1 "a build without its pak is reported"
Remove-Item -Recurse -Force $tmp

# ---- Get-SmokeVerdict: what passes ----
Check ((Get-SmokeVerdict -Config Shipping -Alive $true -ShotOk $true).Pass) "Shipping: alive with a window capture passes"
Check (-not (Get-SmokeVerdict -Config Shipping -Alive $true -ShotOk $false).Pass) "Shipping: alive but no window capture fails (spec 2.2: the capture must exist)"
Check (-not (Get-SmokeVerdict -Config Shipping -Alive $false -ShotOk $true).Pass) "Shipping: not running fails"
Check ((Get-SmokeVerdict -Config Development -Loaded $true -ProgressLine $true -Bad @()).Pass) "Development: menu loaded, save started, no bad lines passes"
Check (-not (Get-SmokeVerdict -Config Development -Loaded $true -ProgressLine $true -Bad @("LogScript: Warning: Accessed None")).Pass) "Development: a script error fails"
Check (-not (Get-SmokeVerdict -Config Development -Loaded $false -ProgressLine $true -Bad @()).Pass) "Development: the menu never loaded fails"
Check (-not (Get-SmokeVerdict -Config Development -Loaded $true -ProgressLine $false -Bad @()).Pass) "Development: no save-system line fails"

if ($failures -gt 0) { Write-Host "$failures failed" -ForegroundColor Red; exit 1 }
Write-Host "all smoke tests passed"
exit 0
