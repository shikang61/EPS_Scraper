#!/usr/bin/env python3
"""One-off probe: log in, find ALL decryption keys in UserDetails, try each
against every component blob, and dump the agenda/sessions one locally so we can
build the agenda viewer. Writes agenda_raw.json (gitignored). Throwaway.

Every decoded blob is also written to probe_dump/ (gitignored) and scored for
poster/abstract keywords, so a per-poster blob (titles/authors/board numbers)
can be located by hand — inspect the top "poster=" candidates it prints.

The attendee blob uses AttendeesDataKey.Key; other components (agenda etc.) use
different keys, so we brute-try every key string we can find in UserDetails.

Usage:  python3 probe_agenda.py
        EPS_EMAIL=you@x.com EPS_PASSWORD=secret python3 probe_agenda.py
"""
import json, os, sys, urllib.request, base64, hashlib
from collections import Counter
from eps_scraper import login, APP_ID, BLOB_BASE, AES_IV, AES_SALT, AES_ITERS, AES_KEYLEN

SESSIONY = {"start", "end", "title", "room", "track", "presenter", "speaker",
            "session", "abstract", "venue", "location", "time", "chair", "date"}
# keys that suggest a per-poster / abstract-book blob (titles, authors, board numbers)
POSTERY = {"poster", "board", "abstract", "author", "presenter", "title", "paper"}
DUMP_DIR = "probe_dump"


def fetch(storage_id):
    req = urllib.request.Request(f"{BLOB_BASE}/{storage_id}",
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def try_decrypt(b64_ciphertext, key_string):
    """AES-128-CBC decrypt; return parsed JSON or None on any failure."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    try:
        key = hashlib.pbkdf2_hmac("sha1", key_string.encode(), AES_SALT,
                                  AES_ITERS, dklen=AES_KEYLEN)
        ct = base64.b64decode(b64_ciphertext)
        dec = Cipher(algorithms.AES(key), modes.CBC(AES_IV)).decryptor()
        padded = dec.update(ct) + dec.finalize()
        pad = padded[-1]
        txt = padded[:-pad].decode("utf-8")
        return json.loads(txt)
    except Exception:
        return None


def collect_keys(obj, found, path=""):
    """Walk UserDetails; collect every string that looks like a data key.
    Records (label, value) for any dict field named *Key holding a 'Key' string,
    or any field literally called 'Key'."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and (k == "Key" or k.lower().endswith("key")) and len(v) > 8:
                found[path + k] = v
            collect_keys(v, found, path + k + ".")
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:5]):
            collect_keys(v, found, path + f"[{i}].")


def all_keys(obj):
    keys = set()

    def collect(o, depth=0):
        if depth > 4:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                keys.add(k.lower())
                collect(v, depth + 1)
        elif isinstance(o, list):
            for x in o[:3]:
                collect(x, depth + 1)
    collect(obj)
    return keys


def kw_score(keys, terms):
    return sum(1 for k in keys if any(t in k for t in terms))


def main():
    email = os.environ.get("EPS_EMAIL") or input("EventsAir email: ").strip()
    import getpass
    password = os.environ.get("EPS_PASSWORD") or getpass.getpass("Password: ")

    print("Logging in ...", file=sys.stderr)
    ud = login(email, password)

    keys = {}
    collect_keys(ud, keys)
    print(f"Found {len(keys)} candidate key(s) in UserDetails: {list(keys)}\n",
          file=sys.stderr)
    keyvals = list(dict.fromkeys(keys.values()))  # unique, preserve order

    manifest = fetch(APP_ID)["Data"]
    comps = manifest["ComponentDataManifests"]
    print(f"{len(comps)} components.\n", file=sys.stderr)

    os.makedirs(DUMP_DIR, exist_ok=True)
    decoded = []  # (session_score, poster_score, sid, obj)
    for c in comps:
        sid = c["DataStorageId"]
        blob = fetch(sid)
        data = blob.get("Data")
        if not blob.get("Encrypted"):
            obj = data
        else:
            obj = None
            for kv in keyvals:
                obj = try_decrypt(data, kv)
                if obj is not None:
                    break
        if obj is None:
            print(f"  {sid}  NO KEY WORKED", file=sys.stderr)
            continue
        keys = all_keys(obj)
        score, pscore = kw_score(keys, SESSIONY), kw_score(keys, POSTERY)
        shape = (f"list({len(obj)})" if isinstance(obj, list)
                 else f"dict[{','.join(list(obj)[:8])}]" if isinstance(obj, dict)
                 else type(obj).__name__)
        # dump every decoded blob so a posters/abstracts component can be found by hand
        with open(f"{DUMP_DIR}/{sid}.json", "w") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        print(f"  {sid}  agenda={score:2} poster={pscore:2}  {shape}", file=sys.stderr)
        decoded.append((score, pscore, sid, obj))

    if not decoded:
        raise SystemExit("Nothing decoded — keys may live elsewhere.")

    decoded.sort(reverse=True, key=lambda t: t[0])
    score, _, sid, obj = decoded[0]
    print(f"\nBest agenda candidate: {sid} (agenda score {score})", file=sys.stderr)

    # surface likely per-poster / abstract blobs for the user to inspect
    pcands = sorted(decoded, key=lambda t: -t[1])
    print(f"\nAll {len(decoded)} decoded blob(s) dumped to {DUMP_DIR}/. "
          f"Top poster/abstract candidates:", file=sys.stderr)
    for s, ps, psid, pobj in pcands[:5]:
        shape = (f"list({len(pobj)})" if isinstance(pobj, list)
                 else f"dict[{','.join(list(pobj)[:8])}]" if isinstance(pobj, dict)
                 else type(pobj).__name__)
        print(f"   poster={ps:2} agenda={s:2}  {DUMP_DIR}/{psid}.json  {shape}", file=sys.stderr)

    with open("agenda_raw.json", "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print("Wrote agenda_raw.json", file=sys.stderr)

    recs = obj if isinstance(obj, list) else None
    if recs is None and isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                recs = v
                break
    if recs:
        print(f"\n{len(recs)} records. Field fill-rates:", file=sys.stderr)
        fill = Counter()
        for r in recs:
            if isinstance(r, dict):
                for k, v in r.items():
                    if v not in (None, "", [], {}):
                        fill[k] += 1
        for k, n in fill.most_common():
            ex = next((r[k] for r in recs if r.get(k)), "")
            print(f"   {n:4}/{len(recs)}  {k:28} e.g. {str(ex)[:60]}", file=sys.stderr)


if __name__ == "__main__":
    main()
