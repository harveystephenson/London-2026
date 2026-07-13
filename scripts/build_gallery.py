"""Convert curated-by-date trip photos into web-ready thumbnails + full images,
organized by itinerary day, and write photos/manifest.json for the site's gallery JS.

Reads data/photo_manifest.csv (written by extract_trip_photos.py), pulls source
files from photos_raw/uk_trip/ (or photos_raw/dc_reunion/ for dc_reunion rows),
and writes JPGs into photos/<day-slug>/thumbs/ and photos/<day-slug>/full/.
Only photos dated on a DAY_SLUGS day are included: the 9-day UK itinerary
window (2026-06-29 to 2026-07-07) plus the 2026-07-10 DC reunion postscript —
earlier prep-day and other out-of-window shots don't map to any day section.

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

Mom's photos (source=moms_phone, from photos_raw/moms_phone) have no usable
datetime — WhatsApp strips EXIF and their file dates are the send time. Their
day comes from the user-assigned location instead: the location's flag day,
or failing that the day the user's own photos with that same final_location
fall on. Rows whose location hasn't been assigned (or can't be mapped to a
day) are skipped and counted, and they sort after the user's photos within
their day.
"""

import argparse
import csv
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps
import pillow_heif

from photo_enhance import enhance

pillow_heif.register_heif_opener()

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_CSV = ROOT / "data" / "photo_manifest.csv"
FLAGS_CSV = ROOT / "data" / "flag_locations.csv"
RAW_DIR = ROOT / "photos_raw" / "uk_trip"
RAW_DC_DIR = ROOT / "photos_raw" / "dc_reunion"
RAW_MOMS_DIR = ROOT / "photos_raw" / "moms_phone"
# filename,decision rows written by apply_photo_edits.py; photos whose
# decision is "approved" get photo_enhance.enhance() applied at encode time,
# so approvals survive any rebuild (including --force).
EDITS_CSV = ROOT / "data" / "photo_edits.csv"
# filename,role,day,location_id,sort — written by apply_featured_photos.py
# from the make_featured_picker.py export (#47). "filename" holds the
# lowercase SLUG (stem_slug output, e.g. "img_2830"), not the raw manifest
# filename — the picker only has {thumb,full} paths to work from, and slugs
# are already this pipeline's canonical join key. Roles: banner_lead (1),
# banner (up to 4, ordered by sort), day_feature (0-1 per day), item_feature
# (0-1 per schedule-linked location). Unpicked slots fall back automatically
# (see resolve_featured_photos) so a missing/empty CSV never breaks the build.
FEATURED_CSV = ROOT / "data" / "featured_photos.csv"
OUT_DIR = ROOT / "photos"
GALLERY_MANIFEST = OUT_DIR / "manifest.json"
INDEX_HTML = ROOT / "index.html"
START_MARKER = "/*GALLERY_DATA*/"
END_MARKER = "/*END_GALLERY_DATA*/"
LOC_START_MARKER = "/*GALLERY_BY_LOCATION*/"
LOC_END_MARKER = "/*END_GALLERY_BY_LOCATION*/"
BANNER_START_MARKER = "<!--BANNER-->"
BANNER_END_MARKER = "<!--END_BANNER-->"

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
    # DC reunion postscript (category dc_reunion, sourced from photos_raw/dc_reunion)
    "2026-07-10": "day-10-jul",
}


def load_flags():
    """Return (name -> location_id, name -> day slug) from flag_locations.csv."""
    with open(FLAGS_CSV, newline="", encoding="utf-8") as f:
        flags = list(csv.DictReader(f))
    name_to_id = {row["name"].strip(): row["location_id"] for row in flags}
    name_to_day = {row["name"].strip(): row["day"].strip() for row in flags}
    return name_to_id, name_to_day


def stem_slug(filename):
    """URL-safe output stem. Identity for the usual img_1234 names; mom's
    WhatsApp names ("PHOTO-2026-07-08-16-37-12 (3).jpg") get their spaces
    and parens collapsed so photos/ paths stay clean."""
    return re.sub(r"[^a-z0-9_-]+", "-", Path(filename).stem.lower()).strip("-")


