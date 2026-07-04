#!/usr/bin/env python3
"""
message_eval.py -- field triage for intercepted Enigma K messages (Caja 745).

For each message it prints a report card assessing what the message contributes to
recovering an unknown rotor wiring (the "C"), given the recovery hierarchy we
validated:

    right rotor  : 1 message with a crib spanning a middle-rotor turnover  (gauge)
    middle rotor : 1 long message (~130+ letters -> several consecutive middle
                   offsets)                                                 (gauge)
    left rotor   : ~3 messages at DISTINCT left-window positions, same wiring
                   and ring (i.e. same day) -> pooled                      (exact)

It does NOT crack the message (use corpus_sweep.py for that); it reads the cheap,
structural signals and flags recoverability + depth value. Over a directory it also
groups messages and highlights ready-made depth sets for the left rotor.

Usage:
    python3 message_eval.py MESSAGE.json
    python3 message_eval.py  path/to/messages/         # whole directory
"""
import sys, os, json, glob
import corpus_sweep as cs
c2n = cs.c2n; A = cs.A; WIN = cs.WIN


def _get(m, *keys, default=None):
    for k in keys:
        if k in m and m[k]:
            return m[k]
    return default


def assess(m):
    """Return a dict of triage signals for one message dict."""
    r = {}
    r["id"] = _get(m, "grundstellung", "reference", "header", "signature", default="?")
    r["class"] = _get(m, "classification", default="unclassified")
    r["sender"] = _get(m, "sender", default="?")
    r["recipient"] = _get(m, "recipient", default="?")
    r["date"] = _get(m, "date_transmission", "date_interception", default="?")
    r["serial"] = _get(m, "serial", "serial_number", "maquina", default=None)
    grund = _get(m, "grundstellung", default="")
    r["grund"] = grund
    # canonical indicator arrangement: (L,M,R)=grund[0,1,2], UKW=grund[3]
    if len(grund) == 4:
        r["windows_ULMR"] = grund[3] + grund[0] + grund[1] + grund[2]
        r["left_window"] = grund[0]
    else:
        r["windows_ULMR"] = None; r["left_window"] = None
    # cipher length
    try:
        cipher, plains = cs.parse_body(m)
        n = len(cipher)
    except Exception:
        n = _get(m, "n", default=0) or 0
        plains = []
    r["n"] = n
    r["inclear_inserts"] = len(plains)
    # crib presence (known plaintext that WAS enciphered)
    crib = _get(m, "crib", "known_plaintext", default=None)
    align = _get(m, "plaintext_cipher_alignment", default=None)
    if crib:
        r["crib_len"] = len(str(crib).replace(" ", ""))
    elif align:
        r["crib_len"] = sum(1 for x in align if isinstance(x, (list, tuple)))
    else:
        r["crib_len"] = 0
    # middle-offset coverage: the middle steps once per ~26 letters, and its offset
    # increments by 1 each step -> the covered offsets are consecutive. Count them.
    r["middle_offsets"] = max(1, (n + 25) // 26) if n else 0
    # recoverability flags for THIS message alone
    r["rec_right"] = (r["crib_len"] >= 20 and n >= 26)      # crib long enough to span a turnover
    r["rec_middle"] = (r["middle_offsets"] >= 5)            # ~5 consecutive offsets -> transitive
    r["rec_left_solo"] = False                              # never from one message
    # wiring hint from classification (actual D/F/C decided by corpus_sweep)
    cl = r["class"].lower()
    if "not" in cl:                                        # probably_not_enigma / not_enigma
        r["wiring_hint"] = "likely NOT enigma"
    elif "enigma_k" in cl:                                 # enigma_k / _certified / _probable
        r["wiring_hint"] = "enigma_k (run corpus_sweep for D/F/C)"
    else:
        r["wiring_hint"] = "unknown (candidate — worth a corpus_sweep pass)"
    return r


def print_card(r):
    print(f"=== {r['id']}  [{r['class']}] ===")
    print(f"  from {r['sender']} -> {r['recipient']}   {r['date']}"
          + (f"   serial {r['serial']}" if r['serial'] else "   serial: (none — note it if the header shows one)"))
    win = r["windows_ULMR"]
    print(f"  Grund {r['grund'] or '?'}"
          + (f"  ->  windows (U,L,M,R) = {win}   left window = {r['left_window']}" if win else "  (no 4-letter Grundstellung)"))
    print(f"  cipher letters: {r['n']}   in-clear inserts: {r['inclear_inserts']}   crib: "
          + (f"{r['crib_len']} letters" if r['crib_len'] else "none"))
    print(f"  middle offsets covered (consecutive): ~{r['middle_offsets']}")
    flag = lambda b: "YES" if b else "no "
    print(f"  recoverable from THIS message alone:  right {flag(r['rec_right'])}  "
          f"middle {flag(r['rec_middle'])}  left {flag(r['rec_left_solo'])} (left always needs depth)")
    print(f"  wiring: {r['wiring_hint']}")
    # value line
    val = []
    if r["rec_right"]: val.append("right-rotor crib")
    if r["rec_middle"]: val.append("middle-rotor length")
    if r["left_window"]: val.append(f"left-position '{r['left_window']}'")
    print(f"  VALUE: " + (", ".join(val) if val else "low (short, no crib)"))
    print()


def aggregate(reports):
    """Depth planning: group by (wiring hint, date) and report distinct left
    positions -- the left rotor needs >=3 -- plus the best right/middle candidates."""
    print("=" * 60)
    print("DEPTH PLANNING (assembling a wiring recovery)")
    print("=" * 60)
    groups = {}
    for r in reports:
        if "not enigma" in r["wiring_hint"]:
            continue
        key = (r["date"],)
        groups.setdefault(key, []).append(r)
    for (date,), rs in sorted(groups.items()):
        lefts = sorted({r["left_window"] for r in rs if r["left_window"]})
        longest = max(rs, key=lambda r: r["n"])
        best_crib = max(rs, key=lambda r: r["crib_len"])
        print(f"\n  day {date}:  {len(rs)} message(s)")
        print(f"    distinct left-window positions: {lefts}  "
              f"-> LEFT rotor {'RECOVERABLE (>=3)' if len(lefts) >= 3 else f'needs {3-len(lefts)} more distinct position(s)'}")
        print(f"    longest message: {longest['n']} letters ({longest['id']})  "
              f"-> MIDDLE {'ok' if longest['n'] >= 130 else 'need >=130'}")
        print(f"    best crib: {best_crib['crib_len']} letters ({best_crib['id']})  "
              f"-> RIGHT {'ok' if best_crib['crib_len'] >= 20 else 'need a crib >=20 spanning a turnover'}")
    print("\n  Note: same day => same Ringstellung, so distinct Grundstellung means")
    print("  distinct left offset. Group only messages of the SAME wiring (confirm with")
    print("  corpus_sweep). Serial numbers in headers -> data/serials/ to pin the machine.")


def load(path):
    data = json.load(open(path, encoding="utf-8"))
    return data if isinstance(data, list) else [data]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    target = sys.argv[1]
    paths = sorted(glob.glob(os.path.join(target, "*.json"))) if os.path.isdir(target) else [target]
    reports = []
    for pth in paths:
        try:
            for m in load(pth):
                r = assess(m); reports.append(r); print_card(r)
        except Exception as e:
            print(f"[skip {os.path.basename(pth)}: {e}]\n")
    if len(reports) > 1:
        aggregate(reports)
