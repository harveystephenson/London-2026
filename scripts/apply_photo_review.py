"""Apply exported photo-review decisions (quality + locations) to the site.

Reads the photo_review_decisions.json downloaded from the review page
(make_photo_review.py) and applies both halves:

- quality: merged into data/photo_edits.csv (the durable record
  build_gallery.py consults), and the derived JPGs of every photo whose
  effective enhancement state CHANGED are deleted so the next build
  re-encodes them — with the enhancement for newly approved photos, without
  it for newly un-approved ones.
- locations: written into data/photo_manifest.csv's final_location column
  for exactly the rows the export marked as changed. No derived files need
  deleting for these — build_gallery.py recomputes paths from the manifest
  and prunes anything orphaned.

Categories that don't match a flag in data/flag_locations.csv are reported:
photos tagged with them group by day only until a flag (with coordinates)
is added, and a mom's photo tagged with one can't be placed on a day at all
until either a flag exists or the user's own photos carry the same tag.

Run build_gallery.py afterwards to make it all real.

Usage:
    python scripts/apply_photo_review.py [path\\to\\photo_review_decisions.json]
    # default path: %USERPROFILE%\\Downloads\\photo_review_decisions.json
    python scripts/build_gallery.py
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_CSV = ROOT / "data" / "photo_manifest.csv"
FLAGS_CSV = ROOT / "data" / "flag_locations.csv"
EDITS_CSV = ROOT / "data" / "photo_edits.csv"
PHOTOS_DIR = ROOT / "photos"

MANIFEST_FIELDS = [
    "filename",
    "category",
    "datetime",
    "lat",
    "lon",
    "suggested_location",
    "final_location",
    "deleted",
    "source",
]


def load_current_edits():
    if not EDITS_CSV.exists():
        return {}
    with open(EDITS_CSV, newline="", encoding="utf-8") as f:
        return {r["filename"]: r["decision"] for r in csv.DictReader(f)}


def stem_slug(filename):
    import re
    return re.sub(r"[^a-z0-9_-]+", "-", Path(filename).stem.lower()).strip("-")


def apply_quality(data):
    incoming = {}
    for f in data.get("quality", {}).get("approved", []):
        incoming[f] = "approved"
    for f in data.get("quality", {}).get("rejected", []):
        incoming[f] = "rejected"

    current = load_current_edits()
    merged = dict(current)
    merged.update(incoming)

    # decisions whose effective enhancement state changed need re-encoding
    changed = [
        f for f in set(current) | set(incoming)
        if (current.get(f) == "approved") != (merged.get(f) == "approved")
    ]

    with open(EDITS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["filename", "decision"])
        w.writeheader()
        for name in sorted(merged):
            w.writerow({"filename": name, "decision": merged[name]})

    # delete stale outputs so the incremental build re-encodes exactly these
    deleted = 0
    for name in changed:
        for out in PHOTOS_DIR.glob(f"day-*/*/{stem_slug(name)}.jpg"):
            out.unlink()
            deleted += 1

    approved_total = sum(1 for d in merged.values() if d == "approved")
    print(f"Quality decisions on file: {len(merged)} ({approved_total} approved)")
    print(f"Newly changed enhancement state: {len(changed)} photos ({deleted} derived JPGs removed)")


def apply_locations(data):
    locations = data.get("locations", {})
    if not locations:
        print("Location changes: none")
        return

    with open(MANIFEST_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row.setdefault("source", "")

    by_name = {r["filename"]: r for r in rows}
    updated = 0
    missing = []
    for filename, loc in locations.items():
        row = by_name.get(filename)
        if row is None:
            missing.append(filename)
            continue
        row["final_location"] = loc
        updated += 1

    with open(MANIFEST_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"Location changes applied to manifest: {updated}")
    if missing:
        print(f"WARNING — filenames in the export but not in the manifest: {missing}")

    # Which assigned categories have no flag (pin) yet? Fine for the user's
    # photos (they group by day); a problem for mom's photos ONLY if the
    # category also never appears on the user's own rows (no day to derive).
    with open(FLAGS_CSV, newline="", encoding="utf-8") as f:
        flag_names = {r["name"].strip() for r in csv.DictReader(f)}
    own_locations = {
        (r.get("final_location") or "").strip()
        for r in rows
        if r.get("source") != "moms_phone"
    }
    flagless = sorted(
        {loc for loc in locations.values() if loc and loc != "Ignore"} - flag_names
    )
    if flagless:
        print("\nCategories with no map flag yet (photos group by day only):")
        for loc in flagless:
            dayless = loc not in own_locations
            note = "  <- NO DAY DERIVABLE: mom's photos with this tag stay off the site until a flag or a user photo carries it" if dayless else ""
            print(f"  {loc}{note}")

    reported = [c for c in data.get("new_categories", []) if c]
    if reported:
        print(f"\nBrand-new categories introduced in this export: {reported}")


def main():
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    else:
        src = Path.home() / "Downloads" / "photo_review_decisions.json"
    if not src.exists():
        sys.exit(f"Decisions file not found: {src}\n"
                 "Export it from the review page, or pass its path as an argument.")

    # utf-8-sig: tolerate a BOM (some Windows tools add one; plain UTF-8 is unaffected)
    data = json.loads(src.read_text(encoding="utf-8-sig"))
    apply_quality(data)
    print()
    apply_locations(data)
    print("\nNow run: python scripts/build_gallery.py")


if __name__ == "__main__":
    main()
