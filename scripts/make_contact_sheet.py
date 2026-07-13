"""Generate a one-page HTML contact sheet for photos_raw/pruned_review/.

Purpose (#24): 226 files were quarantined during the iCloud->USB source
switch and need a manual keep-or-discard decision. Browsers can't render
HEIC, so this decodes each file to a small JPEG thumb (incremental +
parallel, same pattern as build_gallery.py) and writes a date-grouped
contact sheet next to them. 5-July files get a badge as possible missing
Dishoom Cambridge shots (#48).

Everything stays inside the gitignored photos_raw/ tree — the sheet is a
local review tool, never published.

To rescue a photo: copy it back into photos_raw/uk_trip (or dc_reunion)
and re-run extract_trip_photos.py — it's adopted automatically (#61).

Usage:
    python scripts/make_contact_sheet.py
    # then open http://localhost:8123/photos_raw/pruned_review/contact_sheet.html
"""

import html
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import pillow_heif
from PIL import ExifTags, Image, ImageOps

pillow_heif.register_heif_opener()

ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = ROOT / "photos_raw" / "pruned_review"
THUMBS_DIR = REVIEW_DIR / "_thumbs"
OUT_HTML = REVIEW_DIR / "contact_sheet.html"

THUMB_MAX = 320
THUMB_QUALITY = 80
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}
TAG_DATETIME_ORIGINAL = 36867
DISHOOM_CANDIDATE_DATE = "2026-07-05"


def photo_datetime(path):
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            dt_raw = exif.get_ifd(ExifTags.IFD.Exif).get(TAG_DATETIME_ORIGINAL) or exif.get(TAG_DATETIME_ORIGINAL)
        if dt_raw:
            return datetime.strptime(dt_raw, "%Y:%m:%d %H:%M:%S"), "exif"
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime), "mtime"


def make_thumb(task):
    src, dest = task
    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return (src.name, None)
    except Exception as e:
        return (src.name, str(e))


def main():
    entries = []   # (subdir, path, dt, dt_source)
    other_files = []
    for sub in ("uk_trip", "dc_reunion"):
        d = REVIEW_DIR / sub
        if not d.exists():
            continue
        for path in sorted(d.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                other_files.append((sub, path.name))
                continue
            dt, dt_source = photo_datetime(path)
            entries.append((sub, path, dt, dt_source))

    tasks = []
    for sub, path, _, _ in entries:
        dest = THUMBS_DIR / sub / (path.stem.lower() + ".jpg")
        if not dest.exists() or dest.stat().st_mtime <= path.stat().st_mtime:
            tasks.append((path, dest))
    print(f"{len(entries)} photos ({len(entries) - len(tasks)} thumbs up to date, {len(tasks)} to make)")

    failures = {}
    if tasks:
        workers = max(1, (os.cpu_count() or 2) - 1)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, (name, err) in enumerate(pool.map(make_thumb, tasks, chunksize=4), 1):
                if err:
                    failures[name] = err
                if i % 25 == 0 or i == len(tasks):
                    print(f"...{i}/{len(tasks)}")

    by_date = defaultdict(list)
    for sub, path, dt, dt_source in entries:
        if path.name in failures:
            continue
        by_date[dt.date().isoformat()].append((sub, path, dt, dt_source))

    parts = ["""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>pruned_review contact sheet</title>
<style>
  body { background:#14161b; color:#e8eaf0; font-family:'Helvetica Neue',Arial,sans-serif; margin:0; padding:24px; }
  h1 { font-family:Georgia,serif; font-weight:normal; font-size:26px; }
  .note { color:#9aa0ae; max-width:75ch; font-size:14px; line-height:1.5; }
  .note code { background:#22252e; padding:1px 5px; border-radius:4px; }
  h2 { font-family:Georgia,serif; font-weight:normal; font-size:19px; border-top:1px solid #2a2f3d;
       padding-top:20px; margin-top:28px; }
  .badge { display:inline-block; background:#7c3a2e; color:#ffd9cf; font-size:11px; font-weight:700;
           border-radius:99px; padding:2px 10px; margin-left:10px; vertical-align:3px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:10px; margin-top:12px; }
  figure { margin:0; background:#1a1e28; border:1px solid #2a2f3d; border-radius:8px; padding:6px; }
  img { width:100%; aspect-ratio:1/1; object-fit:cover; border-radius:5px; display:block; }
  figcaption { font-size:11px; color:#9aa0ae; padding:6px 2px 2px; word-break:break-all; }
  figcaption b { color:#c9a84c; font-weight:600; }
  .mtime { color:#6b7585; font-style:italic; }
</style></head><body>
<h1>pruned_review — keep or discard?</h1>
<p class="note">Every photo below fell out of the manifest during the iCloud → USB source switch (#24).
For each one: if it was deleted on purpose, do nothing. If you want it back, copy the file from
<code>photos_raw/pruned_review/&lt;folder&gt;/</code> into <code>photos_raw/uk_trip/</code> (or <code>dc_reunion/</code>)
— the next <code>extract_trip_photos.py</code> run adopts it automatically. Photos from
<b>5 July</b> are flagged as possible missing Dishoom Cambridge shots (#48).</p>
"""]
    for date in sorted(by_date):
        items = sorted(by_date[date], key=lambda e: e[2])
        badge = '<span class="badge">possible Dishoom Cambridge — #48</span>' if date == DISHOOM_CANDIDATE_DATE else ""
        parts.append(f"<h2>{date} · {len(items)} photo{'s' if len(items) != 1 else ''}{badge}</h2>\n<div class='grid'>")
        for sub, path, dt, dt_source in items:
            thumb = f"_thumbs/{sub}/{path.stem.lower()}.jpg"
            time_html = dt.strftime("%H:%M") if dt_source == "exif" else f"<span class='mtime'>{dt.strftime('%H:%M')} (mtime)</span>"
            parts.append(
                f"<figure><img src='{thumb}' loading='lazy' alt=''>"
                f"<figcaption><b>{html.escape(path.name)}</b> · {sub} · {time_html}</figcaption></figure>"
            )
        parts.append("</div>")

    if other_files:
        parts.append(f"<h2>Non-image files ({len(other_files)}) — not previewable here</h2><p class='note'>")
        parts.append("<br>".join(f"{html.escape(n)} ({s})" for s, n in other_files))
        parts.append("</p>")
    if failures:
        parts.append(f"<h2>Failed to decode ({len(failures)})</h2><p class='note'>")
        parts.append("<br>".join(f"{html.escape(k)}: {html.escape(v)}" for k, v in failures.items()))
        parts.append("</p>")

    parts.append("</body></html>")
    OUT_HTML.write_text("\n".join(parts), encoding="utf-8")

    print(f"\nDates: {len(by_date)} | photos: {sum(len(v) for v in by_date.values())} | other files: {len(other_files)} | failures: {len(failures)}")
    dishoom = len(by_date.get(DISHOOM_CANDIDATE_DATE, []))
    print(f"5-July (Dishoom candidates): {dishoom}")
    print(f"Contact sheet: {OUT_HTML}")


if __name__ == "__main__":
    main()
