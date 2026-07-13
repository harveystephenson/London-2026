"""Generate the combined photo review page: location tagging + quality approval.

One card per reviewable photo — the user's and mom's together — written to
photos_raw/photo_review/review.html:

- LOCATION: a dropdown prepopulated with every existing category (flag names
  from data/flag_locations.csv + every final_location / suggested_location
  already in the manifest + "Ignore"), current final_location preselected.
  An add-a-category box introduces new places into every dropdown, so new
  names are picked from a list instead of retyped — no typo-duplicates.
- QUALITY: photos with no decision yet in data/photo_edits.csv (mom's photos,
  previously Ignored ones, future additions) get the original-vs-enhanced
  side-by-side with Approve / Reject. Already-decided photos show a single
  site thumbnail and just the location controls, keeping the page light.

Decisions live in the browser's localStorage while reviewing (safe to close
and resume). When done, Export downloads photo_review_decisions.json; feed
that to apply_photo_review.py and run build_gallery.py to make it real.

Everything under photos_raw/ is gitignored — this is a local tool.
Incremental: candidates newer than their raw source are not re-rendered.

Usage:
    python scripts/make_photo_review.py
    # open http://localhost:8123/photos_raw/photo_review/review.html
"""

import csv
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

from build_gallery import (
    DAY_SLUGS,
    RAW_DC_DIR,
    RAW_DIR,
    RAW_MOMS_DIR,
    build_location_day_map,
    load_flags,
    stem_slug,
)
from photo_enhance import RECIPE_VERSION, enhance

pillow_heif.register_heif_opener()

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_CSV = ROOT / "data" / "photo_manifest.csv"
EDITS_CSV = ROOT / "data" / "photo_edits.csv"
PHOTOS_DIR = ROOT / "photos"
OUT_DIR = ROOT / "photos_raw" / "photo_review"
CAND_DIR = OUT_DIR / "cand"
SCORES_JSON = OUT_DIR / "_scores.json"
OUT_HTML = OUT_DIR / "review.html"

FULL_MAX = 1600
FULL_QUALITY = 75


