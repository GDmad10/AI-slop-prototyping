"""DBOX-style local catalog (sqlite). Stores observations, not keys.

Fields mirror the request (Game, Package ID, Content ID, versions,
hashes, sizes, notes) but Key Status / Decryption Status are
observational only — e.g. 'unknown', 'opaque — not attempted',
'plaintext zip readable'. The tool never fills them by breaking
protection and never stores key bytes.
"""
from __future__ import annotations

import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  game TEXT,
  package_id TEXT,
  content_id TEXT,
  key_id TEXT,
  product_id TEXT,
  version TEXT,
  platform TEXT,
  architecture TEXT,
  filename TEXT,
  extension TEXT,
  detected_format TEXT,
  encrypted TEXT,
  encryption_type TEXT,
  key_status TEXT,
  decryption_status TEXT,
  sha1 TEXT,
  sha256 TEXT,
  md5 TEXT,
  file_size INTEGER,
  source_notes TEXT,
  research_notes TEXT,
  created_at REAL
);
CREATE TABLE IF NOT EXISTS dbox_refs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dbox_product_id TEXT,
  dbox_url TEXT,
  title TEXT,
  publisher TEXT,
  relationship TEXT,
  reason TEXT,
  created_at REAL
);
CREATE TABLE IF NOT EXISTS xrefs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  store_product TEXT,
  dbox_product TEXT,
  package_id TEXT,
  content_id TEXT,
  key_id TEXT,
  historical_package TEXT,
  archive_item TEXT,
  runtime_files TEXT,
  note TEXT,
  created_at REAL
);
"""

COLUMNS = ["game", "package_id", "content_id", "key_id", "product_id",
           "version", "platform", "architecture", "filename", "extension",
           "detected_format", "encrypted", "encryption_type", "key_status",
           "decryption_status", "sha1", "sha256", "md5", "file_size",
           "source_notes", "research_notes"]


class Catalog:
    def __init__(self, db_path: str = "comz_catalog.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        with sqlite3.connect(db_path) as c:
            c.executescript(SCHEMA)

    def add(self, record: dict) -> int:
        row = {k: record.get(k, "") for k in COLUMNS}
        # enforce lawful defaults: never claim a break
        if not row["decryption_status"]:
            row["decryption_status"] = "not attempted (analysis only)"
        if not row["key_status"]:
            row["key_status"] = "not collected"
        if not row["encrypted"]:
            row["encrypted"] = "unknown (see zip readability + entropy)"
        with sqlite3.connect(self.db_path) as c:
            cur = c.execute(
                f"INSERT INTO samples ({','.join(COLUMNS)},created_at) "
                f"VALUES ({','.join('?' for _ in COLUMNS)},?)",
                [row[k] for k in COLUMNS] + [time.time()],
            )
            return cur.lastrowid

    def list_all(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute("SELECT * FROM samples ORDER BY id DESC LIMIT 500")]

    def record_dbox(self, dbox_product_id: str, dbox_url: str, title: str,
                    publisher: str, relationship: str, reason: str) -> int:
        with sqlite3.connect(self.db_path) as c:
            cur = c.execute(
                "INSERT INTO dbox_refs (dbox_product_id,dbox_url,title,"
                "publisher,relationship,reason,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                [dbox_product_id, dbox_url, title, publisher,
                 relationship, reason, time.time()])
            return cur.lastrowid

    def record_xref(self, store_product: str = "", dbox_product: str = "",
                    package_id: str = "", content_id: str = "",
                    key_id: str = "", historical_package: str = "",
                    archive_item: str = "", runtime_files: str = "",
                    note: str = "") -> int:
        with sqlite3.connect(self.db_path) as c:
            cur = c.execute(
                "INSERT INTO xrefs (store_product,dbox_product,package_id,"
                "content_id,key_id,historical_package,archive_item,"
                "runtime_files,note,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                [store_product, dbox_product, package_id, content_id,
                 key_id, historical_package, archive_item, runtime_files,
                 note, time.time()])
            return cur.lastrowid

    def list_xrefs(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in
                    c.execute("SELECT * FROM xrefs ORDER BY id DESC LIMIT 500")]

    def list_dbox_refs(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in
                    c.execute("SELECT * FROM dbox_refs ORDER BY id DESC LIMIT 500")]

    def auto_record(self, ident: dict, extra: dict | None = None) -> int:
        extra = extra or {}
        return self.add({
            "game": "Call of Mini: Zombies" if ident.get("is_likely_comz") else "unknown",
            "filename": ident.get("filename", ""),
            "extension": ident.get("extension", ""),
            "detected_format": ident.get("detected_format", ""),
            "encrypted": "likely-opaque" if not ident.get("zip_name_hits") and
                         ident.get("detected_format", "").startswith("unknown") else "unknown",
            "encryption_type": "not attributed",
            "key_status": "not collected",
            "decryption_status": "not attempted (analysis only)",
            "sha1": ident.get("sha1", ""),
            "sha256": ident.get("sha256", ""),
            "md5": ident.get("md5", ""),
            "file_size": ident.get("size", 0),
            "source_notes": extra.get("source_notes", ""),
            "research_notes": extra.get("research_notes", ""),
            "package_id": extra.get("package_id", ""),
            "content_id": extra.get("content_id", ""),
            "key_id": extra.get("key_id", ""),
            "product_id": extra.get("product_id", ""),
            "version": extra.get("version", ""),
            "platform": extra.get("platform", "Windows Phone (candidate)"),
            "architecture": extra.get("architecture", ""),
        })
