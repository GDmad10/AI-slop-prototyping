# Installing GhostIPA 1.0.0 (stage 1) on a jailbroken device

> Requires: jailbroken iPhone/iPad, OpenSSH (or Filza), `dpkg` present
> (Cydia/Sileo/Zebra install it by default). iOS 7.0–16 (32-bit armv7/armv7s
> through arm64e; iOS 17+ expected same path, untested).

## 1. Copy the .deb over

From your computer (same Wi-Fi, device IP `192.168.1.50`):

```bash
scp ghostipa-tweak/packages/com.ghostipa.tweak_1.0.0_iphoneos-arm.deb root@192.168.1.50:/tmp/
```

Or AirDrop / Files it to the device and move to `/tmp/` in Filza.

## 2. Install as root

```bash
ssh root@192.168.1.50
dpkg -i /tmp/com.ghostipa.tweak_1.0.0_iphoneos-arm.deb
```

Expected output ends with:

```
GhostIPA stage 1 installed (docs + discovery scripts). Full tweak arrives with the CI-built .deb.
```

`dpkg -l com.ghostipa.tweak` should show `ii` (installed, ok).

## 3. What works RIGHT NOW

- `/usr/share/doc/ghostipa/` — RESEARCH.md, BUILD.md, HOOKS.md on-device
- `/usr/share/doc/ghostipa/t1_classes.sh t2_trace.sh t3_daemons.sh` — run T1/T2/T3:
  `sh /usr/share/doc/ghostipa/t1_classes.sh` (as root)
- `/var/mobile/Library/GhostIPA/` — data dir seeded
- Inert substrate filter — App Store behaves 100% normally, zero risk

## 4. What does NOT work yet (honest)

- No 👻 rows, no Settings page — those need the compiled `GhostIPA.dylib` +
  prefs binary from the CI build (push the repo → Actions → install that .deb
  over this one, same package id, then respring).
- If `dpkg` warns about anything, paste the full output back and it gets fixed.

## 5. Uninstall (clean, no residue)

```bash
dpkg -r com.ghostipa.tweak
```

Removes filter, docs, scripts. The data dir can be deleted manually if wanted:
`rm -rf /var/mobile/Library/GhostIPA`.
