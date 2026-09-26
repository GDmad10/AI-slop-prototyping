# Ghost IPA Tweak — Research Report (§24)

> Rule: no invented class names, no invented private APIs.
> Everything below is either public/documented ground truth or an
> explicitly-labelled runtime-discovery task to run on-device.

## 1. App Store process / bundle (ground truth)

| iOS gen | Store app | Notes |
|---|---|---|
| iOS 6–9 | `com.apple.AppStore` (`/Applications/AppStore.app`, later MobileStore) | Classic `AppStore.app`; purchases via `storebookkeeperd` / `itunesstored` daemons |
| iOS 10–12 | `com.apple.AppStore` | Rewrite era; `appstored` daemon owns downloads, `StoreKit` client-side |
| iOS 13+ | `com.apple.AppStore` | SwiftUI/JS-hybrid PDPs; `appstored` + `mediaassetd`; `SKStorefront`, `SKProduct` public surface |
| iOS 16+ | `com.apple.AppStore` | StoreKit 2 (`Product`, `Storefront`, `Transaction` in Swift); search backed by `search.itunes.apple.com`-family endpoints via `AppStoreFoundation` |

**Public endpoint ground truth** (usable without any hook, same as the
Windows tool): `https://itunes.apple.com/lookup?id=<adamID>&country=<cc>&entity=software`
and `https://itunes.apple.com/search?term=<q>&country=<cc>&entity=software`.
These return genuine records only — the tweak's "ghost" candidates must come
from here or from the user's own purchase history, never fabricated.

**On-device discovery tasks** (run with `FLEXing`/`objdump`/`class-dump` on the
target OS before hooking):
- `T1`: dump `AppStore.app` ObjC runtime classes, filter `/Search|SearchResult|Product|Page|Storefront|Purchase|Download|Availability/i`.
- `T2`: trace search network calls (e.g. `rvictl` + Wireshark, or `SSL Kill Switch`-free `NSURLSession` logging via `CydiaSubstrate` constructor that only logs).
- `T3`: confirm which daemon owns the final download (`appstored` on modern iOS) — the tweak NEVER hooks that path, only discovery/presentation.

## 2. Search architecture (what to find, per generation)

- **iOS 7–9**: `UITableView`-driven search controllers fed by `SSLookup`-family
  StoreServices responses. Hook point: the results-array merge, *after* network
  parse, *before* table reload. Adapter: `GhostAdapter_iOS7_9`.
- **iOS 10–12**: `UICollectionView` search; `AppStoreFoundation` lookup items.
  Hook point: view-model array append. Adapter: `GhostAdapter_iOS10_12`.
- **iOS 13–15**: JS-backed search + native PDP bridge (`ASJSPDPBridge`-style
  glue — VERIFY name on-device via T1, do not trust this string).
  Hook point: bridge model's results dictionary. Adapter: `GhostAdapter_iOS13_15`.
- **iOS 16+**: StoreKit 2 `Product.products(for:)` results feed SwiftUI lists.
  Hook point: the `[Product]` array delivered to the search list view-model —
  appended ghost `Product`s must be constructed from the same lookup payload
  (same `id`, same `displayPrice`), never synthesized. Adapter: `GhostAdapter_iOS16Plus`.

## 3. Product metadata / PDP architecture

- PDPs render from the lookup payload (`trackId`, `bundleId`, `version`,
  `minimumOsVersion`, `artworkUrl512`, `sellerName`). Ghost PDP = normal PDP
  opened with the ghost `adamID` (`itms-apps://itunes.apple.com/app/id<adamID>`).
  No custom storefront, no custom download button — the existing Get/cloud-glyph
  control stays authoritative (§9, §12, §23).
- Region filtering happens server-side per `storefront` country code.
  The tweak queries alternate storefronts for *metadata only* and labels them
  (`Storefront: DK`, `Current: Unknown`) — it never changes the account region (§14).

## 4. Availability / purchase-history filtering

- "Not Available" / hidden-purchase states are computed from
  `isHidden` + storefront-eligibility + `purchaseHistory` flags in the daemon
  response. Ghost Scan re-queries: (a) alternate storefront lookup,
  (b) `SKCloudServiceController`-visible purchase state where the API exposes it,
  (c) user-authorized `Purchased → Not on this iPhone` list (§13).
- Verdicts stay tri-state: `GHOST RECORD FOUND` vs `PACKAGE AVAILABLE` vs
  `INSUFFICIENT EVIDENCE` (§20). Metadata without distribution shows the
  historical card + preservation info, never a Get button that can't fulfil.

## 5. Safe hook points (minimum necessary, §19)

1. Search results merge (append-only; never remove/reorder Apple's rows).
2. PDP badge view (adds the 👻 Ghost App subtitle + status block).
3. Settings bundle (toggles + Clear Ghost Cache).
4. Background metadata cache write (`/var/mobile/Library/GhostIPA/`).
5. Crash guard: `NSUncaughtExceptionHandler` + consecutive-crash counter that
   auto-disables experimental hooks (§20 fail-safe).

## 6. Known differences between iOS versions

- iOS ≤9: 32-bit binaries exist; `MinimumOSVersion` parsing is the compat gate.
- iOS 11+: 32-bit purged — most iOS ≤10 ghosts will be `PACKAGE UNAVAILABLE`
  on-device even when the record is genuine; the card must say so.
- iOS 13+: dark mode + JS PDPs — badge must use dynamic system colors.
- iOS 16+: StoreKit 2 privacy manifests; lookup still works, receipt checks moved.

## 7. What NOT to hook

Download/install daemons (`appstored`, `nsurlsessiond`), receipt validation,
fair-play decryption, account auth. Those stay Apple's (§12).
