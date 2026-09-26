"""Assemble the real GhostIPA .deb with stdlib only (tar + hand-rolled ar).

Layout mirrors exactly what Theos would emit, minus the compiled dylib:
  - DEBIAN/control, DEBIAN/postinst
  - Library/MobileSubstrate/DynamicLibraries/GhostIPA.plist (+ .dylib placeholder note)
  - Library/PreferenceBundles/GhostIPAPrefs.bundle/{Info.plist, GhostIPA.plist}
  - Library/PreferenceLoader/Preferences/GhostIPA.plist (Settings entry)
  - var/mobile/Library/GhostIPA/README.txt (data dir seed)
  - usr/share/doc/ghostipa/{RESEARCH.md, BUILD.md, HOOKS.md, SOURCES-NOTE.txt}

The SOURCES-NOTE + postinst state plainly: install the compiled GhostIPA.dylib
(via CI ./build.sh output) next to the .plist to activate hooks.
"""
import io
import os
import struct
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
TWEAK = os.path.join(HERE, "..", "ghostipa-tweak")
TWEAK = os.path.normpath(TWEAK)
OUTDIR = os.path.join(TWEAK, "packages")
os.makedirs(OUTDIR, exist_ok=True)

PKG = "com.ghostipa.tweak"
VER = "1.0.0"
ARCH = "iphoneos-arm"
DEB = os.path.join(OUTDIR, f"{PKG}_{VER}_{ARCH}.deb")

CONTROL = f"""Package: {PKG}
Name: Ghost IPA
Version: {VER}
Architecture: {ARCH}
Description: Reveal genuine delisted/hidden App Store records inside the native App Store. Discovery only - Apple stays responsible for auth, downloads, installs.
Maintainer: Ghost IPA Preservation Research
Author: ratman4080
Section: Tweaks
Priority: optional
Homepage: https://github.com/ghostipa/ghostipa-tweak
Depiction: https://your-repo/depic/com.ghostipa.tweak/
Depends: mobilesubstrate, preferenceloader, firmware (>= 7.0)
"""

POSTINST = """#!/bin/sh
# GhostIPA stage-1 postinst: nothing to activate yet (no dylib, no prefs UI).
# Respring-safe, side-effect free apart from the notice below.
if [ ! -f /Library/MobileSubstrate/DynamicLibraries/GhostIPA.dylib ]; then
  echo "GhostIPA stage 1 installed (docs + discovery scripts). Full tweak arrives with the CI-built .deb."
fi
exit 0
"""

PRERM = """#!/bin/sh
# GhostIPA prerm: refresh icon cache on removal; substrate unloads next respring.
uicache 2>/dev/null || true
exit 0
"""

SOURCES_NOTE = """GhostIPA 1.0.0 - STAGE 1 payload (safe to install now)
=====================================================
This package installs cleanly TODAY and harms nothing: the substrate filter
without its dylib is inert; docs, scripts and the data dir just sit on disk.

What IS inside:
- MobileSubstrate filter (AppStore + Preferences) - inert until dylib lands
- /var/mobile/Library/GhostIPA data directory seed
- Full research docs (RESEARCH.md, BUILD.md, HOOKS.md)
- On-device discovery scripts (T1/T2/T3, executable)

What is NOT inside (needs Theos + Apple SDK, ships with the CI .deb):
- GhostIPA.dylib (the hooks) and the GhostIPAPrefs bundle + binary (Settings UI)

Deliberately excluded: a Settings entry without its compiled binary would
crash Settings on tap. It arrives together with the binary. No fake binaries
are shipped - a stub dylib would be worse than none.

To complete: push the repo, let Actions build the full .deb, install it over
this one (same package id), respring.
"""


def read_tweak(rel):
    with open(os.path.join(TWEAK, rel), "rb") as fh:
        return fh.read()


def add_file(tar, arcname, data, mode=0o644):
    ti = tarfile.TarInfo(arcname)
    ti.size = len(data)
    ti.mode = mode
    ti.mtime = 1758735900
    tar.addfile(ti, io.BytesIO(data))


