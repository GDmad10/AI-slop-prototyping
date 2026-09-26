"""Generate a Cydia/Sileo/Zebra repo from the built .deb (stdlib only).

Layout follows MDausch/Example-Cydia-Repository conventions:
  debs/                  packages
  Packages + Packages.bz2  indexes (plain + bzip2)
  Release                repo metadata
  depiction/...          classic Cydia depiction page (Depiction: field)
  depictions/<pkg>/info.xml  Sileo native depiction (auto-discovered by bundle id)
"""
import bz2
import hashlib
import io
import os
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "repo"))
DEB_SRC = os.path.normpath(os.path.join(
    HERE, "..", "ghostipa-tweak", "packages",
    "com.ghostipa.tweak_1.0.0_iphoneos-arm.deb"))
os.makedirs(os.path.join(REPO, "debs"), exist_ok=True)

# Copy .deb in.
name = os.path.basename(DEB_SRC)
with open(DEB_SRC, "rb") as f:
    blob = f.read()
with open(os.path.join(REPO, "debs", name), "wb") as f:
    f.write(blob)

# Read control from the .deb.
raw = blob
off = 8
members = {}
while off < len(raw):
    mname = raw[off:off + 16].decode().strip()
    size = int(raw[off + 48:off + 58].decode().strip())
    members[mname] = raw[off + 60:off + 60 + size]
    off += 60 + size + (size % 2)
ctl = tarfile.open(fileobj=io.BytesIO(members["control.tar.gz"])).extractfile("control").read().decode()

md5 = hashlib.md5(blob).hexdigest()
sha256 = hashlib.sha256(blob).hexdigest()
ctl_lines = [l for l in ctl.strip().splitlines()
             if not l.startswith("Depiction:")]  # repo serves its own depiction path
pkg = ("\n".join(ctl_lines) + f"\nFilename: debs/{name}\nSize: {len(blob)}\n"
       f"MD5sum: {md5}\nSHA256: {sha256}\n"
        "Depiction: https://GDmad10.github.io/AI-slop-prototyping/repo/depiction/com.ghostipa.tweak/index.html\n")
open(os.path.join(REPO, "Packages"), "w", newline="\n").write(pkg)
with open(os.path.join(REPO, "Packages.bz2"), "wb") as f:
    f.write(bz2.compress(pkg.encode(), 9))

INFO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<packageInfo>
    <bundleId>com.ghostipa.tweak</bundleId>
    <name>Ghost IPA</name>
    <version>1.0.0</version>
    <descriptions>
        <description>Reveal genuine delisted/hidden App Store records inside the native App Store.</description>
        <description>Stage 1: docs + discovery kit + inert filter. Hooks arrive with the compiled binary. Discovery only - Apple stays responsible for auth, downloads, installs.</description>
    </descriptions>
    <compatibility>
        <miniOS>7.0</miniOS>
    </compatibility>
    <dependencies>
        <dependency>mobilesubstrate</dependency>
        <dependency>preferenceloader</dependency>
        <dependency>firmware (&gt;= 7.0)</dependency>
    </dependencies>
    <changelog>
        <change>
            <changeVersion>V1.0.0</changeVersion>
            <changeDescription>Stage 1: installable base — filter, docs, T1/T2/T3 kit, hammer art</changeDescription>
            <changeDescription>iOS 7.0–16 support, 32-bit + 64-bit slices planned</changeDescription>
        </change>
    </changelog>
</packageInfo>
"""
sileo_dir = os.path.join(REPO, "depictions", "com.ghostipa.tweak")
os.makedirs(sileo_dir, exist_ok=True)
open(os.path.join(sileo_dir, "info.xml"), "w", encoding="utf-8", newline="\n").write(INFO_XML)

rel = ("Origin: Ghost IPA\nLabel: Ghost IPA\nSuite: stable\nVersion: 1.0\n"
       "Codename: ghost\nArchitectures: iphoneos-arm\nComponents: main\n"
       "Description: Ghost IPA preservation research\n")
open(os.path.join(REPO, "Release"), "w", newline="\n").write(rel)

# Depiction + icon slots served alongside.
dep = os.path.join(REPO, "depiction", "com.ghostipa.tweak")
os.makedirs(dep, exist_ok=True)
tdep = os.path.normpath(os.path.join(HERE, "..", "ghostipa-tweak", "depiction"))
for f in ("index.html", "HOSTING.txt"):
    p = os.path.join(tdep, f)
    if os.path.exists(p):
        open(os.path.join(dep, f), "wb").write(open(p, "rb").read())
print(f"REPO READY: {REPO}")
print(f"Packages: {len(pkg)} bytes, deb {len(blob)} bytes, sha256 {sha256[:16]}…")
