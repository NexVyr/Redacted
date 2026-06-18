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
if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    Write-Host "[!] ADB not found." -ForegroundColor Yellow
    Write-Host "    Downloading platform-tools..." -ForegroundColor Gray

    $ptUrl  = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    $ptZip  = "$env:TEMP\platform-tools.zip"
    $ptDir  = "$installDir\resources"

    Invoke-WebRequest $ptUrl -OutFile $ptZip -UseBasicParsing
    Expand-Archive $ptZip -DestinationPath $ptDir -Force
    Remove-Item $ptZip

    $env:PATH += ";$ptDir\platform-tools"
    Write-Host "[+] ADB installed" -ForegroundColor Green
} else {
    Write-Host "[+] ADB found" -ForegroundColor Green
}

# ── Launch Redacted ─────────────────────────────────────────────
Write-Host ""
Write-Host "[*] Launching Redacted..." -ForegroundColor Cyan
Write-Host ""

Set-Location $installDir
python main.py
