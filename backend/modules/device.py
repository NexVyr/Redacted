"""
device.py - Device hardware detection module for Redacted
Parses SoC, display, RAM, storage etc from ADB output.
"""

import re
from typing import Optional

# Known SoC identifiers → (friendly name, vendor)
SOC_MAP = {
    # ── Qualcomm Snapdragon ──────────────────────────
    "SM7325":     ("Snapdragon 778G",       "Qualcomm"),
    "SM8450":     ("Snapdragon 8 Gen 1",    "Qualcomm"),
    "SM8475":     ("Snapdragon 8+ Gen 1",   "Qualcomm"),
    "SM8550":     ("Snapdragon 8 Gen 2",    "Qualcomm"),
    "SM8650":     ("Snapdragon 8 Gen 3",    "Qualcomm"),
    "SM8750":     ("Snapdragon 8 Elite",    "Qualcomm"),
    "SM7450":     ("Snapdragon 7 Gen 1",    "Qualcomm"),
    "SM7475":     ("Snapdragon 7+ Gen 2",   "Qualcomm"),
    "SM7550":     ("Snapdragon 7 Gen 2",    "Qualcomm"),
    "SM7675":     ("Snapdragon 7+ Gen 3",   "Qualcomm"),
    "SM6375":     ("Snapdragon 695",        "Qualcomm"),
    "SM6450":     ("Snapdragon 6 Gen 1",    "Qualcomm"),
    "SM4450":     ("Snapdragon 4 Gen 2",    "Qualcomm"),
    "SDM845":     ("Snapdragon 845",        "Qualcomm"),
    "SDM855":     ("Snapdragon 855",        "Qualcomm"),
    "SDM865":     ("Snapdragon 865",        "Qualcomm"),
    "SM8250":     ("Snapdragon 865",        "Qualcomm"),
    "SM8350":     ("Snapdragon 888",        "Qualcomm"),
    "SM8150":     ("Snapdragon 855",        "Qualcomm"),
    # ── Google Tensor ────────────────────────────────
    "ZUMA":       ("Tensor G3",             "Google"),
    "ZUMAPRO":    ("Tensor G3 Pro",         "Google"),
    "RIPCURRENT": ("Tensor G2",             "Google"),
    "GS201":      ("Tensor G2",             "Google"),
    "GS101":      ("Tensor G1",             "Google"),
    # ── MediaTek ─────────────────────────────────────
    "MT6895":     ("Dimensity 8100",        "MediaTek"),
    "MT6897":     ("Dimensity 8200",        "MediaTek"),
    "MT6983":     ("Dimensity 9000",        "MediaTek"),
    "MT6985":     ("Dimensity 9200",        "MediaTek"),
    "MT6989":     ("Dimensity 9300",        "MediaTek"),
    "MT6878":     ("Dimensity 7050",        "MediaTek"),
    # ── Samsung Exynos ───────────────────────────────
    "S5E9925":    ("Exynos 2200",           "Samsung"),
    "S5E9935":    ("Exynos 2400",           "Samsung"),
    "EXYNOS2200": ("Exynos 2200",           "Samsung"),
    "EXYNOS2400": ("Exynos 2400",           "Samsung"),
}

class DeviceParser:

    def __init__(self, adb_manager):
        self.adb = adb_manager

    def detect_soc(self, props: dict) -> dict:
        """Detect SoC from device properties."""
        candidates = [
            props.get("ro.board.platform", ""),
            props.get("ro.hardware", ""),
            props.get("ro.product.board", ""),
            props.get("ro.chipname", ""),
            props.get("ro.soc.model", ""),
        ]

        soc_id = soc_name = ""
        soc_vendor = "Unknown"

        for candidate in candidates:
            if not candidate:
                continue
            up = candidate.upper()
            for key, (name, vendor) in SOC_MAP.items():
                if key in up:
                    soc_id, soc_name, soc_vendor = key, name, vendor
                    break
            if soc_name:
                break

        if not soc_id:
            soc_id = next((c for c in candidates if c), "Unknown")

        stdout, _, _ = self.adb.adb("shell", "cat", "/proc/cpuinfo")
        cores = len(re.findall(r'^processor\s*:', stdout, re.M))

        freqs = []
        for i in range(min(cores, 9)):
            freq_out, _, rc = self.adb.adb(
                "shell",
                f"cat /sys/devices/system/cpu/cpu{i}/cpufreq/cpuinfo_max_freq"
            )
            if rc == 0 and freq_out.strip().isdigit():
                freqs.append(int(freq_out.strip()) // 1000)

        max_freq = max(freqs) if freqs else 0

        return {
            "id":       soc_id,
            "name":     soc_name or soc_id,
            "cores":    cores,
            "max_freq": f"{max_freq} MHz" if max_freq else "Unknown",
            "vendor":   soc_vendor,
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
