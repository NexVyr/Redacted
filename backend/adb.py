"""
adb.py - ADB & Fastboot communication layer for Redacted
Handles all device communication via ADB and Fastboot.
"""

import subprocess
import os
import sys
import json
import re
import platform
from typing import Optional

class ADBManager:
    def __init__(self):
        self.adb_path  = self._find_tool("adb")
        self.fastboot_path = self._find_tool("fastboot")
        self._device_serial = None

    def _find_tool(self, tool: str) -> str:
        """Find ADB/Fastboot binary - checks PATH and local resources folder."""
        # Check PATH first
        from shutil import which
        found = which(tool)
        if found:
            return found

        # Check local resources/platform-tools
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join(base, "resources", "platform-tools", tool),
            os.path.join(base, "resources", "platform-tools", tool + ".exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c

        return tool  # Hope it's in PATH

    def check_adb(self) -> bool:
        """Check if ADB is available."""
        try:
            result = subprocess.run(
                [self.adb_path, "version"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _run(self, args: list, timeout: int = 10) -> tuple:
        """Run a command and return (stdout, stderr, returncode)."""
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            return "", "Timeout", 1
        except FileNotFoundError:
            return "", f"Not found: {args[0]}", 1

    def adb(self, *args, timeout: int = 10) -> tuple:
        """Run an ADB command."""
        cmd = [self.adb_path]
        if self._device_serial:
            cmd += ["-s", self._device_serial]
        cmd += list(args)
        return self._run(cmd, timeout)

    def fastboot(self, *args, timeout: int = 10) -> tuple:
        """Run a Fastboot command."""
        cmd = [self.fastboot_path] + list(args)
        return self._run(cmd, timeout)

    # ==========================================
    # Device Detection
    # ==========================================

    def get_devices(self) -> list:
        """Get list of connected ADB devices."""
        stdout, _, _ = self.adb("devices", "-l")
        devices = []
        for line in stdout.splitlines()[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] in ("device", "recovery", "sideload"):
                serial = parts[0]
                mode   = parts[1]
                # Extract model if available
                model = ""
                for part in parts[2:]:
                    if part.startswith("model:"):
                        model = part.split(":")[1].replace("_", " ")
                        break
                devices.append({
                    "serial": serial,
                    "mode":   mode,
                    "model":  model
                })
        return devices

    def get_fastboot_devices(self) -> list:
        """Get list of devices in fastboot mode."""
        stdout, _, _ = self.fastboot("devices")
        devices = []
        for line in stdout.splitlines():
            if "fastboot" in line:
                serial = line.split()[0]
                devices.append({"serial": serial, "mode": "fastboot"})
        return devices

    def select_device(self, serial: str):
        """Select a specific device by serial."""
        self._device_serial = serial

    # ==========================================
    # Device Info
    # ==========================================

    def get_prop(self, prop: str) -> str:
        """Get a single Android property."""
        stdout, _, rc = self.adb("shell", "getprop", prop)
        return stdout.strip() if rc == 0 else ""

    def get_all_props(self) -> dict:
        """Get all Android properties as dict."""
        stdout, _, rc = self.adb("shell", "getprop")
        if rc != 0:
            return {}
        props = {}
        for line in stdout.splitlines():
            match = re.match(r'\[(.+?)\]:\s*\[(.+?)\]', line)
            if match:
                props[match.group(1)] = match.group(2)
        return props

    def get_device_info(self) -> dict:
        """Get comprehensive device information."""
        props = self.get_all_props()

        # CPU Info
        cpu_stdout, _, _ = self.adb("shell", "cat", "/proc/cpuinfo")
        cpu_hardware = ""
        cpu_cores    = 0
        for line in cpu_stdout.splitlines():
            if line.startswith("Hardware"):
                cpu_hardware = line.split(":")[1].strip()
            if line.startswith("processor"):
                cpu_cores += 1

        # RAM Info
        mem_stdout, _, _ = self.adb("shell", "cat", "/proc/meminfo")
        total_ram = ""
        for line in mem_stdout.splitlines():
            if line.startswith("MemTotal"):
                kb = int(re.search(r'\d+', line).group())
                total_ram = f"{round(kb / 1024 / 1024)} GB"
                break

        # Storage Info
        df_stdout, _, _ = self.adb("shell", "df", "/data")
        storage = ""
        for line in df_stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                kb = int(parts[1]) if parts[1].isdigit() else 0
                storage = f"{round(kb / 1024 / 1024)} GB"
                break

        # Bootloader status
        bl_stdout, _, _ = self.adb("shell", "getprop",
                                    "ro.boot.flash.locked")
        bootloader_locked = bl_stdout.strip() == "1"

        return {
            "model":       props.get("ro.product.model", "Unknown"),
            "codename":    props.get("ro.product.device", "Unknown"),
            "brand":       props.get("ro.product.brand", "Unknown"),
            "android":     props.get("ro.build.version.release", "Unknown"),
            "miui":        props.get("ro.miui.ui.version.name", ""),
            "soc":         cpu_hardware or props.get("ro.board.platform", "Unknown"),
            "cpu_cores":   cpu_cores,
            "ram":         total_ram,
            "storage":     storage,
            "bootloader":  "Locked" if bootloader_locked else "Unlocked",
            "selinux":     props.get("ro.build.selinux", "Unknown"),
            "serial":      props.get("ro.serialno", "REDACTED"),
            "android_id":  "REDACTED",
            "imei":        "REDACTED",
        }

    # ==========================================
    # Fastboot Info
    # ==========================================

    def get_fastboot_info(self) -> dict:
        """Get all fastboot variables."""
        stdout, _, _ = self.fastboot("getvar", "all", timeout=15)
        info = {}
        for line in (stdout + "\n").splitlines():
            match = re.match(r'(.+?):\s*(.+)', line)
            if match:
                info[match.group(1).strip()] = match.group(2).strip()
        return info

    # ==========================================
    # Partitions
    # ==========================================

    def get_partitions(self) -> list:
        """Get partition list from device."""
        stdout, _, rc = self.adb(
            "shell",
            "ls", "-la", "/dev/block/by-name/"
        )
        if rc != 0:
            return []

        partitions = []
        for line in stdout.splitlines():
            parts = line.split("->")
            if len(parts) == 2:
                name = parts[0].strip().split()[-1]
                target = parts[1].strip()
                partitions.append({
                    "name":   name,
                    "target": target,
                })
        return partitions

    # ==========================================
    # Drivers
    # ==========================================

    def get_loaded_modules(self) -> list:
        """Get list of loaded kernel modules."""
        stdout, _, rc = self.adb("shell", "lsmod")
        if rc != 0:
            return []

        modules = []
        for line in stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 3:
                modules.append({
                    "name":   parts[0],
                    "size":   parts[1],
                    "used":   parts[2],
                })
        return modules

    def get_dmesg(self, lines: int = 200) -> str:
        """Get kernel log (dmesg)."""
        stdout, _, _ = self.adb(
            "shell", "dmesg",
            timeout=15
        )
        return "\n".join(stdout.splitlines()[-lines:])

    # ==========================================
    # Shell
    # ==========================================

    def shell(self, command: str) -> dict:
        """Execute a shell command and return result."""
        stdout, stderr, rc = self.adb("shell", command, timeout=30)
        return {
            "stdout":     stdout,
            "stderr":     stderr,
            "returncode": rc,
        }

    # ==========================================
    # Boot
    # ==========================================

    def boot_recovery(self, image_path: str) -> bool:
        """Boot a recovery image via fastboot."""
        _, _, rc = self.fastboot("boot", image_path, timeout=60)
        return rc == 0

    def reboot_fastboot(self) -> bool:
        """Reboot device into fastboot mode."""
        _, _, rc = self.adb("reboot", "bootloader")
        return rc == 0

    def reboot_recovery(self) -> bool:
        """Reboot device into recovery mode."""
        _, _, rc = self.adb("reboot", "recovery")
        return rc == 0

    def reboot(self) -> bool:
        """Reboot device normally."""
        _, _, rc = self.adb("reboot")
        return rc == 0
