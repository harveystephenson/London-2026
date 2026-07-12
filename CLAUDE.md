# CLAUDE.md — London 2026 Trip Site

*Working reference for a fresh Claude Code session. Captures decisions and open threads from planning conversations so context isn't lost between sessions.*

---

## 1. Project Identity

A post-trip website for the family/friends UK trip: London as home base, with day trips to the Cotswolds and Cambridge. Repurposes an existing pre-trip itinerary HTML (originally built in a separate Claude conversation, hosted at a `claude.ai/public/artifacts/...` link) into a post-trip site with a map and photo galleries.

Trip dates:
- Left DC: 2026-06-28
- Landed Heathrow: 2026-06-29
- Left UK: 2026-07-07
- Separate: DC "reunion" dinner at Rania restaurant, 2026-07-10 (mom stayed behind in DC — not part of the UK leg, placement on the site TBD)

**Public-facing names are pseudonyms:** the site displays "Hugh" and "Betty" (no surname) instead of the real names, since the repo is public. Real names only exist in the gitignored `original/itinerary_source.html`. Don't reintroduce real names to `index.html`.

Audience: family and friends. Optimize for desktop, iPad, and phone — review on all three before calling the project done.

---

## 2. Repo Layout

```
London-2026/
├── index.html               # live site: hero, tabbed Itinerary+Map / Photo Gallery, Leaflet map, lightbox gallery
├── original/                 # GITIGNORED — preserved, unredacted source material. Never for the public repo.
│   └── itinerary_source.html # verbatim copy of the original pre-trip itinerary HTML, never modified except on explicit user direction
├── scripts/
│   ├── extract_trip_photos.py   # pulls EXIF date/GPS from a source folder, sorts into photos_raw/ (see section 5 — source is currently the USB import, not iCloud)
│   └── build_gallery.py         # converts photos_raw/uk_trip into web-ready JPGs in photos/, writes photos/manifest.json, and injects the data inline into index.html
├── photos_raw/               # GITIGNORED — raw, uncurated photo dump sorted by date. Not for the public repo.
│   ├── iphone/               # current source: manual USB import (see section 5). Raw dump only — never delete files here directly, it won't be tracked (see section 5)
│   ├── uk_trip/               # matched trip photos, copied from whichever source is active. THIS is where the user deletes to curate — see section 5
│   ├── dc_reunion/
│   └── pruned_review/        # files present in an older source but missing from the current one — moved here, not deleted, pending manual review (#24)
├── photos/                   # TRACKED — web-ready thumbs/full JPGs actually shipped on the site, organized by day-slug folder (e.g. day-29-jun/thumbs/, day-29-jun/full/), plus manifest.json
├── data/
│   ├── photo_manifest.csv    # GITIGNORED — filename, category, datetime, lat, lon, suggested_location, final_location, deleted
│   └── flag_locations.csv    # TRACKED — small, public-place lookup (location_id, name, lat, lng, day) used to position map pins; Claude owns lat/lng, user only edits names
├── design/
│   └── main_page_directions.html  # TRACKED — static reference mockups (3 color/type directions, 3 photo-integration layouts) for #47, not linked from index.html or built by any script
└── README.md
```

**Why `photos_raw/` and the manifest are gitignored:** the repo is public (required for free GitHub Pages hosting). Raw unreviewed photos and a CSV of precise GPS coordinates shouldn't be pushed before the user has curated them. Final, reviewed photos go in a separate tracked `photos/` folder once ready.

---

## 3. Itinerary HTML Handling

**Status: done.** The user pasted the original pre-trip itinerary HTML directly into chat (2026-07-12). It was saved verbatim to `original/itinerary_source.html` and used as the source for a redacted, restructured `index.html` — see section 4 for what that restructuring actually looks like. The workflow below is what to follow if the source HTML ever needs to be re-supplied or corrected.

