"""Microsoft package metadata model (DBOX Tools reference shape).

Parses manifests found inside legitimately obtained Windows Phone
packages — primarily Call of Mini: Zombies v1.1.0.0 era XAP/APPX —
and emits a DBOX-style record: identifiers, relationships, version,
architecture, platform, contained files.

Reference: https://dbox.tools/ — package metadata, identifiers,
package relationships, versions, architectures, platforms,
contained files. This module mirrors that *shape* locally from
files the operator already possesses; it performs no network
scraping and no store bypass.

Supported manifests (plaintext XML inside the package):
  - WMAppManifest.xml  (Windows Phone 7/8 Silverlight, XAP)
  - AppxManifest.xml   (Windows Phone 8.1 / Windows, APPX/MSIX)

Primary target pinned: Call of Mini: Zombies v1.1.0.0,
Windows Phone release.
"""
from __future__ import annotations

import os
import re
import zipfile
import xml.etree.ElementTree as ET

PRIMARY_TARGET_GAME = "Call of Mini: Zombies"
PRIMARY_TARGET_VERSION = "1.1.0.0"
PRIMARY_TARGET_PLATFORM = "Windows Phone"

# Known publisher / title tokens observable in lawfully installed
# copies of the historical release (non-secret, manifest-visible).
COMZ_TITLE_TOKENS = ("call of mini", "callofmini", "mini zombies", "minizombies")
COMZ_PUBLISHER_HINTS = ("triniti", "triniti interactive")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def parse_wmappmanifest(xml_bytes: bytes) -> dict:
    """Parse a Windows Phone WMAppManifest.xml into a DBOX-style record."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return {"manifest_type": "WMAppManifest.xml", "parse_error": str(e)}
    # Deployment/App element (namespace varies by SDK)
    app = None
    for el in root.iter():
        if _local(el.tag) == "App":
            app = el
            break
    rec: dict = {"manifest_type": "WMAppManifest.xml"}
    if app is None:
        rec["parse_error"] = "no App element found"
        return rec
    rec["product_id"] = app.attrib.get("ProductID", "")
    rec["title"] = app.attrib.get("Title", "")
    rec["version"] = app.attrib.get("Version", "")
    rec["publisher"] = app.attrib.get("Publisher", "")
    rec["author"] = app.attrib.get("Author", "")
    rec["description"] = app.attrib.get("Description", "")
    rec["genre"] = app.attrib.get("Genre", "")
    # Capabilities / tasks
    caps = [el.attrib.get("Name", "") for el in root.iter()
            if _local(el.tag) == "Capability" and el.attrib.get("Name")]
    rec["capabilities"] = sorted(set(caps))
    tasks = [_local(el.tag) for el in root.iter()
             if _local(el.tag) in ("DefaultTask", "ExtendedTask")]
    rec["tasks"] = tasks
    return rec


def parse_appxmanifest(xml_bytes: bytes) -> dict:
    """Parse an AppxManifest.xml into a DBOX-style record."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return {"manifest_type": "AppxManifest.xml", "parse_error": str(e)}
    rec: dict = {"manifest_type": "AppxManifest.xml"}
    for el in root.iter():
        ln = _local(el.tag)
        if ln == "Identity":
            rec["package_id"] = el.attrib.get("Name", "")
            rec["publisher"] = el.attrib.get("Publisher", "")
            rec["version"] = el.attrib.get("Version", "")
            rec["processor_architecture"] = el.attrib.get("ProcessorArchitecture", "")
        elif ln == "DisplayName":
            rec.setdefault("title", _text(el))
        elif ln == "PublisherDisplayName":
            rec.setdefault("publisher_display", _text(el))
        elif ln == "PhoneIdentity":
            rec["phone_product_id"] = el.attrib.get("PhoneProductId", "")
            rec["phone_publisher_id"] = el.attrib.get("PhonePublisherId", "")
        elif ln == "TargetDeviceFamily":
            rec.setdefault("platforms", []).append(
                {"name": el.attrib.get("Name", ""),
                 "min": el.attrib.get("MinVersion", ""),
                 "max": el.attrib.get("MaxVersionTested", "")})
    # Dependencies block
    deps = []
    for el in root.iter():
        if _local(el.tag) == "PackageDependency":
            deps.append({k.rsplit("}", 1)[-1]: v for k, v in el.attrib.items()})
    if deps:
        rec["dependencies"] = deps
    return rec


