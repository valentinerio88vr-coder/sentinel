# Creates a Desktop shortcut to run.bat, using assets\sentinel.ico as the icon.
# Invoked by install-desktop-icon.bat, or run directly:
#   powershell -ExecutionPolicy Bypass -File tools\make-shortcut.ps1 -Root "C:\path\to\sentinel"

param(
    [Parameter(Mandatory = $true)][string]$Root
)

$ErrorActionPreference = "Stop"

$Root      = (Resolve-Path $Root).Path
$target    = Join-Path $Root "run.bat"
$icon      = Join-Path $Root "assets\sentinel.ico"
$desktop   = [Environment]::GetFolderPath("Desktop")
$linkPath  = Join-Path $desktop "Sentinel.lnk"

if (-not (Test-Path $target)) { throw "run.bat not found at $target" }
if (-not (Test-Path $icon))   { throw "sentinel.ico not found at $icon - run python tools\make_icon.py first" }

$shell    = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($linkPath)

$shortcut.TargetPath       = $target
$shortcut.WorkingDirectory = $Root
$shortcut.IconLocation     = "$icon,0"
$shortcut.Description      = "Sentinel - Family Safety console"
$shortcut.WindowStyle      = 7          # start minimised so the console window stays out of the way
$shortcut.Save()

# Touch the shortcut so Explorer refreshes the icon cache.
(Get-Item $linkPath).LastWriteTime = Get-Date

Write-Host "  Shortcut created: $linkPath"
Write-Host "  Target:           $target"
Write-Host "  Icon:             $icon"
