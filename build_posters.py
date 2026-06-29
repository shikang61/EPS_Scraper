#!/usr/bin/env python3
"""Build posters_data.js from posters_raw.json (the EventsAir "gallery" blob saved
by probe_agenda.py — gitignored) joined with the poster-session topic categories
in agenda_raw.json.

Each gallery entry is one poster: title (DisplayName), presenting author
(FirstName/LastName), organisation, topic code (Theme), the poster session it
belongs to (SessionId, matches an agenda item), and a PDF link (DocumentUri).

    posters_data.js   window.POSTERS        [{t,a,o,th,sid,pdf}, ...]
                      window.POSTER_THEMES  {"MCF02": "SOL, Divertor and PWI", ...}

Usage:  python3 build_posters.py
"""
import html
import json
import re
import sys
import unicodedata
from collections import Counter

# Affiliations that appear under several spellings -> one canonical name. Pure
# case/punctuation variants are merged automatically (see norm_org); this map is
# only for genuinely different strings for the same institute.
ORG_ALIASES = {
    "epfl, swiss plasma center": "EPFL",
    "university of padova": "University of Padua",
    "laboratoire de physique des plasma": "Laboratoire de Physique des Plasmas",
    "university of griefswald": "University of Greifswald",
    "tokamak energy ltd": "Tokamak Energy",
    "tokamak energy ltd.": "Tokamak Energy",
}


def norm_org(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[.,;:]", " ", s).lower()
    return re.sub(r"\s+", " ", s).strip()


def canonicalise_orgs(rows):
    """Set each poster's affiliation to one canonical spelling so institutes group
    cleanly: apply ORG_ALIASES, then collapse case/punctuation variants to the
    most common spelling in the data."""
    based = [ORG_ALIASES.get((p["o"] or "").strip().lower(), p["o"]) for p in rows]
    groups = {}
    for o in based:
        groups.setdefault(norm_org(o), Counter())[o] += 1
    canon = {k: c.most_common(1)[0][0] for k, c in groups.items()}
    for p, b in zip(rows, based):
        p["o"] = canon[norm_org(b)]

RAW = "posters_raw.json"
AGENDA_RAW = "agenda_raw.json"
OUT = "posters_data.js"


def theme_descriptions():
    """code -> description, parsed from the poster-session Details in agenda_raw."""
    desc = {}
    try:
        agenda = json.load(open(AGENDA_RAW))
    except FileNotFoundError:
        print(f"(no {AGENDA_RAW}; theme descriptions will be blank)", file=sys.stderr)
        return desc
    for r in agenda:
        if "poster session" not in (r.get("Name") or "").lower():
            continue
        text = re.sub(r"<[^>]+>", "\n", r.get("Details") or "")
        for line in html.unescape(text).splitlines():
            line = line.strip()
            if not line or set(line) <= set("_ "):
                continue
            m = re.match(r"^([A-Za-z]+)\s*(\d+)\s+(.+)$", line)
            if m:
                desc[(m.group(1) + m.group(2)).upper()] = m.group(3).strip()
    return desc


def main():
    gallery = json.load(open(RAW))
    posters = [g for g in gallery if "poster session" in (g.get("SessionName") or "").lower()]

    out = []
    for g in posters:
        name = f"{(g.get('FirstName') or '').strip()} {(g.get('LastName') or '').strip()}".strip()
        out.append({
            "id":  g.get("Id") or "",
            "t":   (g.get("DisplayName") or "").strip(),
            "a":   name,
            "o":   (g.get("Organization") or "").strip(),
            "th":  (g.get("Theme") or "").strip().upper(),
            "sid": g.get("SessionId") or "",
            "pdf": g.get("DocumentUri") or "",
        })
    canonicalise_orgs(out)

    # stable order: theme, then author surname
    out.sort(key=lambda p: (p["th"], p["a"].rsplit(" ", 1)[-1].lower(), p["t"].lower()))

    themes = theme_descriptions()
    with open(OUT, "w") as f:
        f.write("window.POSTERS = ")
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\nwindow.POSTER_THEMES = ")
        json.dump(themes, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    by_sess = {}
    for p in out:
        by_sess[p["sid"]] = by_sess.get(p["sid"], 0) + 1
    with_pdf = sum(1 for p in out if p["pdf"])
    print(f"Wrote {OUT}: {len(out)} posters across {len(by_sess)} sessions, "
          f"{len(themes)} themes, {with_pdf} with a PDF", file=sys.stderr)


if __name__ == "__main__":
    main()
