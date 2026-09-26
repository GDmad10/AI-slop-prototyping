"""Unity recovery scanner — operates on already-plaintext directories only.

Given a directory of lawfully obtained unpacked game data
(e.g. from a device backup you own and extracted with vendor tools),
lists Unity structures. It never decrypts anything itself.
"""
from __future__ import annotations

import os

UNITY_FILENAMES = [
    "globalgamemanagers",
    "globalgamemanagers.assets",
    "resources.assets",
    "level0",
    "sharedassets0.assets",
    "sharedassets",
    "mainData",
]

UNITY_SUFFIXES = (".assets", ".resource", ".ress", ".resS", ".unity3d", ".bundle")
UNITY_DIRS = ("Managed", "Resources", "StreamingAssets", "Mono", "il2cpp")
UNITY_DLLS = ("assembly-csharp.dll", "unityengine.dll", "mono.dll")


def scan_unity(root: str) -> dict:
    if not os.path.isdir(root):
        raise NotADirectoryError(root)
    found_files: list[str] = []
    found_dirs: list[str] = []
    dlls: list[str] = []
    tree_top: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > 4:
            dirnames[:] = []
            continue
        for d in dirnames:
            if d in UNITY_DIRS:
                found_dirs.append(os.path.join(rel, d))
        for fn in filenames:
            low = fn.lower()
            full_rel = os.path.join(rel, fn) if rel != "." else fn
            if low in UNITY_FILENAMES or low.endswith(UNITY_SUFFIXES):
                found_files.append(full_rel)
            if low in UNITY_DLLS:
                dlls.append(full_rel)
        if rel == ".":
            tree_top = sorted(dirnames + filenames)[:80]
    return {
        "root": os.path.abspath(root),
        "tree_top": tree_top,
        "unity_files": sorted(found_files)[:500],
        "unity_dirs": sorted(set(found_dirs)),
        "unity_dlls": sorted(set(dlls)),
        "unity_file_count": len(found_files),
        "verdict": "UNITY STRUCTURES PRESENT" if (found_files or dlls) else "NO UNITY STRUCTURES FOUND",
    }
