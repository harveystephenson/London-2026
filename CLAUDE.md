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
4. **Day by day** — 9 collapsible `<details>` blocks, one per trip day. Deliberately stripped down from the original pre-trip planning doc for a family/friends retrospective audience: no Cayman Islands time column, no sunrise/sunset/daylight strip, no "Alt: do X instead" suggestions, no CONFIRMED/NOT BOOKED/CHECK NOW status badges or pills, no per-day Confirmations/warning boxes. Kept: time + activity text, a "📷 Photos" link next to each event (for the 9 days that have photos — opens the lightbox), and a "📺 Videos by Others" strip per day (renamed from "Watch Before You Go" — purpose is added context/color, not pre-trip research).
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
- Manifest columns: `filename, category, datetime, lat, lon, suggested_location, final_location, deleted`. `suggested_location` is Claude's guess (via `scripts/suggest_photo_locations.py`, nearest known flag by day + GPS); `final_location` is the user's own call and is what actually drives the site — see [#38](https://github.com/harveystephenson/London-2026/issues/38) (open, user's manual curation pass, in progress as of 2026-07-12).
- **To delete photos: delete from `photos_raw/uk_trip` (or `photos_raw/dc_reunion`), never from `photos_raw/iphone`.** `photos_raw/iphone` is the raw source dump `extract_trip_photos.py` reads from — deleting there just makes the file silently vanish from the source scan, not marked deleted, and re-running the script would likely sweep the still-present curated copy into `pruned_review/` with no record it was intentional. Deleting from `photos_raw/uk_trip` instead gets tracked properly: the next `extract_trip_photos.py` run marks that row `deleted=true` in the manifest (kept, not removed) instead of re-copying it back in from the source.
  - **Known slip:** on 2026-07-12 the user deleted some files directly from `photos_raw/iphone` before this distinction was clarified — those deletions are real but currently untracked in the manifest. Needs a resync (re-run `extract_trip_photos.py`) once the user confirms they're done with their current in-progress `final_location` edits in `photo_manifest.csv` — **do not run it or otherwise touch `photo_manifest.csv` before then**, to avoid clobbering their manual edits mid-session.
- `scripts/build_gallery.py` converts `photos_raw/uk_trip` into web-ready JPGs (thumbs ~400px, full ~1600px/quality 75 — deliberately lower than Pillow defaults to keep git history growth reasonable, ~213MB for 591 photos instead of ~346MB) under `photos/<day-slug>/`, and **injects the resulting JSON directly into `index.html`** between `/*GALLERY_DATA*/ ... /*END_GALLERY_DATA*/` markers rather than having the page `fetch()` it at runtime — `fetch()` of a local file is blocked under `file://`, which broke the gallery when viewed through a local preview panel instead of a real HTTP server. Also prunes (deletes — these are regenerable derived images, not originals) any thumb/full JPG no longer in the manifest.
- Only `uk_trip` photos dated within the 9-day itinerary window (2026-06-29 to 2026-07-07) make it into the gallery — pre-departure prep shots and post-trip photos are matched by `extract_trip_photos.py`'s wider date padding but excluded by `build_gallery.py`, since they don't map to any day section on the site.

**Current state (as of 2026-07-12):** extraction matched **749 UK trip photos + 15 DC/Rania photos (764 total)**; of those, **734 UK trip photos** fall within the 9-day gallery window and are live on the site — all 9 days have real photo coverage (Cotswolds: 133, Cambridge: 86, Mon 6 Jul: 24). Photo gallery is live (thumbnail grid, lightbox). Photo links and map pins now open a per-event grid popup scoped to `final_location`/`suggested_location` where curated, falling back to the whole day's photos otherwise (408/734 photos across 17/23 locations have a `suggested_location` seed as of the last automated pass). Still pending: the user's manual curation pass ([#38](https://github.com/harveystephenson/London-2026/issues/38), in progress), the `pruned_review/` reconciliation ([#24](https://github.com/harveystephenson/London-2026/issues/24)), and reconciling the untracked `photos_raw/iphone` deletions noted above.

**Known gap:** WhatsApp-forwarded photos (from mom) have no EXIF at all (WhatsApp strips it on send) — these will always need manual location tagging.

---

## 6. Open Items / Deferred Decisions

*Do not act on these without the user raising them again — they're tracked here so they aren't lost, not so they're auto-implemented.*

- **iCloud sync still broken** — unresolved as of 2026-07-12. Once fixed, switch `extract_trip_photos.py`'s `SOURCE_DIR` back to the iCloud folder (see section 5) and diff against the USB-sourced state.
- **`photos_raw/pruned_review/` reconciliation** — 226 files (189 photos + 37 screenshots) need manual review to confirm they were intentionally deleted vs. accidentally dropped by the USB import. Tracked in [#24](https://github.com/harveystephenson/London-2026/issues/24).
- **GitHub Pages not yet enabled** — offered, user said "we'll save option 2 for later" (2026-07-12). Repo is public and ready for it whenever the user wants to pull the trigger; needs explicit go-ahead first (publishing public content requires it per standing safety rules), not something to enable proactively.
- **Branch protection on `master`** — GitHub flags it as unprotected. Tracked in [#20](https://github.com/harveystephenson/London-2026/issues/20) with specific recommended settings (restrict deletions, block force pushes; skip PR-required/status-checks given the existing workflow and no CI). Not urgent for a solo repo.
- **Cotswolds lunch restaurant name unknown** — currently a placeholder ("restaurant to confirm from photos") in the Fri 3 Jul schedule. Should be filled in once photos from that day are reviewed and the venue is identified.
- **Itinerary accuracy — partially done, not exhaustively verified.** Known-wrong items the user explicitly flagged have been corrected (see section 4), but this was reactive, not a systematic pass — there could be other inaccuracies nobody's caught yet. [#8](https://github.com/harveystephenson/London-2026/issues/8) stays open for that reason.
- **DC Rania photos placement:** grabbed into `photos_raw/dc_reunion/` but not yet decided how (or whether) they fit into a UK-focused map. Likely a non-map "postscript" section rather than a pin, but undecided.
- **Mom's photos:** deferred entirely for now. Two options discussed for getting them without WhatsApp's metadata-stripping:
  - iCloud Shared Photo Library — full quality + metadata, needs both parties to set up properly.
  - iCloud Shared Album — simpler, but downsizes images and may not reliably preserve GPS EXIF; would likely need manual location tagging regardless.
  - Decision not yet made.
- **Blur/bad-photo triage:** planned but not built — a script to flag likely-blurry shots (e.g. Laplacian variance) to speed up the user's manual review pass. Final delete decisions stay with the user. Tracked in [#7](https://github.com/harveystephenson/London-2026/issues/7).
- **`final_location = "Ignore"` convention (planned, not implemented as of 2026-07-12).** The user is adding "Ignore" as a value in `final_location` for photos worth keeping but not interesting enough to show on the site — distinct from the `deleted` column, which means physically removed from `photos_raw/uk_trip`. `Ignore`-tagged photos should stay in `photos_raw/uk_trip` and in the manifest untouched; `scripts/build_gallery.py` needs a new filter to exclude `final_location == "Ignore"` rows from `photos/` and the gallery data, alongside the existing `deleted` filter. Implement once the user confirms their [#38](https://github.com/harveystephenson/London-2026/issues/38) curation pass is done — not before.
- **Follow-up discussion once #38 is done:** the user wants to sit down and review the actual `final_location` values that ended up in the column together, then discuss (a) how the curated locations should reshape the map — pins, spacing, whether every `final_location` needs its own flag — and (b) where photos should surface on the main page more broadly. Also worth a **typo/duplicate check**: since the user is typing `final_location` values by hand, near-duplicate categories are likely (e.g. two slightly different spellings meant to be the same place) — run a case-insensitive/fuzzy dedup pass over the column and flag likely duplicates before that discussion, rather than assuming every distinct string is intentional. Don't start any of this until the user explicitly says the curation pass is done.

---

## 7. Hosting

GitHub Pages, off the `London-2026` public repo. Free tier requires the repo to stay public — user has confirmed this is acceptable for this project. (User's other, unrelated repos are separate and their visibility is the user's own responsibility to manage — not something to be changed on their behalf.)

**Not yet enabled** — see section 6. Publishing is an explicit-permission action per standing safety rules; don't flip it on without the user saying so in chat, even though the underlying plan is agreed.

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
- **This whole project folder lives inside OneDrive** (`...\OneDrive\Desktop\London-2026`). `build_gallery.py` writing hundreds of JPGs in one run has taken 15-20+ minutes here (vs. a low-minutes baseline elsewhere) — OneDrive's Files On-Demand sync client contends with the script for file I/O on every write. Before kicking off a large `build_gallery.py` or `extract_trip_photos.py` run, proactively suggest the user pause OneDrive syncing first (tray icon → gear → Pause syncing). User confirmed on 2026-07-12 they know where to find it now, so just a heads-up is enough — no need to walk through it again.
