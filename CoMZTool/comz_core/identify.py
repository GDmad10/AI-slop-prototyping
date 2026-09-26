"""Heuristic identification for Call of Mini: Zombies samples.

Lawful scope: reads metadata / plaintext signals only.
Does NOT attempt to bypass platform encryption or extract keys.
A positive match only means "worth cataloging as a candidate",
not proof of origin. A negative match disables game-specific
assumptions.
"""
from __future__ import annotations

import hashlib
import os
import re
import zipfile

# Publicly known, non-secret signals associated with the title.
# These are filenames / strings observable in lawfully installed copies.
COMZ_SIGNALS = [
    b"call of mini",
    b"callofmini",
    b"comz",
    b"mini zombies",
    b"minizombies",
    b"triniti",
    b"triniti interactive",
]

KNOWN_FILENAMES = [
    "wmappmanifest.xml",
    "wmappmanifest",
    "globalgamemanagers",
    "globalgamemanagers.assets",
    "resources.assets",
    "sharedassets",
    "assembly-csharp.dll",
    "unityengine.dll",
    "mono",
    "unity",
    "data.unity3d",
]

KNOWN_WP_IDENTIFIERS = [
    "windows phone",
    "windowsphone",
    "xap",
    "appx",
    "msix",
]

MAX_SCAN_BYTES = 8 * 1024 * 1024  # cap for string scan on large samples


def _hashes(path: str) -> dict:
    h_md5 = hashlib.md5()
    h_sha1 = hashlib.sha1()
    h_sha256 = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            h_md5.update(chunk)
            h_sha1.update(chunk)
            h_sha256.update(chunk)
    return {
        "md5": h_md5.hexdigest(),
        "sha1": h_sha1.hexdigest(),
        "sha256": h_sha256.hexdigest(),
        "size": size,
    }


def _magic(path: str) -> tuple[bytes, str]:
    with open(path, "rb") as f:
        head = f.read(16)
    if head.startswith(b"PK\x03\x04"):
        kind = "zip-based (possible xap/appx/zip/msix)"
    elif head.startswith(b"MSCF"):
        kind = "mscf (possible cab)"
    elif head.startswith(b"MZ"):
        kind = "mz (pe/dll/exe fragment or unpacked binary)"
    elif head.startswith(b"UnityFS"):
        kind = "unityfs (unpacked unity asset bundle)"
    elif head.startswith(b"\x1f\x8b"):
        kind = "gzip"
    elif head.startswith(b"BZh"):
        kind = "bzip2"
    elif head.startswith(b"\xfd7zXZ\x00"):
        kind = "xz"
    elif len(head) == 0:
        kind = "empty"
    else:
        kind = "unknown/opaque"
    return head, kind


def _scan_signals(path: str) -> dict:
    with open(path, "rb") as f:
        data = f.read(MAX_SCAN_BYTES)
    lowered = data.lower()
    hits = [s.decode("ascii", "replace") for s in COMZ_SIGNALS if s in lowered]
    # printable strings sample (for report, not for key recovery)
    strings = re.findall(rb"[\x20-\x7e]{5,}", data)
    decoded = [s.decode("ascii", "replace") for s in strings[:200]]
    # filename hits inside zip central directory (plaintext only, no decryption)
    zip_names: list[str] = []
    zip_comment = ""
    try:
        if data.startswith(b"PK\x03\x04"):
            with zipfile.ZipFile(path, "r") as z:
                zip_names = z.namelist()[:200]
                try:
                    zip_comment = str(z.comment[:256])
                except Exception:
                    zip_comment = ""
    except Exception:
        zip_names = []
    name_hits = [
        n for n in zip_names
        if any(k in n.lower() for k in KNOWN_FILENAMES)
    ]
    return {
        "signal_hits": hits,
        "strings_sample": decoded[:60],
        "zip_names_sample": zip_names[:60],
        "zip_name_hits": name_hits,
        "zip_comment": zip_comment,
        "scanned_bytes": len(data),
    }


def identify_file(path: str) -> dict:
    """Return identification dict. Never attempts decryption."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    info = _hashes(path)
    head, kind = _magic(path)
    sig = _scan_signals(path)
    result = {
        "filename": os.path.basename(path),
        "extension": os.path.splitext(path)[1].lower(),
        "detected_format": kind,
        "magic_hex": head[:8].hex(),
        **info,
        **sig,
    }
    result["is_likely_comz"] = is_likely_comz(result)
    return result


def is_likely_comz(ident: dict) -> bool:
    """Conservative heuristic gate.

    Requires at least one title-specific signal (bytes or inner filename).
    Generic 'zombie' or 'unity' alone is NOT enough.
    """
    if ident.get("signal_hits"):
        return True
    if ident.get("zip_name_hits"):
        # inner filename match must co-occur with title-ish outer name
        # or a Triniti string; otherwise treat as generic Unity app.
        outer = (ident.get("filename") or "").lower()
        if any(k in outer for k in ("mini", "comz", "triniti", "zombie")):
            return True
        return False
    outer = (ident.get("filename") or "").lower()
    # filename alone is weak — require two independent tokens
    tokens = ("mini" in outer) + ("zomb" in outer) + ("comz" in outer) + ("triniti" in outer)
    return tokens >= 2


def gate_message(ident: dict) -> str:
    if ident.get("is_likely_comz"):
        return "CALL OF MINI: ZOMBIES candidate — analysis enabled (no decryption performed)."
    return "NOT CALL OF MINI: ZOMBIES\nGame-specific decryptor disabled."
