"""Convert curated-by-date trip photos into web-ready thumbnails + full images,
organized by itinerary day, and write photos/manifest.json for the site's gallery JS.

Reads data/photo_manifest.csv (written by extract_trip_photos.py), pulls source
files from photos_raw/uk_trip/, and writes JPGs into photos/<day-slug>/thumbs/
and photos/<day-slug>/full/. Only uk_trip photos dated within the 9-day
itinerary window (2026-06-29 to 2026-07-07 inclusive) are included — earlier
prep-day and later post-trip shots don't map to any day section on the site.

Re-run safe: also prunes any thumb/full JPG under photos/ that no longer
corresponds to a manifest row, so photos deleted upstream (iPhone/iCloud)
drop out of the gallery on the next run instead of lingering.

Rows with final_location == "Ignore" are skipped entirely (kept, worth
keeping, just not interesting enough to publish) — distinct from deleted,
which means physically removed from photos_raw/uk_trip.
"""

import csv
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_CSV = ROOT / "data" / "photo_manifest.csv"
FLAGS_CSV = ROOT / "data" / "flag_locations.csv"
RAW_DIR = ROOT / "photos_raw" / "uk_trip"
OUT_DIR = ROOT / "photos"
GALLERY_MANIFEST = OUT_DIR / "manifest.json"
INDEX_HTML = ROOT / "index.html"
START_MARKER = "/*GALLERY_DATA*/"
END_MARKER = "/*END_GALLERY_DATA*/"
LOC_START_MARKER = "/*GALLERY_BY_LOCATION*/"
LOC_END_MARKER = "/*END_GALLERY_BY_LOCATION*/"

THUMB_MAX = 400
THUMB_QUALITY = 78
FULL_MAX = 1600
FULL_QUALITY = 75

DAY_SLUGS = {
    "2026-06-29": "day-29-jun",
    "2026-06-30": "day-30-jun",
    "2026-07-01": "day-01-jul",
    "2026-07-02": "day-02-jul",
    "2026-07-03": "day-03-jul",
    "2026-07-04": "day-04-jul",
    "2026-07-05": "day-05-jul",
    "2026-07-06": "day-06-jul",
    "2026-07-07": "day-07-jul",
}


def load_name_to_location_id():
    with open(FLAGS_CSV, newline="", encoding="utf-8") as f:
        return {row["name"].strip(): row["location_id"] for row in csv.DictReader(f)}


def inject(html, start_marker, end_marker, data):
    if start_marker not in html or end_marker not in html:
        raise RuntimeError(f"Could not find {start_marker} / {end_marker} markers in index.html")
    json_str = json.dumps(data, separators=(",", ":"))
    start_idx = html.index(start_marker) + len(start_marker)
    end_idx = html.index(end_marker)
    return html[:start_idx] + json_str + html[end_idx:]


def update_index_html(gallery, gallery_by_location):
    """Inline the gallery data into index.html so the page doesn't depend on a
    fetch() at runtime — fetch() of a local file is blocked under file://,
    which breaks the gallery when previewed outside a real HTTP server."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    html = inject(html, START_MARKER, END_MARKER, gallery)
    html = inject(html, LOC_START_MARKER, LOC_END_MARKER, gallery_by_location)
    INDEX_HTML.write_text(html, encoding="utf-8")


def save_resized(img, dest, max_dim, quality):
    dest.parent.mkdir(parents=True, exist_ok=True)
    resized = img.copy()
    resized.thumbnail((max_dim, max_dim), Image.LANCZOS)
    resized.save(dest, "JPEG", quality=quality, optimize=True)


def main():
    with open(MANIFEST_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    rows = [
        r
        for r in rows
        if r["category"] == "uk_trip"
        and r["datetime"][:10] in DAY_SLUGS
        and r.get("deleted") != "true"
        and r.get("final_location", "").strip() != "Ignore"
    ]
    rows.sort(key=lambda r: r["datetime"])

    print(f"Processing {len(rows)} photos into {OUT_DIR}...")

    name_to_location_id = load_name_to_location_id()

    gallery = {slug: [] for slug in DAY_SLUGS.values()}
    gallery_by_location = {}
    failures = []

    for i, row in enumerate(rows, 1):
        src = RAW_DIR / row["filename"]
        day_slug = DAY_SLUGS[row["datetime"][:10]]
        stem = Path(row["filename"]).stem.lower()

        thumb_rel = f"{day_slug}/thumbs/{stem}.jpg"
        full_rel = f"{day_slug}/full/{stem}.jpg"

        try:
            with Image.open(src) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                save_resized(img, OUT_DIR / thumb_rel, THUMB_MAX, THUMB_QUALITY)
                save_resized(img, OUT_DIR / full_rel, FULL_MAX, FULL_QUALITY)
        except Exception as e:
            failures.append((row["filename"], str(e)))
            continue

        photo_entry = {"thumb": thumb_rel, "full": full_rel}
        gallery[day_slug].append(photo_entry)

        # final_location (user-confirmed) wins over suggested_location
        # (Claude's guess); photos with neither just stay day-grouped.
        # Hand-typed CSV values are prone to stray leading/trailing
        # whitespace, so strip before matching against flag names.
        location_name = (row.get("final_location") or "").strip() or (row.get("suggested_location") or "").strip()
        location_id = name_to_location_id.get(location_name) if location_name else None
        if location_id:
            gallery_by_location.setdefault(location_id, []).append(photo_entry)

        if i % 50 == 0 or i == len(rows):
            print(f"...{i}/{len(rows)} converted")

    expected_rel_paths = set()
    for photos in gallery.values():
        for p in photos:
            expected_rel_paths.add(p["thumb"])
            expected_rel_paths.add(p["full"])

    pruned = 0
    if OUT_DIR.exists():
        for existing_file in OUT_DIR.rglob("*.jpg"):
            rel = str(existing_file.relative_to(OUT_DIR)).replace("\\", "/")
            if rel not in expected_rel_paths:
                existing_file.unlink()
                pruned += 1

    GALLERY_MANIFEST.write_text(json.dumps(gallery, indent=2), encoding="utf-8")
    update_index_html(gallery, gallery_by_location)

    print("\nPer-day counts:")
    for slug, photos in gallery.items():
        print(f"  {slug}: {len(photos)}")

    assigned = sum(len(p) for p in gallery_by_location.values())
    print(f"\nGrouped by location: {assigned}/{len(rows) - len(failures)} photos across {len(gallery_by_location)} locations")

    if failures:
        print(f"\n{len(failures)} failures:")
        for fname, err in failures:
            print(f"  {fname}: {err}")

    print(f"\nPruned (no longer in manifest, removed from photos/): {pruned}")
    print(f"Gallery manifest written: {GALLERY_MANIFEST}")
    print(f"index.html gallery data updated in place")


if __name__ == "__main__":
    sys.exit(main())
