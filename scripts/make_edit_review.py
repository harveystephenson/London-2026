"""Generate enhanced candidates + a before/after approval page.

For every live photo on the site, renders an enhanced 1600px candidate
(photo_enhance.enhance — the exact recipe build_gallery.py applies to
approved photos) into photos_raw/edit_review/<day>/<stem>.jpg, then writes
photos_raw/edit_review/review.html: a side-by-side original-vs-enhanced page
with Approve / Reject buttons.

Decisions live in the browser's localStorage while reviewing (safe to close
and resume). When done, the Export button downloads photo_edit_decisions.json;
feed that to apply_photo_edits.py to make approvals real.

Everything under photos_raw/ is gitignored — this is a local tool.
Incremental: candidates newer than their raw source are not re-rendered.

Usage:
    python scripts/make_edit_review.py
    # open http://localhost:8123/photos_raw/edit_review/review.html
"""

import csv
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

from photo_enhance import enhance

pillow_heif.register_heif_opener()

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_CSV = ROOT / "data" / "photo_manifest.csv"
EDITS_CSV = ROOT / "data" / "photo_edits.csv"
RAW_UK = ROOT / "photos_raw" / "uk_trip"
RAW_DC = ROOT / "photos_raw" / "dc_reunion"
OUT_DIR = ROOT / "photos_raw" / "edit_review"
SCORES_JSON = OUT_DIR / "_scores.json"
OUT_HTML = OUT_DIR / "review.html"

FULL_MAX = 1600
FULL_QUALITY = 75

DAY_SLUGS = {
    "2026-06-29": "day-29-jun", "2026-06-30": "day-30-jun",
    "2026-07-01": "day-01-jul", "2026-07-02": "day-02-jul",
    "2026-07-03": "day-03-jul", "2026-07-04": "day-04-jul",
    "2026-07-05": "day-05-jul", "2026-07-06": "day-06-jul",
    "2026-07-07": "day-07-jul", "2026-07-10": "day-10-jul",
}


def render_candidate(task):
    """Render one enhanced candidate; return (filename, change_score, error)."""
    src, dest = task
    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((FULL_MAX, FULL_MAX), Image.LANCZOS)
            before = img
            after = enhance(img)
            dest.parent.mkdir(parents=True, exist_ok=True)
            after.save(dest, "JPEG", quality=FULL_QUALITY, optimize=True)
            # change score: RMS pixel difference on 64px proxies (0-255 scale)
            a = before.resize((64, 64))
            b = after.resize((64, 64))
            pa, pb = a.tobytes(), b.tobytes()
            score = (sum((x - y) ** 2 for x, y in zip(pa, pb)) / len(pa)) ** 0.5
        return (src.name, round(score, 2), None)
    except Exception as e:
        return (src.name, 0.0, str(e))


