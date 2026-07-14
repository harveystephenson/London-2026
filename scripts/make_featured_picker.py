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


def crop_of(row):
    """crop_x/crop_y (#84), defaulting to a center crop for rows written
    before this column existed."""
    try:
        x = float(row.get("crop_x") or 50)
    except (TypeError, ValueError):
        x = 50.0
    try:
        y = float(row.get("crop_y") or 50)
    except (TypeError, ValueError):
        y = 50.0
    return {"x": x, "y": y}


def load_featured_photos():
    """Each pick is {filename, crop} or None. crop is the object-position
    the user dragged to in a previous picker session (#84)."""
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
        pick = {"filename": filename, "crop": crop_of(row)}
        if role == "banner_lead":
            picks["banner_lead"] = pick
        elif role == "banner":
            banner.append((int(row.get("sort") or 0), pick))
        elif role == "day_feature" and row.get("day"):
            picks["day_feature"][row["day"]] = pick
        elif role == "item_feature" and row.get("location_id"):
            picks["item_feature"][row["location_id"]] = pick
    picks["banner"] = [p for _, p in sorted(banner, key=lambda t: t[0])]
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

    DEFAULT_CROP = {"x": 50, "y": 50}

    def with_crop(photo, crop):
        return {**photo, "crop": crop} if photo else None

    def resolve(pick):
        """pick is {filename, crop} or None. Returns the candidate photo
        dict with that crop attached, or None if unresolvable."""
        if not pick:
            return None
        photo = filename_to_photo.get(slug(pick["filename"]))
        return with_crop(photo, pick["crop"]) if photo else None

    # Banner candidates: every live photo, across the whole trip.
    all_photos = []
    for day in DAY_ORDER:
        for p in gallery_data.get(day, []):
            all_photos.append({**p, "day": day})

    banner_lead_current = resolve(picks["banner_lead"]) or with_crop(all_photos[0] if all_photos else None, DEFAULT_CROP)
    banner_current = [resolve(p) for p in picks["banner"]]
    banner_current = [p for p in banner_current if p]

    day_slots = []
    for day in DAY_ORDER:
        photos = gallery_data.get(day, [])
        if not photos:
            continue
        current = resolve(picks["day_feature"].get(day)) or with_crop(photos[0], DEFAULT_CROP)
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
            current = resolve(picks["item_feature"].get(loc_id)) or with_crop(photos[0], DEFAULT_CROP)
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
  /* crop frame (#84): shows the photo at (roughly) the real box aspect ratio
     it renders at on the site, and lets you drag it to choose what part of
     the photo shows instead of the browser's arbitrary center crop. */
  .crop-frame { position:relative; width:100%; border-radius:6px; overflow:hidden;
                background:#0d0f14; cursor:grab; touch-action:none; }
  .crop-frame.dragging { cursor:grabbing; }
  .crop-frame[data-role="bannerLead"] { aspect-ratio: 1.4; }
  .crop-frame[data-role="banner"] { aspect-ratio: 1.43; }
  .crop-frame[data-role="day"] { aspect-ratio: 2.23; }
  .crop-frame[data-role="item"] { aspect-ratio: 1.375; }
  .crop-frame img { width:100%; height:100%; object-fit:cover; display:block; pointer-events:none; }
  .crop-hint { font-size:10px; color:#6b7585; margin-top:3px; text-align:center; }
  .slot .empty-ph { width:100%; aspect-ratio:1.4; border-radius:6px; background:#0d0f14; display:flex;
                     align-items:center; justify-content:center; color:#6b7585; font-size:11px; }
  .slot button.choose { width:100%; margin-top:8px; background:#22252e; color:#e8eaf0; border:1px solid #3a4050;
                         border-radius:6px; padding:6px; font-size:12px; cursor:pointer; }
  .slot button.reset-crop { width:100%; margin-top:4px; background:none; color:#6b7585; border:none;
                             font-size:11px; cursor:pointer; text-decoration:underline; padding:2px; }
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
entry (desktop Option B). Anything left unset keeps using the automatic default shown now. Each preview box
is (roughly) the real shape the photo renders at on the site — <b>drag the photo inside its box to choose
what part shows</b> instead of an arbitrary center crop. Choices save in this browser automatically — close
and resume anytime. When done, <b>Export picks</b> downloads
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
const DEFAULT_CROP = { x: 50, y: 50 };
const store = JSON.parse(localStorage.getItem('featured-photo-picks') || '{}');
function save() { localStorage.setItem('featured-photo-picks', JSON.stringify(store)); }

function defaultFor(kind, key) {
  if (kind === 'bannerLead') return DATA.bannerLead;
  if (kind === 'banner') return DATA.banner[key] || null;
  if (kind === 'day') return DATA.daySlots.find(d => d.key === key).current;
  if (kind === 'item') return DATA.itemSlots.find(d => d.key === key).current;
}
function currentFor(kind, key) {
  if (kind === 'bannerLead') return store.bannerLead || defaultFor(kind, key);
  if (kind === 'banner') return (store.banner && store.banner[key]) || defaultFor(kind, key);
  if (kind === 'day') return (store.day && store.day[key]) || defaultFor(kind, key);
  if (kind === 'item') return (store.item && store.item[key]) || defaultFor(kind, key);
}
function isChanged(kind, key) {
  if (kind === 'bannerLead') return !!store.bannerLead;
  if (kind === 'banner') return !!(store.banner && store.banner[key]);
  if (kind === 'day') return !!(store.day && store.day[key]);
  if (kind === 'item') return !!(store.item && store.item[key]);
}
function stemOf(photo) { return photo ? photo.thumb.split('/').pop().replace(/\.[^.]+$/, '') : null; }

// Ensure store holds a mutable pick for this slot (cloning the current
// default the first time it's touched, e.g. a crop-only drag with no photo
// re-pick yet) and return it, so drag edits persist the same way a Choose
// pick does (#84).
function ensureStoreEntry(kind, key) {
  const current = currentFor(kind, key);
  if (!current) return null;
  if (kind === 'bannerLead') {
    if (!store.bannerLead) store.bannerLead = { ...current };
    return store.bannerLead;
  }
  if (kind === 'banner') {
    store.banner = store.banner || {};
    if (!store.banner[key]) store.banner[key] = { ...current };
    return store.banner[key];
  }
  if (kind === 'day') {
    store.day = store.day || {};
    if (!store.day[key]) store.day[key] = { ...current };
    return store.day[key];
  }
  if (kind === 'item') {
    store.item = store.item || {};
    if (!store.item[key]) store.item[key] = { ...current };
    return store.item[key];
  }
}

const ROLE_BY_KIND = { bannerLead: 'bannerLead', banner: 'banner', day: 'day', item: 'item' };

function slotEl(kind, key, label, current, changed) {
  const div = document.createElement('div');
  div.className = 'slot' + (changed ? ' changed' : '');
  const labelEl = document.createElement('div');
  labelEl.className = 'slot-label';
  labelEl.textContent = label;
  div.appendChild(labelEl);
  if (current) {
    const frame = document.createElement('div');
    frame.className = 'crop-frame';
    frame.dataset.role = ROLE_BY_KIND[kind];
    const img = document.createElement('img');
    img.src = '../../photos/' + current.thumb;
    img.loading = 'lazy';
    const crop = current.crop || DEFAULT_CROP;
    img.style.objectPosition = crop.x + '% ' + crop.y + '%';
    frame.appendChild(img);
    div.appendChild(frame);
    attachDrag(frame, img, kind, key);
    const hint = document.createElement('div');
    hint.className = 'crop-hint';
    hint.textContent = 'drag to reposition';
    div.appendChild(hint);
    if (crop.x !== DEFAULT_CROP.x || crop.y !== DEFAULT_CROP.y) {
      const resetBtn = document.createElement('button');
      resetBtn.className = 'reset-crop';
      resetBtn.textContent = 'Reset crop';
      resetBtn.onclick = () => { setCrop(kind, key, DEFAULT_CROP.x, DEFAULT_CROP.y); renderAll(); };
      div.appendChild(resetBtn);
    }
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

function setCrop(kind, key, x, y) {
  const entry = ensureStoreEntry(kind, key);
  if (!entry) return;
  entry.crop = { x, y };
  save();
}

// Drag-to-reposition (#84): converts a pixel drag delta into the
// object-position percentage change that would produce it, using the same
// object-fit:cover math the browser itself uses, so what you see while
// dragging in the picker matches what the real site will render.
function attachDrag(frame, img, kind, key) {
  let dragging = null;
  function onPointerDown(e) {
    if (!img.naturalWidth) return;
    const rect = frame.getBoundingClientRect();
    const boxW = rect.width, boxH = rect.height;
    const scale = Math.max(boxW / img.naturalWidth, boxH / img.naturalHeight);
    const excessW = img.naturalWidth * scale - boxW;
    const excessH = img.naturalHeight * scale - boxH;
    const current = currentFor(kind, key);
    const crop = (current && current.crop) || DEFAULT_CROP;
    dragging = { startX: e.clientX, startY: e.clientY, startCropX: crop.x, startCropY: crop.y, excessW, excessH };
    frame.classList.add('dragging');
    frame.setPointerCapture(e.pointerId);
    e.preventDefault();
  }
  function onPointerMove(e) {
    if (!dragging) return;
    const dx = e.clientX - dragging.startX;
    const dy = e.clientY - dragging.startY;
    const x = dragging.excessW ? clamp(dragging.startCropX - (dx / dragging.excessW) * 100, 0, 100) : 50;
    const y = dragging.excessH ? clamp(dragging.startCropY - (dy / dragging.excessH) * 100, 0, 100) : 50;
    img.style.objectPosition = x + '% ' + y + '%';
    dragging.x = x;
    dragging.y = y;
  }
  function onPointerUp(e) {
    if (!dragging) return;
    frame.classList.remove('dragging');
    if (dragging.x !== undefined) {
      setCrop(kind, key, Math.round(dragging.x * 10) / 10, Math.round(dragging.y * 10) / 10);
      renderAll();
    }
    dragging = null;
  }
  frame.addEventListener('pointerdown', onPointerDown);
  frame.addEventListener('pointermove', onPointerMove);
  frame.addEventListener('pointerup', onPointerUp);
  frame.addEventListener('pointercancel', onPointerUp);
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

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
  // Store the full {thumb,full,crop} object (not just its slug) so
  // re-rendering the slot after picking doesn't need to look anything back
  // up -- the slug is only derived, via stemOf(), at export time. A newly
  // chosen photo resets to a center crop (#84) -- the old crop was framed
  // for a different photo and won't mean anything on this one.
  const { kind, key } = activePicker;
  const picked = { ...photo, crop: { ...DEFAULT_CROP } };
  if (kind === 'bannerLead') {
    store.bannerLead = stemOf(photo) === stemOf(DATA.bannerLead) ? null : picked;
  } else if (kind === 'banner') {
    store.banner = store.banner || {};
    store.banner[key] = picked;
  } else if (kind === 'day') {
    store.day = store.day || {};
    store.day[key] = picked;
  } else if (kind === 'item') {
    store.item = store.item || {};
    store.item[key] = picked;
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

// Convert a stored {thumb,full,crop} object to {filename,crop_x,crop_y} --
// that's the format apply_featured_photos.py / build_gallery.py expect
// (see the FEATURED_CSV comment in build_gallery.py and #84).
function exportPick(photo) {
  if (!photo) return null;
  const crop = photo.crop || DEFAULT_CROP;
  return { filename: stemOf(photo), crop_x: crop.x, crop_y: crop.y };
}

document.getElementById('export').onclick = () => {
  const dayOut = {};
  Object.keys(store.day || {}).forEach(k => { dayOut[k] = exportPick(store.day[k]); });
  const itemOut = {};
  Object.keys(store.item || {}).forEach(k => { itemOut[k] = exportPick(store.item[k]); });
  const out = {
    banner_lead: exportPick(store.bannerLead),
    banner: [0, 1, 2, 3].map(i => exportPick(store.banner && store.banner[i])),
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
