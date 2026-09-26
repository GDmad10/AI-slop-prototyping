"""Outer-wrapper detection. Distinguishes container from protection.

Labels kept strictly separate:
 - container/compression (zip, cab, gzip …)
 - code signing / manifest presence
 - opaque/possibly-protected region (presence only)
Never labels an opaque region as a specific cipher and never
attempts to remove protection.
"""
from __future__ import annotations

WRAPPERS = [
    (b"PK\x03\x04", "zip-based container (xap/appx/msix/zip candidate — verify by central directory, not extension)"),
    (b"PK\x05\x06", "zip end-of-central-directory (truncated/empty archive tail)"),
    (b"PK\x07\x08", "zip data descriptor"),
    (b"MSCF", "mscf (cab candidate)"),
    (b"MZ", "pe image fragment (exe/dll — unpacked binary, not a wrapper)"),
    (b"UnityFS", "unity asset bundle (game data, not platform protection)"),
    (b"\x1f\x8b", "gzip stream (compression, not encryption)"),
]


def detect_wrapper(path: str) -> dict:
    with open(path, "rb") as f:
        head = f.read(8)
        f.seek(0, 2)
        size = f.tell()
        tail = b""
        if size >= 22:
            f.seek(-22, 2)
            tail = f.read(22)
    layers = []
    for magic, label in WRAPPERS:
        if head.startswith(magic):
            layers.append({"layer": "container/compression", "detail": label})
    # Authenticode / signature presence is only reported via zip inventory
    # (done in analyze.py); here we just note opacity.
    layers.append({
        "layer": "protection-status",
        "detail": "opaque-region-presence is reported via entropy + zip readability; "
                  "no algorithm attribution is made without vendor documentation",
    })
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
    ext_hint = {
        "xap": "xap = zip-based Windows Phone package (verify magic, do not trust extension)",
        "appx": "appx = zip-based package (verify magic)",
        "appxbundle": "appxbundle = bundle (verify magic)",
        "eappx": "eappx = encrypted package variant — tool does NOT remove protection",
        "eappxbundle": "eappxbundle — tool does NOT remove protection",
        "cab": "cab = mscf cabinet",
        "zip": "zip container",
        "msix": "msix = zip-based (verify magic)",
        "msixbundle": "msixbundle (verify magic)",
        "file": "generic '.file' — proprietary/opaque until magic + analysis says otherwise",
    }.get(ext, f".{ext} — extension is not authoritative")
    return {"size": size, "head_hex": head.hex(),
            "tail_hex": tail.hex() if tail else "",
            "extension_hint": ext_hint, "layers": layers}
