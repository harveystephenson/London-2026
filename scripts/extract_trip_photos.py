"""
Scan the iCloud Photos download folder, pull EXIF date/GPS from each image,
and sort matches into photos_raw/uk_trip and photos_raw/dc_reunion.

Re-run safe: skips files already recorded in the manifest, and a cheap
filesystem-mtime pre-filter avoids full EXIF decode for files nowhere near
the trip dates (iCloud preserves original capture date as file mtime).
Also moves any photos_raw/uk_trip or photos_raw/dc_reunion file that's no
longer present in the source folder into photos_raw/pruned_review/ (not
deleted — the source folder may simply be an incomplete pull, so these are
kept for manual review rather than lost).

Manual curation: deleting a file directly from photos_raw/uk_trip or
photos_raw/dc_reunion (not the source dump) is treated as an intentional
edit — the manifest row is kept but marked deleted=true, and is never
re-copied back in from the source on a later run.

Usage:
    python scripts/extract_trip_photos.py
"""

import csv
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pillow_heif
from PIL import ExifTags, Image

pillow_heif.register_heif_opener()

# Temporarily sourcing from a manual USB import (photos_raw/iphone) instead of
# the iCloud sync folder — iCloud Photos sync got stuck/paused mid-trip and
# was missing the Cotswolds/Cambridge/Mon-6-Jul days entirely. Switch back to
# the iCloud folder (C:\Users\harve\iCloudPhotos\Photos) once sync is fixed.
SOURCE_DIR = Path(__file__).resolve().parent.parent / "photos_raw" / "iphone"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEST_UK = REPO_ROOT / "photos_raw" / "uk_trip"
DEST_DC = REPO_ROOT / "photos_raw" / "dc_reunion"
REVIEW_UK = REPO_ROOT / "photos_raw" / "pruned_review" / "uk_trip"
REVIEW_DC = REPO_ROOT / "photos_raw" / "pruned_review" / "dc_reunion"
MANIFEST_PATH = REPO_ROOT / "data" / "photo_manifest.csv"

# Padded a day on each side of the known travel dates to avoid clipping
# photos taken late at night / during the flight where the camera's local
# date might be ambiguous. Trip: left DC 2026-06-28, landed Heathrow
# 2026-06-29, left UK 2026-07-07.
UK_TRIP_START = date(2026, 6, 27)
UK_TRIP_END = date(2026, 7, 8)

# Rania restaurant, DC, mom stayed behind — 2026-07-10.
DC_REUNION_START = date(2026, 7, 9)
DC_REUNION_END = date(2026, 7, 11)

# Cheap pre-filter using filesystem mtime (no image decode needed) to skip
# the ~15K-file library down to real candidates before doing expensive HEIC
# EXIF decode. Wider than the actual windows above to give slack in case
# mtime and EXIF DateTimeOriginal drift slightly.
PREFILTER_START = min(UK_TRIP_START, DC_REUNION_START) - timedelta(days=3)
PREFILTER_END = max(UK_TRIP_END, DC_REUNION_END) + timedelta(days=3)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}

PROGRESS_INTERVAL = 500

# Standard EXIF tag IDs (avoids relying on ExifTags.TAGS dict ordering)
TAG_DATETIME_ORIGINAL = 36867
TAG_GPSINFO = 34853
GPS_TAG_LATREF = 1
GPS_TAG_LAT = 2
GPS_TAG_LONREF = 3
GPS_TAG_LON = 4


