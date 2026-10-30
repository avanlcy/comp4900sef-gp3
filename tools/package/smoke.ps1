# The packaging script's checks of a finished build (dot-sourced by tools/package_game.ps1; tested by smoke.Tests.ps1):
# the files a player needs, and the smoke test that starts the game and decides PASS or FAIL.

function Test-StagedBuild([string]$Folder) {
    # Files every build must hold; returns the ones missing (relative paths), empty when complete.
    $need = @("comp4900sef.exe",
              "comp4900sef\Content\Paks\comp4900sef-WindowsNoEditor.pak",
              "Engine\Extras\Redist\en-us\UE4PrereqSetup_x64.exe")  # README.txt promises the first run may install it
    return @($need | Where-Object { -not (Test-Path (Join-Path $Folder $_)) })
}

function Get-SmokeVerdict {
    # Development: the log shows the main menu loaded and the save system started, with no bad line.
    # Shipping (no log): the game still runs after 20 s AND its window was captured for a person to look at (spec 2.2):
    # a game stuck on an error box or a black view is also "running".
    param([string]$Config, [bool]$Loaded = $false, [bool]$ProgressLine = $false, [string[]]$Bad = @(),
          [bool]$Alive = $false, [bool]$ShotOk = $false, [string]$LogCopy = "", [string]$Shot = "")
    $lines = @()
    if ($Config -eq "Development") {
        if (-not $Loaded) { $lines += "the main menu never loaded within 60 s (log: $LogCopy)" }
        elseif (-not $ProgressLine) { $lines += "no 'DF: progress loaded from slot DeadFire' line in $LogCopy" }
        if ($Bad) { $lines += $Bad }
    } else {
        if (-not $Alive) { $lines += "the Shipping game was not running 20 s after start" }
        if (-not $ShotOk) { $lines += "no capture of the game's window: a person must see the menu ($Shot)" }
    }
    return @{ Pass = ($lines.Count -eq 0); Shot = $ShotOk; Lines = $lines }
}

function Stop-BuildProcesses([string]$Folder) {
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($Folder, [StringComparison]::OrdinalIgnoreCase) } |
        ForEach-Object { try { $_.Kill() } catch {} }
    Start-Sleep -Seconds 2
}

function Save-GameWindow([string]$Folder, [string]$Path) {
    # Captures the game's own window only (PrintWindow on its handle), never the rest of the screen: other people's
    # windows must not end up in a file. Returns $false when the game has no window to capture.
    if (-not ("DFWin" -as [type])) {
        Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class DFWin {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
}
"@
    }
    Add-Type -AssemblyName System.Drawing
    $proc = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($Folder, [StringComparison]::OrdinalIgnoreCase) -and $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1
    if (-not $proc) { return $false }
    $r = New-Object DFWin+RECT
    if (-not [DFWin]::GetWindowRect($proc.MainWindowHandle, [ref]$r)) { return $false }
    $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
    if ($w -le 0 -or $h -le 0) { return $false }
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    $ok = [DFWin]::PrintWindow($proc.MainWindowHandle, $hdc, 2)  # 2 = PW_RENDERFULLCONTENT: DirectX content included
    $g.ReleaseHdc($hdc)
    if ($ok) { $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png) }
    $g.Dispose(); $bmp.Dispose()
    return $ok
}

function Invoke-Smoke([string]$Folder, [string]$Config, [string]$Shot, [string]$LogCopy) {
    $exe = Join-Path $Folder "comp4900sef.exe"
    if (-not (Test-Path $exe)) { return @{ Pass = $false; Shot = $false; Lines = @("no comp4900sef.exe in $Folder") } }
    $log = Join-Path $Folder "comp4900sef\Saved\Logs\comp4900sef.log"
    Start-Process -FilePath $exe -ArgumentList @("-windowed", "-resx=1280", "-resy=720", "-nosplash") | Out-Null
    if ($Config -eq "Development") {
        $deadline = (Get-Date).AddSeconds(60)
        $loaded = $false
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 2
            if ((Test-Path $log) -and (Select-String -Path $log -SimpleMatch "Bringing World /Game/DeadFire/Maps/L_MainMenu" -Quiet)) { $loaded = $true; break }
        }
        Start-Sleep -Seconds 5
        $shotOk = Save-GameWindow $Folder $Shot
        Stop-BuildProcesses $Folder
        if (Test-Path $log) { Copy-Item $log $LogCopy -Force }
        $text = if (Test-Path $log) { Get-Content $log } else { @() }
        $bad = @($text | Where-Object { $_ -match "LogScript:|Blueprint Runtime Error|LogBlueprint: Error|Fatal error|LogStreaming: Warning: Failed to read file" })
        $progress = [bool]($text | Where-Object { $_ -match "DF: progress loaded from slot DeadFire" })
        return Get-SmokeVerdict -Config Development -Loaded $loaded -ProgressLine $progress -Bad $bad -ShotOk $shotOk -LogCopy $LogCopy -Shot $Shot
    }
    Start-Sleep -Seconds 20
    $alive = [bool](Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($Folder, [StringComparison]::OrdinalIgnoreCase) -and $_.Name -like "UE4Game*" })
    $shotOk = Save-GameWindow $Folder $Shot
    Stop-BuildProcesses $Folder
    return Get-SmokeVerdict -Config Shipping -Alive $alive -ShotOk $shotOk -Shot $Shot
}