# ---- control.tar.gz ----
cbuf = io.BytesIO()
with tarfile.open(fileobj=cbuf, mode="w:gz") as t:
    add_file(t, "control", CONTROL.encode(), 0o644)
    add_file(t, "postinst", POSTINST.encode(), 0o755)
    add_file(t, "prerm", PRERM.encode(), 0o755)
control_gz = cbuf.getvalue()

# ---- data.tar.gz ----
# STAGE 1 payload (safe to install TODAY): everything that works without a
# compiler. The prefs bundle + PreferenceLoader entry are DELIBERATELY excluded:
# a loader entry pointing at a bundle with no compiled binary makes Settings
# crash (or blank-screen) on tap. They ship with the CI-built .deb instead,
# which supersedes this one. The substrate filter alone is inert and harmless.
dbuf = io.BytesIO()
with tarfile.open(fileobj=dbuf, mode="w:gz") as t:
    add_file(t, "Library/MobileSubstrate/DynamicLibraries/GhostIPA.plist",
             read_tweak("GhostIPA.plist"))
    add_file(t, "Library/MobileSubstrate/DynamicLibraries/GhostIPA.bundle/ASSET-README.txt",
             read_tweak(os.path.join("layout", "Library", "MobileSubstrate",
                                     "DynamicLibraries", "GhostIPA.bundle", "ASSET-README.txt")))
    for _asset in ("testflight.png", "ghost.png"):
        _p = os.path.join("layout", "Library", "MobileSubstrate", "DynamicLibraries",
                          "GhostIPA.bundle", _asset)
        if os.path.exists(os.path.join(TWEAK, _p)):
            add_file(t, "Library/MobileSubstrate/DynamicLibraries/GhostIPA.bundle/" + _asset,
                     read_tweak(_p))
    add_file(t, "var/mobile/Library/GhostIPA/README.txt",
             b"GhostIPA data directory. Discovered ghosts + T1/T2/T3 outputs live here.\n")
    add_file(t, "usr/share/doc/ghostipa/RESEARCH.md", read_tweak(os.path.join("docs", "RESEARCH.md")))
    add_file(t, "usr/share/doc/ghostipa/BUILD.md", read_tweak(os.path.join("docs", "BUILD.md")))
    add_file(t, "usr/share/doc/ghostipa/HOOKS.md", read_tweak(os.path.join("docs", "HOOKS.md")))
    add_file(t, "usr/share/doc/ghostipa/INSTALL.md", read_tweak(os.path.join("docs", "INSTALL.md")))
    add_file(t, "usr/share/doc/ghostipa/SSH-SECURITY.md", read_tweak(os.path.join("docs", "SSH-SECURITY.md")))
    add_file(t, "usr/share/doc/ghostipa/SOURCES-NOTE.txt", SOURCES_NOTE.encode())
    # Research scripts, executable.
    for s in ["t1_classes.sh", "t2_trace.sh", "t3_daemons.sh"]:
        add_file(t, "usr/share/doc/ghostipa/" + s,
                 read_tweak(os.path.join("research", s)), 0o755)
data_gz = dbuf.getvalue()

DEBIAN_BINARY = b"2.0\n"


def ar_entry(name, data):
    # GNU ar header: name(16) mtime(12) uid(6) gid(6) mode(8) size(10) magic(2)
    if len(name) > 15:
        raise ValueError("ar name too long: " + name)
    hdr = struct.pack(
        "16s12s6s6s8s10s2s",
        name.encode().ljust(16), b"1758735900  ", b"0     ", b"0     ",
        b"100644  ", str(len(data)).encode().ljust(10), b"`\n",
    )
    pad = b"\n" if len(data) % 2 else b""
    return hdr + data + pad


with open(DEB, "wb") as fh:
    fh.write(b"!<arch>\n")
    fh.write(ar_entry("debian-binary", DEBIAN_BINARY))
    fh.write(ar_entry("control.tar.gz", control_gz))
    fh.write(ar_entry("data.tar.gz", data_gz))

print("BUILT:", DEB, "(%d bytes)" % os.path.getsize(DEB))
