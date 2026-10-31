<#
.SYNOPSIS
  Measures a packaged Dead Fire build's frame time on PROVING GROUND with the engine's CSV profiler (Phase 7 spec §9).

.DESCRIPTION
  Starts <Build>\comp4900sef.exe with
      L_TestTrack -windowed -ResX=1920 -ResY=1080 -csvCaptureFrames=<WarmupFrames + Frames> -nosound
  so the race starts at once with its three rivals and the player's car on the grid (nobody drives it). The CSV profiler
  writes Profile(<date>).csv under the build's comp4900sef\Saved\Profiling\CSV when the capture ends. The script waits for
  that file to be complete, closes the game by its window handle (CloseMainWindow: no key or mouse input is sent, nothing
  is captured from the screen), reads the FrameTime column and prints

      PERF avg=<ms> p95=<ms> <PASS|FAIL>

  PASS needs avg <= 16.7 ms and p95 <= 20 ms (spec §9: average frame at 60 fps, 95th percentile 20 ms).

  Warm-up: -csvCaptureFrames starts the capture while the engine initialises, so the CSV's first row spans the whole
  start-up and map load (seconds), and the first frames of the level stream textures and create shaders. The first
  -WarmupFrames rows are dropped and the next -Frames rows are measured (spec §9: 1800 frames); the line after PERF gives the
  same numbers over every captured row for comparison.

  Load: the game shares the machine. Before the run, and once while it runs, the script samples every process's CPU time
  for a few seconds and prints the machine's total CPU use and the busiest processes (other people's programs included;
  it never stops any of them), so a FAIL can be told apart from a busy machine.

  Afterwards the CSV and the game's log are copied beside the build (Builds\<name>-perf.csv, -perf.log) and the Saved
  folders the run created inside the build are deleted, as tools\package_game.ps1 does after its smoke test, so the build
  folder stays the same as its zip (-KeepSaved keeps them). Needs the Development build: Shipping has no CSV profiler.

.EXAMPLE
  pwsh -File tools\perf_run.ps1 -Build Builds\DeadFire-v1.0.0-Win64-Development-20261031-0827fc5-dirty
  pwsh -File tools\perf_run.ps1 -Build <folder> -Frames 3600
#>
param(
    [Parameter(Mandatory = $true)] [string]$Build,
    [int]$Frames = 1800,
    [int]$WarmupFrames = 300,
    [string]$Map = "L_TestTrack",
    [double]$AvgLimitMs = 16.7,
    [double]$P95LimitMs = 20.0,
    [int]$TimeoutSeconds = 300,
    [int]$LoadSampleSeconds = 5,
    [switch]$KeepSaved
)

$ErrorActionPreference = "Stop"

function Fail([string]$Reason) {
    Write-Host "PERF ERROR: $Reason" -ForegroundColor Red
    exit 2
}

function Get-BuildProcesses([string]$Folder) {
    @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($Folder, [StringComparison]::OrdinalIgnoreCase) })
}

