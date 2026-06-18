"""
drivers.py - Driver detection and backup module for Redacted
Analyzes loaded kernel modules and creates driver backups.
"""

import os
import re
import zipfile
import tempfile
from datetime import datetime
from typing import Optional

# Known driver categories by name pattern
DRIVER_CATEGORIES = {
    "uart|serial|tty":          "UART",
    "gpio|tlmm|pinctrl":        "GPIO",
    "drm|fb|display|mdss|dpu":  "Display",
    "ath|wifi|wlan|wcn":        "Wi-Fi",
    "bt|bluetooth|hci":         "Bluetooth",
    "usb|dwc|xhci":             "USB",
    "snd|audio|sound|lpass|wcd|wsa": "Audio",
    "pmic|spmi|regulator|rpm":  "Power",
    "i2c|spi|uart":             "Bus",
    "camera|cam|cci":           "Camera",
    "sensor|imu|accel|gyro":    "Sensors",
    "touch|goodix|synaptics":   "Touch",
    "thermal|tsens":            "Thermal",
    "cpufreq|cpu|scheduler":    "CPU",
    "mmc|ufs|sdhci|storage":    "Storage",
    "net|eth|ipa":              "Network",
}

def categorize_driver(name: str) -> str:
    """Categorize a driver by its name."""
    name_lower = name.lower()
    for pattern, category in DRIVER_CATEGORIES.items():
        if re.search(pattern, name_lower):
            return category
    return "Other"

class DriverAnalyzer:

    def __init__(self, adb_manager):
        self.adb = adb_manager

    def get_loaded_drivers(self) -> list:
        """Get all loaded kernel modules with details."""
        stdout, _, rc = self.adb.adb("shell", "lsmod")
        if rc != 0:
            return []

        drivers = []
        for line in stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 3:
                continue
            name     = parts[0]
            size     = int(parts[1]) if parts[1].isdigit() else 0
            used_by  = parts[3] if len(parts) > 3 else ""

            drivers.append({
                "name":     name,
                "size":     f"{size // 1024} KB" if size >= 1024 else f"{size} B",
                "category": categorize_driver(name),
                "used_by":  used_by,
                "status":   "loaded",
            })

        return sorted(drivers, key=lambda x: x["category"])

    def get_available_drivers(self) -> list:
        """Get all available .ko files on device (not just loaded)."""
        stdout, _, rc = self.adb.adb(
            "shell", "find", "/vendor/lib/modules",
            "/lib/modules", "-name", "*.ko",
            "-type", "f",
            timeout=30
        )
        if rc != 0:
            return []

        drivers = []
        for path in stdout.splitlines():
            name = os.path.basename(path).replace(".ko", "")
            drivers.append({
                "name":     name,
                "path":     path,
                "category": categorize_driver(name),
                "status":   "available",
            })

        return drivers

    def get_driver_details(self, module_name: str) -> dict:
        """Get detailed info about a specific kernel module."""
        stdout, _, rc = self.adb.adb("shell", "modinfo", module_name)
        if rc != 0:
            # Try finding the .ko file
            find_stdout, _, _ = self.adb.adb(
                "shell", "find", "/vendor/lib/modules", "-name",
                f"{module_name}.ko"
            )
            if find_stdout.strip():
                stdout, _, rc = self.adb.adb(
                    "shell", "modinfo", find_stdout.strip()
                )

        details = {}
        for line in stdout.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                details[key.strip()] = val.strip()

        return details

    def create_backup_zip(self, output_path: Optional[str] = None) -> str:
        """
        Create a ZIP backup of all driver .ko files from the device.
        Returns the path to the created ZIP file.
        """
        if not output_path:
            timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"redacted_drivers_{timestamp}.zip"
            )

        print(f"[*] Creating driver backup: {output_path}")

        # Find all .ko files
        search_paths = [
            "/vendor/lib/modules",
            "/lib/modules",
            "/system/lib/modules",
        ]

        ko_files = []
        for path in search_paths:
            stdout, _, rc = self.adb.adb(
                "shell", "find", path, "-name", "*.ko", "-type", "f",
                timeout=30
            )
            if rc == 0:
                for f in stdout.splitlines():
                    if f.strip():
                        ko_files.append(f.strip())

        if not ko_files:
            return ""

        print(f"[*] Found {len(ko_files)} driver files")

        # Pull each file and add to ZIP
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add metadata
            metadata = {
                "created":     datetime.now().isoformat(),
                "tool":        "Redacted v0.1",
                "file_count":  len(ko_files),
            }
            zf.writestr("metadata.json",
                        __import__("json").dumps(metadata, indent=2))

            for i, ko_path in enumerate(ko_files):
                print(f"[*] Pulling {i+1}/{len(ko_files)}: {ko_path}")

                # Pull file to temp
                tmp = tempfile.mktemp(suffix=".ko")
                _, _, rc = self.adb.adb("pull", ko_path, tmp, timeout=30)
                if rc == 0 and os.path.exists(tmp):
                    # Add to ZIP preserving path structure
                    arcname = ko_path.lstrip("/")
                    zf.write(tmp, arcname)
                    os.unlink(tmp)

        size_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"[*] Driver backup complete: {size_mb:.1f} MB")
        return output_path

    def get_missing_drivers(self) -> list:
        """
        Compare loaded drivers against expected drivers for known devices.
        Returns list of drivers that should be present but aren't loaded.
        """
        loaded     = {d["name"] for d in self.get_loaded_drivers()}
        available  = {d["name"] for d in self.get_available_drivers()}
        missing    = available - loaded

        return [
            {
                "name":     name,
                "category": categorize_driver(name),
                "status":   "not_loaded",
            }
            for name in sorted(missing)
        ]

    def get_driver_summary(self) -> dict:
        """Get a summary of driver status."""
        loaded    = self.get_loaded_drivers()
        available = self.get_available_drivers()

        by_category = {}
        for d in loaded:
            cat = d["category"]
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "loaded_count":    len(loaded),
            "available_count": len(available),
            "by_category":     by_category,
            "drivers":         loaded,
        }
