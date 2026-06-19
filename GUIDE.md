# 📖 Usage Guide

## 🚀 Quick Start

No manual setup needed! Our automated scripts will clone the repo, verify requirements (Python & ADB), and configure everything.

### Windows
```powershell
irm https://raw.githubusercontent.com/NexVyr/Redacted/main/scripts/run.ps1 | iex
```

### Linux / macOS
```bash
curl -fsSL https://raw.githubusercontent.com/NexVyr/Redacted/main/scripts/run.sh | bash
```

---

## 📋 System Requirements

### Operating System
- **Windows:** 10 or 11 (PowerShell 5.1+)
- **Linux:** Ubuntu 20.04 LTS / 22.04 LTS or modern Debian variant

### Dependencies
*(Auto-installed if missing)*
- **Python:** 3.8+
- **ADB:** Android Debug Bridge
- **Browser:** Chrome, Firefox, or Edge

### Android Device
- **OS:** Android 5.0+
- **Permissions:** No root required
- **USB:** Data cable (not charging-only)

---

## 📱 Enable USB Debugging

1. Open **Settings** → **About phone** → tap **Build number** 7 times
2. Go back to **Settings** → **System** → **Developer options**
3. Enable **USB Debugging**
4. Connect via USB cable and tap **Allow** when prompted

---

## 📊 View Results

Once analysis completes, your dashboard opens automatically in `localhost`. No file searching needed!