def render_candidates(task):
    """Render enhanced (and optionally plain) candidates for one photo.

    Runs in a worker process. Returns (filename, change_score, error)."""
    src, after_dest, orig_dest = task
    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((FULL_MAX, FULL_MAX), Image.LANCZOS)
            before = img
            after = enhance(img)
            after_dest.parent.mkdir(parents=True, exist_ok=True)
            after.save(after_dest, "JPEG", quality=FULL_QUALITY, optimize=True)
            if orig_dest is not None:
                before.save(orig_dest, "JPEG", quality=FULL_QUALITY, optimize=True)
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
        all_rows = list(csv.DictReader(f))

    # Reviewable = everything that could appear on the site, PLUS rows the
    # user may want to bring back or place: Ignored photos and mom's photos
    # (whose datetimes are send times, so no day-window check applies).
    rows = [
        r for r in all_rows
        if r["category"] in ("uk_trip", "dc_reunion")
        and r.get("deleted") != "true"
        and (r["datetime"][:10] in DAY_SLUGS or r.get("source") == "moms_phone")
    ]

    _, flag_days = load_flags()
    location_days = build_location_day_map(rows, flag_days)

    # Dropdown vocabulary: every place name the project already knows.
    categories = set(flag_days)
    for r in all_rows:
        for col in ("final_location", "suggested_location"):
            v = (r.get(col) or "").strip()
            if v:
                categories.add(v)
    categories.discard("Ignore")
    categories = sorted(categories)

    # Prior quality decisions — these photos need no before/after pair.
    decisions = {}
    if EDITS_CSV.exists():
        with open(EDITS_CSV, newline="", encoding="utf-8") as f:
            decisions = {r["filename"]: r["decision"] for r in csv.DictReader(f)}

    # user's photos chronologically, mom's after them (send order)
    rows.sort(key=lambda r: (r.get("source") == "moms_phone", r["datetime"], r["filename"]))

    scores = {}
    if SCORES_JSON.exists():
        data = json.loads(SCORES_JSON.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("recipe") == RECIPE_VERSION:
            scores = data.get("scores", {})

    tasks = []
    seen_stems = {}
    for r in rows:
        is_moms = r.get("source") == "moms_phone"
        if is_moms:
            src_dir = RAW_MOMS_DIR
            day = location_days.get((r.get("final_location") or "").strip()) or "unplaced"
        else:
            src_dir = RAW_DIR if r["category"] == "uk_trip" else RAW_DC_DIR
            day = DAY_SLUGS[r["datetime"][:10]]
        stem = stem_slug(r["filename"])
        if stem in seen_stems:
            raise RuntimeError(
                f"Stem collision: {r['filename']} and {seen_stems[stem]} both map to {stem}"
            )
        seen_stems[stem] = r["filename"]
        r["_src"] = src_dir / r["filename"]
        r["_day"] = day
        r["_stem"] = stem
        r["_moms"] = is_moms
        # Site images exist only for photos currently shipped (day-placed,
        # not Ignored) — check disk rather than re-deriving the rules.
        r["_site_thumb"] = (PHOTOS_DIR / day / "thumbs" / f"{stem}.jpg").exists()
        r["_site_full"] = (PHOTOS_DIR / day / "full" / f"{stem}.jpg").exists()
        needs_pair = r["filename"] not in decisions
        needs_orig = (needs_pair and not r["_site_full"]) or (
            not needs_pair and not r["_site_thumb"]
        )
        r["_pair"] = needs_pair
        if needs_pair or needs_orig:
            after_dest = CAND_DIR / f"{stem}.jpg"
            orig_dest = CAND_DIR / f"{stem}__orig.jpg" if needs_orig else None
            stale = (
                not after_dest.exists()
                or after_dest.stat().st_mtime <= r["_src"].stat().st_mtime
                or (orig_dest is not None and not orig_dest.exists())
                or r["filename"] not in scores
            )
            if stale:
                tasks.append((r["_src"], after_dest, orig_dest))

    print(f"{len(rows)} photos ({len(tasks)} candidates to render)")
    failures = {}
    if tasks:
        workers = max(1, (os.cpu_count() or 2) - 1)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, (name, score, err) in enumerate(pool.map(render_candidates, tasks, chunksize=4), 1):
                if err:
                    failures[name] = err
                else:
                    scores[name] = score
                if i % 25 == 0 or i == len(tasks):
                    print(f"...{i}/{len(tasks)}")
        SCORES_JSON.write_text(json.dumps({"recipe": RECIPE_VERSION, "scores": scores}), encoding="utf-8")

    cards = []
    for r in rows:
        if r["filename"] in failures:
            continue
        site_thumb = f"../../photos/{r['_day']}/thumbs/{r['_stem']}.jpg"
        site_full = f"../../photos/{r['_day']}/full/{r['_stem']}.jpg"
        cand_after = f"cand/{r['_stem']}.jpg"
        cand_orig = f"cand/{r['_stem']}__orig.jpg"
        if r["_pair"]:
            before, img = (site_full if r["_site_full"] else cand_orig), None
        else:
            before, img = None, (site_thumb if r["_site_thumb"] else cand_orig)
        cards.append({
            "file": r["filename"],
            "day": r["_day"],
            "src": "moms" if r["_moms"] else "mine",
            "time": "" if r["_moms"] else r["datetime"][11:16],
            "loc": (r.get("final_location") or "").strip(),
            "sug": (r.get("suggested_location") or "").strip(),
            "q": decisions.get(r["filename"], ""),
            "pair": r["_pair"],
            "before": before,
            "after": cand_after if r["_pair"] else None,
            "img": img,
            "score": scores.get(r["filename"], 0),
        })

    page = PAGE_TEMPLATE.replace("__CARDS__", json.dumps(cards)) \
                        .replace("__CATS__", json.dumps(categories))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(page, encoding="utf-8")

    n_pairs = sum(1 for c in cards if c["pair"])
    print(f"\nCards: {len(cards)} ({n_pairs} with quality pending) | failures: {len(failures)}")
    for k, v in failures.items():
        print(f"  {k}: {v}")
    print(f"Review page: {OUT_HTML}")
    print("Open http://localhost:8123/photos_raw/photo_review/review.html")


PAGE_TEMPLATE = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Photo review — locations &amp; quality</title>
<style>
  body { background:#14161b; color:#e8eaf0; font-family:'Helvetica Neue',Arial,sans-serif; margin:0; }
  header { position:sticky; top:0; background:#1a1e28; border-bottom:1px solid #2a2f3d; padding:10px 20px;
           display:flex; gap:10px; align-items:center; flex-wrap:wrap; z-index:10; }
  h1 { font-family:Georgia,serif; font-weight:normal; font-size:18px; margin:0; }
  .counts { font-size:12px; color:#9aa0ae; flex:1; min-width:220px; }
  .counts b { color:#c9a84c; }
  select, input.cat, button.top { background:#22252e; color:#e8eaf0; border:1px solid #3a4050; border-radius:6px;
           padding:6px 10px; font-size:13px; }
  select, button.top { cursor:pointer; }
  button.top.export { background:#c9a84c; color:#14161b; font-weight:700; border-color:#c9a84c; }
  main { max-width:1200px; margin:0 auto; padding:20px; }
  .note { color:#9aa0ae; font-size:13px; max-width:90ch; line-height:1.5; }
  .card { background:#1a1e28; border:1px solid #2a2f3d; border-radius:10px; margin:16px 0; padding:12px;
          border-left:4px solid transparent; }
  .card.approved { border-left-color:#4a9e7f; }
  .card.rejected { border-left-color:#e05c4b; }
  .card.moms { background:#1b1a26; }
  .pair { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  .single img { max-height:340px; border-radius:6px; display:block; }
  figure { margin:0; }
  figure img { width:100%; display:block; border-radius:6px; }
  figcaption { font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:#6b7585; padding:5px 2px; }
  .bar { display:flex; align-items:center; gap:10px; padding-top:10px; flex-wrap:wrap; }
  .meta { font-size:12px; color:#9aa0ae; flex:1; min-width:200px; }
  .meta .who { color:#c9a84c; }
  .bar select.loc { max-width:280px; }
  .bar select.loc.changed { border-color:#c9a84c; }
  .sug { font-size:12px; color:#6b7585; }
  .sug a { color:#c9a84c; cursor:pointer; text-decoration:underline dotted; }
  .bar button { border:1px solid #3a4050; background:#22252e; color:#e8eaf0; border-radius:6px;
                padding:7px 14px; font-size:13px; cursor:pointer; }
  .bar button.on-approve { background:#2c5c49; border-color:#4a9e7f; }
  .bar button.on-reject { background:#66332b; border-color:#e05c4b; }
  .qdone { font-size:12px; color:#4a9e7f; }
  h2.day { font-family:Georgia,serif; font-weight:normal; border-top:1px solid #2a2f3d; padding-top:18px; }
  @media (max-width:700px){ .pair { grid-template-columns:1fr; } }
</style></head><body>
<header>
  <h1>Photo review</h1>
  <span class="counts" id="counts"></span>
  <select id="filter">
    <option value="all" selected>Show: all</option>
    <option value="q-undecided">Show: quality undecided</option>
    <option value="loc-unassigned">Show: location unassigned</option>
    <option value="loc-changed">Show: location changed</option>
  </select>
  <select id="who">
    <option value="all">Photos: all</option>
    <option value="mine">Photos: mine</option>
    <option value="moms">Photos: mom's</option>
  </select>
  <select id="sort">
    <option value="day">Sort: by day</option>
    <option value="score">Sort: biggest change first</option>
  </select>
  <input class="cat" id="newcat" placeholder="New category name…" size="18">
  <button class="top" id="addcat">+ Add</button>
  <button class="top" id="prev">‹ Prev</button>
  <span class="counts" id="pageinfo" style="flex:none"></span>
  <button class="top" id="next">Next ›</button>
  <button class="top export" id="export">⬇ Export decisions</button>
</header>
<main>
<p class="note">Each photo has a <b>location dropdown</b> (pick from existing categories — add a new one with
the box above and it appears in every dropdown; choose <b>Ignore</b> to keep a photo off the site).
Photos still needing a <b>quality decision</b> (mom's, previously ignored) also show original vs enhanced —
approve the ones that look better. Everything saves in this browser automatically; close and resume anytime.
When done, <b>Export decisions</b> downloads <code>photo_review_decisions.json</code>; hand it to Claude
(or run <code>python scripts/apply_photo_review.py &lt;path&gt;</code> then
<code>python scripts/build_gallery.py</code>).</p>
<div id="cards"></div>
</main>
<script>
const CARDS = __CARDS__;
const BASE_CATS = __CATS__;
const qstore = JSON.parse(localStorage.getItem('photo-review-quality') || '{}');
const lstore = JSON.parse(localStorage.getItem('photo-review-locations') || '{}');
let customCats = JSON.parse(localStorage.getItem('photo-review-categories') || '[]');
CARDS.forEach(c => { if (c.q && !(c.file in qstore)) qstore[c.file] = c.q; });

function save() {
  localStorage.setItem('photo-review-quality', JSON.stringify(qstore));
  localStorage.setItem('photo-review-locations', JSON.stringify(lstore));
  localStorage.setItem('photo-review-categories', JSON.stringify(customCats));
}
function qOf(f) { return qstore[f] || 'undecided'; }
function locOf(c) { return (c.file in lstore) ? lstore[c.file] : c.loc; }
function allCats() {
  const s = new Set(BASE_CATS.concat(customCats));
  return Array.from(s).sort((a, b) => a.localeCompare(b));
}

const PAGE_SIZE = 40;   // cards per page — the full set crashes browsers
let page = 0;

function matches(c, filter) {
  if (filter === 'q-undecided') return qOf(c.file) === 'undecided';
  if (filter === 'loc-unassigned') return !locOf(c);
  if (filter === 'loc-changed') return locOf(c) !== c.loc;
  return true;
}

function buildSelect(c) {
  const sel = document.createElement('select');
  sel.className = 'loc' + (locOf(c) !== c.loc ? ' changed' : '');
  const blank = document.createElement('option');
  blank.value = ''; blank.textContent = '— no location —';
  sel.appendChild(blank);
  const ign = document.createElement('option');
  ign.value = 'Ignore'; ign.textContent = 'Ignore (keep off the site)';
  sel.appendChild(ign);
  allCats().forEach(name => {
    const o = document.createElement('option');
    o.value = name; o.textContent = name;
    sel.appendChild(o);
  });
  sel.value = locOf(c);
  if (sel.value !== locOf(c)) { // stored value missing from the list — keep it visible
    const o = document.createElement('option');
    o.value = locOf(c); o.textContent = locOf(c);
    sel.appendChild(o); sel.value = locOf(c);
  }
  sel.onchange = () => {
    if (sel.value === c.loc) delete lstore[c.file]; else lstore[c.file] = sel.value;
    sel.className = 'loc' + (locOf(c) !== c.loc ? ' changed' : '');
    save(); counts();
  };
  return sel;
}

function counts() {
  let qa = 0, qr = 0, qu = 0, lc = 0, lu = 0;
  CARDS.forEach(c => {
    const q = qOf(c.file);
    if (q === 'approved') qa++; else if (q === 'rejected') qr++; else qu++;
    if (locOf(c) !== c.loc) lc++;
    if (!locOf(c)) lu++;
  });
  document.getElementById('counts').innerHTML =
    'quality: <b>' + qa + '</b>✓ <b>' + qr + '</b>✕ ' + qu + ' left &nbsp;·&nbsp; ' +
    'locations: <b>' + lc + '</b> changed, ' + lu + ' unassigned';
}

function render() {
  const filter = document.getElementById('filter').value;
  const who = document.getElementById('who').value;
  const sort = document.getElementById('sort').value;
  let list = CARDS.slice();
  if (sort === 'score') list.sort((a, b) => b.score - a.score);
  const filtered = list.filter(c => (who === 'all' || c.src === who) && matches(c, filter));
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  if (page >= pages) page = pages - 1;
  if (page < 0) page = 0;
  document.getElementById('pageinfo').textContent =
    'Page ' + (page + 1) + ' / ' + pages + ' (' + filtered.length + ' shown)';
  const slice = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const wrap = document.getElementById('cards');
  wrap.innerHTML = '';
  let lastDay = null;
  slice.forEach(c => {
    const q = qOf(c.file);
    if (sort === 'day' && c.day !== lastDay) {
      lastDay = c.day;
      const h = document.createElement('h2');
      h.className = 'day'; h.textContent = c.day + (c.src === 'moms' ? " — mom's photos" : '');
      wrap.appendChild(h);
    }
    const div = document.createElement('div');
    div.className = 'card ' + (q !== 'undecided' ? q : '') + (c.src === 'moms' ? ' moms' : '');
    let picHtml;
    if (c.pair) {
      picHtml = '<div class="pair">' +
        '<figure><img src="' + encodeURI(c.before) + '" loading="lazy"><figcaption>original</figcaption></figure>' +
        '<figure><img src="' + encodeURI(c.after) + '" loading="lazy"><figcaption>enhanced</figcaption></figure>' +
        '</div>';
    } else {
      picHtml = '<div class="single"><img src="' + encodeURI(c.img) + '" loading="lazy"></div>';
    }
    div.innerHTML = picHtml +
      '<div class="bar">' +
      '<span class="meta"><span class="who">' + (c.src === 'moms' ? "mom's" : 'mine') + '</span> · ' +
      c.file + ' · ' + c.day + (c.time ? ' ' + c.time : '') +
      (c.pair ? ' · change ' + c.score : '') + '</span>' +
      '</div>';
    const bar = div.querySelector('.bar');
    bar.appendChild(buildSelect(c));
    if (c.sug && !locOf(c)) {
      const s = document.createElement('span');
      s.className = 'sug';
      s.innerHTML = 'suggested: <a></a>';
      const link = s.querySelector('a');
      link.textContent = c.sug;
      link.onclick = () => { lstore[c.file] = c.sug; save(); render(); };
      bar.appendChild(s);
    }
    if (c.pair) {
      const a = document.createElement('button');
      a.className = 'a' + (q === 'approved' ? ' on-approve' : '');
      a.textContent = '✓ Approve';
      const r = document.createElement('button');
      r.className = 'r' + (q === 'rejected' ? ' on-reject' : '');
      r.textContent = '✕ Reject';
      a.onclick = () => { if (q === 'approved') delete qstore[c.file]; else qstore[c.file] = 'approved'; save(); render(); };
      r.onclick = () => { if (q === 'rejected') delete qstore[c.file]; else qstore[c.file] = 'rejected'; save(); render(); };
      bar.appendChild(a); bar.appendChild(r);
    } else if (q !== 'undecided') {
      const s = document.createElement('span');
      s.className = 'qdone';
      s.textContent = q === 'approved' ? '✓ enhanced' : '✕ unenhanced';
      bar.appendChild(s);
    }
    wrap.appendChild(div);
  });
  counts();
}

document.getElementById('filter').onchange = () => { page = 0; render(); };
document.getElementById('who').onchange = () => { page = 0; render(); };
document.getElementById('sort').onchange = () => { page = 0; render(); };
document.getElementById('prev').onclick = () => { page--; render(); window.scrollTo(0, 0); };
document.getElementById('next').onclick = () => { page++; render(); window.scrollTo(0, 0); };
document.getElementById('addcat').onclick = () => {
  const inp = document.getElementById('newcat');
  const name = inp.value.trim();
  if (!name) return;
  const clash = allCats().find(x => x.toLowerCase() === name.toLowerCase());
  if (clash) { alert('Already exists as: ' + clash); inp.value = ''; return; }
  customCats.push(name); save(); inp.value = ''; render();
};
document.getElementById('export').onclick = () => {
  const out = { quality: { approved: [], rejected: [] }, locations: {}, new_categories: [] };
  const used = new Set();
  CARDS.forEach(c => {
    const q = qOf(c.file);
    if (q !== 'undecided') out.quality[q].push(c.file);
    const l = locOf(c);
    if (l !== c.loc) { out.locations[c.file] = l; used.add(l); }
  });
  out.new_categories = customCats.filter(x => used.has(x));
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' });
  const aEl = document.createElement('a');
  aEl.href = URL.createObjectURL(blob);
  aEl.download = 'photo_review_decisions.json';
  aEl.click();
};
render();
</script></body></html>"""


if __name__ == "__main__":
    main()
