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

Incremental: a photo whose thumb and full JPGs already exist and are newer
than the source file is not re-decoded — its gallery entry is built from
paths alone. Data-only runs (final_location edits, flag changes) therefore
finish in seconds instead of re-encoding ~1,400 JPGs, and OneDrive has no
rewritten files to re-upload. The size/quality settings are stamped into
photos/.build_settings.json; changing them triggers a full rebuild, as does
passing --force. Photos that do need pixel work are processed in parallel
(HEIC decode is CPU-bound), and the thumb is resized from the 1600px full
image rather than the ~12MP original to halve the resize cost.

Rows with final_location == "Ignore" are skipped entirely (kept, worth
keeping, just not interesting enough to publish) — distinct from deleted,
which means physically removed from photos_raw/uk_trip.
"""

import argparse
import csv
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
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

# Written after each run; a mismatch with the constants above means existing
# JPGs were built with different settings and the mtime skip must not apply.
SETTINGS_STAMP = OUT_DIR / ".build_settings.json"

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


def current_settings():
    return {
        "thumb_max": THUMB_MAX,
        "thumb_quality": THUMB_QUALITY,
        "full_max": FULL_MAX,
        "full_quality": FULL_QUALITY,
    }


def settings_changed():
    # A missing stamp is treated as matching: the stamp only started existing
    # after the incremental rebuild landed, and the outputs on disk at that
    # point were built with the current constants. An unreadable stamp is
    # treated as changed (rebuild rather than trust stale JPGs).
    if not SETTINGS_STAMP.exists():
        return False
    try:
        return json.loads(SETTINGS_STAMP.read_text(encoding="utf-8")) != current_settings()
    except (OSError, ValueError):
        return True


def is_up_to_date(src, thumb_path, full_path):
    try:
        src_mtime = src.stat().st_mtime
        return (
            thumb_path.stat().st_mtime > src_mtime
            and full_path.stat().st_mtime > src_mtime
        )
    except OSError:
        # Any of the three missing (or unreadable) means it needs processing;
        # a missing source will surface as a failure there, same as before.
        return False


def process_photo(task):
    """Decode one source photo and write its full + thumb JPGs.

    Runs in a worker process. The thumb is resized from the already-reduced
    full image, not the original — LANCZOS from ~12MP twice was nearly half
    the per-photo CPU cost for an identical-looking 400px result.
    """
    src, thumb_dest, full_dest = task
    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((FULL_MAX, FULL_MAX), Image.LANCZOS)
            full_dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(full_dest, "JPEG", quality=FULL_QUALITY, optimize=True)
            img.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
            thumb_dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(thumb_dest, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return (src.name, None)
    except Exception as e:
        return (src.name, str(e))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-process every photo even if its thumb/full JPGs look up to date",
    )
    args = parser.parse_args()

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

    force = args.force
    if not force and settings_changed():
        print("Size/quality settings changed since last run — full rebuild.")
        force = True

    # Plan: decide per photo whether the existing JPGs can be reused, so a
    # data-only run (retagged locations, flag edits) skips image work entirely.
    tasks = []
    for row in rows:
        src = RAW_DIR / row["filename"]
        day_slug = DAY_SLUGS[row["datetime"][:10]]
        stem = Path(row["filename"]).stem.lower()
        row["_thumb_rel"] = f"{day_slug}/thumbs/{stem}.jpg"
        row["_full_rel"] = f"{day_slug}/full/{stem}.jpg"
        thumb_path = OUT_DIR / row["_thumb_rel"]
        full_path = OUT_DIR / row["_full_rel"]
        if force or not is_up_to_date(src, thumb_path, full_path):
            tasks.append((src, thumb_path, full_path))

    print(f"{len(rows)} photos in manifest: {len(rows) - len(tasks)} up to date, {len(tasks)} to process")

    failed_names = {}
    if tasks:
        workers = max(1, (os.cpu_count() or 2) - 1)
        print(f"Converting with {workers} workers...")
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, (name, err) in enumerate(pool.map(process_photo, tasks, chunksize=4), 1):
                if err:
                    failed_names[name] = err
                if i % 25 == 0 or i == len(tasks):
                    print(f"...{i}/{len(tasks)} converted")

    name_to_location_id = load_name_to_location_id()

    gallery = {slug: [] for slug in DAY_SLUGS.values()}
    gallery_by_location = {}
    failures = []

    for row in rows:
        if row["filename"] in failed_names:
            failures.append((row["filename"], failed_names[row["filename"]]))
            continue

        day_slug = DAY_SLUGS[row["datetime"][:10]]
        photo_entry = {"thumb": row["_thumb_rel"], "full": row["_full_rel"]}
        gallery[day_slug].append(photo_entry)

        # final_location (user-confirmed) wins over suggested_location
        # (Claude's guess) whenever it actually matches a known flag.
        # A generic-but-non-blank final_location (e.g. "Cotswolds" before
        # it's broken into specific villages) matches no flag on its own,
        # so fall through to suggested_location rather than dead-ending —
        # it still loses to final_location wherever that resolves.
        # Hand-typed CSV values are prone to stray leading/trailing
        # whitespace, so strip before matching against flag names.
        final_location = (row.get("final_location") or "").strip()
        suggested_location = (row.get("suggested_location") or "").strip()
        location_id = name_to_location_id.get(final_location) or name_to_location_id.get(suggested_location)
        if location_id:
            gallery_by_location.setdefault(location_id, []).append(photo_entry)

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
    SETTINGS_STAMP.write_text(json.dumps(current_settings(), indent=2), encoding="utf-8")
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
