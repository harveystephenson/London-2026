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
├── index.html               # itinerary + map (pending — HTML not yet supplied by user)
├── scripts/
│   └── extract_trip_photos.py   # pulls EXIF date/GPS from local iCloud sync folder, sorts into photos_raw/
├── photos_raw/               # GITIGNORED — raw, uncurated photo dump sorted by date. Not for the public repo.
│   ├── uk_trip/
│   └── dc_reunion/
├── photos/                   # curated, final photos for the live site (not yet created — populated after review)
├── data/
│   └── photo_manifest.csv    # GITIGNORED — filename, category, datetime, lat, lon, location_name (blank, needs manual fill)
└── README.md
```

**Why `photos_raw/` and the manifest are gitignored:** the repo is public (required for free GitHub Pages hosting). Raw unreviewed photos and a CSV of precise GPS coordinates shouldn't be pushed before the user has curated them. Final, reviewed photos go in a separate tracked `photos/` folder once ready.

---

## 3. Photo Pipeline

- Source: iCloud for Windows syncs the user's full ~15K photo library to `C:\Users\harve\iCloudPhotos\Photos` (flat folder, no date subfolders, mostly `.HEIC`). Sync was still in progress as of last check.
- `scripts/extract_trip_photos.py` reads EXIF `DateTimeOriginal` + GPS from each file (via `pillow-heif` for HEIC support), and copies matches into `photos_raw/uk_trip` or `photos_raw/dc_reunion` based on date windows (padded a day on each side of known travel dates). Writes `data/photo_manifest.csv`.
- Script is idempotent — safe to re-run as the iCloud sync completes; it skips files already copied and rewrites the manifest fresh each run.
- `location_name` column in the manifest is intentionally blank — needs manual user review, especially for any photo missing GPS.

**Known gap:** WhatsApp-forwarded photos (from mom) have no EXIF at all (WhatsApp strips it on send) — these will always need manual location tagging.

---

## 4. Open Items / Deferred Decisions

*Do not act on these without the user raising them again — they're tracked here so they aren't lost, not so they're auto-implemented.*

- **DC Rania photos placement:** grabbed into `photos_raw/dc_reunion/` but not yet decided how (or whether) they fit into a UK-focused map. Likely a non-map "postscript" section rather than a pin, but undecided.
- **Mom's photos:** deferred entirely for now. Two options discussed for getting them without WhatsApp's metadata-stripping:
  - iCloud Shared Photo Library — full quality + metadata, needs both parties to set up properly.
  - iCloud Shared Album — simpler, but downsizes images and may not reliably preserve GPS EXIF; would likely need manual location tagging regardless.
  - Decision not yet made.
- **Blur/bad-photo triage:** planned but not built — a script to flag likely-blurry shots (e.g. Laplacian variance) to speed up the user's manual review pass. Final delete decisions stay with the user.
- **Itinerary accuracy:** the original HTML itinerary has drifted from what actually happened (some stops skipped or changed). Plan is to build a review checklist once the HTML is supplied, and/or diff against an updated schedule if the user has a separate Claude session regenerate one from their email.
- **Map library:** planned choice is Leaflet.js + OpenStreetMap tiles (free, no API key), not Google Maps JS API. Not yet implemented.
- **Site structure:** planned as a single static page with JS-toggled tabs ("Itinerary + Map" / "Photo Gallery") rather than separate page loads. Schedule entries and map pins should share a location identifier so clicking either jumps to the relevant photos. Not yet implemented — waiting on the source HTML.

---

## 5. Hosting

GitHub Pages, off the `London-2026` public repo. Free tier requires the repo to stay public — user has confirmed this is acceptable for this project. (User's other, unrelated repos are separate and their visibility is the user's own responsibility to manage — not something to be changed on their behalf.)

---

## 6. Development Workflow

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

## 7. Known Gotchas / Environment Notes

*Running log of environment traps hit during development — add to this as new ones surface.*

- `gh` is not on the system PATH on this machine. Use the full path: `C:\Program Files\GitHub CLI\gh.exe`.
- Almost all real iPhone photos are `.HEIC`, not `.jpg`/`.png` — Pillow needs the `pillow-heif` plugin (`pip install pillow-heif`, then `pillow_heif.register_heif_opener()`) to read them at all, EXIF included.
- The local iCloud Photos sync folder (`C:\Users\harve\iCloudPhotos\Photos`) is flat — no date-based subfolders, and filenames (`IMG_0044.PNG`, random UUIDs) carry no reliable ordering. Always filter by EXIF `DateTimeOriginal`, never by filename.
- WhatsApp strips all EXIF metadata (including GPS) on send — any photo forwarded via WhatsApp will need fully manual location tagging.
- The iCloud sync runs as its own background process independent of anything in this repo — file counts in the source folder can grow between script runs with no action from us; re-running `extract_trip_photos.py` is safe (idempotent) and picks up newly-synced files automatically.
