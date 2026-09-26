"""IPA forensic analyzer (§8) + encryption detection (§9) + hashing (§19)."""
from __future__ import annotations

import hashlib
import os
import plistlib
import struct
import zipfile
from dataclasses import dataclass, field


@dataclass
class IPAReport:
    name: str = ""
    bundle_id: str = ""
    version: str = ""
    build: str = ""
    minimum_ios: str = ""
    device_family: str = ""
    architectures: str = ""
    encryption: str = "UNKNOWN"   # UNENCRYPTED | FAIRPLAY_ENCRYPTED | UNKNOWN
    signature_present: bool = False
    provisioning_present: bool = False
    executable: str = ""
    sha256: str = ""
    sha1: str = ""
    md5: str = ""
    file_size: int = 0
    error: str = ""

    def render(self) -> str:
        return (
            "## IPA ANALYSIS\n\n"
            f"Name: {self.name}\n"
            f"Bundle ID: {self.bundle_id}\n"
            f"Version: {self.version}\n"
            f"Build: {self.build}\n"
            f"Minimum iOS: {self.minimum_ios}\n"
            f"Architecture: {self.architectures}\n"
            f"Encryption: {self.encryption}\n"
            f"Signature: {'present' if self.signature_present else 'absent/unknown'}\n"
            f"Provisioning: {'embedded.mobileprovision found' if self.provisioning_present else 'not found'}\n"
            f"Executable: {self.executable}\n"
            f"File Hash: {self.sha256}\n"
        )


def hash_file(path: str) -> tuple[str, str, str, int]:
    """SHA-256 + SHA-1 + MD5 (§19). Never modifies the original."""
    h256, h1, hmd5 = hashlib.sha256(), hashlib.sha1(), hashlib.md5()
    size = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h256.update(chunk)
            h1.update(chunk)
            hmd5.update(chunk)
            size += len(chunk)
    return h256.hexdigest(), h1.hexdigest(), hmd5.hexdigest(), size


def _find_app_dir(zf: zipfile.ZipFile) -> str | None:
    for name in zf.namelist():
        if name.startswith("Payload/") and name.count("/") == 2 and name.endswith(".app/"):
            return name
    for name in zf.namelist():
        if name.startswith("Payload/") and ".app/Info.plist" in name:
            prefix = name.split(".app/")[0] + ".app/"
            return prefix
    return None


def _read_plist(zf: zipfile.ZipFile, app_dir: str) -> dict:
    for candidate in (app_dir + "Info.plist",):
        try:
            with zf.open(candidate) as fh:
                return plistlib.load(fh)
        except KeyError:
            continue
    return {}


# Mach-O magic values (little + big endian, 32/64 + FAT).
_MH_MAGICS = {0xFEEDFACE, 0xCEFAEDFE, 0xFEEDFACF, 0xCFFAEDFE, 0xCAFEBABE, 0xBEBAFECA}
LC_ENCRYPTION_INFO = 0x21
LC_ENCRYPTION_INFO_64 = 0x2C


