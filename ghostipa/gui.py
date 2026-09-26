"""Ghost IPA Installer — GUI (§24). Tabs: search/details/history/sources/IPA/device/install/preservation."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ghostipa.core.confidence import Confidence
from ghostipa.core.database import ResearchDB
from ghostipa.core.research_log import ResearchLog
from ghostipa.modules.detector import detect
from ghostipa.modules.device import detect_device, render_device
from ghostipa.modules.ipa_analysis import analyze_ipa
from ghostipa.modules.preservation import build_preservation_package, final_report

TABS = ("Search", "App Details", "History", "Sources", "IPA Analyzer", "Device", "Install", "Preservation")

STATUS_COLORS = {
    "PUBLIC": "#2e7d32", "DELISTED": "#e65100", "HISTORICAL": "#1565c0",
    "PACKAGE FOUND": "#2e7d32", "PACKAGE NOT FOUND": "#b71c1c",
    "INSTALLABLE": "#2e7d32", "INCOMPATIBLE": "#b71c1c",
}


class GhostGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Ghost IPA Installer")
        root.geometry("860x620")
        self.db = ResearchDB()
        self.log = ResearchLog()
        self.record = None
        self.report = None

        top = ttk.Frame(root, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Application name / Apple ID / Bundle ID").pack(side="left")
        self.q = tk.StringVar()
        ttk.Entry(top, textvariable=self.q, width=46).pack(side="left", padx=6)
        ttk.Button(top, text="SEARCH", command=self.on_search).pack(side="left")

        self.statusbar = ttk.Frame(root, padding=(8, 0))
        self.statusbar.pack(fill="x")
        self.status_labels: dict[str, ttk.Label] = {}
        for key in ("PUBLIC", "DELISTED", "HISTORICAL", "PACKAGE FOUND",
                    "PACKAGE NOT FOUND", "INSTALLABLE", "INCOMPATIBLE"):
            lab = ttk.Label(self.statusbar, text=f" {key} ",
                            background="#333", foreground="#fff", padding=2)
            lab.pack(side="left", padx=2)
            self.status_labels[key] = lab

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.panes: dict[str, tk.Text] = {}
        for name in TABS:
            frame = ttk.Frame(self.nb)
            self.nb.add(frame, text=name.upper())
            txt = tk.Text(frame, wrap="word", height=24)
            txt.pack(fill="both", expand=True)
            self.panes[name] = txt

        brow = ttk.Frame(root, padding=8)
        brow.pack(fill="x")
        ttk.Button(brow, text="Inspect IPA…", command=self.on_inspect).pack(side="left")
        ttk.Button(brow, text="Probe Device", command=self.on_device).pack(side="left", padx=6)
        ttk.Button(brow, text="Build Preservation Package", command=self.on_preserve).pack(side="left")

    def _set(self, tab: str, text: str) -> None:
        w = self.panes[tab]
        w.delete("1.0", "end")
        w.insert("1.0", text)

    def _light(self, key: str, on: bool) -> None:
        lab = self.status_labels[key]
        lab.configure(background=STATUS_COLORS[key] if on else "#333")

    def on_search(self) -> None:
        q = self.q.get().strip()
        if not q:
            messagebox.showinfo("Ghost IPA", "Enter a name, Apple ID, or bundle ID.")
            return
        apple = q if q.isdigit() else ""
        bundle = q if ("." in q and " " not in q and not apple) else ""
        name = "" if (apple or bundle) else q
        try:
            report, _sm, record = detect(name=name, apple_id=apple, bundle_id=bundle,
                                         db=self.db, log=self.log)
        except Exception as exc:  # keep GUI alive; technical error goes to log (§26)
            self.log.log("SEARCH", "Apple metadata", q, error=str(exc))
            messagebox.showerror("Ghost IPA", f"Search failed: {exc}")
            return
        self.record, self.report = record, report
        self._set("Search", report.render())
        self._set("App Details", f"{record.name}\nDeveloper: {record.developer}\n"
                  f"Bundle: {record.bundle_id}\nApple ID: {record.apple_id}\n"
                  f"Status: {record.status}\nSource: {record.source}")
        self._set("History", f"{len(record.historical_versions)} version(s) in local DB.\n"
                  + "\n".join(f"- {v.version_string} ({v.build_number}) [{v.source}]"
                               for v in record.historical_versions))
        self._set("Sources", f"Primary: {record.source}\nChecked: {record.checked_at}")
        self._light("PUBLIC", report.public_listing == "YES")
        self._light("DELISTED", report.public_listing == "NO" and report.metadata == "FOUND")
        self._light("HISTORICAL", report.historical_versions == "FOUND")
        self._light("PACKAGE FOUND", report.package == "FOUND")
        self._light("PACKAGE NOT FOUND", report.package in ("NOT FOUND", "UNKNOWN"))
        self._light("INSTALLABLE", report.installation == "POSSIBLE")
        self._light("INCOMPATIBLE", report.installation == "IMPOSSIBLE")
        self.nb.select(1)

    def on_inspect(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("IPA files", "*.ipa"), ("All files", "*.*")])
        if not path:
            return
        rep = analyze_ipa(path)
        text = rep.render() if not rep.error else f"ERROR: {rep.error}"
        if rep.encryption == "FAIRPLAY_ENCRYPTED":
            text += ("\nPackage obtained, but executable is encrypted and cannot be "
                     "analyzed/installed through this workflow.")
        self._set("IPA Analyzer", text)

    def on_device(self) -> None:
        dev = detect_device()
        min_ios = ipa_arch = ""
        if self.record:
            for v in self.record.historical_versions:
                min_ios = min_ios or v.minimum_ios
                ipa_arch = ipa_arch or v.architecture
        self._set("Device", render_device(dev, min_ios, ipa_arch))
        self._set("Install",
                  "Legitimate workflows only (§10):\n"
                  "A. User-owned Apple Account redownload (purchase history).\n"
                  "B. Developer-signed IPA provided by the user.\n"
                  "C. User-owned archival IPA + user signing authority.\n"
                  "D. Legacy device matching the IPA's MinimumOSVersion.\n\n"
                  "No DRM bypass, no auth bypass, no cert forgery — ever.")

    def on_preserve(self) -> None:
        if self.record is None:
            messagebox.showinfo("Ghost IPA", "Search for an app first.")
            return
        dest = build_preservation_package(self.record, self.log)
        rep = final_report(self.record, len(self.record.historical_versions),
                           self.report.package if self.report else "UNKNOWN",
                           self.report.installation if self.report else "UNKNOWN",
                           self.report.reason if self.report else "",
                           Confidence(self.report.confidence) if self.report else Confidence.UNKNOWN,
                           [self.record.source])
        self._set("Preservation", f"Package: {dest}\n\n{rep}")
        messagebox.showinfo("Ghost IPA", f"Preservation package built:\n{dest}")


def main() -> None:
    root = tk.Tk()
    GhostGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
