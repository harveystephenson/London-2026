"""Apply exported featured-photo picks to the site.

Reads the featured_photo_decisions.json downloaded from the picker page
(make_featured_picker.py) and rewrites data/featured_photos.csv from it —
a full rewrite, not a merge, since the picker's localStorage already holds
the complete current state (seeded from the CSV when it was generated).

Each pick in the export is {filename, crop_x, crop_y} (#84) — filename is
a slug (e.g. "img_2830"), not a raw filename, see the comment on
FEATURED_CSV in build_gallery.py for why. crop_x/crop_y (0-100, default 50)
is the object-position the user dragged to in the picker's crop-frame
preview, so the site crops the same part of the photo the user chose
instead of an arbitrary center crop. Unset slots (null in the export)
simply don't get a row, which is fine: build_gallery.py falls back
automatically for anything unpicked.

Run build_gallery.py afterwards to bake the picks into index.html — no
photos need re-encoding for this, so it's the fast, data-only path (~3s).

Usage:
    python scripts/apply_featured_photos.py [path\\to\\featured_photo_decisions.json]
    # default path: %USERPROFILE%\\Downloads\\featured_photo_decisions.json
    python scripts/build_gallery.py
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEATURED_CSV = ROOT / "data" / "featured_photos.csv"

FIELDS = ["role", "filename", "day", "location_id", "sort", "crop_x", "crop_y"]


def crop_of(pick):
    """Each pick is {filename, crop_x, crop_y} — default to a center crop
    (50, 50) if crop fields are missing, e.g. from a manually-edited JSON."""
    x = pick.get("crop_x") if isinstance(pick, dict) else None
    y = pick.get("crop_y") if isinstance(pick, dict) else None
    return (round(x, 1) if x is not None else 50, round(y, 1) if y is not None else 50)


def filename_of(pick):
    return pick.get("filename") if isinstance(pick, dict) else pick


def main():
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    else:
        src = Path.home() / "Downloads" / "featured_photo_decisions.json"
    if not src.exists():
        sys.exit(f"Decisions file not found: {src}\n"
                 "Export it from the picker page, or pass its path as an argument.")

    data = json.loads(src.read_text(encoding="utf-8-sig"))

    rows = []
    lead = data.get("banner_lead")
    if lead and filename_of(lead):
        cx, cy = crop_of(lead)
        rows.append({"role": "banner_lead", "filename": filename_of(lead), "day": "", "location_id": "", "sort": 1, "crop_x": cx, "crop_y": cy})
    for i, pick in enumerate(data.get("banner") or []):
        if pick and filename_of(pick):
            cx, cy = crop_of(pick)
            rows.append({"role": "banner", "filename": filename_of(pick), "day": "", "location_id": "", "sort": i + 2, "crop_x": cx, "crop_y": cy})
    for day, pick in (data.get("day_feature") or {}).items():
        if pick and filename_of(pick):
            cx, cy = crop_of(pick)
            rows.append({"role": "day_feature", "filename": filename_of(pick), "day": day, "location_id": "", "sort": "", "crop_x": cx, "crop_y": cy})
    for location_id, pick in (data.get("item_feature") or {}).items():
        if pick and filename_of(pick):
            cx, cy = crop_of(pick)
            rows.append({"role": "item_feature", "filename": filename_of(pick), "day": "", "location_id": location_id, "sort": "", "crop_x": cx, "crop_y": cy})

    with open(FEATURED_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    banner_count = sum(1 for r in rows if r["role"] == "banner")
    day_count = sum(1 for r in rows if r["role"] == "day_feature")
    item_count = sum(1 for r in rows if r["role"] == "item_feature")
    print(f"Banner: lead {'set' if data.get('banner_lead') else 'using default'}, {banner_count}/4 supporting photos picked")
    print(f"Day photos picked: {day_count}")
    print(f"Item photos picked: {item_count}")
    print(f"Written: {FEATURED_CSV}")
    print("Now run: python scripts/build_gallery.py")


if __name__ == "__main__":
    main()
