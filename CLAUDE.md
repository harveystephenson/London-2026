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

## 3. Itinerary HTML Handling

The original pre-trip itinerary HTML (source for `index.html`, tracked in [#2](https://github.com/harveystephenson/London-2026/issues/2)) contains sensitive personal details that must **never** be committed to this public repo: flight booking references (PNRs), hotel/train/tour confirmation numbers, partial payment card digits, and a tour operator's personal phone number, among others.

**Handover method:** the user pastes the raw HTML directly into chat — don't scrape it via browser automation. An earlier attempt to pull it from its `claude.ai/public/artifacts/...` URL via the in-app browser was stopped by the user mid-attempt as less safe than a direct paste (see gotcha in section 8). Default to asking the user to paste content directly when there's a choice.

**Redaction rule (agreed 2026-07-11):** before committing any version of this HTML (or any derived file) to the repo, strip:
- Flight/train/restaurant/tour booking references and confirmation numbers
- Partial or full payment card digits
- Personal phone numbers of hotel/tour/venue contacts
- Any other unique identifier that could be used to look up or interfere with a real booking

Keep the unredacted original **out of git entirely** — don't commit it, even temporarily on a branch. If it needs to be saved to disk at all, keep it outside the repo or in a gitignored location.

After redacting, report a **high-level summary of what categories were stripped** back in chat — not the actual values — since the chat transcript itself shouldn't contain the sensitive detail either.

---

## 4. Photo Pipeline

- Source: iCloud for Windows synced the user's full library (15,212 files, mostly `.HEIC`) to `C:\Users\harve\iCloudPhotos\Photos` — a flat folder with no date-based subfolders. Sync completed as of 2026-07-11.
- `scripts/extract_trip_photos.py` reads EXIF `DateTimeOriginal` + GPS from each file (via `pillow-heif` for HEIC support) and copies matches into `photos_raw/uk_trip` or `photos_raw/dc_reunion` based on date windows (padded a day or more on each side of known travel dates). Writes `data/photo_manifest.csv`.
- Fast and idempotent: a filesystem-mtime pre-filter skips full EXIF decode for files nowhere near the trip window, and rows already recorded in the manifest are reused on re-run rather than re-decoded (see #12/#13 in section 8). A full run over the 15K-file library completes in seconds.
- `location_name` column in the manifest is intentionally blank — needs manual user review, especially for any photo missing GPS.

**Current state (as of 2026-07-11):** extraction complete — **613 UK trip photos + 15 DC/Rania photos (628 total)** in `photos_raw/`, manifest written to `data/photo_manifest.csv`. Ready for the manual review pass ([#9](https://github.com/harveystephenson/London-2026/issues/9), [#10](https://github.com/harveystephenson/London-2026/issues/10)).

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
