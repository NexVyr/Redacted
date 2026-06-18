# Redacted - Hardware Analysis Tool
# Windows Launcher Script
# Usage: irm https://raw.githubusercontent.com/NexVyr/Redacted/main/scripts/run.ps1 | iex

$ErrorActionPreference = "Stop"
$REPO = "https://github.com/NexVyr/Redacted"
$RAW  = "https://raw.githubusercontent.com/NexVyr/Redacted/main"

Write-Host ""
Write-Host "  ██████████ REDACTED" -ForegroundColor Cyan
Write-Host "  Hardware Analysis Tool v0.1" -ForegroundColor DarkCyan
Write-Host "  ===========================================" -ForegroundColor DarkGray
Write-Host ""

# ── Check Python ────────────────────────────────────────────────
Write-Host "[*] Checking Python..." -ForegroundColor Gray
try {
    $pyver = python --version 2>&1
    if ($pyver -notmatch "Python 3") { throw "Python 3 required" }
    Write-Host "[+] $pyver found" -ForegroundColor Green
} catch {
    Write-Host "[!] Python 3 not found. Installing via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.12 --silent
    $env:PATH += ";$env:LOCALAPPDATA\Programs\Python\Python312"
}

# ── Check / Install Git ─────────────────────────────────────────
Write-Host "[*] Checking Git..." -ForegroundColor Gray
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Git not found. Installing..." -ForegroundColor Yellow
    winget install Git.Git --silent
}

# ── Install / Update Redacted ───────────────────────────────────
$installDir = "$env:LOCALAPPDATA\Redacted"

if (Test-Path "$installDir\.git") {
    Write-Host "[*] Updating Redacted..." -ForegroundColor Gray
    git -C $installDir pull --quiet
    Write-Host "[+] Updated!" -ForegroundColor Green
} else {
    Write-Host "[*] Installing Redacted..." -ForegroundColor Gray
    git clone --depth=1 $REPO $installDir --quiet
    Write-Host "[+] Installed to $installDir" -ForegroundColor Green
}

# ── Install Python dependencies ─────────────────────────────────
Write-Host "[*] Installing dependencies..." -ForegroundColor Gray
$reqFile = "$installDir\requirements.txt"
if (Test-Path $reqFile) {
    python -m pip install -r $reqFile --quiet --disable-pip-version-check
}
Write-Host "[+] Dependencies ready" -ForegroundColor Green

# ── Check ADB ───────────────────────────────────────────────────
Write-Host "[*] Checking ADB..." -ForegroundColor Gray

$ptDir    = "$installDir\resources"
$adbLocal = "$ptDir\platform-tools\adb.exe"

# Check: ADB in PATH or already downloaded locally
$adbInPath  = Get-Command adb -ErrorAction SilentlyContinue
$adbExists  = Test-Path $adbLocal

if ($adbInPath) {
    Write-Host "[+] ADB found in PATH" -ForegroundColor Green
    
} elseif ($adbExists) {
    # Already downloaded - just add to PATH, don't re-download
    Write-Host "[+] ADB already downloaded - skipping" -ForegroundColor Green
    $env:PATH += ";$ptDir\platform-tools"
    
} else {
    # First time - download platform-tools
    Write-Host "[!] ADB not found." -ForegroundColor Yellow
    Write-Host "    Downloading platform-tools..." -ForegroundColor Gray

    $ptUrl = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    $ptZip = "$env:TEMP\platform-tools-redacted.zip"

    New-Item -ItemType Directory -Force -Path $ptDir | Out-Null
    Invoke-WebRequest $ptUrl -OutFile $ptZip -UseBasicParsing

    # Extract without -Force to avoid overwrite errors on locked files
    try {
        Expand-Archive $ptZip -DestinationPath $ptDir -Force
    } catch {
        # If -Force fails (file in use), try without it
        Expand-Archive $ptZip -DestinationPath $ptDir
    }

    # Clean up zip only (never touch the extracted files)
    if (Test-Path $ptZip) {
        Remove-Item $ptZip -ErrorAction SilentlyContinue
    }

    $env:PATH += ";$ptDir\platform-tools"
    Write-Host "[+] ADB installed" -ForegroundColor Green
}

# ── Launch Redacted ─────────────────────────────────────────────
Write-Host ""
Write-Host "[*] Launching Redacted..." -ForegroundColor Cyan
Write-Host ""

Set-Location $installDir
python main.py
