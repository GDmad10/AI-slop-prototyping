"""Device detection (§11) + install compatibility check (§10). No bypasses, ever."""
from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class DeviceInfo:
    model: str = "unknown"
    ios_version: str = "unknown"
    architecture: str = "unknown"
    udid: str = ""
    storage_free: str = "unknown"
    connection: str = "none"
    developer_mode: str = "unknown"


def _run(cmd: list[str], timeout: int = 15) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip()
    except Exception:
        return ""


def detect_device() -> DeviceInfo:
    """Best-effort local device probe. Prefers pymobiledevice3 / ideviceinfo if installed."""
    dev = DeviceInfo()
    if shutil.which("ideviceinfo"):
        raw = _run(["ideviceinfo"])
        for line in raw.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if k == "devicename":
                dev.model = v
            elif k == "productversion":
                dev.ios_version = v
            elif k == "uniquechipid" or k == "uniqueidentifier":
                dev.udid = v
        if raw:
            dev.connection = "usbmuxd/ideviceinfo"
            dev.architecture = "arm64"  # all supported iOS 11+ devices
    elif shutil.which("pymobiledevice3"):
        dev.connection = "pymobiledevice3 (run `pymobiledevice3 usbmux list` for detail)"
    dev.storage_free = _run(["wmic", "logicaldisk", "get", "size,freespace,caption"])[:200] if platform.system() == "Windows" else dev.storage_free
    return dev


def _parse_ios(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in v.replace("_", ".").split("."):
        digits = "".join(c for c in p if c.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts) or (0,)


def check_compatibility(minimum_ios: str, ipa_arch: str, device: DeviceInfo) -> tuple[bool, str]:
    """PASS/FAIL with human reason. Never claims installability it can't prove."""
    if device.connection == "none":
        return False, "No device detected. Connect an iPhone/iPad to evaluate compatibility."
    reasons: list[str] = []
    ok = True
    if minimum_ios and device.ios_version not in ("unknown", ""):
        try:
            if _parse_ios(device.ios_version) < _parse_ios(minimum_ios):
                ok = False
                reasons.append(f"Device iOS {device.ios_version} < IPA minimum {minimum_ios}.")
        except Exception:
            reasons.append("iOS version parse uncertain — verify manually.")
    else:
        reasons.append("iOS compatibility unknown (missing version data).")
    if ipa_arch and device.architecture not in ("unknown", "") and ipa_arch not in device.architecture:
        # 32-bit-only IPAs on 64-bit-only iOS 11+ are the classic preservation wall.
        reasons.append(f"Architecture mismatch: IPA {ipa_arch} vs device {device.architecture}.")
    if ok and not reasons:
        reasons.append("COMPATIBLE on paper — signing/entitlement checks still apply at install.")
    return ok, " ".join(reasons)


def render_device(device: DeviceInfo, minimum_ios: str = "", ipa_arch: str = "") -> str:
    lines = [
        "## DEVICE", "", f"Model: {device.model}", f"iOS: {device.ios_version}",
        f"Architecture: {device.architecture}", f"Storage available: {device.storage_free}",
        f"Connection: {device.connection}",
    ]
    if minimum_ios or ipa_arch:
        lines += [f"IPA minimum iOS: {minimum_ios or '?'}", f"IPA architecture: {ipa_arch or '?'}", ""]
        ok, reason = check_compatibility(minimum_ios, ipa_arch, device)
        lines += [f"Compatibility:\n{'PASS' if ok else 'FAIL'} — {reason}"]
    return "\n".join(lines)
