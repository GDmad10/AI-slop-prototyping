"""Package retrieval for preservation workflows (Windows-native, stdlib).

Sources:
  1. Local ingest  — file the operator already possesses; hashed,
     identified, copied into the preservation staging directory.
  2. URL retrieval — direct-link download of a historical package /
     archive the operator names (device-backup host, personal archive,
     vendor CDN link they hold). Streams to disk with progress +
     SHA-256 verification against an expected hash when supplied.

No store scraping, no authentication bypass, no search API.
The operator names the exact artifact; this module fetches bytes.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import time
import urllib.request

CHUNK = 1024 * 256


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            c = f.read(1024 * 1024)
            if not c:
                break
            h.update(c)
    return h.hexdigest()


def ingest_local(src: str, staging_dir: str) -> dict:
    """Copy a possessed file into staging; return recovery record."""
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    os.makedirs(staging_dir, exist_ok=True)
    from .identify import identify_file
    ident = identify_file(src)
    dst = os.path.join(staging_dir, ident["filename"])
    # avoid clobber: suffix when name exists with different hash
    if os.path.isfile(dst) and sha256_file(dst) != ident["sha256"]:
        base, ext = os.path.splitext(ident["filename"])
        dst = os.path.join(staging_dir, f"{base}_{ident['sha256'][:8]}{ext}")
    if not os.path.isfile(dst) or sha256_file(dst) != ident["sha256"]:
        shutil.copy2(src, dst)
    return {
        "mode": "local-ingest",
        "source": os.path.abspath(src),
        "staged": os.path.abspath(dst),
        "sha256": ident["sha256"],
        "size": ident["size"],
        "is_likely_comz": ident.get("is_likely_comz"),
    }


def retrieve_url(url: str, staging_dir: str, filename: str = "",
                 expected_sha256: str = "", timeout: int = 60,
                 progress_cb=None) -> dict:
    """Download a package URL to staging. Real bytes, verified hash."""
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("URL must be http(s)")
    os.makedirs(staging_dir, exist_ok=True)
    if not filename:
        filename = url.rstrip("/").rsplit("/", 1)[-1] or "package.file"
        filename = filename.split("?")[0][:128] or "package.file"
    dst = os.path.join(staging_dir, filename)
    req = urllib.request.Request(url, headers={"User-Agent": "CoMZ-Preservation-Decryptor/1.0"})
    h = hashlib.sha256()
    total = 0
    started = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dst, "wb") as f:
        while True:
            chunk = r.read(CHUNK)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            total += len(chunk)
            if progress_cb:
                progress_cb(total)
    digest = h.hexdigest()
    ok = True
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        ok = False
    return {
        "mode": "url-retrieval",
        "source": url,
        "staged": os.path.abspath(dst),
        "sha256": digest,
        "sha256_match": ok if expected_sha256 else None,
        "size": total,
        "elapsed_s": round(time.time() - started, 2),
    }
