# Ghost IPA Tweak — build & on-device workflow

## Prereqs (macOS/Linux builder; Windows edits fine, Theos builds elsewhere)
- Theos (`$THEOS` set), Xcode toolchain or `theos/toolchain`.
- Target device jailbroken, OpenSSH + PreferenceLoader installed.

## Build
```bash
export THEOS=~/theos
make package FINALPACKAGE=1
```

## Install
```bash
make install THEOS_DEVICE_IP=<device-ip>
# resprings AppStore + Preferences automatically
```

## On-device research FIRST (§24 — before trusting any hook)
1. Dump runtime classes: FLEXing / `class-dump AppStore.app`, grep
   `Search|Product|Storefront|Purchase|Download|Availability`.
2. Replace the `safeClass:` placeholder strings in
   `adapters/GhostAdapter.m` with the T1-confirmed names.
3. Trace one search with `rvictl`, confirm the results-array merge point,
   wire `appendGhostResults:` there.
4. Confirm PDP class, wire `GhostBadge attachToProductView:` there.

## Use
1. Settings → Ghost IPA → enable toggles.
2. Open App Store, search e.g. `Vector` — ghost rows append with 👻.
3. Open a ghost → normal PDP via `itms-apps://…/id<adamID>`.
4. Get/cloud-glyph appears ONLY if Apple serves it; otherwise the
   status card reads "Ghost record found, but Apple is not currently
   providing an authorized download for this application."
5. `ghost://app/<adamID>` deep-links from preservation notes.

## Safety contract
- No download/install/auth/fairplay hooks. Ever.
- No fabricated records: lookup-confirm or it doesn't display.
- 2 consecutive App Store crashes → experimental hooks auto-off.
- Binaries untouched: metadata cache is JSON + PNGs only.
