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

Audience: family and friends. Optimize for desktop, iPad, and phone — review on all three before calling the project done.

---

## 2. Repo Layout

```
London-2026/
├── index.html               # live site: hero, tabbed Itinerary+Map / Photo Gallery, Leaflet map, lightbox gallery
├── original/                 # GITIGNORED — preserved, unredacted source material. Never for the public repo.
│   └── itinerary_source.html # verbatim copy of the original pre-trip itinerary HTML, never modified except on explicit user direction
├── scripts/
│   ├── extract_trip_photos.py   # pulls EXIF date/GPS from a source folder, sorts into photos_raw/ (see section 4 — source is currently the USB import, not iCloud)
│   └── build_gallery.py         # converts photos_raw/uk_trip into web-ready JPGs in photos/, writes photos/manifest.json, and injects the data inline into index.html
├── photos_raw/               # GITIGNORED — raw, uncurated photo dump sorted by date. Not for the public repo.
│   ├── iphone/               # current source: manual USB import (see section 4)
│   ├── uk_trip/               # matched trip photos, copied from whichever source is active
│   ├── dc_reunion/
│   └── pruned_review/        # files present in an older source but missing from the current one — moved here, not deleted, pending manual review (#24)
├── photos/                   # TRACKED — web-ready thumbs/full JPGs actually shipped on the site, organized by day-slug folder (e.g. day-29-jun/thumbs/, day-29-jun/full/), plus manifest.json
├── data/
│   └── photo_manifest.csv    # GITIGNORED — filename, category, datetime, lat, lon, location_name (blank, needs manual fill)
└── README.md
```

**Why `photos_raw/` and the manifest are gitignored:** the repo is public (required for free GitHub Pages hosting). Raw unreviewed photos and a CSV of precise GPS coordinates shouldn't be pushed before the user has curated them. Final, reviewed photos go in a separate tracked `photos/` folder once ready.

---

## 3. Itinerary HTML Handling

