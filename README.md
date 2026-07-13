# London 2026 Trip

Post-trip website with the itinerary, an interactive map, and photos from our UK
trip (London, plus day trips to the Cotswolds and Cambridge, and a closing
dinner in DC).

**Live site: https://harveystephenson.github.io/London-2026/**

## Structure
- `index.html` — the whole site: itinerary + Leaflet map + photo gallery, in one file
- `index-rose.html` / `index-green.html` / `index-terracotta.html` — full-site palette previews (design decision pending)
- `photos/` — web-ready thumbnails and full-size JPEGs, one folder per day
- `data/flag_locations.csv` — map pin positions
- `scripts/` — the Python pipeline that turns a raw iPhone photo dump into the gallery
- `design/` — visual-direction mockups

## How it all works
New to HTML/CSS/JavaScript or curious about the design choices? Read
**[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)** — a crash course on every
technology in this repo, written for a Python reader, using this project as the
worked example.

## Hosting
GitHub Pages, serving the `master` branch — every merge to `master` deploys
automatically.