function Get-CpuLoad([int]$Seconds, [string]$OwnFolder) {
    # CPU use over $Seconds: the machine's total (Win32_Processor LoadPercentage, sampled each second) and every process's
    # share from its CPU-time delta, as a percentage of all logical processors. Returns one line of text.
    $cores = [Environment]::ProcessorCount
    $before = @{}
    foreach ($p in Get-Process -ErrorAction SilentlyContinue) { if ($null -ne $p.CPU) { $before[$p.Id] = $p.CPU } }
    $loads = @()
    for ($i = 0; $i -lt $Seconds; $i++) {
        Start-Sleep -Seconds 1
        $loads += (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    }
    $rows = foreach ($p in Get-Process -ErrorAction SilentlyContinue) {
        if ($null -ne $p.CPU -and $before.ContainsKey($p.Id)) {
            $pct = ($p.CPU - $before[$p.Id]) / $Seconds / $cores * 100
            $own = $p.Path -and $OwnFolder -and $p.Path.StartsWith($OwnFolder, [StringComparison]::OrdinalIgnoreCase)
            [pscustomobject]@{ Name = $p.ProcessName; Id = $p.Id; Pct = $pct; Own = $own }
        }
    }
    $total = [Math]::Round(($loads | Measure-Object -Average).Average)
    $game = ($rows | Where-Object Own | Measure-Object -Property Pct -Sum).Sum
    $top = $rows | Where-Object { -not $_.Own -and $_.Pct -ge 0.5 } | Sort-Object Pct -Descending | Select-Object -First 8 |
        ForEach-Object { "{0}({1}) {2:N1}%" -f $_.Name, $_.Id, $_.Pct }
    $gameText = if ($game) { ("; this game {0:N1}%" -f $game) } else { "" }
    return ("cpu {0}% of {1} threads{2}; others: {3}" -f $total, $cores, $gameText, ($(if ($top) { $top -join ", " } else { "none above 0.5%" })))
}

function Read-FrameTimes([string]$Csv) {
    # The 4.27 CSV: a header row (EVENTS, then one column per stat), one row per frame, a closing header row, then one
    # metadata row ("[HasHeaderRowAtEnd],1,...,[Commandline],..."). An event string could hold a comma, so values are
    # counted from the end of each row.
    $lines = [System.IO.File]::ReadAllLines($Csv)
    if ($lines.Count -lt 3) { Fail "the CSV has $($lines.Count) line(s): $Csv" }
    $header = $lines[0].Split(",")
    $cols = @{}
    for ($i = 0; $i -lt $header.Count; $i++) { $cols[$header[$i].Trim()] = $i }
    if (-not $cols.ContainsKey("FrameTime")) { Fail "no FrameTime column in $Csv" }
    $series = @{}
    foreach ($name in @("FrameTime", "GameThreadTime", "RenderThreadTime", "RHIThreadTime", "GPUTime")) {
        if ($cols.ContainsKey($name)) { $series[$name] = New-Object System.Collections.Generic.List[double] }
    }
    for ($r = 1; $r -lt $lines.Count; $r++) {
        $line = $lines[$r]
        if ($line.StartsWith("EVENTS,") -or $line.StartsWith("[")) { break }  # the closing header row, then the metadata
        $f = $line.Split(",")
        if ($f.Count -lt $header.Count) { continue }
        foreach ($name in @($series.Keys)) {
            $v = $f[$f.Count - ($header.Count - $cols[$name])]
            $series[$name].Add([double]::Parse($v, [Globalization.CultureInfo]::InvariantCulture))
        }
    }
    return $series
}

function Get-Stats([double[]]$Values) {
    $sorted = $Values | Sort-Object
    $n = $sorted.Count
    $avg = ($sorted | Measure-Object -Average).Average
    $p95 = $sorted[[Math]::Max(0, [int][Math]::Ceiling(0.95 * $n) - 1)]  # nearest rank
    return @{ N = $n; Avg = $avg; P95 = $p95; Min = $sorted[0]; Max = $sorted[$n - 1] }
}

# ---- the build ----
if (-not (Test-Path $Build)) { Fail "no build folder at $Build" }
$Build = (Resolve-Path $Build).Path.TrimEnd("\")
$exe = Join-Path $Build "comp4900sef.exe"
if (-not (Test-Path $exe)) { Fail "no comp4900sef.exe in $Build" }
if ((Get-BuildProcesses $Build).Count -gt 0) { Fail "the game from this build is already running; close it first" }
$csvDir = Join-Path $Build "comp4900sef\Saved\Profiling\CSV"
$gameLog = Join-Path $Build "comp4900sef\Saved\Logs\comp4900sef.log"
$seen = @{}
if (Test-Path $csvDir) { Get-ChildItem $csvDir -File | ForEach-Object { $seen[$_.Name] = $true } }
$captured = $WarmupFrames + $Frames
$name = Split-Path $Build -Leaf
$outRoot = Split-Path $Build -Parent

Write-Host ("PERF run: {0}, map {1}, 1920x1080 windowed, {2} frames measured after {3} warm-up frames" -f $name, $Map, $Frames, $WarmupFrames)
Write-Host ("LOAD before: " + (Get-CpuLoad $LoadSampleSeconds $Build))

# ---- run ----
$gameArgs = @($Map, "-windowed", "-ResX=1920", "-ResY=1080", "-csvCaptureFrames=$captured", "-nosound")
$started = Get-Date
Start-Process -FilePath $exe -ArgumentList $gameArgs | Out-Null
$deadline = $started.AddSeconds($TimeoutSeconds)
$csv = $null
$window = $null
$loadDuring = $null
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    if (-not $window) {
        $window = Get-BuildProcesses $Build | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1
        # sampled at once: at a few hundred frames a second the whole capture lasts under 10 s; the game's own share is
        # reported apart from the others
        if ($window) { $loadDuring = Get-CpuLoad $LoadSampleSeconds $Build }
    }
    if (Test-Path $csvDir) {
        $new = Get-ChildItem $csvDir -File -Filter "*.csv" | Where-Object { -not $seen.ContainsKey($_.Name) } | Sort-Object LastWriteTime | Select-Object -Last 1
        if ($new) {
            # written in one go when the capture ends (csv.ContinuousWrites 0); complete once its last row is the metadata row
            $fs = $null
            $tail = ""
            try {
                $fs = [System.IO.File]::Open($new.FullName, "Open", "Read", "ReadWrite")
                $len = $fs.Length
                if ($len -gt 0) {
                    $take = [Math]::Min($len, 65536)
                    $fs.Seek(-$take, "End") | Out-Null
                    $buf = New-Object byte[] $take
                    $fs.Read($buf, 0, $take) | Out-Null
                    $tail = [Text.Encoding]::ASCII.GetString($buf)
                }
            } catch { } finally { if ($fs) { $fs.Dispose() } }
            if ($tail -match "\[HasHeaderRowAtEnd\]" -and $tail -match "\[Commandline\]") { $csv = $new.FullName; break }
        }
    }
    if ($window -and $window.HasExited) { break }
}
$seconds = [Math]::Round(((Get-Date) - $started).TotalSeconds)
if ($csv) { Start-Sleep -Seconds 2 }  # the file is closed right after its last row

# ---- close the game by its window handle ----
$closed = "not running"
$procs = Get-BuildProcesses $Build
if ($procs.Count -gt 0) {
    foreach ($p in $procs) { if ($p.MainWindowHandle -ne [IntPtr]::Zero) { [void]$p.CloseMainWindow() } }
    $closeBy = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $closeBy -and (Get-BuildProcesses $Build).Count -gt 0) { Start-Sleep -Seconds 1 }
    $left = Get-BuildProcesses $Build
    if ($left.Count -eq 0) { $closed = "closed by its window" }
    else {
        # only this build's own processes, and only when the window close did not end them
        $left | ForEach-Object { try { $_.Kill() } catch {} }
        Start-Sleep -Seconds 2
        $closed = "did not close by its window in 30 s; its processes were ended"
    }
}

