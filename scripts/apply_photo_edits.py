"""Apply exported photo-edit decisions to the site.

Reads the photo_edit_decisions.json downloaded from the review page
(make_edit_review.py), merges it into data/photo_edits.csv (the durable
record build_gallery.py consults), and deletes the derived JPGs of every
photo whose decision CHANGED so the next build re-encodes them — with the
enhancement for newly approved photos, without it for newly un-approved ones.

Run build_gallery.py afterwards to actually re-encode; only the changed
photos get processed thanks to the incremental build.

Usage:
    python scripts/apply_photo_edits.py [path\\to\\photo_edit_decisions.json]
    # default path: %USERPROFILE%\\Downloads\\photo_edit_decisions.json
    python scripts/build_gallery.py
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITS_CSV = ROOT / "data" / "photo_edits.csv"
PHOTOS_DIR = ROOT / "photos"


def load_current():
    if not EDITS_CSV.exists():
        return {}
    with open(EDITS_CSV, newline="", encoding="utf-8") as f:
        return {r["filename"]: r["decision"] for r in csv.DictReader(f)}


def main():
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    else:
        src = Path.home() / "Downloads" / "photo_edit_decisions.json"
    if not src.exists():
        sys.exit(f"Decisions file not found: {src}\n"
                 "Export it from the review page, or pass its path as an argument.")

    data = json.loads(src.read_text(encoding="utf-8"))
    incoming = {}
    for f in data.get("approved", []):
        incoming[f] = "approved"
    for f in data.get("rejected", []):
        incoming[f] = "rejected"

    current = load_current()
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
        stem = Path(name).stem.lower()
        for out in PHOTOS_DIR.glob(f"day-*/*/{stem}.jpg"):
            out.unlink()
            deleted += 1

    approved_total = sum(1 for d in merged.values() if d == "approved")
    print(f"Decisions on file: {len(merged)} ({approved_total} approved)")
    print(f"Newly changed enhancement state: {len(changed)} photos ({deleted} derived JPGs removed)")
    print("Now run: python scripts/build_gallery.py")


if __name__ == "__main__":
    main()
