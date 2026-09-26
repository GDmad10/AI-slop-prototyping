"""Tkinter GUI — CoM Zombies Preservation Decryptor (Windows-native)."""
from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from comz_core.identify import identify_file, gate_message
from comz_core.analyze import analyze_file
from comz_core.wrappers import detect_wrapper
from comz_core.unity import scan_unity
from comz_core.compare import compare_files
from comz_core.package_meta import build_package_record
from comz_core.retrieve import ingest_local, retrieve_url
from comz_core import crypto as _crypto
from comz_core import decryptor as _dec

PRIMARY_ACTION = "DECRYPT + EXTRACT CALL OF MINI: ZOMBIES v1.1.0.0"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CoM Zombies Preservation Decryptor — v1.1.0.0 Windows Phone")
        self.geometry("1060x720")
        self.sample = tk.StringVar()
        self.key_hex = tk.StringVar()
        self.iv_hex = tk.StringVar(value="")
        self.mode = tk.StringVar(value="aes-cbc-file")
        self.password = tk.StringVar()
        self.log_q: queue.Queue[str] = queue.Queue()
        self._build()
        self.after(150, self._drain)

    def _build(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Open package", command=self.pick).pack(side="left")
        ttk.Entry(top, textvariable=self.sample, width=52).pack(side="left", padx=8)
        ttk.Button(top, text=PRIMARY_ACTION, command=self.decrypt_threaded).pack(side="left")

        keybar = ttk.Frame(self, padding=(8, 0))
        keybar.pack(fill="x")
        ttk.Label(keybar, text="Mode:").pack(side="left")
        ttk.Combobox(keybar, textvariable=self.mode, width=20, values=[
            "aes-cbc-file", "aes-ecb-file", "xor-file", "zip-password",
            "playready-aesctr-file"],
            state="readonly").pack(side="left", padx=4)
        ttk.Label(keybar, text="Key-hex:").pack(side="left", padx=(8, 2))
        ttk.Entry(keybar, textvariable=self.key_hex, width=34).pack(side="left")
        ttk.Label(keybar, text="IV-hex:").pack(side="left", padx=(8, 2))
        ttk.Entry(keybar, textvariable=self.iv_hex, width=24).pack(side="left")
        ttk.Label(keybar, text="Zip-pwd:").pack(side="left", padx=(8, 2))
        ttk.Entry(keybar, textvariable=self.password, width=14, show="*").pack(side="left")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.tabs = {}
        for name in ["Identify", "Analyze", "Package Metadata", "Decrypt + Extract",
                     "Hex Viewer", "Compare Builds", "Unity Recovery", "Logs"]:
            f = ttk.Frame(nb, padding=8)
            nb.add(f, text=name)
            t = tk.Text(f, wrap="word")
            t.pack(fill="both", expand=True)
            self.tabs[name] = t

        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        for label, fn in [("Identify", self.do_identify), ("Analyze", self.analyze_threaded),
                          ("Metadata", self.do_metadata), ("Decrypt", self.decrypt_threaded),
                          ("Extract", self.do_extract),
                          ("Compare Builds", self.do_compare), ("Unity Recovery", self.do_unity)]:
            ttk.Button(bar, text=label, command=fn).pack(side="left", padx=4)

    def log(self, tab: str, text: str):
        self.log_q.put((tab, text))

    def _drain(self):
        try:
            while True:
                tab, text = self.log_q.get_nowait()
                w = self.tabs.get(tab, self.tabs["Logs"])
                w.insert("end", text + "\n")
                w.see("end")
                self.tabs["Logs"].insert("end", f"[{tab}] {text[:200]}\n")
        except queue.Empty:
            pass
        self.after(150, self._drain)

    def pick(self):
        p = filedialog.askopenfilename(filetypes=[("All", "*.*"), ("Archive .file", "*.file")])
        if p:
            self.sample.set(p)

    def need(self):
        p = self.sample.get().strip().strip('"')
        if not p or not os.path.isfile(p):
            messagebox.showwarning("No file", "Open a .file sample first.")
            return ""
        return p

    def do_identify(self):
        p = self.need()
        if not p:
            return
        ident = identify_file(p)
        self.tabs["Identify"].delete("1.0", "end")
        self.tabs["Identify"].insert("end", gate_message(ident) + "\n\n" + json.dumps(ident, indent=2))
        self.log("Logs", f"identify done likely={ident.get('is_likely_comz')}")

    def analyze_threaded(self):
        p = self.need()
        if not p:
            return
        threading.Thread(target=self._analyze, args=(p,), daemon=True).start()

    def _analyze(self, p):
        self.log("Analyze", f"analyzing {os.path.basename(p)} …")
        try:
            rep = analyze_file(p)
            wrap = detect_wrapper(p)
            self.log("Analyze", gate_message(rep["identification"]))
            self.log("Analyze", rep["structural_map"]["tree"])
            self.log("Analyze", json.dumps(wrap, indent=2)[:4000])
            self.log("Package Metadata", json.dumps(rep["identification"], indent=2))
            try:
                rec = build_package_record(p)
                self.log("Package Metadata", json.dumps(
                    {k: rec[k] for k in ("game", "version",
                     "is_primary_target_v1_1_0_0", "package_id",
                     "product_id", "platform", "architecture",
                     "manifest_files", "contained_count")}, indent=2))
            except Exception as e:  # noqa: BLE001
                self.log("Package Metadata", f"metadata: {e}")
            with open(p, "rb") as f:
                head = f.read(4096)
            hexs = " ".join(f"{b:02x}" for b in head[:512])
            self.log("Hex Viewer", f"offset 0x0000 size 512:\n{hexs}")
            self.log("Analyze", "done.")
        except Exception as e:  # noqa: BLE001
            self.log("Logs", f"analyze failed: {type(e).__name__}: {e}")

    def do_metadata(self):
        p = self.need()
        if not p:
            return
        try:
            rec = build_package_record(p)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Metadata failed", f"{type(e).__name__}: {e}")
            return
        self.tabs["Package Metadata"].delete("1.0", "end")
        self.tabs["Package Metadata"].insert("end", json.dumps(rec, indent=2)[:12000])

    def _key_bytes(self):
        kh = self.key_hex.get().strip()
        if kh:
            return _crypto.parse_key_hex(kh)
        pw = self.password.get()
        if self.mode.get() == "zip-password":
            if not pw:
                raise ValueError("enter the Zip password first")
            return pw.encode("utf-8")
        if pw:
            return _crypto.derive_key_sha256(pw.encode("utf-8"))
        raise ValueError("enter Key-hex (or Zip password for zip-password mode)")

    def decrypt_threaded(self):
        p = self.need()
        if not p:
            return
        threading.Thread(target=self._decrypt, args=(p,), daemon=True).start()

    def _decrypt(self, p):
        try:
            key = self._key_bytes()
        except ValueError as e:
            self.log("Decrypt + Extract", f"key error: {e}")
            return
        mode = self.mode.get()
        out = p + ".decrypted"
        self.log("Decrypt + Extract", f"{mode} on {os.path.basename(p)} …")
        try:
            if mode == "zip-password":
                outdir = p + ".decrypted.d"
                os.makedirs(outdir, exist_ok=True)
                res = _dec.decrypt_zip_password(p, os.path.join(outdir, "x"), key)
            else:
                iv = bytes.fromhex(self.iv_hex.get().strip()) if (
                    mode in ("aes-cbc-file", "playready-aesctr-file")
                    and self.iv_hex.get().strip()) else None
                res = _dec.decrypt_file_blob(p, out, key, mode, iv)
        except _dec.NotComZombies as e:
            self.log("Decrypt + Extract", str(e))
            return
        except Exception as e:  # noqa: BLE001
            self.log("Decrypt + Extract", f"DECRYPTION FAILED: {type(e).__name__}: {e}")
            return
        self.log("Decrypt + Extract", json.dumps(res, indent=2)[:6000])
        self.log("Decrypt + Extract",
                 "DECRYPTION SUCCEEDED / PLAINTEXT VERIFIED" if res.get("ok")
                 else "DECRYPTION FAILED / PLAINTEXT VALIDATION FAILED")

    def do_extract(self):
        p = self.need()
        if not p:
            return
        out = filedialog.askdirectory(title="Extract decrypted package to…")
        if not out:
            return
        try:
            res = _dec.extract_package(p, out)
        except _dec.NotComZombies as e:
            messagebox.showerror("Gated", str(e))
            return
        self.tabs["Decrypt + Extract"].delete("1.0", "end")
        self.tabs["Decrypt + Extract"].insert("end", json.dumps(res, indent=2))
        if not res.get("ok"):
            messagebox.showerror("Extract failed", res.get("error", "opaque input"))

    def do_compare(self):
        a = filedialog.askopenfilename(title="Build A")
        b = filedialog.askopenfilename(title="Build B")
        if not (a and b):
            return
        d = compare_files(a, b)
        self.tabs["Compare Builds"].delete("1.0", "end")
        self.tabs["Compare Builds"].insert("end", json.dumps(d, indent=2))

    def do_unity(self):
        d = filedialog.askdirectory(title="Unpacked game directory")
        if not d:
            return
        r = scan_unity(d)
        self.tabs["Unity Recovery"].delete("1.0", "end")
        self.tabs["Unity Recovery"].insert("end", json.dumps(r, indent=2))


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