def dms_to_decimal(dms, ref):
    degrees, minutes, seconds = (float(v) for v in dms)
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def read_exif(path):
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None, None, None
            exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:
        return None, None, None

    dt_raw = exif_ifd.get(TAG_DATETIME_ORIGINAL) or exif.get(TAG_DATETIME_ORIGINAL)
    photo_date = None
    if dt_raw:
        try:
            photo_date = datetime.strptime(dt_raw, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            photo_date = None

    lat = lon = None
    if gps_ifd:
        try:
            lat = dms_to_decimal(gps_ifd[GPS_TAG_LAT], gps_ifd[GPS_TAG_LATREF])
            lon = dms_to_decimal(gps_ifd[GPS_TAG_LON], gps_ifd[GPS_TAG_LONREF])
        except (KeyError, TypeError, ZeroDivisionError):
            lat = lon = None

    return photo_date, lat, lon


def mtime_in_prefilter_range(path):
    mtime_date = datetime.fromtimestamp(path.stat().st_mtime).date()
    return PREFILTER_START <= mtime_date <= PREFILTER_END


def load_existing_manifest():
    if not MANIFEST_PATH.exists():
        return {}
    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        return {row["filename"]: row for row in csv.DictReader(f)}


def main():
    DEST_UK.mkdir(parents=True, exist_ok=True)
    DEST_DC.mkdir(parents=True, exist_ok=True)
    REVIEW_UK.mkdir(parents=True, exist_ok=True)
    REVIEW_DC.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing = load_existing_manifest()
    rows = []
    scanned = 0
    prefiltered_out = 0
    reused = 0
    no_exif_date = 0
    matched_uk = 0
    matched_dc = 0
    deleted_skipped = 0
    newly_deleted = 0

    all_paths = sorted(SOURCE_DIR.iterdir())
    total = len(all_paths)

    for i, path in enumerate(all_paths, start=1):
        if i % PROGRESS_INTERVAL == 0:
            print(f"...{i}/{total} scanned ({len(rows)} matched so far)")

        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        scanned += 1

        existing_row = existing.get(path.name)
        if existing_row:
            dest = DEST_UK if existing_row["category"] == "uk_trip" else DEST_DC
            dest_path = dest / path.name
            if existing_row.get("deleted") == "true":
                # User already deleted this from the curated folder — never
                # resurrect it from the raw source dump.
                rows.append(existing_row)
                reused += 1
                deleted_skipped += 1
                continue
            if not dest_path.exists():
                # Missing from the curated folder but not yet marked deleted
                # means the user just deleted it manually this session.
                existing_row["deleted"] = "true"
                rows.append(existing_row)
                reused += 1
                deleted_skipped += 1
                newly_deleted += 1
                continue
            rows.append(existing_row)
            reused += 1
            if existing_row["category"] == "uk_trip":
                matched_uk += 1
            else:
                matched_dc += 1
            continue

        if not mtime_in_prefilter_range(path):
            prefiltered_out += 1
            continue

        photo_dt, lat, lon = read_exif(path)
        if photo_dt is None:
            no_exif_date += 1
            continue

        photo_date = photo_dt.date()
        category = None
        if UK_TRIP_START <= photo_date <= UK_TRIP_END:
            category = "uk_trip"
            dest = DEST_UK / path.name
            matched_uk += 1
        elif DC_REUNION_START <= photo_date <= DC_REUNION_END:
            category = "dc_reunion"
            dest = DEST_DC / path.name
            matched_dc += 1
        else:
            continue

        if not dest.exists():
            shutil.copy2(path, dest)

        rows.append(
            {
                "filename": path.name,
                "category": category,
                "datetime": photo_dt.isoformat(),
                "lat": lat if lat is not None else "",
                "lon": lon if lon is not None else "",
                "location_name": "",
                "deleted": "",
            }
        )

    rows.sort(key=lambda r: r["datetime"])
    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["filename", "category", "datetime", "lat", "lon", "location_name", "deleted"],
        )
        writer.writeheader()
        writer.writerows(rows)

    expected_uk = {r["filename"] for r in rows if r["category"] == "uk_trip"}
    expected_dc = {r["filename"] for r in rows if r["category"] == "dc_reunion"}
    pruned = 0
    for dest_dir, review_dir, expected in (
        (DEST_UK, REVIEW_UK, expected_uk),
        (DEST_DC, REVIEW_DC, expected_dc),
    ):
        for existing_file in dest_dir.iterdir():
            if existing_file.is_file() and existing_file.name not in expected:
                shutil.move(str(existing_file), str(review_dir / existing_file.name))
                pruned += 1

    print(f"Total files:      {total}")
    print(f"Image files:      {scanned}")
    print(f"Reused from prior manifest: {reused}")
    print(f"Marked deleted (removed from photos_raw/uk_trip or dc_reunion by user): {deleted_skipped} ({newly_deleted} new this run)")
    print(f"Skipped by mtime prefilter: {prefiltered_out}")
    print(f"No EXIF date:     {no_exif_date}")
    print(f"Matched UK trip:  {matched_uk}")
    print(f"Matched DC:       {matched_dc}")
    print(f"Moved to photos_raw/pruned_review/ (not in current source): {pruned}")
    print(f"Manifest written: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
