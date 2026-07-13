# How this site works — a crash course for a Python person

*A guided tour of every technology in this repo, using the London 2026 site itself
as the worked example. Written for someone comfortable with Python but new to
HTML, CSS, JavaScript, and web hosting.*

---

## 1. The big picture: there is no program running

The most important mental shift from Python: **nothing executes on a server.**
When someone opens https://harveystephenson.github.io/London-2026/, GitHub's
computers just hand their browser a copy of [index.html](../index.html) and the
image files it references, byte for byte, the same way a file server hands over
a PDF. This is called a **static site**.

All the "behavior" — tabs switching, the map, photo popups — happens *inside the
visitor's browser*, executed by the JavaScript that travels along inside
`index.html`. Think of `index.html` as a self-contained `.py` script that the
browser downloads and runs locally, except it's three languages in one file:

| Language | Role | Python analogy |
|---|---|---|
| **HTML** | structure & content | a nested data structure (dicts/lists) |
| **CSS** | appearance | none really — declarative styling rules |
| **JavaScript** | behavior | the actual code; browser's Python |

The Python scripts in [scripts/](../scripts/) never run on the website. They run
on your PC, ahead of time, to *prepare* the files that get uploaded. Python is
the factory; HTML/CSS/JS is the product.

(One naming trap: **JavaScript has nothing to do with Java.** The name was a
1995 marketing decision. Nobody in this repo uses Java.)

---

## 2. HTML: the structure

HTML is nested tags. A tag looks like `<name attribute="value">content</name>`.
Nesting works like nested Python data — this:

```html
<div class="overview-row" onclick="jumpToDay('day-03-jul')">
  <div class="ov-date">FRI 3 JUL</div>
  <div class="ov-desc">🌿 The Cotswolds — Broadway Tower · Snowshill ...</div>
</div>
```

is conceptually:

```python
{"tag": "div", "class": "overview-row", "onclick": "jumpToDay('day-03-jul')",
 "children": [
     {"tag": "div", "class": "ov-date", "text": "FRI 3 JUL"},
     {"tag": "div", "class": "ov-desc", "text": "🌿 The Cotswolds — ..."},
 ]}
```

The browser parses the whole file into exactly such a tree, called the **DOM**
(Document Object Model), and *keeps it live in memory* — JavaScript can then
find nodes and change them, which is how everything interactive works.

Tags you'll meet in `index.html`:

- `<div>` — a generic box. 90% of modern pages are nested divs.
- `<details>`/`<summary>` — a native collapsible section. Each **day block**
  is one of these; the open/collapse behavior costs zero JavaScript because
  the browser implements it. Free behavior like this is always preferred.
- `<table>`, `<tr>`, `<td>` — the schedule rows.
- `<a href="...">` — a link. Our event names are `<a>` tags whose job is
  hijacked: instead of navigating away, `onclick` runs a function and
  `return false` cancels the navigation.
