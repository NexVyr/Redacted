#!/usr/bin/env bash
# Redacted - Hardware Analysis Tool
# Linux/macOS Launcher Script
# Usage: curl -fsSL https://raw.githubusercontent.com/NexVyr/Redacted/main/scripts/run.sh | bash

set -e

REPO="https://github.com/NexVyr/Redacted"
INSTALL_DIR="$HOME/.local/share/redacted"
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GRAY='\033[0;37m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${CYAN}  ██████████ REDACTED${NC}"
echo -e "${CYAN}  Hardware Analysis Tool v0.1${NC}"
echo -e "${GRAY}  ===========================================${NC}"
echo ""

# ── Detect OS ──────────────────────────────────────────────────
OS="linux"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
fi

# ── Check Python ───────────────────────────────────────────────
echo -e "${GRAY}[*] Checking Python...${NC}"
if ! command -v python3 &>/dev/null; then
    echo -e "${YELLOW}[!] Python 3 not found. Installing...${NC}"
    if [ "$OS" = "linux" ]; then
        sudo apt-get install -y python3 python3-pip 2>/dev/null || \
        sudo dnf install -y python3 python3-pip 2>/dev/null || \
        sudo pacman -S python python-pip 2>/dev/null
    elif [ "$OS" = "macos" ]; then
        brew install python3
    fi
fi
echo -e "${GREEN}[+] $(python3 --version) found${NC}"

# ── Check Git ─────────────────────────────────────────────────
echo -e "${GRAY}[*] Checking Git...${NC}"
if ! command -v git &>/dev/null; then
    echo -e "${YELLOW}[!] Git not found. Installing...${NC}"
    if [ "$OS" = "linux" ]; then
        sudo apt-get install -y git 2>/dev/null || sudo dnf install -y git
    elif [ "$OS" = "macos" ]; then
        brew install git
    fi
fi
echo -e "${GREEN}[+] Git found${NC}"

# ── Install / Update Redacted ──────────────────────────────────
echo -e "${GRAY}[*] Setting up Redacted...${NC}"
mkdir -p "$(dirname $INSTALL_DIR)"

if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${GRAY}[*] Updating...${NC}"
    git -C "$INSTALL_DIR" pull --quiet
    echo -e "${GREEN}[+] Updated!${NC}"
else
    echo -e "${GRAY}[*] Installing to $INSTALL_DIR...${NC}"
    git clone --depth=1 "$REPO" "$INSTALL_DIR" --quiet
    echo -e "${GREEN}[+] Installed!${NC}"
fi

# ── Python venv + dependencies ─────────────────────────────────
echo -e "${GRAY}[*] Setting up Python environment...${NC}"
cd "$INSTALL_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet --disable-pip-version-check
fi
echo -e "${GREEN}[+] Dependencies ready${NC}"

# ── Check ADB ─────────────────────────────────────────────────
echo -e "${GRAY}[*] Checking ADB...${NC}"
if ! command -v adb &>/dev/null; then
    echo -e "${YELLOW}[!] ADB not found. Installing platform-tools...${NC}"
    if [ "$OS" = "linux" ]; then
        sudo apt-get install -y android-tools-adb 2>/dev/null || {
            # Manual install
            PT_URL="https://dl.google.com/android/repository/platform-tools-latest-linux.zip"
            PT_DIR="$INSTALL_DIR/resources"
            mkdir -p "$PT_DIR"
            curl -fsSL "$PT_URL" -o /tmp/platform-tools.zip
            unzip -q /tmp/platform-tools.zip -d "$PT_DIR"
            rm /tmp/platform-tools.zip
            export PATH="$PATH:$PT_DIR/platform-tools"
        }
    elif [ "$OS" = "macos" ]; then
        brew install android-platform-tools
    fi
fi
echo -e "${GREEN}[+] ADB ready${NC}"

# ── Launch ────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}[*] Launching Redacted...${NC}"
echo ""

cd "$INSTALL_DIR"
python3 main.py
