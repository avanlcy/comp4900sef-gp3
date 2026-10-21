<#
.SYNOPSIS
  Runs the Dead Fire editor automation tests headless and prints a pass/fail summary.

.DESCRIPTION
  Launches UE4Editor-Cmd with -NullRHI, runs every automation test whose name
  starts with -Filter (default "DeadFire"), quits, then parses the log for
  "Test Completed. Result={Passed|Failed}" lines. Python remote execution is
  disabled in this instance so it never confuses an MCP server attached to a
  normally running editor, and background CPU throttling is off so Play-In-Editor
  tests run at full speed.

  Exit code 0 only when the editor exited cleanly, every test it found completed,
  none failed, and no fatal error was logged.

.EXAMPLE
  .\tools\run_tests.ps1
  .\tools\run_tests.ps1 -Filter DeadFire.Vehicle
#>
param(
    [string]$Filter = "DeadFire",
    [string]$EnginePath = "D:\UE_4.27",
    [string]$Project = (Join-Path $PSScriptRoot "..\comp4900sef\comp4900sef.uproject"),
    [int]$TimeoutSeconds = 900
)

$ErrorActionPreference = "Stop"
$Project = (Resolve-Path $Project).Path
$editorCmd = Join-Path $EnginePath "Engine\Binaries\Win64\UE4Editor-Cmd.exe"
if (-not (Test-Path $editorCmd)) { throw "UE4Editor-Cmd.exe not found at $editorCmd" }

$logName = "DFTests.log"
$logPath = Join-Path (Split-Path $Project) "Saved\Logs\$logName"
if (Test-Path $logPath) { Remove-Item $logPath -Force }

$editorArgs = @(
    "`"$Project`"",
    "-ExecCmds=`"Automation RunTests $Filter; Quit`"",
    "-unattended", "-nopause", "-nosplash", "-NullRHI", "-nosound",
    "-log=$logName",
    "-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False",
    "-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False"
)

Write-Host "Running automation tests matching '$Filter'..."
$proc = Start-Process -FilePath $editorCmd -ArgumentList $editorArgs -PassThru -NoNewWindow
$null = $proc.Handle   # cache the handle so ExitCode is available after exit
if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
    $proc.Kill()
    Write-Host "TIMEOUT after $TimeoutSeconds s" -ForegroundColor Red
    exit 1
}
$exitCode = $proc.ExitCode

if (-not (Test-Path $logPath)) {
    Write-Host "No log produced at $logPath (editor exit code $exitCode)" -ForegroundColor Red
    exit 1
}

$lines = Get-Content $logPath
$results = $lines | Where-Object { $_ -match "Test Completed\. Result=\{(Passed|Failed)\} Name=\{([^}]*)\}" } | ForEach-Object {
    $m = [regex]::Match($_, "Result=\{(Passed|Failed)\} Name=\{([^}]*)\}")
    [pscustomobject]@{ Result = $m.Groups[1].Value; Name = $m.Groups[2].Value }
}
$foundLine = $lines | Where-Object { $_ -match "Found (\d+) automation tests" } | Select-Object -First 1
$found = if ($foundLine -and $foundLine -match "Found (\d+) automation tests") { [int]$Matches[1] } else { -1 }
$fatal = $lines | Where-Object { $_ -match "Fatal error|Assertion failed|LogWindows: Error: === Critical error" }
$errors = $lines | Where-Object { $_ -match "LogAutomationController: Error" }

$passed = @($results | Where-Object Result -eq "Passed").Count
$failed = @($results | Where-Object Result -eq "Failed").Count
foreach ($r in $results) {
    $color = if ($r.Result -eq "Passed") { "Green" } else { "Red" }
    Write-Host ("  [{0}] {1}" -f $r.Result, $r.Name) -ForegroundColor $color
}
if ($errors) {
    Write-Host "--- errors ---" -ForegroundColor Yellow
    $errors | Select-Object -First 40 | ForEach-Object { Write-Host $_ }
}
if ($fatal) {
    Write-Host "--- fatal ---" -ForegroundColor Red
    $fatal | Select-Object -First 10 | ForEach-Object { Write-Host $_ }
}
Write-Host ("{0} passed, {1} failed, {2} found (editor exit code {3}); log: {4}" -f $passed, $failed, $found, $exitCode, $logPath)

$incomplete = ($found -lt 0) -or (($passed + $failed) -lt $found)
if ($failed -gt 0 -or $incomplete -or $fatal -or $exitCode -ne 0) {
    if ($incomplete) { Write-Host "Not every test that was found completed." -ForegroundColor Red }
    exit 1
}
exit 0
