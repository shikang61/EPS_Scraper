#!/usr/bin/env python3
"""
Scrape EPS Edinburgh 2026 (EventsAir attendee app) attendee list and group by affiliation.

How it works
------------
The attendee app stores its data as AES-encrypted JSON blobs on a public Azure
CDN (airdrive.eventsair.com). The blobs are world-readable, but the decryption
key is only handed out after you log in with a real attendee account. So this
script:

  1. POSTs your email/password to the EventsAir login API to obtain UserDetails,
     which contains the per-event AES key (AttendeesDataKey.Key).
  2. Downloads the app manifest blob to find the current AttendeesStorageId.
  3. Downloads + AES-128-CBC-decrypts the attendee blob (scheme reverse-engineered
     from the app bundle: PBKDF2-HMAC-SHA1, 1000 iterations, fixed salt + IV).
  4. Groups attendees by affiliation/organisation and writes CSV + JSON.

Credentials are read from env vars EPS_EMAIL / EPS_PASSWORD, or prompted for
(password via getpass so it never appears on screen or in shell history).

Usage
-----
    python3 eps_scraper.py
    EPS_EMAIL=you@example.com EPS_PASSWORD=secret python3 eps_scraper.py
"""

import base64
import csv
import getpass
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict

# --- Event constants (from the app URL / config) ---------------------------
APP_ID      = "114ab0d14ad54df48df8b61dfeca42ca"
EVENT_SLUG  = "eps-edinburgh"
SLUG        = "edinburgh2026"
BLOB_BASE   = "https://airdrive.eventsair.com/eventsairwesteuprod/production-orcula-public"
WEB_API_URI = "https://orcula.eventsair.com"

# --- AES scheme (reverse-engineered from app.js DecryptData) ----------------
AES_IV   = bytes.fromhex("F5502320F8429037B8DAEF761B189D12")
AES_SALT = b"92AE31A79FEEB2A3"
AES_ITERS = 1000
AES_KEYLEN = 16  # 128 bits

# Candidate field names for an attendee's affiliation, best first.
AFFILIATION_FIELDS = [
    "Organisation", "Organization", "Company", "CompanyName",
    "Affiliation", "Institution", "Employer", "OrganisationName",
]
FIRSTNAME_FIELDS = ["FirstName", "GivenName", "Firstname"]
LASTNAME_FIELDS  = ["LastName", "Surname", "Lastname", "FamilyName"]


def http_get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def login(email, password):
    """Authenticate and return the UserDetails dict (contains the AES key)."""
    qs = urllib.parse.urlencode({"eventSlug": EVENT_SLUG, "slug": SLUG})
    url = f"{WEB_API_URI}/api/Login/Login?{qs}"
    body = urllib.parse.urlencode({
        "eventSlug": EVENT_SLUG,
        "slug": SLUG,
        "email": email,
        "password": password,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Refresh-Capable": "true",
        "X-Login-Version": "2",
    })
    with urllib.request.urlopen(req, timeout=300) as r:
        payload = json.loads(r.read())
    data = payload.get("data") or payload.get("Data") or {}
    ud = data.get("UserDetails")
    if not ud:
        msg = data.get("ErrorMessage") or payload.get("ErrorMessage") or payload
        raise SystemExit(f"Login failed / no UserDetails returned: {msg}")
    return ud


def decrypt(b64_ciphertext, key_string):
    """AES-128-CBC decrypt a base64 blob using the app's PBKDF2 scheme."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    key = hashlib.pbkdf2_hmac("sha1", key_string.encode(), AES_SALT,
                              AES_ITERS, dklen=AES_KEYLEN)
    ct = base64.b64decode(b64_ciphertext)
    dec = Cipher(algorithms.AES(key), modes.CBC(AES_IV)).decryptor()
    padded = dec.update(ct) + dec.finalize()
    pad = padded[-1]                       # PKCS7 strip
    return padded[:-pad].decode("utf-8")


def fetch_blob_json(storage_id):
    return json.loads(http_get(f"{BLOB_BASE}/{storage_id}"))


def first_present(d, candidates):
    for c in candidates:
        if c in d and d[c] not in (None, ""):
            return d[c]
    return None


def find_attendee_list(obj):
    """The decrypted JSON may be a list, or a dict wrapping a list. Find it."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        # take the longest list of dicts among the values
        best = None
        for v in obj.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                if best is None or len(v) > len(best):
                    best = v
        if best is not None:
            return best
    raise SystemExit("Could not locate attendee array in decrypted data.")


