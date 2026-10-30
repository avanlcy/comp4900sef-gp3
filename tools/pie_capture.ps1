param([string]$Out, [int]$WaitSeconds = 6, [switch]$Play, [string]$Keys = "", [int]$ClickX = -1, [int]$ClickY = -1)
# Starts Play-In-Editor in the GUI editor (Alt+P: the editor has no Python entry point for a real PIE session in 4.27),
# optionally sends extra keys, waits, and captures the primary screen. End the session afterwards with
#   python tools/ue_remote.py --code "import unreal; unreal.EditorLevelLibrary.editor_end_play()"
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$p = Get-Process UE4Editor -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { throw "no editor" }
$shell = New-Object -ComObject WScript.Shell
$shell.AppActivate($p.Id) | Out-Null
Start-Sleep -Milliseconds 1500
if ($Play) { [System.Windows.Forms.SendKeys]::SendWait("%p"); Start-Sleep -Seconds $WaitSeconds }
if ($Keys -ne "") { [System.Windows.Forms.SendKeys]::SendWait($Keys); Start-Sleep -Seconds 2 }
if ($ClickX -ge 0) {
  Add-Type -MemberDefinition '[DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, System.UIntPtr e);' -Name M -Namespace W
  [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($ClickX, $ClickY)
  Start-Sleep -Milliseconds 300
  [W.M]::mouse_event(2, 0, 0, 0, [System.UIntPtr]::Zero); Start-Sleep -Milliseconds 80; [W.M]::mouse_event(4, 0, 0, 0, [System.UIntPtr]::Zero)
  Start-Sleep -Seconds 2
}
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "saved $Out $($b.Width)x$($b.Height)"