def _cryptid_of_macho(data: bytes) -> str | None:
    """Return cryptid state for one Mach-O slice, or None if not Mach-O."""
    if len(data) < 4:
        return None
    (magic,) = struct.unpack("<I", data[:4])
    if magic not in _MH_MAGICS and struct.unpack(">I", data[:4])[0] not in _MH_MAGICS:
        return None
    # FAT binary: recurse into first slice header region (cheap heuristic).
    if magic == 0xBEBAFECA or struct.unpack(">I", data[:4])[0] == 0xCAFEBABE:
        if len(data) < 8:
            return None
        nfat = struct.unpack(">I", data[4:8])[0]
        # Only inspect the header area; full slice parse is out of scope.
        return _cryptid_of_macho(data[8:8 + 4096]) if nfat else None
    le = magic in (0xFEEDFACE, 0xFEEDFACF)
    is64 = magic in (0xFEEDFACF, 0xCFFAEDFE)
    endian = "<" if le else ">"
    try:
        ncmds_off = 16
        ncmds = struct.unpack(endian + "I", data[ncmds_off:ncmds_off + 4])[0]
        off = 28 if is64 else 28 - 4
        for _ in range(min(ncmds, 128)):
            if off + 8 > len(data):
                break
            cmd, cmdsize = struct.unpack(endian + "II", data[off:off + 8])
            if cmd in (LC_ENCRYPTION_INFO, LC_ENCRYPTION_INFO_64):
                if off + 12 > len(data):
                    break
                cryptid = struct.unpack(endian + "I", data[off + 8:off + 12])[0] if cmd == LC_ENCRYPTION_INFO else struct.unpack(endian + "I", data[off + 12:off + 16])[0]
                return "FAIRPLAY_ENCRYPTED" if cryptid != 0 else "UNENCRYPTED"
            if cmdsize == 0:
                break
            off += cmdsize
    except struct.error:
        return None
    return "UNENCRYPTED"  # Mach-O with no crypt command: platform binary / decrypted research copy


def detect_encryption(zf: zipfile.ZipFile, app_dir: str, executable: str) -> str:
    """Detect FairPlay encryption via LC_ENCRYPTION_INFO cryptid (§9). Read-only."""
    if not executable:
        return "UNKNOWN"
    try:
        with zf.open(app_dir + executable) as fh:
            header = fh.read(1 << 20)
    except KeyError:
        return "UNKNOWN"
    result = _cryptid_of_macho(header)
    return result or "UNKNOWN"


def analyze_ipa(path: str) -> IPAReport:
    """Full IPA inspection (§8). Never writes to the IPA."""
    rep = IPAReport()
    if not os.path.exists(path):
        rep.error = f"File not found: {path}"
        return rep
    rep.sha256, rep.sha1, rep.md5, rep.file_size = hash_file(path)
    try:
        zf = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile:
        rep.error = "Not a valid zip/IPA container."
        return rep
    with zf:
        app_dir = _find_app_dir(zf)
        if not app_dir:
            rep.error = "No Payload/*.app directory found."
            return rep
        info = _read_plist(zf, app_dir)
        if not info:
            rep.error = "Info.plist missing or unreadable."
            return rep
        rep.name = info.get("CFBundleDisplayName", info.get("CFBundleName", ""))
        rep.bundle_id = info.get("CFBundleIdentifier", "")
        rep.version = info.get("CFBundleShortVersionString", "")
        rep.build = str(info.get("CFBundleVersion", ""))
        rep.minimum_ios = str(info.get("MinimumOSVersion", info.get("LSMinimumSystemVersion", "")))
        fam = info.get("UIDeviceFamily", [])
        rep.device_family = ",".join(str(x) for x in fam) if isinstance(fam, list) else str(fam)
        rep.executable = info.get("CFBundleExecutable", "")
        names = zf.namelist()
        rep.signature_present = any(n.startswith(app_dir + "_CodeSignature/") for n in names)
        rep.provisioning_present = (app_dir + "embedded.mobileprovision") in names
        rep.architectures = info.get("UIRequiredDeviceCapabilities", {}).get("arm64", "") and "arm64?" or ""
        rep.encryption = detect_encryption(zf, app_dir, rep.executable)
    return rep


def compare_ipas(path_a: str, path_b: str) -> str:
    """Duplicate detection (§20): hash + bundle/version/build comparison."""
    ra, rb = analyze_ipa(path_a), analyze_ipa(path_b)
    if ra.sha256 == rb.sha256:
        return "EXACT DUPLICATE"
    if ra.bundle_id == rb.bundle_id and ra.version == rb.version:
        if ra.build != rb.build:
            return "SAME VERSION / DIFFERENT BUILD"
        return "SAME VERSION / DIFFERENT BYTES (re-sign or re-encrypt suspected)"
    return "DIFFERENT VERSION"
