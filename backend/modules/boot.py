"""
boot.py - Boot sequence analyzer for Redacted
Parses dmesg to map the boot timeline and identify key events.
"""

import re
from typing import Optional

# Key boot events to look for in dmesg
BOOT_EVENTS = [
    (r"Booting Linux",                          "Kernel start"),
    (r"Linux version",                          "Kernel version"),
    (r"UEFI|ABL|abl",                          "ABL / UEFI"),
    (r"Qualcomm Technologies",                  "QCom platform init"),
    (r"spmi_pmic_arb.*probe",                   "PMIC / SPMI"),
    (r"qcom_rpmh|rpmh",                         "RPMh init"),
    (r"qcom-cpufreq|cpufreq",                   "CPU frequency"),
    (r"qcom_geni_serial|msm_serial",            "UART / Serial"),
    (r"tlmm|pinctrl",                           "GPIO / TLMM"),
    (r"regulator.*enabled|vreg",                "Regulators"),
    (r"msm_drm|drm.*probe|simplefb|simple-fb",  "Display"),
    (r"goodix|synaptics.*touch",                "Touchscreen"),
    (r"ath11k|wcn.*wifi",                       "Wi-Fi"),
    (r"dwc3|xhci.*usb",                         "USB"),
    (r"wcd|wsa|lpass|sound.*card",              "Audio"),
    (r"mmc|ufs.*probe",                         "Storage"),
    (r"systemd.*running|init.*started",         "Userspace init"),
]

class BootAnalyzer:

    def __init__(self, adb_manager):
        self.adb = adb_manager

    def _parse_timestamp(self, line: str) -> Optional[float]:
        """Extract timestamp from dmesg line like [  1.234567]"""
        match = re.match(r'\[\s*([\d.]+)\]', line)
        if match:
            return float(match.group(1))
        return None

    def get_boot_timeline(self) -> list:
        """
        Parse dmesg and return a timeline of key boot events.
        """
        dmesg, _, rc = self.adb.adb("shell", "dmesg", timeout=15)
        if rc != 0:
            return []

        lines     = dmesg.splitlines()
        timeline  = []
        seen      = set()

        for line in lines:
            ts = self._parse_timestamp(line)
            if ts is None:
                continue

            for pattern, label in BOOT_EVENTS:
                if label in seen:
                    continue
                if re.search(pattern, line, re.IGNORECASE):
                    # Clean up the line for display
                    clean = re.sub(r'\[\s*[\d.]+\]\s*', '', line).strip()
                    clean = re.sub(r'<\d+>', '', clean).strip()
                    if len(clean) > 80:
                        clean = clean[:80] + "..."

                    timeline.append({
                        "time_s":  ts,
                        "time_ms": int(ts * 1000),
                        "label":   label,
                        "detail":  clean,
                        "status":  "ok",
                    })
                    seen.add(label)
                    break

        # Sort by timestamp
        timeline.sort(key=lambda x: x["time_s"])

        # Add relative timing
        if timeline:
            base = timeline[0]["time_s"]
            for event in timeline:
                event["relative_ms"] = int((event["time_s"] - base) * 1000)

        return timeline

    def get_boot_errors(self) -> list:
        """Get errors and warnings from dmesg."""
        dmesg, _, rc = self.adb.adb("shell", "dmesg", timeout=15)
        if rc != 0:
            return []

        errors = []
        for line in dmesg.splitlines():
            ts = self._parse_timestamp(line)
            if ts is None:
                continue

            level = ""
            if re.search(r'\bERR\b|error:|failed|FAILED', line, re.I):
                level = "error"
            elif re.search(r'\bWARN\b|warning:', line, re.I):
                level = "warning"
            else:
                continue

            clean = re.sub(r'\[\s*[\d.]+\]\s*', '', line).strip()
            errors.append({
                "time_ms": int(ts * 1000),
                "level":   level,
                "message": clean[:120],
            })

        return errors[-50:]  # Last 50 errors

    def get_loaded_partitions(self) -> list:
        """Get partitions mounted during boot from dmesg."""
        dmesg, _, _ = self.adb.adb("shell", "dmesg", timeout=15)
        partitions  = []
        seen        = set()

        for line in dmesg.splitlines():
            match = re.search(r'EXT4-fs \((\w+)\).*mounted', line, re.I)
            if match:
                part = match.group(1)
                if part not in seen:
                    ts = self._parse_timestamp(line) or 0
                    partitions.append({
                        "partition": part,
                        "time_ms":   int(ts * 1000),
                        "fs":        "ext4",
                    })
                    seen.add(part)

        return partitions

    def get_boot_summary(self) -> dict:
        """Full boot analysis summary."""
        timeline   = self.get_boot_timeline()
        errors     = self.get_boot_errors()
        partitions = self.get_loaded_partitions()

        total_time = 0
        if timeline:
            total_time = timeline[-1]["time_ms"]

        return {
            "total_time_ms": total_time,
            "event_count":   len(timeline),
            "error_count":   len([e for e in errors if e["level"] == "error"]),
            "warn_count":    len([e for e in errors if e["level"] == "warning"]),
            "timeline":      timeline,
            "errors":        errors,
            "partitions":    partitions,
        }
