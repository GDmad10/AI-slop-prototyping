# Ghost UI asset — DROP FILE HERE
Place the ghost artwork here as:

    ghost.png      (1x, 60×60 px minimum)
    ghost@2x.png   (2x, 120×120 px — recommended, same art)
    ghost@3x.png   (3x, 180×180 px — same art, ideal)

This directory ships on-device as:
    /Library/MobileSubstrate/DynamicLibraries/GhostIPA.bundle/
and the tweak loads it at runtime for:
  - ghost search-row thumbnails (App Store results list)
  - ghost status-card header image (product page)
  - Settings bundle rows (falls back to icon.png if absent)

Rules: PNG with transparency, white ghost on transparent (the App Store row
backgrounds vary by mode — dark/light). No rounded-rectangle masking; rows
and cards mask it themselves.

TESTFLIGHT ICON (maintainer-supplied):
    testflight.png      (1x, 60×60 px minimum)
    testflight@2x.png   (2x, 120×120 px — recommended, same art)
    testflight@3x.png   (3x, 180×180 px — same art, ideal)
Marks TestFlight beta rows/cards in the tweak UI (loaded as +tfImage).
Same rules: transparent PNG, no pre-masking. Until dropped in, beta rows
use the ghost mark.