def build_location_day_map(rows, flag_days):
    """Map every location name to a day slug: the flag's day where one
    exists, else the modal day of the user's own photos carrying that
    final_location (covers deliberately-flagless names like Heathrow)."""
    by_name = {}
    for r in rows:
        if r.get("source") == "moms_phone":
            continue
        day = DAY_SLUGS.get(r["datetime"][:10])
        name = (r.get("final_location") or "").strip()
        if day and name:
            by_name.setdefault(name, {}).setdefault(day, 0)
            by_name[name][day] += 1
    result = {name: max(days, key=days.get) for name, days in by_name.items()}
    result.update(flag_days)
    return result


def day_slug_for(row, location_days):
    """The day a row belongs to: datetime-derived normally, location-derived
    for mom's photos (their datetimes are WhatsApp send times, meaningless)."""
    if row.get("source") == "moms_phone":
        name = (row.get("final_location") or "").strip()
        return location_days.get(name)
    return DAY_SLUGS.get(row["datetime"][:10])


def load_approved_edits():
    if not EDITS_CSV.exists():
        return set()
    with open(EDITS_CSV, newline="", encoding="utf-8") as f:
        return {row["filename"] for row in csv.DictReader(f) if row.get("decision") == "approved"}


def inject(html, start_marker, end_marker, data):
    if start_marker not in html or end_marker not in html:
        raise RuntimeError(f"Could not find {start_marker} / {end_marker} markers in index.html")
    json_str = json.dumps(data, separators=(",", ":"))
    start_idx = html.index(start_marker) + len(start_marker)
    end_idx = html.index(end_marker)
    return html[:start_idx] + json_str + html[end_idx:]


def inject_html(html, start_marker, end_marker, content, search_from=0):
    start_idx = html.index(start_marker, search_from) + len(start_marker)
    end_idx = html.index(end_marker, start_idx)
    return html[:start_idx] + content + html[end_idx:]


