<#
    install-pyqt-windows.ps1
    Installs the PyQt6 version that matches the Qt6 ABI shipped with Scribus.
    This is what enables the bridge's interactive-with-GUI mode on Windows.

    Logic:
      1. Locate the Scribus install (auto-detect under Program Files or take -ScribusDir).
      2. Read Qt6Core.dll's FileVersion to learn Scribus's Qt minor version.
      3. Locate Scribus's bundled Python (<install>\python\python.exe).
      4. pip install PyQt6==<MAJOR>.<MINOR>.* (and matching PyQt6-Qt6) into Scribus's
         site-packages (requires admin).
      5. Verify with `from PyQt6.QtCore import QTimer`.

    Must be run in an elevated PowerShell (Run as administrator) because Program Files
    needs write access.

    Usage:
      Run as administrator:
        & .\scripts\install-pyqt-windows.ps1
      With explicit install path:
        & .\scripts\install-pyqt-windows.ps1 -ScribusDir "D:\Scribus"
      Dry run (show what would happen):
        & .\scripts\install-pyqt-windows.ps1 -DryRun
#>

[CmdletBinding()]
param(
    [string]$ScribusDir,
    [switch]$DryRun,
    [switch]$Force          # reinstall even if a Qt binding is already importable
)

$ErrorActionPreference = 'Stop'

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Info($msg) { Write-Host "    $msg" -ForegroundColor Gray }
function Write-Ok($msg)   { Write-Host "[OK] $msg"  -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[!!] $msg"  -ForegroundColor Red }


function Test-Admin {
    $current = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($current)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}


function Resolve-ScribusDir([string]$override) {
    if ($override) {
        if (-not (Test-Path $override)) { throw "ScribusDir not found: $override" }
        return (Resolve-Path $override).Path
    }
    $candidates = @()
    foreach ($pf in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not $pf) { continue }
        $candidates += Get-ChildItem $pf -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^Scribus[\s\-_]?\d' } |
            Sort-Object Name -Descending |
            ForEach-Object FullName
    }
    if ($candidates.Count -eq 0) {
        throw "No Scribus install found under Program Files. Pass -ScribusDir <path>."
    }
    if ($candidates.Count -gt 1) {
        Write-Info "Multiple Scribus installs found:"
        $candidates | ForEach-Object { Write-Info "  $_" }
        Write-Info "Using the highest-versioned one. Pass -ScribusDir to override."
    }
    return $candidates[0]
}


function Get-ScribusQtVersion([string]$scribusDir) {
    $dll = Join-Path $scribusDir 'Qt6Core.dll'
    if (-not (Test-Path $dll)) {
        throw "Qt6Core.dll not found in $scribusDir. Is this really a Scribus install?"
    }
    $ver = (Get-Item $dll).VersionInfo.FileVersion
    if (-not $ver) {
        throw "Could not read FileVersion of $dll"
    }
    # FileVersion looks like "6.10.3.0" — take MAJOR.MINOR
    $parts = $ver -split '\.'
    if ($parts.Count -lt 2) { throw "Unexpected version string: $ver" }
    return @{
        Full  = $ver
        Major = [int]$parts[0]
        Minor = [int]$parts[1]
        Patch = if ($parts.Count -ge 3) { [int]$parts[2] } else { 0 }
        Spec  = "$($parts[0]).$($parts[1]).*"
    }
}


function Get-ScribusPython([string]$scribusDir) {
    $py = Join-Path $scribusDir 'python\python.exe'
    if (-not (Test-Path $py)) {
        throw "Scribus's bundled Python not found at $py. This Scribus build may not have an embedded Python."
    }
    return $py
}


function Test-QtAlreadyWorking([string]$pyExe) {
    $cmd = "from PyQt6.QtCore import QTimer; print('OK')"
    $out = & $pyExe -c $cmd 2>&1
    return ($LASTEXITCODE -eq 0 -and ($out -match 'OK'))
}


function Get-InstalledPyQtVersion([string]$pyExe) {
    $cmd = "import importlib.metadata; print(importlib.metadata.version('PyQt6-Qt6'))"
    $out = & $pyExe -c $cmd 2>$null
    if ($LASTEXITCODE -eq 0) { return $out.Trim() }
    return $null
}


# ---- main ------------------------------------------------------------------

Write-Step "Checking elevation"
if (-not (Test-Admin)) {
    Write-Fail "Not running as Administrator. Program Files writes require elevation."
    Write-Info "Right-click PowerShell -> Run as administrator, then re-run this script."
    exit 1
}
Write-Ok "Administrator"

