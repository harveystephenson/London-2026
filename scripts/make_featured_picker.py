"""Generate the featured-photo picker: assign photos to the site's fixed
"slots" — the hero banner, one per-day mobile photo, and one per-location
photo beside each schedule item (#47).

Unlike make_photo_review.py (which asks "what should happen to this
photo?"), this tool asks the reverse question per slot: "which photo goes
here?" Each slot shows its current pick (or the automatic fallback if
unset) plus a Choose button; clicking it opens a candidate grid scoped to
what's relevant for that slot (the whole trip for the banner, just that
day for a day photo, just that location for an item photo). Decisions
live in localStorage while working; Export downloads
featured_photo_decisions.json — feed that to apply_featured_photos.py and
run build_gallery.py to make it real.

Reads its candidate pools straight from the *live* gallery data already
baked into index.html (between the GALLERY_DATA / GALLERY_BY_LOCATION
markers) rather than recomputing grouping — that's build_gallery.py's job,
and this way the picker always matches exactly what's on the site.

Usage:
    python scripts/make_featured_picker.py
    # open http://localhost:8123/photos_raw/featured_picker/picker.html
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = ROOT / "index.html"
FLAGS_CSV = ROOT / "data" / "flag_locations.csv"
FEATURED_CSV = ROOT / "data" / "featured_photos.csv"
OUT_DIR = ROOT / "photos_raw" / "featured_picker"
OUT_HTML = OUT_DIR / "picker.html"

DAY_LABELS = {
    "day-29-jun": "Monday 29 June",
    "day-30-jun": "Tuesday 30 June",
    "day-01-jul": "Wednesday 1 July",
    "day-02-jul": "Thursday 2 July",
    "day-03-jul": "Friday 3 July",
    "day-04-jul": "Saturday 4 July",
    "day-05-jul": "Sunday 5 July",
    "day-06-jul": "Monday 6 July",
    "day-07-jul": "Tuesday 7 July",
    "day-10-jul": "Friday 10 July — Washington, DC",
}
DAY_ORDER = list(DAY_LABELS)


def extract_json(html, start_marker, end_marker):
    start = html.index(start_marker) + len(start_marker)
    end = html.index(end_marker, start)
    return json.loads(html[start:end])


def load_flags():
    with open(FLAGS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_featured_photos():
    picks = {"banner_lead": None, "banner": [], "day_feature": {}, "item_feature": {}}
    if not FEATURED_CSV.exists():
        return picks
    with open(FEATURED_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    banner = []
    for row in rows:
        role, filename = row.get("role"), row.get("filename")
        if not role or not filename:
            continue
        if role == "banner_lead":
            picks["banner_lead"] = filename
        elif role == "banner":
            banner.append((int(row.get("sort") or 0), filename))
        elif role == "day_feature" and row.get("day"):
            picks["day_feature"][row["day"]] = filename
        elif role == "item_feature" and row.get("location_id"):
            picks["item_feature"][row["location_id"]] = filename
    picks["banner"] = [f for _, f in sorted(banner)]
    return picks


def main():
    html = INDEX_HTML.read_text(encoding="utf-8")
    gallery_data = extract_json(html, "/*GALLERY_DATA*/", "/*END_GALLERY_DATA*/")
    gallery_by_location = extract_json(html, "/*GALLERY_BY_LOCATION*/", "/*END_GALLERY_BY_LOCATION*/")
    flags = load_flags()
    picks = load_featured_photos()

    # filename -> {thumb,full}, for resolving picks to actual paths
    filename_to_photo = {}
    for photos in gallery_data.values():
        for p in photos:
            filename_to_photo[Path(p["thumb"]).stem] = p
    # gallery entries are keyed by stem (lowercase, slugged) not original
    # filename, so picks (which store the real manifest filename) resolve
    # via the same slugging build_gallery.py uses.
    def slug(name):
        return re.sub(r"[^a-z0-9_-]+", "-", Path(name).stem.lower()).strip("-")

    def resolve(filename):
        if not filename:
            return None
        return filename_to_photo.get(slug(filename))

    # Banner candidates: every live photo, across the whole trip.
    all_photos = []
    for day in DAY_ORDER:
        for p in gallery_data.get(day, []):
            all_photos.append({**p, "day": day})

    banner_lead_current = resolve(picks["banner_lead"]) or (all_photos[0] if all_photos else None)
    banner_current = [resolve(f) for f in picks["banner"]]
    banner_current = [p for p in banner_current if p]

    day_slots = []
    for day in DAY_ORDER:
        photos = gallery_data.get(day, [])
        if not photos:
            continue
        current = resolve(picks["day_feature"].get(day)) or photos[0]
        day_slots.append({
            "key": day,
            "label": DAY_LABELS[day],
            "current": current,
            "candidates": photos,
        })

    flags_by_day = {}
    for flag in flags:
        flags_by_day.setdefault(flag["day"], []).append(flag)

    item_slots = []
    for day in DAY_ORDER:
        for flag in flags_by_day.get(day, []):
            loc_id = flag["location_id"]
            photos = gallery_by_location.get(loc_id, [])
            if not photos:
                continue
            current = resolve(picks["item_feature"].get(loc_id)) or photos[0]
            item_slots.append({
                "key": loc_id,
                "label": flag["name"],
                "day": day,
                "dayLabel": DAY_LABELS[day],
                "current": current,
                "candidates": photos,
            })

    data = {
        "bannerLead": banner_lead_current,
        "bannerLeadCandidates": all_photos,
        "banner": banner_current,
        "daySlots": day_slots,
        "itemSlots": item_slots,
    }

    page = PAGE_TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(page, encoding="utf-8")

    print(f"Banner: lead {'set' if banner_lead_current else 'MISSING'}, {len(banner_current)}/4 supporting photos picked")
    print(f"Day slots: {len(day_slots)}")
    print(f"Item slots: {len(item_slots)}")
    print(f"Picker page: {OUT_HTML}")
    print("Open http://localhost:8123/photos_raw/featured_picker/picker.html")


PAGE_TEMPLATE = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Featured photo picker (#47)</title>
<style>
  body { background:#14161b; color:#e8eaf0; font-family:'Helvetica Neue',Arial,sans-serif; margin:0; }
  header { position:sticky; top:0; background:#1a1e28; border-bottom:1px solid #2a2f3d; padding:12px 20px;
           display:flex; gap:14px; align-items:center; flex-wrap:wrap; z-index:20; }
  h1 { font-family:Georgia,serif; font-weight:normal; font-size:18px; margin:0; flex:1; }
  button.top { background:#c9a84c; color:#14161b; font-weight:700; border:none; border-radius:6px;
               padding:8px 16px; font-size:13px; cursor:pointer; }
  main { max-width:1100px; margin:0 auto; padding:20px; }
  .note { color:#9aa0ae; font-size:13px; max-width:90ch; line-height:1.5; margin-bottom:20px; }
  h2.section { font-family:Georgia,serif; font-weight:normal; font-size:20px; border-top:1px solid #2a2f3d;
               padding-top:22px; margin-top:26px; }
  h2.section:first-of-type { border-top:none; margin-top:0; padding-top:0; }
  .section-desc { color:#9aa0ae; font-size:13px; margin-bottom:14px; }
  .slots { display:flex; flex-wrap:wrap; gap:12px; }
  .slot { background:#1a1e28; border:1px solid #2a2f3d; border-radius:10px; padding:10px; width:170px; }
  .slot.day-group-heading { width:100%; background:none; border:none; padding:4px 0 0; }
  .slot-label { font-size:12px; color:#c9a84c; margin-bottom:6px; min-height:2.6em; }
  .slot img { width:100%; height:110px; object-fit:cover; border-radius:6px; display:block; background:#0d0f14; }
  .slot .empty-ph { width:100%; height:110px; border-radius:6px; background:#0d0f14; display:flex;
                     align-items:center; justify-content:center; color:#6b7585; font-size:11px; }
  .slot button.choose { width:100%; margin-top:8px; background:#22252e; color:#e8eaf0; border:1px solid #3a4050;
                         border-radius:6px; padding:6px; font-size:12px; cursor:pointer; }
  .slot.changed { border-color:#c9a84c; }
  .slot.changed .slot-label { color:#4a9e7f; }
  .day-heading { font-family:Georgia,serif; font-size:15px; color:#e8eaf0; margin:18px 0 8px; width:100%; }

  .overlay { position:fixed; inset:0; background:rgba(10,11,14,0.85); z-index:50; display:none;
             align-items:flex-start; justify-content:center; overflow-y:auto; padding:40px 20px; }
  .overlay.open { display:flex; }
  .picker-panel { background:#1a1e28; border:1px solid #2a2f3d; border-radius:12px; padding:18px;
                  max-width:960px; width:100%; }
  .picker-panel h3 { font-family:Georgia,serif; font-weight:normal; margin-bottom:4px; }
  .picker-panel .sub { color:#9aa0ae; font-size:12px; margin-bottom:14px; }
  .picker-filter { margin-bottom:12px; }
  .picker-filter select { background:#22252e; color:#e8eaf0; border:1px solid #3a4050; border-radius:6px;
                           padding:6px 10px; font-size:13px; }
  .candidate-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(100px,1fr)); gap:8px;
                     max-height:60vh; overflow-y:auto; }
  .candidate-grid img { width:100%; height:80px; object-fit:cover; border-radius:6px; cursor:pointer;
                         border:2px solid transparent; display:block; }
  .candidate-grid img:hover { border-color:#c9a84c; }
  .picker-close { margin-top:14px; background:#22252e; color:#e8eaf0; border:1px solid #3a4050;
                  border-radius:6px; padding:7px 16px; font-size:13px; cursor:pointer; }
</style></head><body>
<header>
  <h1>Featured photo picker</h1>
  <button class="top" id="export">⬇ Export picks</button>
</header>
<main>
<p class="note">Pick which photo goes in each fixed spot on the site: the <b>hero banner</b> (same across
every theme), one <b>day photo</b> per day (used on phones), and one <b>item photo</b> beside each schedule
entry (desktop Option B). Anything left unset keeps using the automatic default shown now. Choices save in
this browser automatically — close and resume anytime. When done, <b>Export picks</b> downloads
<code>featured_photo_decisions.json</code>; hand it to Claude (or run
<code>python scripts/apply_featured_photos.py &lt;path&gt;</code> then
<code>python scripts/build_gallery.py</code>).</p>

<h2 class="section">Hero banner</h2>
<p class="section-desc">One large lead photo + four smaller ones, identical across all four themes.</p>
<div class="slots" id="banner-slots"></div>

<h2 class="section">Day photos</h2>
<p class="section-desc">One photo per day, shown under the date on phones.</p>
<div class="slots" id="day-slots"></div>

<h2 class="section">Item photos</h2>
<p class="section-desc">One photo beside each schedule entry with its own map pin (desktop/tablet).</p>
<div class="slots" id="item-slots"></div>
</main>

<div class="overlay" id="overlay">
  <div class="picker-panel">
    <h3 id="panel-title"></h3>
    <p class="sub" id="panel-sub"></p>
    <div class="picker-filter" id="panel-filter" style="display:none">
      <select id="day-filter"><option value="">All days</option></select>
    </div>
    <div class="candidate-grid" id="panel-grid"></div>
    <button class="picker-close" id="panel-close">Cancel</button>
  </div>
</div>

<script>
const DATA = __DATA__;
const store = JSON.parse(localStorage.getItem('featured-photo-picks') || '{}');
function save() { localStorage.setItem('featured-photo-picks', JSON.stringify(store)); }

function currentFor(kind, key) {
  if (kind === 'bannerLead') return store.bannerLead || DATA.bannerLead;
  if (kind === 'banner') return (store.banner && store.banner[key]) || DATA.banner[key] || null;
  if (kind === 'day') return (store.day && store.day[key]) || DATA.daySlots.find(d => d.key === key).current;
  if (kind === 'item') return (store.item && store.item[key]) || DATA.itemSlots.find(d => d.key === key).current;
}
function isChanged(kind, key) {
  if (kind === 'bannerLead') return !!store.bannerLead;
  if (kind === 'banner') return !!(store.banner && store.banner[key]);
  if (kind === 'day') return !!(store.day && store.day[key]);
  if (kind === 'item') return !!(store.item && store.item[key]);
}
function stemOf(photo) { return photo ? photo.thumb.split('/').pop().replace(/\.[^.]+$/, '') : null; }

function slotEl(kind, key, label, current, changed) {
  const div = document.createElement('div');
  div.className = 'slot' + (changed ? ' changed' : '');
  const labelEl = document.createElement('div');
  labelEl.className = 'slot-label';
  labelEl.textContent = label;
  div.appendChild(labelEl);
  if (current) {
    const img = document.createElement('img');
    img.src = '../../photos/' + current.thumb;
    img.loading = 'lazy';
    div.appendChild(img);
  } else {
    const ph = document.createElement('div');
    ph.className = 'empty-ph';
    ph.textContent = 'no photo';
    div.appendChild(ph);
  }
  const btn = document.createElement('button');
  btn.className = 'choose';
  btn.textContent = 'Choose…';
  btn.onclick = () => openPicker(kind, key, label);
  div.appendChild(btn);
  return div;
}

function renderBanner() {
  const wrap = document.getElementById('banner-slots');
  wrap.innerHTML = '';
  wrap.appendChild(slotEl('bannerLead', null, 'Lead photo (large)', currentFor('bannerLead'), isChanged('bannerLead')));
  for (let i = 0; i < 4; i++) {
    wrap.appendChild(slotEl('banner', i, 'Photo ' + (i + 2), currentFor('banner', i), isChanged('banner', i)));
  }
}

function renderDaySlots() {
  const wrap = document.getElementById('day-slots');
  wrap.innerHTML = '';
  DATA.daySlots.forEach(d => {
    wrap.appendChild(slotEl('day', d.key, d.label, currentFor('day', d.key), isChanged('day', d.key)));
  });
}

function renderItemSlots() {
  const wrap = document.getElementById('item-slots');
  wrap.innerHTML = '';
  let lastDay = null;
  DATA.itemSlots.forEach(it => {
    if (it.day !== lastDay) {
      lastDay = it.day;
      const h = document.createElement('div');
      h.className = 'day-heading';
      h.textContent = it.dayLabel;
      wrap.appendChild(h);
    }
    wrap.appendChild(slotEl('item', it.key, it.label, currentFor('item', it.key), isChanged('item', it.key)));
  });
}

function renderAll() { renderBanner(); renderDaySlots(); renderItemSlots(); }

let activePicker = null;

function openPicker(kind, key, label) {
  activePicker = { kind, key };
  const overlay = document.getElementById('overlay');
  const grid = document.getElementById('panel-grid');
  const filterWrap = document.getElementById('panel-filter');
  const daySelect = document.getElementById('day-filter');
  document.getElementById('panel-title').textContent = 'Choose: ' + label;

  let candidates, sub;
  if (kind === 'bannerLead' || kind === 'banner') {
    candidates = DATA.bannerLeadCandidates;
    sub = candidates.length + ' photos across the whole trip';
    filterWrap.style.display = 'block';
    daySelect.innerHTML = '<option value="">All days</option>' +
      [...new Set(candidates.map(c => c.day))].map(d => `<option value="${d}">${d}</option>`).join('');
    daySelect.value = '';
    daySelect.onchange = () => renderGrid(candidates.filter(c => !daySelect.value || c.day === daySelect.value));
  } else if (kind === 'day') {
    candidates = DATA.daySlots.find(d => d.key === key).candidates;
    sub = candidates.length + " photos from this day";
    filterWrap.style.display = 'none';
  } else {
    candidates = DATA.itemSlots.find(d => d.key === key).candidates;
    sub = candidates.length + ' photos tagged to this spot';
    filterWrap.style.display = 'none';
  }
  document.getElementById('panel-sub').textContent = sub;
  renderGrid(candidates);
  overlay.classList.add('open');
}

function renderGrid(candidates) {
  const grid = document.getElementById('panel-grid');
  grid.innerHTML = '';
  candidates.forEach(c => {
    const img = document.createElement('img');
    img.src = '../../photos/' + c.thumb;
    img.loading = 'lazy';
    img.onclick = () => choosePhoto(c);
    grid.appendChild(img);
  });
}

function choosePhoto(photo) {
  // Store the full {thumb,full} object (not just its slug) so re-rendering
  // the slot after picking doesn't need to look anything back up -- the
  // slug is only derived, via stemOf(), at export time.
  const { kind, key } = activePicker;
  if (kind === 'bannerLead') {
    store.bannerLead = stemOf(photo) === stemOf(DATA.bannerLead) ? null : photo;
  } else if (kind === 'banner') {
    store.banner = store.banner || {};
    store.banner[key] = photo;
  } else if (kind === 'day') {
    store.day = store.day || {};
    store.day[key] = photo;
  } else if (kind === 'item') {
    store.item = store.item || {};
    store.item[key] = photo;
  }
  save();
  closePicker();
  renderAll();
}

function closePicker() {
  document.getElementById('overlay').classList.remove('open');
  activePicker = null;
}
document.getElementById('panel-close').onclick = closePicker;
document.getElementById('overlay').onclick = (e) => { if (e.target.id === 'overlay') closePicker(); };

document.getElementById('export').onclick = () => {
  // Convert the stored {thumb,full} objects to slugs only at the last
  // moment -- that's the format apply_featured_photos.py / build_gallery.py
  // expect (see the FEATURED_CSV comment in build_gallery.py).
  const dayOut = {};
  Object.keys(store.day || {}).forEach(k => { dayOut[k] = stemOf(store.day[k]); });
  const itemOut = {};
  Object.keys(store.item || {}).forEach(k => { itemOut[k] = stemOf(store.item[k]); });
  const out = {
    banner_lead: store.bannerLead ? stemOf(store.bannerLead) : null,
    banner: [0, 1, 2, 3].map(i => (store.banner && store.banner[i]) ? stemOf(store.banner[i]) : null),
    day_feature: dayOut,
    item_feature: itemOut,
  };
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'featured_photo_decisions.json';
  a.click();
};

renderAll();
</script></body></html>"""


if __name__ == "__main__":
    main()