The original pre-trip itinerary HTML (source for `index.html`, tracked in [#2](https://github.com/harveystephenson/London-2026/issues/2)) contains sensitive personal details that must **never** be committed to this public repo: flight booking references (PNRs), hotel/train/tour confirmation numbers, partial payment card digits, and a tour operator's personal phone number, among others.

**Handover method:** the user pastes the raw HTML directly into chat — don't scrape it via browser automation. An earlier attempt to pull it from its `claude.ai/public/artifacts/...` URL via the in-app browser was stopped by the user mid-attempt as less safe than a direct paste (see gotcha in section 8). Default to asking the user to paste content directly when there's a choice.

**Preserve the unredacted original (agreed 2026-07-11):** when the user pastes the raw itinerary HTML, save it verbatim to `original/itinerary_source.html` (gitignored). This is a preservation copy so the user has the full original in one place if they ever want to reproduce it — it is **never modified** except when the user explicitly directs a fix (e.g. a schedule detail that changed after the trip). The site's `index.html` is a separate, derived, redacted file built from this source — not the same file, and not where source-of-truth edits happen.

**Redaction rule (agreed 2026-07-11):** before committing any version of this HTML (or any derived file) to the repo, strip:
- Flight/train/restaurant/tour booking references and confirmation numbers
- Partial or full payment card digits
- Personal phone numbers of hotel/tour/venue contacts
- Any other unique identifier that could be used to look up or interfere with a real booking

Keep the unredacted original **out of git entirely** — don't commit it, even temporarily on a branch. If it needs to be saved to disk at all, keep it outside the repo or in a gitignored location.

After redacting, report a **high-level summary of what categories were stripped** back in chat — not the actual values — since the chat transcript itself shouldn't contain the sensitive detail either.

---

## 4. Photo Pipeline

- **Source is currently a manual USB import, not iCloud (temporary, as of 2026-07-12).** iCloud Photos sync got stuck/paused mid-trip and was missing every photo from three full days — Fri 3 Jul (Cotswolds), Sun 5 Jul (Cambridge), Mon 6 Jul — even after being unpaused and left overnight. Root cause suspected to be iCloud storage or a stuck upload queue on the phone; not fully resolved. Worked around by connecting the iPhone directly via USB, using Windows' "Import photos and videos" wizard, and dumping everything into `photos_raw/iphone/`. `scripts/extract_trip_photos.py`'s `SOURCE_DIR` was repointed at `photos_raw/iphone/` accordingly (see comment in the script) — **switch it back to `C:\Users\harve\iCloudPhotos\Photos` once iCloud sync is actually fixed**, then re-run and diff against the current state as a sanity check.
- `scripts/extract_trip_photos.py` reads EXIF `DateTimeOriginal` + GPS from each file (via `pillow-heif` for HEIC support) and copies matches into `photos_raw/uk_trip` or `photos_raw/dc_reunion` based on date windows (padded a day or more on each side of known travel dates). Writes `data/photo_manifest.csv`.
- Fast and idempotent: a filesystem-mtime pre-filter skips full EXIF decode for files nowhere near the trip window, and rows already recorded in the manifest are reused on re-run rather than re-decoded (see #12/#13 in section 8).
- **Re-run safe with source switches, non-destructively:** any file present in an older source (e.g. iCloud) but missing from whatever the current `SOURCE_DIR` is gets *moved* — not deleted — into `photos_raw/pruned_review/`, for manual review rather than silent loss. See #24: switching to the USB import lost 226 files (189 photos + 37 screenshots) this way, likely from a manual deletion pass the user did the same morning — needs a look before being discarded for good.
- `location_name` column in the manifest is intentionally blank — needs manual user review, especially for any photo missing GPS.
- `scripts/build_gallery.py` converts `photos_raw/uk_trip` into web-ready JPGs (thumbs ~400px, full ~1600px) under `photos/<day-slug>/`, and **injects the resulting JSON directly into `index.html`** between `/*GALLERY_DATA*/ ... /*END_GALLERY_DATA*/` markers rather than having the page `fetch()` it at runtime — `fetch()` of a local file is blocked under `file://`, which broke the gallery when viewed through a local preview panel instead of a real HTTP server. Also prunes (deletes — these are regenerable derived images, not originals) any thumb/full JPG no longer in the manifest.

**Current state (as of 2026-07-12):** **749 UK trip photos + 15 DC/Rania photos (764 total)**, all 9 itinerary days have at least some coverage. Photo gallery is live on the site (thumbnail grid, lightbox, per-event and per-map-pin links to that day's photos). Still pending: the manual curation/review pass ([#9](https://github.com/harveystephenson/London-2026/issues/9), [#10](https://github.com/harveystephenson/London-2026/issues/10)) and the `pruned_review/` reconciliation ([#24](https://github.com/harveystephenson/London-2026/issues/24)).

**Known gap:** WhatsApp-forwarded photos (from mom) have no EXIF at all (WhatsApp strips it on send) — these will always need manual location tagging.

---

## 5. Open Items / Deferred Decisions

*Do not act on these without the user raising them again — they're tracked here so they aren't lost, not so they're auto-implemented.*

- **DC Rania photos placement:** grabbed into `photos_raw/dc_reunion/` but not yet decided how (or whether) they fit into a UK-focused map. Likely a non-map "postscript" section rather than a pin, but undecided.
- **Mom's photos:** deferred entirely for now. Two options discussed for getting them without WhatsApp's metadata-stripping:
  - iCloud Shared Photo Library — full quality + metadata, needs both parties to set up properly.
  - iCloud Shared Album — simpler, but downsizes images and may not reliably preserve GPS EXIF; would likely need manual location tagging regardless.
  - Decision not yet made.
- **Blur/bad-photo triage:** planned but not built — a script to flag likely-blurry shots (e.g. Laplacian variance) to speed up the user's manual review pass. Final delete decisions stay with the user. Tracked in [#7](https://github.com/harveystephenson/London-2026/issues/7).
- **Itinerary accuracy:** the original HTML itinerary has drifted from what actually happened (some stops skipped or changed). Plan is to build a review checklist once the HTML is supplied, and/or diff against an updated schedule if the user has a separate Claude session regenerate one from their email. Tracked in [#8](https://github.com/harveystephenson/London-2026/issues/8).
- **Map library:** planned choice is Leaflet.js + OpenStreetMap tiles (free, no API key), not Google Maps JS API. Not yet implemented. Tracked in [#3](https://github.com/harveystephenson/London-2026/issues/3).
- **Site structure:** planned as a single static page with JS-toggled tabs ("Itinerary + Map" / "Photo Gallery") rather than separate page loads. Schedule entries and map pins should share a location identifier so clicking either jumps to the relevant photos. Not yet implemented — waiting on the source HTML. Tracked in [#4](https://github.com/harveystephenson/London-2026/issues/4).

---

## 6. Hosting

GitHub Pages, off the `London-2026` public repo. Free tier requires the repo to stay public — user has confirmed this is acceptable for this project. (User's other, unrelated repos are separate and their visibility is the user's own responsibility to manage — not something to be changed on their behalf.)

---

## 7. Development Workflow

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
- **No plan-first gate for this project.** Unlike macro_consensus, implement directly off the user's requests (branches, commits, PRs) rather than proposing a plan and waiting for approval first — confirmed 2026-07-11 as the preferred style here specifically.

---

## 8. Known Gotchas / Environment Notes

*Running log of environment traps hit during development — add to this as new ones surface.*

- `gh` is not on the system PATH on this machine. Use the full path: `C:\Program Files\GitHub CLI\gh.exe`.
- Almost all real iPhone photos are `.HEIC`, not `.jpg`/`.png` — Pillow needs the `pillow-heif` plugin (`pip install pillow-heif`, then `pillow_heif.register_heif_opener()`) to read them at all, EXIF included.
- The local iCloud Photos sync folder (`C:\Users\harve\iCloudPhotos\Photos`) is flat — no date-based subfolders, and filenames (`IMG_0044.PNG`, random UUIDs) carry no reliable ordering. Always filter by EXIF `DateTimeOriginal`, never by filename.
- WhatsApp strips all EXIF metadata (including GPS) on send — any photo forwarded via WhatsApp will need fully manual location tagging.
- The iCloud sync ran as its own background process independent of anything in this repo — completed 2026-07-11 (15,212 files total).
- `extract_trip_photos.py` was originally slow (30-40+ min against ~13K synced files): full-resolution HEIC decode is CPU-intensive per file, and the first version gave zero progress output and re-decoded every file on every run. **Fixed** in PR #13 (closed [#12](https://github.com/harveystephenson/London-2026/issues/12)): a filesystem-mtime pre-filter (iCloud preserves original capture date as file mtime, so files nowhere near the trip window skip decode entirely) + manifest-reuse on re-run + progress logging brought a full run down to a few seconds.
- The date-window filter is intentionally content-blind — it grabs *everything* timestamped in the trip window (screenshots, unrelated shots, burst duplicates included), not just touristy photos. This is by design (a missed real trip photo is worse than a few extras to delete) — culling happens later in the manual review pass (#9, #10), not at extraction time. GPS-based filtering was considered but rejected since the user confirmed nearly all photos in the window are genuinely UK trip photos anyway (aside from the separate DC/Rania bucket).
- **Don't scrape claude.ai artifact content via browser automation by default.** The rendered artifact loads in a cross-origin iframe (`claudeusercontent.com`) that can't be navigated to directly; getting the raw source required awkward workarounds (chunked JS reads via the same-origin `/api/published_artifacts/...` endpoint). During one attempt, a silent file download was also triggered without asking the user first — that's a standing rule violation (downloads require explicit permission) and didn't even succeed (browsers block un-requested downloads). The user stopped this approach and prefers pasting content directly into chat. Prefer direct paste over scraping when the user can reasonably provide the content themselves, and always ask before triggering any file download regardless of source.
- This project was originally created from a Claude Code session rooted in a different repo (`macro_consensus`), which meant this file wasn't auto-loaded into context — it had to be fetched manually each time. Working from a session rooted directly in `London-2026` (rather than `cd`-ing into it from elsewhere) is the correct setup going forward so this file loads automatically.
- **The desktop app's local file preview panel does not reliably run the site's JS.** Removing a `fetch()` call (which is genuinely blocked under `file://`) didn't fix a blank gallery there — the user only got a working preview after running a real local HTTP server (`python -m http.server`) and opening that URL in an actual browser tab instead of the app's preview panel. Always verify changes via a real server, not just the preview panel; if something looks broken there but works over `http://localhost`, it's the panel, not the code.
- **iCloud Photos sync can silently get stuck for days**, even after manually unpausing and leaving it overnight, with zero visible progress in the Photos app. If this happens again: check icloud.com/photos directly to see if the phone→cloud upload even happened (separate from the Windows app's cloud→local download); check iCloud storage quota (Settings → [name] → iCloud → Manage Storage) since a full quota silently blocks new uploads; as a fallback, a direct USB import (see section 4) reliably works when iCloud doesn't.
- **`pkill -f "http.server ..."` from the Bash tool does not reliably kill background Python servers on this machine** — several accumulated as zombie processes across a session despite `pkill` reporting success. Use PowerShell instead to actually kill them: `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*http.server*" } | Stop-Process -Force`.
