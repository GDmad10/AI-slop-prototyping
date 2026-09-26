import os
import plistlib
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ghostipa-tweak")
ROOT = os.path.normpath(ROOT)

CHECKS = [
    ("Makefile", True),
    ("Tweak.x", True),
    ("GhostCore.h", True),
    ("GhostCore.m", True),
    ("GhostCompat.h", True),
    ("GhostDB.h", True),
    ("GhostDB.m", True),
    ("GhostScan.h", True),
    ("GhostScan.m", True),
    ("GhostBadge.h", True),
    ("GhostBadge.m", True),
    ("GhostGuard.h", True),
    ("GhostGuard.m", True),
    ("GhostPurchased.h", True),
    ("GhostPurchased.m", True),
    ("GhostIPA.plist", True),
    ("control", True),
    ("build.sh", True),
    (os.path.join("adapters", "GhostAdapter.h"), True),
    (os.path.join("adapters", "GhostAdapter.m"), True),
    (os.path.join("settings", "Makefile"), True),
    (os.path.join("settings", "GhostPrefs.m"), True),
    (os.path.join("settings", "Info.plist"), True),
    (os.path.join("settings", "icon.png"), True),
    (os.path.join("settings", "GhostIPA.plist"), True),
    (os.path.join("docs", "RESEARCH.md"), True),
    (os.path.join("docs", "BUILD.md"), True),
    (os.path.join("docs", "HOOKS.md"), True),
    (os.path.join("docs", "INSTALL.md"), True),
    (os.path.join("docs", "SSH-SECURITY.md"), True),
    ("MergeHooks.x.template", True),
    (os.path.join("depiction", "index.html"), True),
    (os.path.join("depiction", "HOSTING.txt"), True),
    (os.path.join("research", "t1_classes.sh"), True),
    (os.path.join("research", "t1_dump.m"), True),
    (os.path.join("research", "t2_trace.sh"), True),
    (os.path.join("research", "t3_daemons.sh"), True),
    (os.path.join("research", "hookprobe.m"), True),
]

fails = []
for rel, required in CHECKS:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        fails.append("MISSING: " + rel)

# Plist validity (XML plists only — the top-level GhostIPA.plist is
# Logos filter syntax, checked separately).
for rel in [os.path.join("settings", "Info.plist"),
            os.path.join("settings", "GhostIPA.plist"),
            os.path.join("layout", "Library", "MobileSubstrate",
                         "DynamicLibraries", "GhostIPA.plist")]:
    p = os.path.join(ROOT, rel)
    if os.path.exists(p):
        try:
            with open(p, "rb") as fh:
                plistlib.load(fh)
        except Exception as exc:
            fails.append("BAD-PLIST %s: %s" % (rel, exc))

# Control file fields.
ctl = os.path.join(ROOT, "control")
if os.path.exists(ctl):
    t = open(ctl, encoding="utf-8").read()
    for field in ("Package:", "Name:", "Version:", "Architecture:", "Description:",
                  "Depends:", "Depiction:"):
        if field not in t:
            fails.append("CONTROL missing " + field)

# Depiction: index.html must reference icon.png; the icon file itself is
# supplied by the maintainer (warn, don't fail, until dropped in).
dep = os.path.join(ROOT, "depiction", "index.html")
if os.path.exists(dep):
    html = open(dep, encoding="utf-8").read()
    if 'src="icon.png"' not in html:
        fails.append("depiction index.html does not reference icon.png")
icon = os.path.join(ROOT, "depiction", "icon.png")
if not os.path.exists(icon):
    print("NOTE: depiction/icon.png not yet supplied — Cydia logo pending maintainer drop.")

# Ghost UI asset: bundle slot must exist; art file warns until dropped in.
bundle_dir = os.path.join(ROOT, "layout", "Library", "MobileSubstrate",
                          "DynamicLibraries", "GhostIPA.bundle")
if not os.path.isdir(bundle_dir):
    fails.append("missing GhostIPA.bundle asset dir")
elif not os.path.exists(os.path.join(bundle_dir, "ghost.png")):
    print("NOTE: GhostIPA.bundle/ghost.png not yet supplied — App Store UI falls back to text badge.")
if not os.path.exists(os.path.join(bundle_dir, "testflight.png")):
    print("NOTE: GhostIPA.bundle/testflight.png not yet supplied — beta rows use ghost mark.")

# Repo: Packages index must match the shipped .deb byte-for-byte metadata.
REPO = os.path.normpath(os.path.join(ROOT, "..", "repo"))
DEB = os.path.join(ROOT, "packages", "com.ghostipa.tweak_1.0.0_iphoneos-arm.deb")
if not os.path.exists(os.path.join(REPO, "Packages")):
    fails.append("repo/Packages missing — run tests/build_repo.py")
else:
    import hashlib as _hl
    blob = open(DEB, "rb").read() if os.path.exists(DEB) else b""
    pkg = open(os.path.join(REPO, "Packages"), encoding="utf-8").read()
    for needle in (f"Size: {len(blob)}",
                   f"SHA256: {_hl.sha256(blob).hexdigest()}",
                   f"MD5sum: {_hl.md5(blob).hexdigest()}",
                   "Filename: debs/com.ghostipa.tweak_1.0.0_iphoneos-arm.deb"):
        if blob and needle not in pkg:
            fails.append("repo/Packages stale: missing " + needle)
    if pkg.count("Depiction:") != 1:
        fails.append("repo/Packages must carry exactly one Depiction line")
    for extra in ("Release", "README.txt", "Packages.bz2",
                  os.path.join("depiction", "com.ghostipa.tweak", "index.html"),
                  os.path.join("depictions", "com.ghostipa.tweak", "info.xml"),
                  os.path.join("debs", "com.ghostipa.tweak_1.0.0_iphoneos-arm.deb")):
        if not os.path.exists(os.path.join(REPO, extra)):
            fails.append("repo missing " + extra)
    # Sileo info.xml parses; bz2 index round-trips to Packages.
    import xml.etree.ElementTree as _ET
    import bz2 as _bz2
    try:
        _ET.parse(os.path.join(REPO, "depictions", "com.ghostipa.tweak", "info.xml"))
    except Exception as exc:
        fails.append("repo info.xml invalid: " + str(exc))
    try:
        raw_bz = open(os.path.join(REPO, "Packages.bz2"), "rb").read()
        plain = open(os.path.join(REPO, "Packages"), encoding="utf-8").read()
        if _bz2.decompress(raw_bz).decode() != plain:
            fails.append("repo Packages.bz2 does not match Packages")
    except Exception as exc:
        fails.append("repo bz2 check failed: " + str(exc))

# Logos sanity: %ctor, %hook, %end balanced.
tweak = os.path.join(ROOT, "Tweak.x")
if os.path.exists(tweak):
    t = open(tweak, encoding="utf-8").read()
    if t.count("%hook") != t.count("%end"):
        fails.append("Tweak.x: %%hook/%%end imbalance")
    if "%ctor" not in t:
        fails.append("Tweak.x: no %ctor")

if fails:
    print("TWEAK PACKAGE CHECK: FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("TWEAK PACKAGE CHECK: PASS (%d files, plists valid, control complete)" % len(CHECKS))