def load_featured_photos():
    """Read data/featured_photos.csv into {role: ...} buckets. Missing file
    (picker never run yet) is treated as empty — everything falls back."""
    banner_lead = None
    banner = []
    day_feature = {}
    item_feature = {}
    if not FEATURED_CSV.exists():
        return banner_lead, banner, day_feature, item_feature
    with open(FEATURED_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            role = row.get("role", "")
            filename = row.get("filename", "")
            if not role or not filename:
                continue
            if role == "banner_lead":
                banner_lead = filename
            elif role == "banner":
                banner.append((int(row.get("sort") or 0), filename))
            elif role == "day_feature" and row.get("day"):
                day_feature[row["day"]] = filename
            elif role == "item_feature" and row.get("location_id"):
                item_feature[row["location_id"]] = filename
    banner = [f for _, f in sorted(banner)]
    return banner_lead, banner, day_feature, item_feature


def resolve_featured_photos(filename_to_paths, gallery, gallery_by_location):
    """Turn the featured_photos.csv picks into actual {thumb,full} paths,
    falling back to sensible defaults for anything unpicked (or picked but
    no longer live, e.g. a since-deleted photo) so the build never breaks:
    banner falls back to the terracotta-mockup seed photos, day_feature to
    that day's first (chronological) photo, item_feature to that location's
    first photo."""
    picked_lead, picked_banner, picked_day, picked_item = load_featured_photos()

    def lookup(filename):
        return filename_to_paths.get(filename) if filename else None

    banner_seed = ["img_2830", "img_3374", "img_2493", "img_3027", "img_2536"]
    lead_paths = lookup(picked_lead) or lookup(banner_seed[0])
    banner_rest = [lookup(f) for f in picked_banner] or []
    banner_rest = [p for p in banner_rest if p] or [lookup(f) for f in banner_seed[1:]]
    banner_resolved = [p for p in ([lead_paths] + banner_rest) if p][:5]

    day_feature_resolved = {}
    for day, photos in gallery.items():
        explicit = lookup(picked_day.get(day))
        if explicit:
            day_feature_resolved[day] = explicit
        elif photos:
            day_feature_resolved[day] = photos[0]

    item_feature_resolved = {}
    for location_id, photos in gallery_by_location.items():
        explicit = lookup(picked_item.get(location_id))
        if explicit:
            item_feature_resolved[location_id] = explicit
        elif photos:
            item_feature_resolved[location_id] = photos[0]

    return banner_resolved, day_feature_resolved, item_feature_resolved


PHOTO_V_RE = re.compile(r"const PHOTO_V = '([^']*)';")


def read_photo_v(html):
    """Read the cache-busting query string (e.g. "?v=2") straight out of
    index.html's own JS constant, so the banner/day/item images built here
    stay in sync with the gallery/lightbox images without duplicating the
    value in two places — bump PHOTO_V in index.html, both paths pick it up."""
    m = PHOTO_V_RE.search(html)
    return m.group(1) if m else "?v=2"


def update_banner(html, banner_resolved, photo_v):
    if BANNER_START_MARKER not in html or BANNER_END_MARKER not in html:
        raise RuntimeError(f"Could not find {BANNER_START_MARKER} / {BANNER_END_MARKER} markers in index.html")
    imgs = []
    for i, photo in enumerate(banner_resolved):
        src = photo["full"] if i == 0 else photo["thumb"]
        imgs.append(f'<img src="photos/{src}{photo_v}" alt="" loading="eager">')
    return inject_html(html, BANNER_START_MARKER, BANNER_END_MARKER, "".join(imgs))


def update_day_features(html, day_feature_resolved, photo_v):
    for day, photo in day_feature_resolved.items():
        start_marker = f"<!--DAYFEATURE:{day}-->"
        end_marker = "<!--END_DAYFEATURE-->"
        if start_marker not in html:
            continue
        img = f'<img src="photos/{photo["thumb"]}{photo_v}" alt="" loading="lazy">'
        start_idx = html.index(start_marker)
        html = inject_html(html, start_marker, end_marker, img, search_from=start_idx)
    return html


ITEM_PHOTO_CELL_RE = re.compile(r'<td class="item-photo">.*?</td>', re.DOTALL)
LOC_ROW_RE = re.compile(r'(<tr id="loc-([a-z0-9_-]+)">)(.*?)(</tr>)', re.DOTALL)


def update_item_photos(html, item_feature_resolved, photo_v):
    def repl(m):
        open_tag, location_id, body, close_tag = m.groups()
        body = ITEM_PHOTO_CELL_RE.sub("", body)
        photo = item_feature_resolved.get(location_id)
        if photo:
            body += (
                f'<td class="item-photo"><a href="#" '
                f"onclick=\"openLocationGrid('{location_id}');return false;\">"
                f'<img src="photos/{photo["thumb"]}{photo_v}" alt="" loading="lazy"></a></td>'
            )
        return open_tag + body + close_tag

    return LOC_ROW_RE.sub(repl, html)


def update_index_html(gallery, gallery_by_location, banner_resolved, day_feature_resolved, item_feature_resolved):
    """Inline the gallery + featured-photo data into index.html so the page
    doesn't depend on a fetch() at runtime — fetch() of a local file is
    blocked under file://, which breaks the gallery when previewed outside
    a real HTTP server."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    html = inject(html, START_MARKER, END_MARKER, gallery)
    html = inject(html, LOC_START_MARKER, LOC_END_MARKER, gallery_by_location)
    photo_v = read_photo_v(html)
    html = update_banner(html, banner_resolved, photo_v)
    html = update_day_features(html, day_feature_resolved, photo_v)
    html = update_item_photos(html, item_feature_resolved, photo_v)
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
    src, thumb_dest, full_dest, do_enhance = task
    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((FULL_MAX, FULL_MAX), Image.LANCZOS)
            if do_enhance:
                img = enhance(img)
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
        if r["category"] in ("uk_trip", "dc_reunion")
        and r.get("deleted") != "true"
        and r.get("final_location", "").strip() != "Ignore"
    ]

    name_to_location_id, flag_days = load_flags()
    location_days = build_location_day_map(rows, flag_days)

    placed = []
    moms_unplaced = 0
    for r in rows:
        day = day_slug_for(r, location_days)
        if day is None:
            # Out-of-window shots (prep days etc.), or mom's photos whose
            # location hasn't been assigned / mapped to a day yet.
            if r.get("source") == "moms_phone":
                moms_unplaced += 1
            continue
        r["_day"] = day
        placed.append(r)
    rows = placed
    # Mom's photos sort after the user's within each day regardless of what
    # their (meaningless, send-time) datetimes happen to be.
    rows.sort(key=lambda r: (r.get("source") == "moms_phone", r["datetime"], r["filename"]))

    force = args.force
    if not force and settings_changed():
        print("Size/quality settings changed since last run — full rebuild.")
        force = True

    approved_edits = load_approved_edits()

    # Plan: decide per photo whether the existing JPGs can be reused, so a
    # data-only run (retagged locations, flag edits) skips image work entirely.
    # Note: a changed edit DECISION doesn't change any mtime — apply_photo_edits.py
    # deletes the affected outputs so they show up as missing here.
    tasks = []
    seen_rel = {}
    for row in rows:
        if row.get("source") == "moms_phone":
            src_dir = RAW_MOMS_DIR
        else:
            src_dir = RAW_DIR if row["category"] == "uk_trip" else RAW_DC_DIR
        src = src_dir / row["filename"]
        day_slug = row["_day"]
        stem = stem_slug(row["filename"])
        row["_thumb_rel"] = f"{day_slug}/thumbs/{stem}.jpg"
        row["_full_rel"] = f"{day_slug}/full/{stem}.jpg"
        # Slugging could theoretically collapse two filenames onto one output
        # path — fail loudly rather than silently overwrite.
        if row["_full_rel"] in seen_rel:
            raise RuntimeError(
                f"Output path collision: {row['filename']} and "
                f"{seen_rel[row['_full_rel']]} both map to {row['_full_rel']}"
            )
        seen_rel[row["_full_rel"]] = row["filename"]
        thumb_path = OUT_DIR / row["_thumb_rel"]
        full_path = OUT_DIR / row["_full_rel"]
        if force or not is_up_to_date(src, thumb_path, full_path):
            tasks.append((src, thumb_path, full_path, row["filename"] in approved_edits))

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

    gallery = {slug: [] for slug in DAY_SLUGS.values()}
    gallery_by_location = {}
    filename_to_paths = {}
    failures = []

    for row in rows:
        if row["filename"] in failed_names:
            failures.append((row["filename"], failed_names[row["filename"]]))
            continue

        day_slug = row["_day"]
        photo_entry = {"thumb": row["_thumb_rel"], "full": row["_full_rel"]}
        gallery[day_slug].append(photo_entry)
        # Keyed by slug, not the raw manifest filename: that's what the
        # featured-photo picker's candidate grid exports (it only has
        # {thumb,full} paths to work from, not original filenames), and
        # slugs are already the pipeline's canonical, collision-checked
        # join key (see stem_slug / the seen_rel guard above).
        filename_to_paths[stem_slug(row["filename"])] = photo_entry

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

    banner_resolved, day_feature_resolved, item_feature_resolved = resolve_featured_photos(
        filename_to_paths, gallery, gallery_by_location
    )

    GALLERY_MANIFEST.write_text(json.dumps(gallery, indent=2), encoding="utf-8")
    SETTINGS_STAMP.write_text(json.dumps(current_settings(), indent=2), encoding="utf-8")
    update_index_html(gallery, gallery_by_location, banner_resolved, day_feature_resolved, item_feature_resolved)

    print("\nPer-day counts:")
    for slug, photos in gallery.items():
        print(f"  {slug}: {len(photos)}")

    assigned = sum(len(p) for p in gallery_by_location.values())
    print(f"\nGrouped by location: {assigned}/{len(rows) - len(failures)} photos across {len(gallery_by_location)} locations")
    if moms_unplaced:
        print(f"Mom's photos awaiting a location (not on the site yet): {moms_unplaced}")

    if failures:
        print(f"\n{len(failures)} failures:")
        for fname, err in failures:
            print(f"  {fname}: {err}")

    print(f"\nPruned (no longer in manifest, removed from photos/): {pruned}")
    print(f"Gallery manifest written: {GALLERY_MANIFEST}")
    print(f"index.html gallery data updated in place")


if __name__ == "__main__":
    sys.exit(main())
