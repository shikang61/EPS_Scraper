#!/usr/bin/env python3
"""Build the static assets the dashboard's country filter + map ship.

Everything here is public (geometry + institution->country facts); NO attendee
data is baked in. The map/filter are rendered client-side from whatever attendee
data is loaded (bundled locally, or live-pulled in-browser on the public deploy).

  affil_country.js  window.AFFIL_COUNTRY  normalised affiliation -> ISO2
                    window.COUNTRY_NAMES  ISO2 -> display name
  world_map.js      window.WORLD_MAP      land backdrop + per-country SVG paths
                                          + centroids (equirectangular, 1000x500)

Also prints a coverage report against the local attendee data.

    python3 build_countries.py
"""

import json
import sys
import urllib.request

from eps_scraper import norm_key  # same normalisation the dashboard uses

LAND_URL = ("https://raw.githubusercontent.com/martynafford/"
            "natural-earth-geojson/master/110m/physical/ne_110m_land.json")
ADMIN_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
             "master/geojson/ne_110m_admin_0_countries.geojson")

W, H = 1000, 500
EMPTY = "(no affiliation)"

# ISO2 -> (lat, lon, display name). Countries our affiliations map to.
COUNTRIES = {
    "DE": (51.1, 10.4, "Germany"),      "FR": (46.6, 2.4, "France"),
    "GB": (54.0, -2.5, "United Kingdom"),"CH": (46.8, 8.2, "Switzerland"),
    "US": (39.8, -98.6, "United States"),"JP": (36.2, 138.3, "Japan"),
    "ES": (40.0, -3.7, "Spain"),        "CZ": (49.8, 15.5, "Czechia"),
    "KR": (36.4, 127.9, "South Korea"), "IT": (42.8, 12.6, "Italy"),
    "SE": (62.2, 14.9, "Sweden"),       "CN": (35.9, 104.2, "China"),
    "FI": (64.5, 26.3, "Finland"),      "PT": (39.6, -8.0, "Portugal"),
    "SG": (1.35, 103.82, "Singapore"),  "IN": (22.6, 79.6, "India"),
    "BE": (50.6, 4.6, "Belgium"),       "AT": (47.6, 14.1, "Austria"),
    "PL": (52.1, 19.4, "Poland"),       "TW": (23.7, 121.0, "Taiwan"),
    "NL": (52.2, 5.6, "Netherlands"),   "RO": (45.9, 24.9, "Romania"),
    "CA": (56.1, -106.3, "Canada"),     "UA": (48.4, 31.2, "Ukraine"),
    "IL": (31.4, 35.0, "Israel"),       "GR": (39.1, 22.0, "Greece"),
    "SI": (46.1, 14.9, "Slovenia"),     "HU": (47.2, 19.4, "Hungary"),
    "NO": (64.5, 11.5, "Norway"),    "AU": (-25.0, 134.0, "Australia"),
}
COUNTRY_NAMES = {iso: name for iso, (_, _, name) in COUNTRIES.items()}


def project(lon, lat):
    return (lon + 180) * (W / 360), (90 - lat) * (H / 180)


def ring_to_path(ring):
    return "M" + "L".join("%.1f %.1f" % project(lon, lat) for lon, lat in ring) + "Z"


def geom_to_path(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return "".join(ring_to_path(ring) for poly in polys for ring in poly)


def country_path(geom, clat, clon, dlat=30, dlon=40):
    """Like geom_to_path but drops polygons far from (clat, clon) — i.e. overseas
    territories (e.g. French Guiana) that otherwise smear the shape across the map."""
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    segs = []
    for poly in polys:
        outer = poly[0]
        plat = sum(p[1] for p in outer) / len(outer)
        plon = sum(p[0] for p in outer) / len(outer)
        if abs(plat - clat) <= dlat and abs(plon - clon) <= dlon:
            segs.extend(ring_to_path(ring) for ring in poly)
    return "".join(segs)


def fetch(url):
    return json.loads(urllib.request.urlopen(url, timeout=60).read())


def iso_of(props):
    for k in ("ISO_A2_EH", "ISO_A2", "WB_A2"):
        v = props.get(k)
        if v and v not in ("-99", "-1"):
            return v
    return None


def build_world():
    print("Fetching land + country geometry ...", file=sys.stderr)
    land = "".join(geom_to_path(f["geometry"]) for f in fetch(LAND_URL)["features"])
    paths = {}
    for f in fetch(ADMIN_URL)["features"]:
        iso = iso_of(f["properties"])
        if iso in COUNTRIES:
            lat, lon, _ = COUNTRIES[iso]
            paths[iso] = country_path(f["geometry"], lat, lon) or geom_to_path(f["geometry"])
    centroids = {iso: [round(x, 1), round(y, 1)]
                 for iso, (lat, lon, _) in COUNTRIES.items()
                 for x, y in [project(lon, lat)]}
    return {"w": W, "h": H, "land": land, "paths": paths, "centroids": centroids}


def write_js(path, *pairs):
    with open(path, "w") as f:
        for i, (var, obj) in enumerate(pairs):
            f.write(f"window.{var} = ")
            json.dump(obj, f, ensure_ascii=False)
            f.write(";\n")


def main():
    cmap = json.load(open("affiliation_country.json"))
    affil_country = {norm_key(a): iso for a, iso in cmap.items()
                     if not a.startswith("_") and iso}
    write_js("affil_country.js",
             ("AFFIL_COUNTRY", affil_country), ("COUNTRY_NAMES", COUNTRY_NAMES))

    world = build_world()
    write_js("world_map.js", ("WORLD_MAP", world))
    missing = sorted(set(COUNTRIES) - set(world["paths"]))
    if missing:
        print(f"No polygon at this resolution (marker fallback): {missing}",
              file=sys.stderr)

    # ---- coverage report against local attendee data ----
    affil = json.load(open("attendees_by_affiliation.json"))
    unmapped, unknown_iso, mapped = [], set(), 0
    for aff, names in affil.items():
        if aff == EMPTY:
            continue
        iso = affil_country.get(norm_key(aff))
        if not iso:
            unmapped.append((aff, len(names)))
        elif iso not in COUNTRIES:
            unknown_iso.add(iso)
        else:
            mapped += len(names)
    print(f"\nMapped {mapped} attendees · {len(unmapped)} affiliations unmapped "
          f"({sum(n for _, n in unmapped)} attendees)", file=sys.stderr)
    if unknown_iso:
        print(f"!! ISO codes missing from COUNTRIES table: {sorted(unknown_iso)}",
              file=sys.stderr)
    if unmapped:
        print("\nUnmapped (edit affiliation_country.json):", file=sys.stderr)
        for a, n in sorted(unmapped, key=lambda t: -t[1]):
            print(f"   {n:3}  {a}", file=sys.stderr)
    print("\nWrote affil_country.js + world_map.js", file=sys.stderr)


if __name__ == "__main__":
    main()
