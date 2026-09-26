# CoM Zombies Preservation Decryptor

Windows-native reverse-engineering, preservation, package-retrieval,
decryption, and extraction for **Call of Mini: Zombies / Call of Mini
Zombies** — legitimately obtained historical packages only.

Primary target: **historical Windows Phone release**, especially
packages / server-archive files for **Call of Mini: Zombies v1.1.0.0**.

Package-metadata reference model: **DBOX Tools (https://dbox.tools/)** —
identifiers, relationships, versions, architectures, platforms,
contained files. `comz_core/package_meta.py` mirrors that field shape
locally from manifests inside files you already possess.

**Real recovery + real decryption** — nothing simulated:
- `retrieve` — local ingest into staging, or direct-URL download with
  SHA-256 verification.
- `metadata` — WMAppManifest.xml / AppxManifest.xml parsing into a
  DBOX-style record (Package ID, Product/Content ID, Version, Arch,
  Platform, contained-files inventory, dependency relationships).
- `decrypt` — `CallOfMiniZombiesDecryptor`: zip-password, AES-CBC file,
  AES-ECB file, XOR file — all with operator-supplied keys only
  (pure-Python AES-128/192/256 in `comz_core/crypto.py`, stdlib only).
  Post-decrypt validation is real: output must parse as a readable
  container or expose Unity/PE/manifest structures or the run reports
  `DECRYPTION FAILED / PLAINTEXT VALIDATION FAILED`.
- `extract` — unpacks the decrypted plaintext XAP/APPX (zip-based).

Gate: every decrypt/extract path requires a CoM Zombies match.
Anything else prints `NOT CALL OF MINI: ZOMBIES` and the
game-specific decryptor stays disabled. No keys are hard-coded,
stored, or brute-forced — key bytes never touch the catalog DB.

## Install

Python 3.10+ on Windows. Stdlib only — no third-party dependencies.

```powershell
cd CoMZTool
python comz_tool.py identify "sample.file"
```

## Commands

```powershell
# recovery
python comz_tool.py retrieve --file game.file --staging staging\ --catalog comz_catalog.db
python comz_tool.py retrieve --url "https://…" --filename game.file --staging staging\ --expect-sha256 abc…

# DBOX-style metadata
python comz_tool.py metadata game.file --format json --output meta.json --catalog comz_catalog.db

# real decryption (operator key only, CoM Zombies-gated)
python comz_tool.py decrypt enc.file --output plain.file --mode aes-cbc-file --key-hex 0011… --iv-hex 0102…
python comz_tool.py decrypt enc.file --output plain.file --mode aes-ecb-file --key-hex 0011…
python comz_tool.py decrypt enc.file --output plain.file --mode xor-file --key-hex 0011…
python comz_tool.py decrypt prot.file --output unpacked\ --mode zip-password --password "…"
python comz_tool.py decrypt media.pre --output plain.bin --mode playready-aesctr-file --key-hex <content-key-hex> --iv-hex <iv-hex>

# extraction of decrypted plaintext
python comz_tool.py extract plain.file --output recovered\

# analysis / catalog / research (prior build, retained)
python comz_tool.py identify game.file
python comz_tool.py analyze game.file --json analysis.json
python comz_tool.py report game.file --format json --output report.json
python comz_tool.py compare buildA.file buildB.file
python comz_tool.py scan-unity recovered\
python comz_tool.py catalog-add game.file --db comz_catalog.db --source-notes "archive X"
python comz_tool.py catalog-list --db comz_catalog.db
python comz_tool.py extract-plaintext game.file --output recovered\
python comz_tool.py verify-plaintext recovered\
python comz_tool.py research-diff buildA.file buildB.file

# TEST-B automatic acquisition (DBOX > Store > RG-Adguard …)
python comz_tool.py retrieve-test-b --source rg-adguard --chain --json testb.json
python comz_tool.py test TEST-B --chain --json testb.json

# resolver profiles: normal | legacy-wp8 | last-resort
python comz_tool.py retrieve-test-b --profile normal
python comz_tool.py retrieve-test-b --profile legacy-wp8
python comz_tool.py retrieve-test-b --profile last-resort --chain --json testb.json
python comz_tool.py test TEST-B --profile last-resort

# profile reproducibility record (PC / WP8 / historical / last-resort)
python comz_tool.py test-store-profiles --json profiles.json

# RG-Adguard Microsoft file-index metadata lookup
python comz_tool.py rg-file-index "Call of Mini Zombies"
```

## GUI

```powershell
python gui.py
```

Tabs: Identify / Analyze / Package Metadata / Decrypt + Extract /
Hex Viewer / Compare Builds / Unity Recovery / Logs.
Primary action: **DECRYPT + EXTRACT CALL OF MINI: ZOMBIES v1.1.0.0**.
Key fields (Key-hex / IV-hex / Zip password) feed the real decryptor;
results land in Decrypt + Extract with `DECRYPTION SUCCEEDED /
PLAINTEXT VERIFIED` or a genuine failure.

## Catalog schema

SQLite `comz_catalog.db`, table `samples`: Game, Package ID,
Content ID, Key ID, Product ID, Version, Platform, Architecture,
Filename, Extension, Detected Format, Encrypted, Encryption Type,
Key Status, Decryption Status, SHA-1, SHA-256, MD5, File Size,
Source Notes, Research Notes. Key Status is always observational
(`operator-supplied (never stored)` / `not collected`) — key bytes
are never stored.

## Performance

Analysis is O(n) single-pass hashing + capped string/entropy scan.
AES is pure-Python (preservation-correct, not speed-tuned): ~tens of
KB/s — fine for historical XAP sizes in an archival workflow. No
brute force exists in this codebase.

## Building CoMZTool.exe

Use PyInstaller on Windows (optional):

```powershell
pip install pyinstaller
pyinstaller --onefile --name CoMZ-Preservation-Decryptor comz_tool.py
pyinstaller --onefile --name CoMZ-Preservation-Decryptor-GUI gui.py
```

## Tests

```powershell
python tests/test_basic.py
python tests/test_decryptor.py
python tests/test_rg_adguard.py
python tests/test_dbox.py
python tests/test_playready.py
python tests/test_wpcompat.py
```

## TEST-B / RG-Adguard notes

- Backend: `comz_core/rg_adguard.py` — resolver (`store.rg-adguard.net`),
  file index (`files.rg-adguard.net`), candidate verification, TEST-B
  pipeline, source-hash consensus.
- Target: CoM Zombies `1.1.0.0`, Windows Phone, app ID
  `0febf8fa-35e8-4a87-8090-58b65220b3ed`, historical XAP ~79 MB.
- All candidate generations are reported before the exact target is
  selected; no newest-first substitution. First-file auto-accept is
  refused — every candidate is verified on filename/type/version/arch/
  identity/hashes. States: NOT FOUND through READY FOR DECRYPTION.
- Live probe (2026-09): resolver reachable, 0 links for the legacy WP
  GUID (delisted) — TEST-B honestly reports NOT FOUND until a mirror
  or configured source yields a verifiable package.

## DBOX product resolution notes

- Reference: `comz_core/dbox.py` — DBOX product `9WZDNCRFHZSZ`
  (`https://dbox.tools/store/products/9WZDNCRFHZSZ/`) treated strictly
  as lookup/correlation source, never as proof of the historical package.
- Identifiers kept separate: DBOX product ID != package ID != Content ID
  != historical WP app ID `0febf8fa-35e8-4a87-8090-58b65220b3ed`.
  Relationship (EXACT TARGET / RELATED GENERATION / UNRELATED /
  INSUFFICIENT METADATA) is determined from observed metadata only.
- Candidates failing the historical target gate are marked
  `REFERENCE ONLY`, never TEST-B. READY packages get a preservation
  record (IDs, filename, version, platform, arch, URL/source, hashes,
  size, timestamp) riding alongside the unaltered original.
- Xref tables (`dbox_refs`, `xrefs`): Store Product ↔ DBOX Product ↔
  Package ID ↔ Content ID ↔ Key ID ↔ Historical package ↔ Archive item
  ↔ Recovered runtime files.
- Pipeline: DBOX product → Store metadata → package services →
  RG-Adguard → downloader → Archive → Wayback → verify → TEST-B.
- Live probe: DBOX page returns 403 to plain fetch (bot guard) —
  `dbox-product` honestly reports NOT FOUND; metadata import path is
  covered by fixture tests.

```powershell
python comz_tool.py dbox-product --product-id 9WZDNCRFHZSZ --json dbox.json
python comz_tool.py xref-add --store-product 0febf8fa-35e8-4a87-8090-58b65220b3ed --dbox-product 9WZDNCRFHZSZ --note "correlation"
python comz_tool.py xref-list
```

## Legacy WP8 compatibility-emulation notes

- Layer: `comz_core/wpcompat.py` — virtual request profiles
  (`CallOfMiniZombies-WP8`, research-only `CoM-WP8-VirtualDevice`)
  isolated to package-resolution HTTP metadata. The real Windows
  install is never touched; no credentials, tokens, certificates,
  signatures, entitlements, DRM credentials, attestation, or private
  keys are ever forged or sent.
- Modes: `normal` (PC resolution) / `legacy-wp8` (WP8 profile probe) /
  `last-resort` (legacy metadata → current infra → RG-Adguard →
  Archive → Wayback, automatic, no manual repeats).
- Cross-match classes: EXACT HISTORICAL WP PACKAGE (only TEST-B
  eligible) / HISTORICAL MOBILE PACKAGE / CURRENT PC PACKAGE
  (CURRENT PC REFERENCE ONLY — a 4.x PC download never passes TEST-B,
  no silent downgrade) / WRONG PLATFORM / WRONG VERSION / UNRELATED.
- Failure taxonomy: INCOMPATIBLE DEVICE / PACKAGE NOT OFFERED / LEGACY
  PLATFORM / PACKAGE FAMILY MISMATCH / HISTORICAL VERSION UNAVAILABLE
  / UNKNOWN RESPONSE. Existence ladder (page → product → metadata →
  package → URL → downloadable → downloaded → verified → decryptable)
  keeps "page exists" distinct from "package downloadable."
- Final report fields: store page / DBOX / RG-Adguard / legacy-WP8
  profile / historical package / downloaded / verified / runtime /
  offline decryption / plaintext / Unity / TEST-B PASS-FAIL-NOT
  AVAILABLE.
- Live probe: profile metadata accepted locally; no public Microsoft
  endpoint takes virtual WP8 device metadata for delivery
  (recorded UNKNOWN, honestly). TEST-B stays NOT AVAILABLE until a
  real historical package verifies.
