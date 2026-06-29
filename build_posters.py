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
            "t":   (g.get("DisplayName") or "").strip(),
            "a":   name,
            "o":   (g.get("Organization") or "").strip(),
            "th":  (g.get("Theme") or "").strip().upper(),
            "sid": g.get("SessionId") or "",
            "pdf": g.get("DocumentUri") or "",
        })
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