def main():
    email = os.environ.get("EPS_EMAIL") or input("EventsAir email: ").strip()
    password = os.environ.get("EPS_PASSWORD") or getpass.getpass("Password: ")

    print("[1/4] Logging in ...", file=sys.stderr)
    ud = login(email, password)
    key_obj = ud.get("AttendeesDataKey") or {}
    key = key_obj.get("Key")
    if not key:
        raise SystemExit("No AttendeesDataKey in UserDetails — account may lack "
                         "access to the attendee directory.")

    print("[2/4] Reading manifest ...", file=sys.stderr)
    manifest = fetch_blob_json(APP_ID)["Data"]
    storage_id = manifest["AttendeesStorageId"]

    print("[3/4] Downloading + decrypting attendee blob ...", file=sys.stderr)
    blob = fetch_blob_json(storage_id)
    plaintext = decrypt(blob["Data"], key) if blob.get("Encrypted") else json.dumps(blob["Data"])
    data = json.loads(plaintext)
    attendees = find_attendee_list(data)
    print(f"      {len(attendees)} attendee records.", file=sys.stderr)

    # --- diagnostics: which fields are populated, and a sample record ----
    from collections import Counter
    fill = Counter()
    for a in attendees:
        for k, v in a.items():
            if v not in (None, "", [], {}):
                fill[k] += 1
    print("\n--- field fill-rates (non-empty / total) ---", file=sys.stderr)
    for k, c in fill.most_common():
        print(f"   {c:4}/{len(attendees)}  {k}", file=sys.stderr)
    with open("_sample_record.json", "w") as f:
        json.dump(attendees[:3], f, indent=2, ensure_ascii=False)
    print("   (wrote _sample_record.json — first 3 records)\n", file=sys.stderr)

    # Detect which field holds affiliation (sample first ~50 records).
    sample = attendees[:50]
    aff_field = next(
        (f for f in AFFILIATION_FIELDS if any(f in a for a in sample)), None
    )
    if aff_field is None:
        print("Sample record fields:", sorted(sample[0].keys()), file=sys.stderr)
        raise SystemExit("Could not auto-detect affiliation field — inspect fields above.")
    print(f"      Affiliation field: {aff_field!r}", file=sys.stderr)

    print("[4/4] Grouping by affiliation ...", file=sys.stderr)
    groups = defaultdict(list)
    for a in attendees:
        fn = first_present(a, FIRSTNAME_FIELDS) or ""
        ln = first_present(a, LASTNAME_FIELDS) or ""
        name = (f"{fn} {ln}").strip() or a.get("Name") or "(no name)"
        aff = (a.get(aff_field) or "(no affiliation)").strip() or "(no affiliation)"
        groups[aff].append(name)

    # --- outputs ---
    out_json = {aff: sorted(names) for aff, names in
                sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))}
    with open("attendees_by_affiliation.json", "w") as f:
        json.dump(out_json, f, indent=2, ensure_ascii=False)
    with open("attendees_by_affiliation.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Affiliation", "Name"])
        for aff, names in out_json.items():
            for n in names:
                w.writerow([aff, n])

    # data file consumed by dashboard.html (avoids file:// fetch/CORS issues)
    with open("dashboard_data.js", "w") as f:
        f.write("window.ATTENDEE_DATA = ")
        json.dump(out_json, f, ensure_ascii=False)
        f.write(";\n")

    # console summary
    print(f"\n{len(attendees)} attendees across {len(out_json)} affiliations\n")
    for aff, names in out_json.items():
        print(f"== {aff} ({len(names)}) ==")
        for n in names:
            print(f"   {n}")
        print()
    print("Wrote attendees_by_affiliation.json and .csv")


if __name__ == "__main__":
    main()
