#!/usr/bin/env python3
"""Build agenda_data.js (shipped, consumed by dashboard.html) from the locally
decrypted agenda_raw.json (produced by probe_agenda.py — gitignored).

The agenda is the public conference programme (session titles / times / rooms /
tracks), so unlike the attendee list it is bundled and deployed. Trims the
204-item EventsAir agenda blob down to the fields the viewer needs and strips
HTML out of the description.

Usage:  python3 build_agenda.py
"""
import html
import json
import re
import sys

RAW = "agenda_raw.json"
OUT = "agenda_data.js"

EMPTY_DETAILS = {"", "none", "n/a", "na", "."}


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<\s*br\s*/?>", "\n", s, flags=re.I)   # <br/> -> newline
    s = re.sub(r"</p\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)                        # drop remaining tags
    s = html.unescape(s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*", "\n\n", s).strip()
    return s


def main():
    with open(RAW) as f:
        raw = json.load(f)

    items = []
    for r in raw:
        details = strip_html(r.get("Details"))
        if details.strip().lower() in EMPTY_DETAILS:
            details = ""
        items.append({
            "id":    r["AgendaItemId"],
            "date":  (r.get("Date") or "")[:10],          # 2026-06-28 (day sort key)
            "dayLabel": r.get("DateString") or "",         # Sunday, June 28, 2026
            "start": r.get("StartDateTimeUtc"),            # UTC ISO -> ICS DTSTART
            "end":   r.get("EndDateTimeUtc"),
            "s":     str(r.get("StartTime") or "").zfill(4),  # local HHMM display
            "e":     str(r.get("EndTime") or "").zfill(4),
            "name":  (r.get("Name") or "").strip(),
            "loc":   (r.get("Location") or "").strip(),
            "track": (r.get("TrackName") or "").strip(),
            "type":  r.get("AgendaTypeName") or "",
            "details": details,
        })

    # stable sort: by day, then start time, then track
    items.sort(key=lambda x: (x["date"], x["s"], x["track"]))

    with open(OUT, "w") as f:
        f.write("window.AGENDA = ")
        json.dump(items, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    days = sorted({i["date"]: i["dayLabel"] for i in items}.items())
    print(f"Wrote {OUT}: {len(items)} agenda items across {len(days)} days",
          file=sys.stderr)
    for d, lbl in days:
        n = sum(1 for i in items if i["date"] == d)
        print(f"   {d}  {lbl:30}  {n:3} items", file=sys.stderr)


if __name__ == "__main__":
    main()