- `<img src="photos/...">` — images by reference; the browser fetches each
  one separately (that's why the gallery lazy-loads them).
- `<script>` and `<style>` — carry the JavaScript and CSS payloads.

Two attributes carry almost all meaning:

- **`id`** — unique lookup key, like a dict key. Every day block has
  `id="day-03-jul"`, every schedule row `id="loc-broadway-tower"`. JavaScript
  fetches them with `document.getElementById(...)` — a dict lookup.
- **`class`** — non-unique tag for styling groups. All 30 photo-linked event
  names share `class="act-link"` so one CSS rule styles all of them.

---

## 3. CSS: the appearance

CSS is a list of rules: *selector* `{ property: value; ... }`. The selector
matches elements; the properties style them.

```css
.act-link {                       /* every element with class="act-link" */
  color: var(--text);
  border-bottom: 1px dotted var(--gold-dim);
}
.act-link:hover { color: var(--gold); }   /* same elements, mouse over */
```

The killer feature we exploit: **CSS variables**. At the top of `index.html`:

```css
:root {
  --bg:   #0d0f14;      /* page background */
  --gold: #c9a84c;      /* accent */
  --text: #e8eaf0;      /* body text */
  ...
}
```

`#c9a84c` is a color as hex RGB — same idea as `(201, 168, 76)` in Pillow.
Every rule below refers to `var(--gold)` instead of hard-coding the color. This
is why the three palette previews (`index-rose.html` etc.) were cheap to make:
a script swaps ~14 variable definitions plus a handful of stragglers, and the
whole site re-skins. That's also why the final palette choice (#47) is a small
change, not a rewrite.

Also in there: `@media (max-width: 600px) { ... }` blocks — rules that apply
only on narrow screens. That's the entire mechanism behind "the site works on
phones": same HTML, conditional styling.

---

## 4. JavaScript: the behavior

JavaScript is the only language browsers execute, so it plays the role Python
plays elsewhere. If you read Python, you can mostly read it:

```js
function jumpToDay(daySlug) {                        // def jumpToDay(day_slug):
  const day = document.getElementById(daySlug);     //   day = dom[day_slug]
  if (!day) return;                                 //   if day is None: return
  day.open = true;                                  //   day.open = True
  day.scrollIntoView({ behavior: 'smooth' });       //   (scroll the page there)
}
```

Differences that matter: `const`/`let` declare variables; `===` is `==`;
braces replace indentation; `null`/`undefined` split Python's `None`;
dictionaries are "objects" written `{key: value}` and lists are `[...]` (JSON —
see below — is literally this syntax frozen into a data format).

Everything interactive on the site is a small function wired to a click:

| You click... | ...which calls | What it does |
|---|---|---|
| a tab button | `showTab('gallery')` | flips `class="active"` between two panels |
| an event name | `openLocationGrid('kew-gardens')` | fills the floating modal with that location's thumbnails |
| a flight/Rania row | `openDayGrid('day-07-jul')` | same modal, but a whole day's photos |
| a thumbnail | `openLightbox(...)` | full-size viewer with ◀ ▶ navigation |
| an At-a-Glance row | `jumpToDay('day-03-jul')` | opens + scrolls to that day |
| a map pin, then a link | `jumpToLocation(...)` | switches tab, scrolls to the row, flashes it gold |

None of this "reloads the page" — the functions just mutate the DOM tree in
memory, and the browser repaints. That's the whole trick behind every modern
web app; big frameworks (React etc.) automate it, but this site is small enough
to do it by hand.

---

## 5. The data-injection trick (the strangest choice, explained)

The gallery needs to know all 717 photo paths. The obvious design — put them in
`photos/manifest.json` and have the page download it at runtime — is how most
sites work, and we deliberately **don't** do it. Why: when previewing the site
from a local file (no web server), browsers block a page from reading other
local files for security reasons, and the gallery silently broke.

Instead, [build_gallery.py](../scripts/build_gallery.py) pastes the data
*directly into the page source* between marker comments:

```js
const galleryData = /*GALLERY_DATA*/{"day-29-jun":[{"thumb":"day-29-jun/thumbs/img_2467.jpg",...}]}/*END_GALLERY_DATA*/;
```

The Python side finds the text between `/*GALLERY_DATA*/` and
`/*END_GALLERY_DATA*/` and replaces it with `json.dumps(...)` output. This
works because **JSON is valid JavaScript syntax** — Python writes a string that
the browser later reads as a literal object. It's code generation: Python
writing JavaScript.

Same story for `galleryByLocation` (photos keyed by flag id, which powers the
per-event popups). One known wart: the map-pin list `tripLocations` is
hand-maintained inside `index.html` while flag coordinates also live in
[data/flag_locations.csv](../data/flag_locations.csv) — two sources of truth
that must be edited together. A planned fix is to inject that array from the
CSV the same way.

---

## 6. The map: Leaflet

The map is not an image — it's a live widget built by **Leaflet**, an
open-source JavaScript mapping library. Loading it looks like this:

```html
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
```

That's the browser equivalent of `pip install` + `import`, except the library
is fetched from a **CDN** (content delivery network — a public file host) every
time the page loads, and pinned to version 1.9.4 like a `requirements.txt`
entry.

Three pieces make the map:

1. **Tiles** — the map imagery itself is thousands of little 256px PNG squares
   fetched on demand from CartoDB's free "Voyager" tile server. Zoom in and the
   browser fetches finer tiles. We never store any map imagery.
2. **Markers** — for each entry in `tripLocations`, `L.marker([lat, lng])`
   drops a pin. Ours are the 🚩 emoji in a styled div rather than Leaflet's
   default blue pin.
3. **Popups & tooltips** — `bindPopup(html)` builds the click bubble ("📷 View
   22 photos / Jump to this day →"); `bindTooltip(name)` is the hover label.

The London/Cambridge/Cotswolds buttons don't filter anything — they just call
`setView(center, zoom)` to fly the camera. All 41 pins exist at all times.

---

## 7. The Python pipeline (the part you already speak)

Three scripts, run in order, all feeding two CSVs:

```
photos_raw/iphone (USB dump)                      data/flag_locations.csv
        │                                            (flag name ⇄ lat/lng ⇄ pin)
        ▼                                                      │
extract_trip_photos.py ──► data/photo_manifest.csv ◄───────────┤
  EXIF date+GPS, sorts        one row per photo                │
  into uk_trip/dc_reunion     suggested_location ◄─ suggest_photo_locations.py
        │                     final_location  ◄── YOU          │
        ▼                                                      ▼
photos_raw/uk_trip  ─────────────► build_gallery.py ─────► photos/ + index.html
  (curate by deleting/adding here)   resize + inject JSON
```

Design decisions worth knowing, since they're the repo's real "architecture":

- **The manifest CSV is the database.** No SQL, no server — a 750-row CSV that
  Python reads/writes and you can open in Excel. At this scale a database
  would be pure overhead.
- **Column ownership is a contract.** `suggested_location` belongs to the
  scripts (nearest flag within 600m, haversine formula); `final_location`
  belongs to *you* and is never machine-written. Where your value matches no
  flag (e.g. the generic "Cotswolds"), the build falls back to the suggestion —
  so machine guesses fill gaps but never override you.
- **Idempotency everywhere.** Every script can be re-run safely: extract skips
  files already in the manifest and uses file-modification-time as a cheap
  pre-filter (full HEIC decode is expensive — this took a run from 30+ min to
  seconds); build_gallery skips any photo whose output JPGs are newer than the
  source. Deleting a file from `photos_raw/uk_trip` marks its row
  `deleted=true` (kept, not erased); adding one there gets it adopted into the
  manifest. The folder itself is the editing UI.
- **Parallelism.** Image work uses `ProcessPoolExecutor` (7 workers) because
  HEIC decoding is CPU-bound — same reason you'd use multiprocessing over
  threads in any Python program.
- **Derived files are disposable.** Everything in `photos/` can be regenerated
  from the raw photos + CSVs, so the scripts delete/rewrite there freely. The
  raw photos and the manifest are the only precious data — and both are
  gitignored (next section).

---

## 8. Git, GitHub, and how the site is published

- **Git** tracks every change as a commit — a snapshot with a message. The
  repo's history is the project's undo log and audit trail.
- **Branches + pull requests**: work happens on a short-lived branch
  (`feature/photo-first-links`), then a **pull request** merges it into
  `master`. On a solo project this is ceremony, but it groups each change with
  its description and links it to the issue it solves ("Closes #61" on a PR
  auto-closes the issue when merged).
- **Issues** are the to-do list (#31 videos, #24 photo review...). Numbers are
  permanent, so docs and commits can reference them forever.
- **GitHub Pages** is the host: it takes whatever is on `master` and serves it
  at the public URL. *Merging to master is deploying* — there is no separate
  publish step, no staging environment. Free tier condition: the repo must be
  public.
- **Privacy strategy**, given a public repo: [.gitignore](../.gitignore) keeps
  the raw photo dump, the GPS-laden manifest CSV, and the unredacted itinerary
  out of git entirely. Only curated, resized photos and hand-checked content
  are committed. The site also uses pseudonyms (Betty & Hugh).

Local previewing: because of the file-blocking issue from §5 and friends, the
site is always tested through a real web server —
`python -m http.server 8123` — which serves the folder over
`http://localhost:8123` exactly the way GitHub Pages will.

---

## 9. Why so deliberately low-tech?

A professional building this in 2026 would often reach for React, a build
system, a CDN for images, maybe a small backend. This repo intentionally uses
none of that:

- **One HTML file** — no build step means nothing to install or break; the
  file you edit is the file that ships.
- **No JavaScript framework** — ~300 lines of hand-written functions cover the
  needed interactivity; a framework would add megabytes and a toolchain to
  save perhaps 100 of those lines.
- **No database, no backend** — a static site can't be hacked in any
  interesting way, costs nothing, and will still work unchanged in ten years.
  The "backend" is Python scripts run manually on one PC.
- **Costs**: hosting free (Pages), map tiles free (CartoDB/OSM), library free
  (Leaflet via CDN). The only real cost is repo size from committed JPEGs,
  which is why thumbnails are resized aggressively (~400px/1600px, quality 75).

The trade-off accepted: some duplication (palette variants are generated
copies; pins are listed in two places) and everything manual (publishing a new
photo means running two scripts and pushing). For a family memory site
maintained by one person with an AI assistant, that's the right side of the
trade.

---

## 10. Mini-glossary

| Term | Meaning |
|---|---|
| **DOM** | the live tree the browser builds from HTML; what JavaScript reads/mutates |
| **tag / element** | one node of that tree, written `<div>...</div>` |
| **id / class** | unique key / reusable label on an element, for JS lookup and CSS styling |
| **CSS selector** | pattern matching elements (`.act-link`, `#trip-map`, `.day-block:hover`) |
| **CSS variable** | `--gold: #c9a84c;` — a named constant usable throughout the stylesheet |
| **media query** | CSS applied conditionally, e.g. only under 600px width (phones) |
| **JSON** | data format identical to JS literal syntax; Python's `json` module speaks it natively |
| **CDN** | public host serving popular libraries/files (unpkg for Leaflet, CartoDB for tiles) |
| **static site** | a site that is only files — no code runs on the server |
| **GitHub Pages** | GitHub's free static-site host; serves the `master` branch at a public URL |
| **EXIF** | metadata inside photo files: capture time, GPS, orientation |
| **HEIC** | Apple's photo format; Pillow needs the `pillow-heif` plugin to read it |
| **haversine** | formula for distance between two lat/lng points on a sphere |
| **lazy loading** | `loading="lazy"` on `<img>`: browser fetches images only as they scroll into view |
| **lightbox** | the dark full-screen photo viewer overlay |
| **modal** | any floating panel that blocks the page behind it (our photo grids) |

---

*Written 2026-07-13. If something here drifts out of date, the code is the
truth — this document explains the shape of things, not every detail.*
