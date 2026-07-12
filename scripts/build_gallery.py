"""Convert curated-by-date trip photos into web-ready thumbnails + full images,
organized by itinerary day, and write photos/manifest.json for the site's gallery JS.

Reads data/photo_manifest.csv (written by extract_trip_photos.py), pulls source
files from photos_raw/uk_trip/, and writes JPGs into photos/<day-slug>/thumbs/
and photos/<day-slug>/full/. Only uk_trip photos dated within the 9-day
itinerary window (2026-06-29 to 2026-07-07 inclusive) are included — earlier
prep-day and later post-trip shots don't map to any day section on the site.
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
RAW_DIR = ROOT / "photos_raw" / "uk_trip"
OUT_DIR = ROOT / "photos"
GALLERY_MANIFEST = OUT_DIR / "manifest.json"

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


def save_resized(img, dest, max_dim, quality):
    dest.parent.mkdir(parents=True, exist_ok=True)
    resized = img.copy()
    resized.thumbnail((max_dim, max_dim), Image.LANCZOS)
    resized.save(dest, "JPEG", quality=quality, optimize=True)


def main():
    with open(MANIFEST_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    rows = [r for r in rows if r["category"] == "uk_trip" and r["datetime"][:10] in DAY_SLUGS]
    rows.sort(key=lambda r: r["datetime"])

    print(f"Processing {len(rows)} photos into {OUT_DIR}...")

    gallery = {slug: [] for slug in DAY_SLUGS.values()}
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

        gallery[day_slug].append({"thumb": thumb_rel, "full": full_rel})

        if i % 50 == 0 or i == len(rows):
            print(f"...{i}/{len(rows)} converted")

    GALLERY_MANIFEST.write_text(json.dumps(gallery, indent=2), encoding="utf-8")

    print("\nPer-day counts:")
    for slug, photos in gallery.items():
        print(f"  {slug}: {len(photos)}")

    if failures:
        print(f"\n{len(failures)} failures:")
        for fname, err in failures:
            print(f"  {fname}: {err}")

    print(f"\nGallery manifest written: {GALLERY_MANIFEST}")


if __name__ == "__main__":
    sys.exit(main())
