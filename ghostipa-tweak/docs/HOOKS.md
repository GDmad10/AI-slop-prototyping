# Hook Wiring Guide — from T1/T2/T3 output to working Ghost hooks

> Do these in order. Each step confirms the previous one. No guessing.

## Step 1 — T1: name the classes
1. On-device root: `sh t1_classes.sh`, or build+run `t1_dump.m`.
2. Open `/var/mobile/Library/GhostIPA/T1-classes.txt`.
3. Pick ONE class per role:

| Role | What it looks like | Example pattern |
|---|---|---|
| Search results holder | has an array/dict property fed by lookup | `*SearchResult*`, `*SearchResponse*` |
| Row/cell | renders one result | `*LockupCell*`, `*SearchCell*`, `*CollectionCell*` |
| Product page | shows title+Get button | `*ProductPage*`, `*PDP*`, `*ItemPage*` |
| Purchase history | "Not on this iPhone" list | `*PurchaseHistory*`, `*Purchased*` |

4. Write the confirmed names here (this file is per-device truth):

```
iOS version: ___
Search results class: ___
Results setter/merge selector: ___
Row class: ___
PDP class: ___
Purchase-history class: ___
```

## Step 2 — hookprobe: confirm the selector
1. Fill `kResultsClass`/`kResultsSel` in `research/hookprobe.m`, build, inject.
2. Perform ONE search. Syslog must show `confirmed … implements …`.
3. If NOT FOUND: adjacent selectors on the same class (T1 lists the class —
   dump its methods with `class-dump -H` or `otool -o` and pick the setter
   taking an array/dictionary).

## Step 3 — wire GhostAdapter (per generation)

In `adapters/GhostAdapter.m`, replace the stub bodies:

```objc
// BEFORE (stub):
- (void)appendGhostResults:(NSArray *)ghosts {
    [[GhostCore shared] log:@"%@: append %lu ghost rows", ...];
}

// AFTER (example shape — use YOUR Step-1 names):
%hook ConfirmedSearchResultsClass
- (void)confirmedMergeSelector:(id)results {
    %orig; // Apple's rows first — never reorder/remove
    [ghostAdapter appendGhostResults:pendingGhosts]; // append-only
}
%end
```

Rules:
- `%orig` ALWAYS first. Ghost rows append after.
- PDP badge: hook the PDP's `viewDidAppear:`/`didSetModel:` equivalent,
  call `[GhostBadge attachToProductView:…]` once (guard with associated-object flag).
- Row ghost mark: in the search cell's layout hook, call
  `[GhostBadge applyRowArtwork:cellArtworkView]` + set the subtitle from
  `ghostSubtitleForApp:`. Art comes from
  `/Library/MobileSubstrate/DynamicLibraries/GhostIPA.bundle/ghost.png`
  (nil-safe: text-only fallback until the file is dropped in).
- Purchase history (§13): same append-only pattern on the history list's reload.
- Download/install selectors: NEVER hook. If T2 shows them in `appstored`,
  that confirms hands-off — close the file, you're done with T2.

## Step 3b — Purchased tab (the whole point)
The Purchased → Not on this iPhone list is Apple's own redownload door.
Hook its reload (T1: purchase-history class) and append one row per
`[[GhostPurchased shared] redownloadCandidates]`, titled with
`+[GhostPurchased rowTitleForApp:]`. Row tap calls
`-[GhostPurchased openRedownloadForApp:]` → normal PDP → Apple's cloud
Get button does the download. Tombstoned ghosts stay in the list: Apple
sometimes restores the package while the listing stays dead, and the PDP
— not us — is the authority on that.

## Step 4 — Ghost Scan wiring checklist
- [ ] Search hook fires with (query, visible adamID set)
- [ ] `scanQuery:` returns lookup-confirmed ghosts only
- [ ] Sweep stays fast (Pass 2 is concurrent; watch syslog timings)
- [ ] Rows render with 👻 subtitle, tap opens `itms-apps://…/id<adamID>`
- [ ] PDP shows status card; Get control iff Apple serves it
- [ ] Airplane-mode test: cached ghosts render from DB, zero crashes
- [ ] 2 forced crashes → experimental hooks auto-disable (GhostGuard)

## Step 5 — ship
`./build.sh` → `.deb` → install → Settings → Ghost IPA → enable →
search an old app → ghost row → normal PDP → normal Apple install path.
