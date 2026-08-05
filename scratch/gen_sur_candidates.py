#!/usr/bin/env python3
"""Generate data/messages/SUR_cand_?.json, one per candidate 4th letter of the
Grundstellung ('SUR' + A..Z). mixed_rotors.py requires a concrete 4-letter
grundstellung -- no wildcards -- so this brute-forces the missing letter as
26 separate message files instead.

Body uses our best current transcription (MHRO, BFBL, KCVH resolved from the
photo; BFBL keeps the human reading over Claude's 'EFBL' -- unresolved, flag
if the whole sweep comes back empty). NO '?' characters anywhere: parse_body()
silently drops any non A-Z character, which would silently shift/corrupt the
rest of the ciphertext rather than erroring.
"""
import json, string, pathlib

BODY = ("IZSLWFRBYSQVMHROJHHXBFBLZJQLNWVBWQCQGQEZKCVHXQPOWPRKPJUNSNCKQGKC")
assert len(BODY) == 64, len(BODY)
assert set(BODY) <= set(string.ascii_uppercase)

OUT = pathlib.Path("data/messages")
OUT.mkdir(parents=True, exist_ok=True)

base = {
    "archive": "CDMH",
    "signature": "Caja 745",
    "date_transmission": "1936-12-06",
    "date_interception": "1936-12-08",
    "sender": "Comandante Militar de Baleares (Mallorca)",
    "recipient": "Generalísimo (Salamanca)",
    "header": None,
    "body": BODY,
    "garble_check": None,          # unknown/absent; do NOT let parse_body guess-strip one
    "reference": "REF 13 43 y 17",
    "classification": "candidate",
    "n": 64,
    "source_type": "typed_intercept",
    "notes": ("Grundstellung brute-forced: 'SUR' is legible, 4th letter lost in the "
              "scan. This file fixes grundstellung='SUR<X>' for one candidate X; run "
              "all 26 to cover the missing letter. body letters MHRO/BFBL/KCVH are the "
              "best current photo reading, not certain -- if the full 26-letter sweep "
              "finds nothing, revisit those 3 positions next (see SUR.json uncertain_cells)."),
}

for x in string.ascii_uppercase:
    m = dict(base)
    m["grundstellung"] = "SUR" + x
    path = OUT / f"SUR_cand_{x}.json"
    path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"wrote 26 files to {OUT}/SUR_cand_?.json")