# ---- keep the evidence beside the build, clean the build ----
$csvCopy = Join-Path $outRoot "$name-perf.csv"
$logCopy = Join-Path $outRoot "$name-perf.log"
if ($csv) { Copy-Item $csv $csvCopy -Force }
$mapLoaded = $false
if (Test-Path $gameLog) {
    Copy-Item $gameLog $logCopy -Force
    $mapLoaded = [bool](Select-String -Path $gameLog -Pattern ("Bringing World /Game/.*/" + [regex]::Escape($Map) + "\.") -Quiet)
}
if (-not $KeepSaved) {
    foreach ($runSaved in @((Join-Path $Build "comp4900sef\Saved"), (Join-Path $Build "Engine\Saved"))) {
        if (Test-Path $runSaved) { Remove-Item -Recurse -Force $runSaved }
    }
}
Write-Host ("LOAD during: " + $(if ($loadDuring) { $loadDuring } else { "not sampled (the game showed no window)" }))
Write-Host "game: $closed after $seconds s"
if (-not $csv) { Fail "no complete CSV under $csvDir within $TimeoutSeconds s" }
if ((Test-Path $logCopy) -and -not $mapLoaded) { Fail "the game log does not show $Map loading (log: $logCopy)" }

# ---- numbers ----
$series = Read-FrameTimes $csvCopy
$all = $series["FrameTime"].ToArray()
if ($all.Count -lt $captured) { Fail "the CSV holds $($all.Count) frames, expected $captured ($csvCopy)" }
$measured = $all[$WarmupFrames..($WarmupFrames + $Frames - 1)]
$s = Get-Stats $measured
$a = Get-Stats $all
$inv = [Globalization.CultureInfo]::InvariantCulture
$parts = foreach ($k in @("GameThreadTime", "RenderThreadTime", "RHIThreadTime", "GPUTime")) {
    if ($series.ContainsKey($k)) {
        $v = $series[$k].ToArray()
        "{0} {1}" -f $k, (($v[$WarmupFrames..($WarmupFrames + $Frames - 1)] | Measure-Object -Average).Average).ToString("0.00", $inv)
    }
}
$pass = ($s.Avg -le $AvgLimitMs) -and ($s.P95 -le $P95LimitMs)
Write-Host ("frames {0}..{1} of {2}: min {3} ms, max {4} ms; averages over them: {5}" -f $WarmupFrames, ($WarmupFrames + $Frames - 1), $all.Count,
    $s.Min.ToString("0.00", $inv), $s.Max.ToString("0.00", $inv), ($parts -join ", "))
Write-Host ("all {0} captured frames: avg={1} p95={2} max={3} (first row = start-up)" -f $a.N, $a.Avg.ToString("0.00", $inv), $a.P95.ToString("0.00", $inv), $a.Max.ToString("0.00", $inv))
Write-Host "CSV: $csvCopy"
$line = "PERF avg={0} p95={1} {2}" -f $s.Avg.ToString("0.00", $inv), $s.P95.ToString("0.00", $inv), $(if ($pass) { "PASS" } else { "FAIL" })
Write-Host $line -ForegroundColor $(if ($pass) { "Green" } else { "Red" })
exit $(if ($pass) { 0 } else { 1 })
