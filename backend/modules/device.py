"""
device.py - Device hardware detection module for Redacted
Parses SoC, display, RAM, storage etc from ADB output.
"""

import re
from typing import Optional

# Known Snapdragon SoC identifiers
SNAPDRAGON_MAP = {
    "SM7325":  "Snapdragon 778G",
    "SM8450":  "Snapdragon 8 Gen 1",
    "SM8475":  "Snapdragon 8+ Gen 1",
    "SM8550":  "Snapdragon 8 Gen 2",
    "SM8650":  "Snapdragon 8 Gen 3",
    "SM7450":  "Snapdragon 7 Gen 1",
    "SM7475":  "Snapdragon 7+ Gen 2",
    "SM6375":  "Snapdragon 695",
    "SM6450":  "Snapdragon 6 Gen 1",
    "SM4450":  "Snapdragon 4 Gen 2",
    "SDM845":  "Snapdragon 845",
    "SDM855":  "Snapdragon 855",
    "SDM865":  "Snapdragon 865",
    "SM8250":  "Snapdragon 865",
    "SM8350":  "Snapdragon 888",
}

class DeviceParser:

    def __init__(self, adb_manager):
        self.adb = adb_manager

    def detect_soc(self, props: dict) -> dict:
        """Detect SoC from device properties."""
        platform = props.get("ro.board.platform", "").upper()
        hardware = props.get("ro.hardware", "").upper()
        product  = props.get("ro.product.board", "").upper()

        soc_id   = platform or hardware or product
        soc_name = ""

        for key, name in SNAPDRAGON_MAP.items():
            if key in soc_id:
                soc_name = name
                soc_id   = key
                break

        # CPU core count from /proc/cpuinfo
        stdout, _, _ = self.adb.adb("shell", "cat", "/proc/cpuinfo")
        cores = len(re.findall(r'^processor\s*:', stdout, re.M))

        # CPU frequencies
        freqs = []
        for i in range(cores):
            freq_stdout, _, rc = self.adb.adb(
                "shell",
                f"cat /sys/devices/system/cpu/cpu{i}/cpufreq/cpuinfo_max_freq"
            )
            if rc == 0 and freq_stdout.strip().isdigit():
                freqs.append(int(freq_stdout.strip()) // 1000)  # MHz

        max_freq = max(freqs) if freqs else 0

        return {
            "id":       soc_id,
            "name":     soc_name or soc_id,
            "cores":    cores,
            "max_freq": f"{max_freq} MHz" if max_freq else "Unknown",
            "vendor":   "Qualcomm" if soc_name else "Unknown",
        }

    def detect_display(self, props: dict) -> dict:
        """Detect display panel information."""
        # Try to get display info from sysfs
        panel_name = ""

        panel_paths = [
            "/sys/class/drm/card0-DSI-1/panel_info",
            "/sys/class/graphics/fb0/modes",
            "/sys/devices/platform/soc/ae00000.qcom,mdss_mdp/drm/card0/card0-DSI-1/status",
        ]

        for path in panel_paths:
            stdout, _, rc = self.adb.adb("shell", "cat", path)
            if rc == 0 and stdout.strip():
                panel_name = stdout.strip().split("\n")[0]
                break

        # Fallback: get resolution from wm size
        wm_stdout, _, _ = self.adb.adb("shell", "wm", "size")
        resolution = ""
        match = re.search(r'(\d+x\d+)', wm_stdout)
        if match:
            resolution = match.group(1)

        # Get density
        wm_density, _, _ = self.adb.adb("shell", "wm", "density")
        density = ""
        match = re.search(r'(\d+)', wm_density)
        if match:
            density = f"{match.group(1)} dpi"

        # Refresh rate
        dumpsys, _, _ = self.adb.adb(
            "shell", "dumpsys", "display", "|", "grep", "mRefreshRate"
        )
        refresh = ""
        match = re.search(r'mRefreshRate=([\d.]+)', dumpsys)
        if match:
            refresh = f"{float(match.group(1)):.0f}Hz"

        return {
            "panel":      panel_name or "Unknown",
            "resolution": resolution,
            "density":    density,
            "refresh":    refresh,
        }

    def detect_memory(self) -> dict:
        """Detect RAM information."""
        stdout, _, _ = self.adb.adb("shell", "cat", "/proc/meminfo")
        total = available = 0

        for line in stdout.splitlines():
            if line.startswith("MemTotal:"):
                total = int(re.search(r'\d+', line).group())
            elif line.startswith("MemAvailable:"):
                available = int(re.search(r'\d+', line).group())

        total_gb     = round(total / 1024 / 1024, 1)
        available_gb = round(available / 1024 / 1024, 1)
        used_gb      = round(total_gb - available_gb, 1)

        return {
            "total":     f"{total_gb} GB",
            "available": f"{available_gb} GB",
            "used":      f"{used_gb} GB",
            "percent":   round((used_gb / total_gb) * 100) if total_gb else 0,
        }

    def detect_storage(self) -> list:
        """Detect storage partitions and usage."""
        stdout, _, _ = self.adb.adb("shell", "df", "-h")
        partitions = []

        for line in stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 6:
                filesystem = parts[0]
                size       = parts[1]
                used       = parts[2]
                available  = parts[3]
                use_pct    = parts[4]
                mount      = parts[5]

                # Only interesting partitions
                if any(m in mount for m in ["/data", "/sdcard", "/storage"]):
                    partitions.append({
                        "filesystem": filesystem,
                        "size":       size,
                        "used":       used,
                        "available":  available,
                        "use_pct":    use_pct,
                        "mount":      mount,
                    })

        return partitions

    def detect_battery(self) -> dict:
        """Detect battery information."""
        stdout, _, _ = self.adb.adb("shell", "dumpsys", "battery")
        info = {}

        for line in stdout.splitlines():
            line = line.strip()
            if "level:" in line:
                info["level"] = line.split(":")[1].strip() + "%"
            elif "voltage:" in line:
                mv = int(line.split(":")[1].strip())
                info["voltage"] = f"{mv/1000:.2f}V"
            elif "temperature:" in line:
                t = int(line.split(":")[1].strip())
                info["temperature"] = f"{t/10:.1f}°C"
            elif "status:" in line:
                status_map = {"1": "Unknown", "2": "Charging",
                              "3": "Discharging", "4": "Not charging",
                              "5": "Full"}
                s = line.split(":")[1].strip()
                info["status"] = status_map.get(s, s)

        return info

    def get_full_hardware_info(self) -> dict:
        """Get complete hardware info in one call."""
        props    = self.adb.get_all_props()
        soc      = self.detect_soc(props)
        display  = self.detect_display(props)
        memory   = self.detect_memory()
        storage  = self.detect_storage()
        battery  = self.detect_battery()

        return {
            "device": {
                "model":    props.get("ro.product.model", "Unknown"),
                "codename": props.get("ro.product.device", "Unknown"),
                "brand":    props.get("ro.product.brand", "Unknown"),
                "android":  props.get("ro.build.version.release", "Unknown"),
                "build":    props.get("ro.build.display.id", "Unknown"),
                "serial":   "REDACTED",
            },
            "soc":      soc,
            "display":  display,
            "memory":   memory,
            "storage":  storage,
            "battery":  battery,
        }
