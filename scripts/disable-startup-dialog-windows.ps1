<#
    disable-startup-dialog-windows.ps1
    Toggles ShowStartupDialog="0" in Scribus's user prefs (scribus172.rc) so
    the "New Document" startup dialog stops blocking `-py` script execution.

    Persistent — affects every Scribus launch for the current Windows user.
    Doesn't touch system files; runs as the current user (no admin needed).

    Usage:
      Interactive (asks before changing):
        & .\scripts\disable-startup-dialog-windows.ps1

      Non-interactive (for CI / auto-spawn flows):
        & .\scripts\disable-startup-dialog-windows.ps1 -Force

      Re-enable the dialog:
        & .\scripts\disable-startup-dialog-windows.ps1 -Enable

    Notes:
      - Scribus must be CLOSED while this script runs, otherwise Scribus will
        overwrite the file on quit and undo the change.
      - The setting is also reachable in Scribus's GUI:
        File -> Preferences -> General -> "Always show 'New Document' dialog at startup"
#>

[CmdletBinding()]
param(
    [switch]$Force,    # skip the confirmation prompt
    [switch]$Enable    # set ShowStartupDialog="1" instead
)

$ErrorActionPreference = 'Stop'

function Write-Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Info($m) { Write-Host "    $m" -ForegroundColor Gray }
function Write-Ok($m)   { Write-Host "[OK] $m"  -ForegroundColor Green }
function Write-Fail($m) { Write-Host "[!!] $m"  -ForegroundColor Red }

$desiredValue = if ($Enable) { '1' } else { '0' }
$desiredLabel = if ($Enable) { 'ENABLE' } else { 'DISABLE' }

# --- 1. find the Scribus prefs file ----------------------------------------

$candidates = @(
    "$env:APPDATA\Scribus\scribus172.rc",   # 1.7.x
    "$env:APPDATA\Scribus\scribus170.rc",
    "$env:APPDATA\Scribus\scribus160.rc",   # 1.6.x
    "$env:APPDATA\Scribus\scribus150.rc"
)
$rcPath = $null
foreach ($c in $candidates) {
    if (Test-Path $c) { $rcPath = $c; break }
}
# Fallback: any scribusXXX.rc file in $env:APPDATA\Scribus
if (-not $rcPath) {
    $rcPath = Get-ChildItem "$env:APPDATA\Scribus" -Filter "scribus*.rc" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty FullName
}

if (-not $rcPath -or -not (Test-Path $rcPath)) {
    Write-Fail "No Scribus prefs file found in $env:APPDATA\Scribus."
    Write-Info "Launch Scribus once so it creates one, then re-run this script."
    exit 1
}
Write-Step "Prefs file"
Write-Info $rcPath

# --- 2. check Scribus isn't running (it would overwrite our edit on quit) --

$running = Get-Process -Name scribus -ErrorAction SilentlyContinue
if ($running) {
    Write-Fail "Scribus is currently running (PIDs: $($running.Id -join ', ')). Close it before running this script — otherwise Scribus will overwrite the change on quit."
    exit 2
}

# --- 3. read current value -------------------------------------------------
# Use .NET I/O directly; Get-Content -Raw + -Encoding UTF8 has subtle BOM /
# newline differences against [System.IO.File]::WriteAllText that caused the
# verify step to spuriously fail.

$content = [System.IO.File]::ReadAllText($rcPath)
if ($content -notmatch 'ShowStartupDialog="(\d)"') {
    Write-Fail "ShowStartupDialog attribute not found in $rcPath. The file format may have changed."
    Write-Info 'Look for a <UI ...> element with ShowStartupDialog attribute and edit it manually.'
    exit 3
}
$currentValue = $Matches[1]
Write-Step "Current setting"
Write-Info "ShowStartupDialog=`"$currentValue`""

if ($currentValue -eq $desiredValue) {
    Write-Ok "Already set to `"$desiredValue`" — nothing to do."
    exit 0
}

# --- 4. confirm ------------------------------------------------------------

if (-not $Force) {
    Write-Host ""
    Write-Host "About to $desiredLabel the Scribus startup dialog by setting" -ForegroundColor Yellow
    Write-Host "  ShowStartupDialog=`"$currentValue`"  ->  ShowStartupDialog=`"$desiredValue`"" -ForegroundColor Yellow
    Write-Host "in $rcPath" -ForegroundColor Yellow
    Write-Host ""
    $reply = Read-Host "Proceed? [y/N]"
    if ($reply -notmatch '^(y|yes)$') {
        Write-Info "Aborted."
        exit 0
    }
}

# --- 5. backup + edit ------------------------------------------------------

$backup = "$rcPath.scribus-mcp.bak"
Copy-Item $rcPath $backup -Force
Write-Info "Backup: $backup"

$new = $content -replace 'ShowStartupDialog="\d"', "ShowStartupDialog=`"$desiredValue`""
# Preserve UTF-8 encoding without BOM (matches Scribus's own writes)
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($rcPath, $new, $utf8)

# --- 6. verify -------------------------------------------------------------

$verify = [System.IO.File]::ReadAllText($rcPath)
if ($verify -match 'ShowStartupDialog="(\d)"' -and $Matches[1] -eq $desiredValue) {
    Write-Ok "ShowStartupDialog is now `"$desiredValue`". Next Scribus launch will skip the startup dialog."
} else {
    Write-Fail "Edit did not take. Restoring backup."
    Copy-Item $backup $rcPath -Force
    exit 4
}
