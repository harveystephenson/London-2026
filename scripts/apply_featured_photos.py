"""Apply exported featured-photo picks to the site.

Reads the featured_photo_decisions.json downloaded from the picker page
(make_featured_picker.py) and rewrites data/featured_photos.csv from it —
a full rewrite, not a merge, since the picker's localStorage already holds
the complete current state (seeded from the CSV when it was generated).

Each pick in the export is a slug (e.g. "img_2830"), not a raw filename —
see the comment on FEATURED_CSV in build_gallery.py for why. Unset slots
(null in the export) simply don't get a row, which is fine: build_gallery.py
falls back automatically for anything unpicked.

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

FIELDS = ["role", "filename", "day", "location_id", "sort"]


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
    if data.get("banner_lead"):
        rows.append({"role": "banner_lead", "filename": data["banner_lead"], "day": "", "location_id": "", "sort": 1})
    for i, filename in enumerate(data.get("banner") or []):
        if filename:
            rows.append({"role": "banner", "filename": filename, "day": "", "location_id": "", "sort": i + 2})
    for day, filename in (data.get("day_feature") or {}).items():
        if filename:
            rows.append({"role": "day_feature", "filename": filename, "day": day, "location_id": "", "sort": ""})
    for location_id, filename in (data.get("item_feature") or {}).items():
        if filename:
            rows.append({"role": "item_feature", "filename": filename, "day": "", "location_id": location_id, "sort": ""})

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
