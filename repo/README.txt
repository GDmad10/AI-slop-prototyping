# Ghostly Repo - https://GDmad10.github.io/AI-slop-prototyping/repo/ - Cydia / Sileo / Zebra
# Layout follows MDausch/Example-Cydia-Repository conventions
# (Packages + Packages.bz2, Release, depictions/<pkg>/info.xml for Sileo).

## Add the source (once pushed + Pages enabled, see below)
Cydia -> Sources -> Edit -> Add -> `https://GDmad10.github.io/AI-slop-prototyping/repo/`
(Zebra/Sileo: same, add source with that URL). Search "Ghost IPA".

## TIMEOUT on old Cydia? (iOS 7-8 + HTTPS)
Old APT's TLS cannot handshake with modern hosts. This is expected, not
broken. Use the LAN method below (plain HTTP, no TLS) - it always works
on the same Wi-Fi. Safari test: if Safari on the iPad also fails to open
the Packages URL, it's the TLS stack - LAN method it is.

## Going live (GitHub Pages)
1. Push master to GitHub.
2. Repo Settings -> Pages -> Deploy from branch -> master, folder / (root).
3. Wait ~1 min, open the URL above in a browser - Packages must download.
4. Add the URL as a Cydia source on the iPad. Done - public repo.

## Serve locally (works today, no push needed)
1. On the PC, in THIS folder (`repo/`): `python -m http.server 8000`
2. PC's LAN IP from `ipconfig` (e.g. 192.168.1.20).
3. Add `http://192.168.1.20:8000/` as the source instead.

## Refresh after rebuilds
Run `python tests/build_repo.py` after every `.deb` rebuild, commit, push,
then Refresh in Cydia. Hashes and sizes regenerate; clients see the update.
