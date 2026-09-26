"""Structural analysis — header/entropy/strings/offsets. No decryption."""
from __future__ import annotations

import math
import os
import re
import struct
import zipfile
from collections import Counter

GUID_RE = re.compile(
    rb"\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    rb"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}"
    rb"|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    rb"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def chunk_entropies(path: str, chunk: int = 256 * 1024, max_chunks: int = 16) -> list[dict]:
    out = []
    with open(path, "rb") as f:
        offset = 0
        for _ in range(max_chunks):
            data = f.read(chunk)
            if not data:
                break
            out.append({
                "offset": offset,
                "size": len(data),
                "entropy": round(shannon_entropy(data), 3),
                "zero_ratio": round(data.count(0) / len(data), 4),
            })
            offset += len(data)
    return out


def structural_map(path: str) -> dict:
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(4096)
    sections = [
        {"name": "Header", "offset": 0, "size": min(512, size),
         "note": "magic + version-ish fields (observed, not decoded as keys)"},
        {"name": "Metadata", "offset": 512 if size > 512 else size, "size": min(3584, max(0, size - 512)),
         "note": "printable strings / GUIDs / manifest hints if plaintext"},
    ]
    if size > 4096:
        sections.append({"name": "Body", "offset": 4096, "size": size - 4096,
                         "note": "opaque payload; entropy profile distinguishes "
                                 "compressed/encrypted vs structured data, "
                                 "not the algorithm"})
    text = (
        "FILE\n"
        "+-- Header\n"
        "+-- Metadata\n"
        "+-- File Table (only if plaintext container; otherwise 'not visible')\n"
        "+-- Encryption Metadata (presence/absence only — not decoded)\n"
        "+-- Compressed/Encrypted Data (opaque)\n"
        "+-- Integrity Data (hashes recorded externally)\n"
    )
    return {"file_size": size, "sections": sections, "tree": text,
            "head_hex": head[:256].hex()}


def extract_observables(path: str, max_bytes: int = 4 * 1024 * 1024) -> dict:
    with open(path, "rb") as f:
        data = f.read(max_bytes)
    guids = sorted({m.group(0).decode("ascii", "replace") for m in GUID_RE.finditer(data)})[:20]
    strings = re.findall(rb"[\x20-\x7e]{6,}", data)
    texts = [s.decode("ascii", "replace") for s in strings[:300]]
    interesting = [t for t in texts
                   if any(k in t.lower() for k in
                           ("manifest", "package", "version", "triniti",
                            "unity", "assembly", "assets", "windows phone",
                            "content", "product", "publisher", "xap", "appx"))][:60]
    # 32-bit LE fields at fixed offsets — displayed as raw integers,
    # NOT interpreted as crypto parameters.
    le32 = []
    for off in (0, 4, 8, 12, 16, 24, 32, 64, 128):
        if off + 4 <= len(data):
            (v,) = struct.unpack_from("<I", data, off)
            le32.append({"offset": off, "u32le": v, "hex": f"{v:08x}"})
    return {"guids": guids, "interesting_strings": interesting,
            "strings_count": len(strings), "le32_header_view": le32}


def zip_inventory(path: str) -> dict:
    """List central-directory entries only if the file is a plaintext zip.
    Encrypted / opaque files return {'readable': False} — no brute force."""
    try:
        with zipfile.ZipFile(path, "r") as z:
            infos = []
            for i in z.infolist()[:500]:
                infos.append({
                    "name": i.filename,
                    "compress_size": i.compress_size,
                    "file_size": i.file_size,
                    "compress_type": i.compress_type,
                    "flag_bits": i.flag_bits,
                    "is_encrypted_flag": bool(i.flag_bits & 0x1),
                })
            return {"readable": True, "count": len(z.infolist()), "entries": infos}
    except Exception as e:
        return {"readable": False, "error": f"{type(e).__name__}: {e}"}


def analyze_file(path: str) -> dict:
    from .identify import identify_file
    ident = identify_file(path)
    sm = structural_map(path)
    return {
        "identification": ident,
        "structural_map": sm,
        "chunk_entropies": chunk_entropies(path),
        "observables": extract_observables(path),
        "zip_inventory": zip_inventory(path),
        "full_entropy_head": round(shannon_entropy(open(path, "rb").read(1024 * 1024)), 3),
    }
