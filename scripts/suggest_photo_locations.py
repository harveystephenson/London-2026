"""Suggest a flag location for each UK-trip photo based on GPS + day.

Reads data/photo_manifest.csv and data/flag_locations.csv, and fills in the
suggested_location column by finding the nearest known flag (preferring
flags tagged for the same day, falling back to all flags if none exist for
that day) within a distance tolerance. Never touches final_location — that
column is the user's own call and is left exactly as found.

Photos with no GPS, or whose nearest flag is further than the tolerance,
are left blank and reported in the summary for manual review rather than
guessed at.

Usage:
    python scripts/suggest_photo_locations.py
"""

import csv
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "photo_manifest.csv"
FLAGS_PATH = REPO_ROOT / "data" / "flag_locations.csv"

# Photos further than this from the nearest known flag are left unmatched
# rather than guessed at — itinerary stops are usually well over this far
# apart, so anything closer is a safe match.
MATCH_TOLERANCE_M = 600

DAY_SLUGS = {
    "2026-06-29": "day-29-jun",
    "2026-06-30": "day-30-jun",
    "2026-07-01": "day-01-jul",
    "2026-07-02": "day-02-jul",
    "2026-07-03": "day-03-jul",
    "2026-07-04": "day-04-jul",
    "2026-07-05": "day-05-jul",
    "2026-07-06": "day-06-jul",
    "2026-07-07": "day-07-jul",
}

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def load_flags():
    with open(FLAGS_PATH, newline="", encoding="utf-8") as f:
        flags = list(csv.DictReader(f))
    for flag in flags:
        flag["lat"] = float(flag["lat"])
        flag["lng"] = float(flag["lng"])
    return flags


def nearest_flag(lat, lon, candidates):
    best, best_dist = None, None
    for flag in candidates:
        dist = haversine_m(lat, lon, flag["lat"], flag["lng"])
        if best_dist is None or dist < best_dist:
            best, best_dist = flag, dist
    return best, best_dist


def main():
    flags = load_flags()
    flags_by_day = {}
    for flag in flags:
        flags_by_day.setdefault(flag["day"], []).append(flag)

    with open(MANIFEST_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    matched = 0
    unmatched = []
    no_gps = []

    for row in rows:
        if row["category"] != "uk_trip" or row.get("deleted") == "true":
            continue
        if row.get("source") == "moms_phone":
            # WhatsApp exports carry no GPS at all — nothing to suggest,
            # and no point flooding the no-GPS report with them.
            continue
        if not row["lat"] or not row["lon"]:
            no_gps.append(row["filename"])
            continue

        lat, lon = float(row["lat"]), float(row["lon"])
        day_slug = DAY_SLUGS.get(row["datetime"][:10])
        candidates = flags_by_day.get(day_slug, flags)

        flag, dist = nearest_flag(lat, lon, candidates)
        if flag and dist <= MATCH_TOLERANCE_M:
            row["suggested_location"] = flag["name"]
            matched += 1
        else:
            row["suggested_location"] = ""
            nearest_desc = f"{flag['name']} ({dist:.0f}m)" if flag else "no candidates"
            unmatched.append((row["filename"], nearest_desc))

    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "filename",
                "category",
                "datetime",
                "lat",
                "lon",
                "suggested_location",
                "final_location",
                "deleted",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Matched to a flag within {MATCH_TOLERANCE_M}m: {matched}")
    print(f"No GPS data: {len(no_gps)}")
    print(f"Unmatched (nearest flag too far, needs manual review): {len(unmatched)}")
    if unmatched:
        print("\nUnmatched photos (filename -> nearest flag):")
        for filename, nearest_desc in unmatched[:40]:
            print(f"  {filename} -> {nearest_desc}")
        if len(unmatched) > 40:
            print(f"  ...and {len(unmatched) - 40} more")


if __name__ == "__main__":
    main()