def main():
    with open(MANIFEST_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows = [
        r for r in rows
        if r["category"] in ("uk_trip", "dc_reunion")
        and r["datetime"][:10] in DAY_SLUGS
        and r.get("deleted") != "true"
        and r.get("final_location", "").strip() != "Ignore"
    ]
    rows.sort(key=lambda r: r["datetime"])

    scores = {}
    if SCORES_JSON.exists():
        scores = json.loads(SCORES_JSON.read_text(encoding="utf-8"))

    tasks = []
    for r in rows:
        src_dir = RAW_UK if r["category"] == "uk_trip" else RAW_DC
        src = src_dir / r["filename"]
        day = DAY_SLUGS[r["datetime"][:10]]
        stem = Path(r["filename"]).stem.lower()
        r["_day"] = day
        r["_stem"] = stem
        dest = OUT_DIR / day / f"{stem}.jpg"
        if not dest.exists() or dest.stat().st_mtime <= src.stat().st_mtime or r["filename"] not in scores:
            tasks.append((src, dest))

    print(f"{len(rows)} photos ({len(rows) - len(tasks)} candidates up to date, {len(tasks)} to render)")
    failures = {}
    if tasks:
        workers = max(1, (os.cpu_count() or 2) - 1)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, (name, score, err) in enumerate(pool.map(render_candidate, tasks, chunksize=4), 1):
                if err:
                    failures[name] = err
                else:
                    scores[name] = score
                if i % 25 == 0 or i == len(tasks):
                    print(f"...{i}/{len(tasks)}")
        SCORES_JSON.write_text(json.dumps(scores), encoding="utf-8")

    # existing decisions (from a previous apply) pre-populate the page
    decisions = {}
    if EDITS_CSV.exists():
        with open(EDITS_CSV, newline="", encoding="utf-8") as f:
            decisions = {r["filename"]: r["decision"] for r in csv.DictReader(f)}

    cards = []
    for r in rows:
        if r["filename"] in failures:
            continue
        cards.append({
            "file": r["filename"],
            "day": r["_day"],
            "before": f"../../photos/{r['_day']}/full/{r['_stem']}.jpg",
            "after": f"{r['_day']}/{r['_stem']}.jpg",
            "score": scores.get(r["filename"], 0),
            "time": r["datetime"][11:16],
        })

    page = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Photo edit review — approve or reject</title>
<style>
  body { background:#14161b; color:#e8eaf0; font-family:'Helvetica Neue',Arial,sans-serif; margin:0; }
  header { position:sticky; top:0; background:#1a1e28; border-bottom:1px solid #2a2f3d; padding:12px 20px;
           display:flex; gap:14px; align-items:center; flex-wrap:wrap; z-index:10; }
  h1 { font-family:Georgia,serif; font-weight:normal; font-size:18px; margin:0; flex:1; }
  .counts { font-size:13px; color:#9aa0ae; }
  .counts b { color:#c9a84c; }
  select, button.top { background:#22252e; color:#e8eaf0; border:1px solid #3a4050; border-radius:6px;
           padding:6px 12px; font-size:13px; cursor:pointer; }
  button.top.export { background:#c9a84c; color:#14161b; font-weight:700; border-color:#c9a84c; }
  main { max-width:1200px; margin:0 auto; padding:20px; }
  .note { color:#9aa0ae; font-size:13px; max-width:80ch; line-height:1.5; }
  .card { background:#1a1e28; border:1px solid #2a2f3d; border-radius:10px; margin:18px 0; padding:12px;
          border-left:4px solid transparent; }
  .card.approved { border-left-color:#4a9e7f; }
  .card.rejected { border-left-color:#e05c4b; }
  .pair { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  figure { margin:0; }
  figure img { width:100%; display:block; border-radius:6px; }
  figcaption { font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:#6b7585; padding:5px 2px; }
  .bar { display:flex; align-items:center; gap:10px; padding-top:10px; flex-wrap:wrap; }
  .meta { font-size:12px; color:#9aa0ae; flex:1; }
  .bar button { border:1px solid #3a4050; background:#22252e; color:#e8eaf0; border-radius:6px;
                padding:7px 16px; font-size:13px; cursor:pointer; }
  .bar button.on-approve { background:#2c5c49; border-color:#4a9e7f; }
  .bar button.on-reject { background:#66332b; border-color:#e05c4b; }
  h2.day { font-family:Georgia,serif; font-weight:normal; border-top:1px solid #2a2f3d; padding-top:18px; }
  @media (max-width:700px){ .pair { grid-template-columns:1fr; } }
</style></head><body>
<header>
  <h1>Photo edit review</h1>
  <span class="counts" id="counts"></span>
  <select id="filter">
    <option value="all">Show: all</option>
    <option value="undecided" selected>Show: undecided</option>
    <option value="approved">Show: approved</option>
    <option value="rejected">Show: rejected</option>
  </select>
  <select id="sort">
    <option value="day">Sort: by day</option>
    <option value="score">Sort: biggest change first</option>
  </select>
  <button class="top export" id="export">⬇ Export decisions</button>
</header>
<main>
<p class="note">Left = what's on the site today, right = auto-enhanced (contrast + colour + sharpening).
Approve the ones that look better; reject the rest. Decisions save in this browser automatically —
close and resume anytime. When done, <b>Export decisions</b> downloads
<code>photo_edit_decisions.json</code>; hand that file to Claude (or run
<code>python scripts/apply_photo_edits.py &lt;path&gt;</code> then <code>python scripts/build_gallery.py</code>)
and approved photos are re-encoded with the enhancement everywhere on the site.</p>
<div id="cards"></div>
</main>
<script>
const CARDS = __CARDS__;
const PRIOR = __PRIOR__;
const store = JSON.parse(localStorage.getItem('photo-edit-decisions') || '{}');
for (const [f, d] of Object.entries(PRIOR)) if (!(f in store)) store[f] = d;

function save() { localStorage.setItem('photo-edit-decisions', JSON.stringify(store)); }
function stateOf(f) { return store[f] || 'undecided'; }

function render() {
  const filter = document.getElementById('filter').value;
  const sort = document.getElementById('sort').value;
  let list = CARDS.slice();
  if (sort === 'score') list.sort((a, b) => b.score - a.score);
  const wrap = document.getElementById('cards');
  wrap.innerHTML = '';
  let lastDay = null;
  list.forEach(c => {
    const st = stateOf(c.file);
    if (filter !== 'all' && st !== filter) return;
    if (sort === 'day' && c.day !== lastDay) {
      lastDay = c.day;
      const h = document.createElement('h2');
      h.className = 'day'; h.textContent = c.day;
      wrap.appendChild(h);
    }
    const div = document.createElement('div');
    div.className = 'card ' + (st !== 'undecided' ? st : '');
    div.innerHTML =
      '<div class="pair">' +
      '<figure><img src="' + c.before + '" loading="lazy"><figcaption>original</figcaption></figure>' +
      '<figure><img src="' + c.after + '" loading="lazy"><figcaption>enhanced</figcaption></figure>' +
      '</div><div class="bar">' +
      '<span class="meta">' + c.file + ' · ' + c.day + ' ' + c.time + ' · change ' + c.score + '</span>' +
      '<button class="a' + (st === 'approved' ? ' on-approve' : '') + '">✓ Approve</button>' +
      '<button class="r' + (st === 'rejected' ? ' on-reject' : '') + '">✕ Reject</button>' +
      '</div>';
    div.querySelector('.a').onclick = () => { store[c.file] = st === 'approved' ? undefined : 'approved'; if (!store[c.file]) delete store[c.file]; save(); render(); };
    div.querySelector('.r').onclick = () => { store[c.file] = st === 'rejected' ? undefined : 'rejected'; if (!store[c.file]) delete store[c.file]; save(); render(); };
    wrap.appendChild(div);
  });
  const a = CARDS.filter(c => stateOf(c.file) === 'approved').length;
  const r = CARDS.filter(c => stateOf(c.file) === 'rejected').length;
  document.getElementById('counts').innerHTML =
    '<b>' + a + '</b> approved · <b>' + r + '</b> rejected · ' + (CARDS.length - a - r) + ' undecided';
}
document.getElementById('filter').onchange = render;
document.getElementById('sort').onchange = render;
document.getElementById('export').onclick = () => {
  const out = { approved: [], rejected: [] };
  CARDS.forEach(c => { const st = stateOf(c.file); if (st !== 'undecided') out[st].push(c.file); });
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' });
  const aEl = document.createElement('a');
  aEl.href = URL.createObjectURL(blob);
  aEl.download = 'photo_edit_decisions.json';
  aEl.click();
};
render();
</script></body></html>"""
    page = page.replace("__CARDS__", json.dumps(cards)).replace("__PRIOR__", json.dumps(decisions))
    OUT_HTML.write_text(page, encoding="utf-8")

    print(f"\nCards: {len(cards)} | failures: {len(failures)}")
    for k, v in failures.items():
        print(f"  {k}: {v}")
    print(f"Review page: {OUT_HTML}")
    print("Open http://localhost:8123/photos_raw/edit_review/review.html")


if __name__ == "__main__":
    main()
