"""
Scan the iCloud Photos download folder, pull EXIF date/GPS from each image,
and sort matches into photos_raw/uk_trip and photos_raw/dc_reunion.

Re-run safe: skips files already copied to the destination.

Usage:
    python scripts/extract_trip_photos.py
"""

import csv
import shutil
from datetime import date, datetime
from pathlib import Path

import pillow_heif
from PIL import ExifTags, Image

pillow_heif.register_heif_opener()

SOURCE_DIR = Path(r"C:\Users\harve\iCloudPhotos\Photos")
REPO_ROOT = Path(__file__).resolve().parent.parent
DEST_UK = REPO_ROOT / "photos_raw" / "uk_trip"
DEST_DC = REPO_ROOT / "photos_raw" / "dc_reunion"
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

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}

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


def main():
    DEST_UK.mkdir(parents=True, exist_ok=True)
    DEST_DC.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    scanned = 0
    no_exif_date = 0
    matched_uk = 0
    matched_dc = 0

    for path in sorted(SOURCE_DIR.iterdir()):
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        scanned += 1

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
            }
        )

    rows.sort(key=lambda r: r["datetime"])
    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["filename", "category", "datetime", "lat", "lon", "location_name"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Scanned:          {scanned}")
    print(f"No EXIF date:     {no_exif_date}")
    print(f"Matched UK trip:  {matched_uk}")
    print(f"Matched DC:       {matched_dc}")
    print(f"Manifest written: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
