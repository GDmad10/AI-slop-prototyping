# Ghostly Repo — http://ghostly.repo — add to Cydia / Sileo / Zebra
# Layout follows MDausch/Example-Cydia-Repository conventions
# (Packages + Packages.bz2, Release, depictions/<pkg>/info.xml for Sileo).

## Add the source
Cydia → Sources → Edit → Add → `http://ghostly.repo/`
(Zebra/Sileo: same, add source with that URL). Search "Ghost IPA".

## Serve locally (before DNS is live)
1. On the PC, in THIS folder (`repo/`): `python -m http.server 8000`
2. PC's LAN IP from `ipconfig` (e.g. 192.168.1.20).
3. Add `http://192.168.1.20:8000/` as the source instead.

## Option A — serve from this PC (same Wi-Fi, 2 minutes)
1. On the PC, in THIS folder (`repo/`): `python -m http.server 8000`
2. Find the PC's LAN IP (Windows: `ipconfig`, e.g. 192.168.1.20).
3. On the iPad: Cydia → Sources → Edit → Add → `http://192.168.1.20:8000/`
   (Zebra/Sileo: same, add source with that URL).
4. Ghost IPA appears under Search and in Tweaks. Install from there —
   proper queue, proper Installed entry, clean upgrades later.
5. Keep the server running while installing. Afterwards it can stop.

## Option B — static host (permanent)
Upload this whole folder to any static host (GitHub Pages, Netlify, VPS).
Add `https://YOUR-HOST/` as the source. The `depiction/` page serves with it.

## Refresh after rebuilds
Run `python tests/build_repo.py` again after every `.deb` rebuild, then in
Cydia hit Refresh. Hashes and sizes regenerate; clients see the update.