def extract_manifests(package_path: str) -> dict[str, bytes]:
    """Return {arcname: bytes} for manifest files inside a zip package."""
    out: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(package_path, "r") as z:
            for info in z.infolist():
                low = info.filename.lower()
                if low.endswith(("wmappmanifest.xml", "appxmanifest.xml")):
                    try:
                        out[info.filename] = z.read(info.filename)
                    except Exception:
                        continue
    except zipfile.BadZipFile:
        pass
    return out


def list_contained_files(package_path: str, limit: int = 2000) -> list[dict]:
    """DBOX-style contained-files inventory (central directory only)."""
    try:
        with zipfile.ZipFile(package_path, "r") as z:
            infos = z.infolist()
    except zipfile.BadZipFile:
        return []
    rows = []
    for i in infos[:limit]:
        rows.append({
            "name": i.filename,
            "size": i.file_size,
            "compressed": i.compress_size,
            "method": i.compress_type,
            "encrypted_flag": bool(i.flag_bits & 0x1),
        })
    return rows


def build_package_record(package_path: str) -> dict:
    """Build the full DBOX-style package record for one local file."""
    from .identify import identify_file
    ident = identify_file(package_path)
    manifests = extract_manifests(package_path)
    parsed: dict = {}
    for arcname, blob in manifests.items():
        low = arcname.lower()
        if low.endswith("wmappmanifest.xml"):
            parsed[arcname] = parse_wmappmanifest(blob)
        elif low.endswith("appxmanifest.xml"):
            parsed[arcname] = parse_appxmanifest(blob)
    # Merge identifiers across manifests
    game = "unknown"
    version = ""
    platform = "Windows Phone (candidate)"
    arch = ""
    package_id = ""
    product_id = ""
    content_id = ""
    publisher = ""
    for rec in parsed.values():
        title = rec.get("title", "")
        if any(t in title.lower() for t in COMZ_TITLE_TOKENS):
            game = PRIMARY_TARGET_GAME
        if rec.get("version"):
            version = version or rec["version"]
        if rec.get("package_id"):
            package_id = package_id or rec["package_id"]
        if rec.get("product_id") or rec.get("phone_product_id"):
            product_id = product_id or rec.get("product_id") or rec.get("phone_product_id", "")
        if rec.get("publisher") and not publisher:
            publisher = rec["publisher"]
        if rec.get("processor_architecture"):
            arch = arch or rec["processor_architecture"]
        if rec.get("manifest_type") == "AppxManifest.xml":
            platform = "Windows Phone 8.1 / Windows (APPX)"
        elif rec.get("manifest_type") == "WMAppManifest.xml":
            platform = "Windows Phone 7/8 (XAP Silverlight)"
    # Fallback: filename/byte signals
    if game == "unknown" and ident.get("is_likely_comz"):
        game = PRIMARY_TARGET_GAME
    files = list_contained_files(package_path)
    is_primary_target = (game == PRIMARY_TARGET_GAME
                         and (version == PRIMARY_TARGET_VERSION or version == ""))
    return {
        "game": game,
        "package_id": package_id,
        "content_id": content_id,
        "product_id": product_id,
        "publisher": publisher,
        "version": version,
        "is_primary_target_v1_1_0_0": is_primary_target,
        "primary_target": f"{PRIMARY_TARGET_GAME} {PRIMARY_TARGET_VERSION} ({PRIMARY_TARGET_PLATFORM})",
        "platform": platform,
        "architecture": arch,
        "manifests": parsed,
        "manifest_files": sorted(manifests.keys()),
        "contained_files": files,
        "contained_count": len(files),
        "identification": {
            "filename": ident.get("filename"),
            "extension": ident.get("extension"),
            "detected_format": ident.get("detected_format"),
            "sha1": ident.get("sha1"),
            "sha256": ident.get("sha256"),
            "md5": ident.get("md5"),
            "size": ident.get("size"),
            "is_likely_comz": ident.get("is_likely_comz"),
        },
        "relationships": {
            "notes": "bundle members / dependencies listed under manifests[].dependencies "
                     "when present; framework packages recorded per-manifest",
            "dependencies": [d for r in parsed.values() for d in r.get("dependencies", [])],
        },
        "reference_model": "DBOX Tools (https://dbox.tools/) field shape: "
                           "identifiers / relationships / versions / "
                           "architectures / platforms / contained files",
    }


def match_primary_target(record: dict) -> bool:
    """True when the record matches the pinned preservation target."""
    if record.get("game") != PRIMARY_TARGET_GAME:
        return False
    v = record.get("version", "")
    return v in ("", PRIMARY_TARGET_VERSION)