The original pre-trip itinerary HTML (tracked in [#2](https://github.com/harveystephenson/London-2026/issues/2), closed) contained sensitive personal details that must **never** be committed to this public repo: flight booking references (PNRs), hotel/train/tour confirmation numbers, partial payment card digits, and a tour operator's personal phone number, among others.

**Handover method:** the user pastes the raw HTML directly into chat — don't scrape it via browser automation. An earlier attempt to pull it from its `claude.ai/public/artifacts/...` URL via the in-app browser was stopped by the user mid-attempt as less safe than a direct paste (see gotcha in section 9). Default to asking the user to paste content directly when there's a choice.

**Preserve the unredacted original:** when the user pastes the raw itinerary HTML, save it verbatim to `original/itinerary_source.html` (gitignored). This is a preservation copy so the user has the full original in one place if they ever want to reproduce it — it is **never modified** except when the user explicitly directs a fix (e.g. a schedule detail that changed after the trip). The site's `index.html` is a separate, derived, redacted file built from this source — not the same file, and not where source-of-truth edits happen.

**Redaction rule:** before committing any version of this HTML (or any derived file) to the repo, strip:
- Flight/train/restaurant/tour booking references and confirmation numbers
- Partial or full payment card digits
- Personal phone numbers of hotel/tour/venue contacts
- Any other unique identifier that could be used to look up or interfere with a real booking

Keep the unredacted original **out of git entirely** — don't commit it, even temporarily on a branch. If it needs to be saved to disk at all, keep it outside the repo or in a gitignored location.

After redacting, report a **high-level summary of what categories were stripped** back in chat — not the actual values — since the chat transcript itself shouldn't contain the sensitive detail either.

**Verification habit:** before trusting that redaction actually worked, audit the full git history (`git log --all -p | grep <sensitive-value>` across every commit/branch/file), not just the current working tree — confirmed clean this way on 2026-07-12 before a round of site restructuring, no history rewrite was ever needed because `index.html` was written pre-redacted from its first commit.

---

## 4. Site Structure & Content Decisions

`index.html` is a single static page, two JS-toggled tabs (`showTab()`), no separate page loads:

**Tab 1 — "Itinerary + Map"**, top to bottom:
1. Hero (title, dates, "Hugh & Betty" names)
2. **Map** — deliberately placed here, above "At a Glance," so it's the first real content visitors see. Leaflet.js + CartoDB Voyager tiles (colorful, retina-aware via `{r}` — an earlier CartoDB dark-tile attempt rendered as solid black and had to be reverted). Markers are single-style 🚩 flag-emoji `L.divIcon`s (not colored circles — no more confirmed/pending/free status coloring, since that stopped being meaningful post-trip). Three region tabs above the map (London / Cambridge / Cotswolds) just change `setView()` center/zoom — all markers exist regardless of which region tab is active.
3. **At a Glance** — one-line-per-day overview grid.
4. **Day by day** — 9 collapsible `<details>` blocks, one per trip day. Deliberately stripped down from the original pre-trip planning doc for a family/friends retrospective audience: no Cayman Islands time column, no sunrise/sunset/daylight strip, no "Alt: do X instead" suggestions, no CONFIRMED/NOT BOOKED/CHECK NOW status badges or pills, no per-day Confirmations/warning boxes. Kept: time + activity text, a "📷 Photos" link next to most events (opens a per-event grid popup scoped to that specific location where one's matched — see section 5 — falling back to the whole day's lightbox otherwise), and a "📺 Videos by Others" strip per day (renamed from "Watch Before You Go" — purpose is added context/color, not pre-trip research; user finds this label inelegant, rename tracked in [#31](https://github.com/harveystephenson/London-2026/issues/31)).
5. **Confirmed Bookings** — flights + hotel only, no confirmation numbers, deliberately placed last (was first in the original pre-trip doc).

**Tab 2 — "Photo Gallery"**: thumbnail grid grouped by day (`buildGalleryTab()`), click any thumbnail for a lightbox (prev/next buttons + arrow keys, Escape/click-outside to close). Gallery data is embedded **inline** in `index.html` between `/*GALLERY_DATA*/ ... /*END_GALLERY_DATA*/` markers, not fetched at runtime — see section 5, this was a deliberate fix for a real bug (blank gallery under `file://`/local-preview contexts).

**Itinerary corrected to match what actually happened**, not the original pre-trip plan (agreed 2026-07-12, applied directly as the user reported corrections — no formal audit/checklist was built, see section 6 for what's still unverified):
- Removed entirely (never happened): Pride Parade, the Chelsea breakfast, Churchill Arms, Harry Potter Studios
- Added: The Notting Hill Bookshop (the film's bookstore), Cutie's trip to Liverpool Street Station, High Tea at Jacqueline (The Chancery Rosewood), a Burford stop in the Cotswolds
- Retimed: Notting Hill/Portobello Road to morning, Dishoom Permit Room to lunch (were afternoon/dinner in the plan)
- The whole "Reference & Ideas" section (action items, restaurant wishlist, useful links) was deleted outright — pre-trip planning content with no place on a retrospective site

---

## 5. Photo Pipeline

- **Source is currently a manual USB import, not iCloud (temporary, as of 2026-07-12).** iCloud Photos sync got stuck/paused mid-trip and was missing every photo from three full days — Fri 3 Jul (Cotswolds), Sun 5 Jul (Cambridge), Mon 6 Jul — even after being unpaused and left overnight. Root cause suspected to be iCloud storage or a stuck upload queue on the phone; not fully resolved. Worked around by connecting the iPhone directly via USB, using Windows' "Import photos and videos" wizard, and dumping everything into `photos_raw/iphone/`. `scripts/extract_trip_photos.py`'s `SOURCE_DIR` was repointed at `photos_raw/iphone/` accordingly (see comment in the script) — **switch it back to `C:\Users\harve\iCloudPhotos\Photos` once iCloud sync is actually fixed**, then re-run and diff against the current state as a sanity check.
- `scripts/extract_trip_photos.py` reads EXIF `DateTimeOriginal` + GPS from each file (via `pillow-heif` for HEIC support) and copies matches into `photos_raw/uk_trip` or `photos_raw/dc_reunion` based on date windows (padded a day or more on each side of known travel dates). Writes `data/photo_manifest.csv`.
- Fast and idempotent: a filesystem-mtime pre-filter skips full EXIF decode for files nowhere near the trip window, and rows already recorded in the manifest are reused on re-run rather than re-decoded (see #12/#13 in section 9).
- **Re-run safe with source switches, non-destructively:** any file present in an older source (e.g. iCloud) but missing from whatever the current `SOURCE_DIR` is gets *moved* — not deleted — into `photos_raw/pruned_review/`, for manual review rather than silent loss. See #24: switching to the USB import lost 226 files (189 photos + 37 screenshots) this way, likely from a manual deletion pass the user did the same morning — needs a look before being discarded for good.
- Manifest columns: `filename, category, datetime, lat, lon, suggested_location, final_location, deleted`. `suggested_location` is Claude's guess (via `scripts/suggest_photo_locations.py`, nearest known flag by day + GPS); `final_location` is the user's own call and is what actually drives the site. **`final_location = "Ignore"`** is a reserved value meaning keep the photo but never show it on the site — `build_gallery.py` excludes those rows entirely (28 photos as of 2026-07-12), distinct from `deleted` (physically removed from `photos_raw/uk_trip`).
- **To delete photos: delete from `photos_raw/uk_trip` (or `photos_raw/dc_reunion`), never from `photos_raw/iphone`.** `photos_raw/iphone` is the raw source dump `extract_trip_photos.py` reads from — deleting there just makes the file silently vanish from the source scan, not marked deleted, and re-running the script would likely sweep the still-present curated copy into `pruned_review/` with no record it was intentional. Deleting from `photos_raw/uk_trip` instead gets tracked properly: the next `extract_trip_photos.py` run marks that row `deleted=true` in the manifest (kept, not removed) instead of re-copying it back in from the source.
- **Grouping by location is exact-string match against `data/flag_locations.csv`'s `name` column — strip whitespace before comparing.** Hand-typed CSV values are prone to stray leading/trailing spaces (bit us on 2026-07-12: `"Bank of England "`, `"Battersea Power Station "` silently failed to group until `build_gallery.py` started stripping both sides before the lookup). If a `final_location` looks like it should be grouping but isn't, check for this first.
- **Don't add every `final_location` value to `flag_locations.csv` blindly — check geography first.** `Heathrow Airport` and `Dulles Airport` are deliberately excluded from ever becoming map pins (per explicit user instruction, 2026-07-12) — they still group fine by day, they just never get flag/lat-lng entries. Dulles especially: a Virginia coordinate on a UK-focused map would badly skew any future auto-bounds-fitting. Same caution applies to `Rania, DC` (already naturally excluded since it's `category: dc_reunion`, not `uk_trip`).
- `scripts/build_gallery.py` converts `photos_raw/uk_trip` into web-ready JPGs (thumbs ~400px, full ~1600px/quality 75 — deliberately lower than Pillow defaults to keep git history growth reasonable, ~213MB for 591 photos instead of ~346MB) under `photos/<day-slug>/`, and **injects the resulting JSON directly into `index.html`** between `/*GALLERY_DATA*/ ... /*END_GALLERY_DATA*/` markers rather than having the page `fetch()` it at runtime — `fetch()` of a local file is blocked under `file://`, which broke the gallery when viewed through a local preview panel instead of a real HTTP server. Also prunes (deletes — these are regenerable derived images, not originals) any thumb/full JPG no longer in the manifest.
- Only `uk_trip` photos dated within the 9-day itinerary window (2026-06-29 to 2026-07-07) make it into the gallery — pre-departure prep shots and post-trip photos are matched by `extract_trip_photos.py`'s wider date padding but excluded by `build_gallery.py`, since they don't map to any day section on the site.

**Current state (as of 2026-07-12, end of session):** extraction matched 745 UK trip photos + 11 DC/Rania photos (756 total). Of those, **706 UK trip photos** are live on the site (734 within the 9-day window, minus 28 tagged `final_location = "Ignore"`) — all 9 days have real photo coverage. The user's manual `final_location` curation pass ([#38](https://github.com/harveystephenson/London-2026/issues/38)) is done, the site was reconciled against it in #49, and two follow-up bug/data fixes landed in #51 and #52: **628/706 photos group by specific location across 36 map pins, all populated (zero empty pins)** — up from 408/734 across 22 pins pre-curation, down from a peak of 46 pins before the empty ones were removed. Photo links and map pins open a per-event grid popup scoped to that specific location, falling back to the whole day's photos where no match exists yet. **The site is live** at https://harveystephenson.github.io/London-2026/ (see section 7). Still pending: the `pruned_review/` reconciliation ([#24](https://github.com/harveystephenson/London-2026/issues/24)), the Cotswolds villages ([#53](https://github.com/harveystephenson/London-2026/issues/53) — user disputes only 3/8 tour-guide stops having matched photos), pin-crowding/overlap cleanup ([#50](https://github.com/harveystephenson/London-2026/issues/50)), and build speed ([#54](https://github.com/harveystephenson/London-2026/issues/54)).

**Known gap:** WhatsApp-forwarded photos (from mom) have no EXIF at all (WhatsApp strips it on send) — these will always need manual location tagging.

---

## 6. Open Items / Deferred Decisions

*Do not act on these without the user raising them again — they're tracked here so they aren't lost, not so they're auto-implemented.*

- **iCloud sync still broken** — unresolved as of 2026-07-12. Once fixed, switch `extract_trip_photos.py`'s `SOURCE_DIR` back to the iCloud folder (see section 5) and diff against the USB-sourced state.
- **`photos_raw/pruned_review/` reconciliation** — 226 files (189 photos + 37 screenshots) need manual review to confirm they were intentionally deleted vs. accidentally dropped by the USB import. Tracked in [#24](https://github.com/harveystephenson/London-2026/issues/24).
- **Branch protection on `master`** — GitHub flags it as unprotected. Tracked in [#20](https://github.com/harveystephenson/London-2026/issues/20) with specific recommended settings (restrict deletions, block force pushes; skip PR-required/status-checks given the existing workflow and no CI). Not urgent for a solo repo.
- **Cotswolds lunch restaurant name unknown** — currently a placeholder ("restaurant to confirm from photos") in the Fri 3 Jul schedule. Should be filled in once photos from that day are reviewed and the venue is identified.
- **Itinerary accuracy — partially done, not exhaustively verified.** Known-wrong items the user explicitly flagged have been corrected (see section 4), but this was reactive, not a systematic pass — there could be other inaccuracies nobody's caught yet. [#8](https://github.com/harveystephenson/London-2026/issues/8) stays open for that reason.
- **DC Rania photos placement:** grabbed into `photos_raw/dc_reunion/` but not yet decided how (or whether) they fit into a UK-focused map. Likely a non-map "postscript" section rather than a pin, but undecided.
- **Mom's photos:** deferred entirely for now. Two options discussed for getting them without WhatsApp's metadata-stripping:
  - iCloud Shared Photo Library — full quality + metadata, needs both parties to set up properly.
  - iCloud Shared Album — simpler, but downsizes images and may not reliably preserve GPS EXIF; would likely need manual location tagging regardless.
  - Decision not yet made.
- **Blur/bad-photo triage:** planned but not built — a script to flag likely-blurry shots (e.g. Laplacian variance) to speed up the user's manual review pass. Final delete decisions stay with the user. Tracked in [#7](https://github.com/harveystephenson/London-2026/issues/7).
- **Cotswolds villages still mostly unresolved — tracked in [#53](https://github.com/harveystephenson/London-2026/issues/53).** Of the 8 tour-guide stops from #39, only 3 ended up with any matched photos (Broad Campden: 1, Broadway Tower: 22, Broadway: 32); the other 5 (Chipping Campden, Snowshill, Upper Slaughter, Lower Slaughter, Bourton-on-the-Water) had zero matches and were removed as flags in #52. (Burford — 2 matches — and Moreton-in-Marsh — 0, also removed — are separate pre-existing flags, not part of the 8-stop list; 57/133 Cotswolds photos are matched in total across all flags.) **User is confident they have photos from every stop on the tour-guide list**, not just 3 — this is a real discrepancy to investigate, not assumed absence. The `broadway-tower` flag itself was a worked example of the likely fix: it also showed zero matches until the actual GPS cluster was found by hand (a tight 22-photo, 16-minute cluster ~2.5km from the original hand-estimated coordinate) and the flag's lat/lng corrected to match reality. Same technique likely needed for the other 5: pull unmatched Cotswolds photos chronologically with GPS, look for tight time/location clusters, recompute flag coordinates from real cluster centroids rather than estimates. See #53 for the exact investigation steps.
- **Typo/duplicate check on `final_location`, still not done.** Ran an eyeball pass during the reconciliation on 2026-07-12 (caught 5 real naming mismatches, fixed in #49) but never ran a systematic fuzzy/case-insensitive dedup pass over the full column. Worth doing before the next round of map changes.
- **Map reshaping / main-page photo placement discussion — in progress, not concluded.** #49 (merged 2026-07-12) added 23 new flags driven by the user's actual `final_location` data; #52 then removed 10 flags that ended up with zero matched photos (empty pins were "distracting," per the user), landing at **36 pins, all populated** as of 2026-07-12. Still open: Piccadilly Circus/Ambassadors Clubhouse pin overlap and general spacing ([#50](https://github.com/harveystephenson/London-2026/issues/50)), and where photos surface on the main page beyond the map (see #47 — the mockups are saved at `design/main_page_directions.html` (PR #58), a permanent local copy of what was originally only a published Artifact; open that file directly rather than hunting for the Artifact link).
- ~~Build speed~~ — **fixed 2026-07-12** ([#54](https://github.com/harveystephenson/London-2026/issues/54), PR #55): `build_gallery.py` is now incremental (skips any photo whose thumb/full JPGs are newer than the source) and parallel (ProcessPoolExecutor for photos that do need work; thumbs derive from the 1600px full, not the ~12MP original). Data-only rebuilds (`final_location` edits, flag changes) run in ~3s instead of 7+ min, and OneDrive no longer re-uploads ~267MB of identical JPGs after every run. `photos/.build_settings.json` stamps the size/quality constants — changing them (or passing `--force`) triggers a full rebuild.

---

## 7. Hosting

**Live since 2026-07-12: https://harveystephenson.github.io/London-2026/** — GitHub Pages, off the `London-2026` public repo, serving `master` from `/`. Free tier requires the repo to stay public — user has confirmed this is acceptable for this project. (User's other, unrelated repos are separate and their visibility is the user's own responsibility to manage — not something to be changed on their behalf.)

**Auto-rebuilds on every push to master** — no separate publish step needed; a merged PR is live within a minute or two.

**No private staging exists on the free tier for a public repo** — enabling Pages is the same action as publishing to the world (the URL is just unguessable/unlinked, not access-controlled). User explicitly chose "publish as-is, known gaps included" over a pre-publish cleanup pass, and shares the link with family themselves — not something to send on their behalf. Enabled via `gh api repos/harveystephenson/London-2026/pages -X POST -f "source[branch]=master" -f "source[path]=/"`.

---

## 8. Development Workflow

**Push periodically via pull request — this is a standing user preference, not a one-off request.**

- Config/reference files (`CLAUDE.md`, `.gitignore`, `README.md`) may be pushed directly to `master`.
- Everything else (scripts, site code, content) goes through a feature branch + PR:
  ```
  git checkout -b feature/short-desc
  # commit changes
  git push -u origin feature/short-desc
  gh pr create --title "..." --body "..."
  ```
- **If the change relates to an open issue, link the PR to it** — include `Closes #N` (or `Refs #N` if it only partially addresses the issue) in the PR body so GitHub attaches them automatically. Check open issues before opening a PR if it's not obvious which one applies.
- **PRs are for tracking, not per-PR review** — the user does not want to review each PR individually. Merge once the PR is open, mergeable (clean, no failing checks if any are configured), and its issue links are in place — no need to ask for confirmation first. The user's engagement in this chat/session is standing approval for the work being merged.
- **Close issues proactively when the related work merges** — don't wait to be asked. Use `gh issue close <N> --comment "..."` with a comment covering: (1) what was implemented, (2) the key design decisions, (3) the relevant commit hash(es) or PR number. Do this immediately after the relevant work lands.
- **No plan-first gate for this project.** Unlike macro_consensus, implement directly off the user's requests (branches, commits, PRs) rather than proposing a plan and waiting for approval first.
- **Watch out for accidental direct-to-master commits** — happened once (2026-07-12) when a large restructuring commit was made without first creating a feature branch. Caught before pushing and moved onto a proper branch/PR, but double-check `git branch --show-current` before committing site-code changes.

---

## 9. Known Gotchas / Environment Notes

*Running log of environment traps hit during development — add to this as new ones surface.*

- `gh` is not on the system PATH on this machine. Use the full path: `C:\Program Files\GitHub CLI\gh.exe`.
- Almost all real iPhone photos are `.HEIC`, not `.jpg`/`.png` — Pillow needs the `pillow-heif` plugin (`pip install pillow-heif`, then `pillow_heif.register_heif_opener()`) to read them at all, EXIF included.
- The local iCloud Photos sync folder (`C:\Users\harve\iCloudPhotos\Photos`) is flat — no date-based subfolders, and filenames (`IMG_0044.PNG`, random UUIDs) carry no reliable ordering. Always filter by EXIF `DateTimeOriginal`, never by filename.
- WhatsApp strips all EXIF metadata (including GPS) on send — any photo forwarded via WhatsApp will need fully manual location tagging.
- `extract_trip_photos.py` was originally slow (30-40+ min against ~13K synced files): full-resolution HEIC decode is CPU-intensive per file, and the first version gave zero progress output and re-decoded every file on every run. **Fixed** in PR #13 (closed [#12](https://github.com/harveystephenson/London-2026/issues/12)): a filesystem-mtime pre-filter (source folders preserve original capture date as file mtime, so files nowhere near the trip window skip decode entirely) + manifest-reuse on re-run + progress logging brought a full run down to seconds/low-minutes even for hundreds of files.
- The date-window filter is intentionally content-blind — it grabs *everything* timestamped in the trip window (screenshots, unrelated shots, burst duplicates included), not just touristy photos. This is by design (a missed real trip photo is worse than a few extras to delete) — culling happens later in the manual review pass (#9, #10), not at extraction time. GPS-based filtering was considered but rejected since the user confirmed nearly all photos in the window are genuinely UK trip photos anyway (aside from the separate DC/Rania bucket).
- **Don't scrape claude.ai artifact content via browser automation by default.** The rendered artifact loads in a cross-origin iframe (`claudeusercontent.com`) that can't be navigated to directly; getting the raw source required awkward workarounds (chunked JS reads via the same-origin `/api/published_artifacts/...` endpoint). During one attempt, a silent file download was also triggered without asking the user first — that's a standing rule violation (downloads require explicit permission) and didn't even succeed (browsers block un-requested downloads). The user stopped this approach and prefers pasting content directly into chat. Prefer direct paste over scraping when the user can reasonably provide the content themselves, and always ask before triggering any file download regardless of source.
- This project was originally created from a Claude Code session rooted in a different repo (`macro_consensus`), which meant this file wasn't auto-loaded into context — it had to be fetched manually each time. Working from a session rooted directly in `London-2026` (rather than `cd`-ing into it from elsewhere) is the correct setup going forward so this file loads automatically.
- **The desktop app's local file preview panel does not reliably run the site's JS.** Removing a `fetch()` call (which is genuinely blocked under `file://`) didn't fix a blank gallery there — the user only got a working preview after running a real local HTTP server (`python -m http.server`) and opening that URL in an actual browser tab instead of the app's preview panel. Always verify changes via a real server, not just the preview panel; if something looks broken there but works over `http://localhost`, it's the panel, not the code.
- **iCloud Photos sync can silently get stuck for days**, even after manually unpausing and leaving it overnight, with zero visible progress in the Photos app. If this happens again: check icloud.com/photos directly to see if the phone→cloud upload even happened (separate from the Windows app's cloud→local download); check iCloud storage quota (Settings → [name] → iCloud → Manage Storage) since a full quota silently blocks new uploads; as a fallback, a direct USB import (see section 5) reliably works when iCloud doesn't.
- **`pkill -f "http.server ..."` from the Bash tool does not reliably kill background Python servers on this machine** — several accumulated as zombie processes across a session despite `pkill` reporting success. Use PowerShell instead to actually kill them: `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*http.server*" } | Stop-Process -Force`.
- The Enter-key-inserts-newline issue the user hit is **not** a Claude Code keybindings problem — `~/.claude/keybindings.json` doesn't exist, so the default (`Enter` submits, `Ctrl+J` for newline) is in effect. If it recurs, it's likely a setting inside whatever chat surface the user is typing into (Desktop app preference), not this project or Claude Code's config.
- **This whole project folder lives inside OneDrive** (`...\OneDrive\Desktop\London-2026`). `build_gallery.py` writing hundreds of JPGs in one run has taken 15-20+ minutes here (vs. a low-minutes baseline elsewhere) — OneDrive's Files On-Demand sync client contends with the script for file I/O on every write. Since the #54 incremental rebuild landed, ordinary `build_gallery.py` runs write almost nothing and don't need any OneDrive precautions — the heads-up only still applies to genuinely large write runs: `build_gallery.py --force` (or after changing size/quality constants), or an `extract_trip_photos.py` run pulling in many new files. For those, proactively suggest pausing OneDrive syncing first (tray icon → gear → Pause syncing). User confirmed on 2026-07-12 they know where to find it, so just a heads-up is enough — no need to walk through it again.