Write-Step "Locating Scribus install"
$scribusDir = Resolve-ScribusDir -override $ScribusDir
Write-Ok "Scribus dir: $scribusDir"

Write-Step "Reading Scribus's Qt6 version"
$qt = Get-ScribusQtVersion $scribusDir
Write-Ok "Scribus Qt6 = $($qt.Full)  (will install PyQt6 matching $($qt.Spec))"

Write-Step "Locating Scribus's bundled Python"
$pyExe = Get-ScribusPython $scribusDir
$pyVer = (& $pyExe --version) -replace '^Python\s+', ''
Write-Ok "Python: $pyExe ($pyVer)"

if (-not $Force) {
    Write-Step "Checking if a working PyQt is already present"
    if (Test-QtAlreadyWorking $pyExe) {
        $cur = Get-InstalledPyQtVersion $pyExe
        Write-Ok "PyQt6.QtCore already imports successfully (PyQt6-Qt6 = $cur). Nothing to do. Pass -Force to reinstall."
        exit 0
    }
    Write-Info "PyQt6.QtCore not importable; proceeding with install"
}

# Build pip args. PyQt6-Qt6 is the package that ships the Qt6 DLLs; pinning that
# is what actually controls the ABI we need. PyQt6 itself versions in lockstep.
$pyqtSpec = "PyQt6==$($qt.Spec)"
$pyqtQtSpec = "PyQt6-Qt6==$($qt.Spec)"

Write-Step "Plan"
Write-Info "Uninstall any existing PyQt6 / PyQt6-Qt6 / PyQt6-sip (system AND user site)"
Write-Info "Install: $pyqtSpec  $pyqtQtSpec  (PyQt6-sip resolved by pip)"

if ($DryRun) {
    Write-Info "DRY RUN — not modifying anything."
    exit 0
}

Write-Step "Removing any existing PyQt6 in user site-packages"
& $pyExe -m pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6-sip 2>&1 | ForEach-Object { Write-Info $_ }

# Also try to remove any user-site copies. pip uninstall above only removes from
# the first matching location; the user-site copy can leak through.
$userSite = & $pyExe -c "import site; print(site.USER_SITE)" 2>$null
if ($LASTEXITCODE -eq 0 -and $userSite -and (Test-Path $userSite)) {
    foreach ($dir in @('PyQt6', 'PyQt6_Qt6')) {
        $p = Join-Path $userSite $dir
        if (Test-Path $p) {
            Write-Info "Removing leftover user-site copy: $p"
            Remove-Item -Recurse -Force $p
        }
    }
}

Write-Step "Installing $pyqtSpec into $($pyExe | Split-Path)"
& $pyExe -m pip install --upgrade pip
& $pyExe -m pip install --no-warn-script-location $pyqtSpec $pyqtQtSpec
if ($LASTEXITCODE -ne 0) {
    Write-Fail "pip install failed. PyPI may not have a $($qt.Spec) wheel — check https://pypi.org/project/PyQt6/#history"
    exit 1
}

Write-Step "Verifying"
$verifyOut = & $pyExe -c "import os, PyQt6; from PyQt6.QtCore import QTimer; print(os.path.dirname(PyQt6.__file__))" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "QtCore still failed to import after install:"
    Write-Host $verifyOut
    Write-Info "Possible causes:"
    Write-Info "  - PyPI doesn't have a $($qt.Spec) wheel; try -Force with the closest available version"
    Write-Info "  - The Scribus process needs to be fully closed and restarted"
    Write-Info "  - There's a different ABI mismatch we didn't catch"
    exit 1
}
$installPath = $verifyOut.Trim()
if ($installPath -notlike "$scribusDir*") {
    Write-Fail "PyQt6 installed but at unexpected path: $installPath"
    Write-Info "Expected under: $scribusDir"
    exit 1
}
Write-Ok "PyQt6 installed at: $installPath"
$installedVer = Get-InstalledPyQtVersion $pyExe
Write-Ok "PyQt6-Qt6 version: $installedVer (Scribus expects matching $($qt.Spec))"

Write-Host ""
Write-Host "Done. Now (re)launch Scribus with the bridge:" -ForegroundColor Cyan
Write-Host '  & "' + (Join-Path $scribusDir 'scribus.exe') + '" --console -py "<path-to-bridge.spy>"' -ForegroundColor Gray
Write-Host ""
Write-Host "Bridge log should now say `qt=PyQt6` instead of `qt=NONE-thread-fallback`." -ForegroundColor Cyan
