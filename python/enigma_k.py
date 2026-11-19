#!/usr/bin/env python3

# Spanish-Enigma: A research toolkit for the cryptanalysis of Spanish
# Enigma K traffic (1936-1945)
# Copyright (C) 2026  Jordi Fornés, Alba Rebull
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
enigma_k.py -- encipher or decipher one Enigma K message with a known key.

The plain machine, no search: give it the whole key and a text. The Enigma is
reciprocal, so the same command enciphers and deciphers.

It does not reimplement the machine. It calls decode_all from corpus_sweep,
the kernel the searches use, so there is one implementation to trust.

KEY CONVENTIONS (as in data/messages/*.json)
  --windows / --ring   four letters in the order U,L,M,R (reflector, left,
                       middle, right).
  --grund              group 3 of the header as transmitted. It gives the
                       windows in that same order: --grund XMOT is
                       --windows XMOT. Give one of --windows / --grund.
  --order              rotors in the left, middle and right slots, e.g. II-I-III.

STEPPING
  A rotor carries its left neighbour on when (window - ring) mod 26 equals its
  offset in data/wirings/wirings.json, block 'stepping': 22 for III and 15 for
  II on wiring F. A rotor with no offset there (I) turns over at its window
  letter in 'turnovers'. This representation reproduces every message from the
  header letters as transmitted; wirings.json says which reading of the header
  it stands for. Two overrides, for experiments:
      --turnover III=N     turnover at a window letter
      --notch III=22       turnover at a core offset (--notch none drops them all)

USAGE
    # encipher the opening of LUIS: gives OBAL XWWB JUKR UF
    python3 enigma_k.py --wiring F --order II-I-III --windows LUIS --ring UFSF \
        --text "HORAS HOY ACCION"

    # replay a stored reading, or override part of its key
    python3 enigma_k.py --json data/messages/XMOT.json
    python3 enigma_k.py --json data/messages/LUIS.json --ring AMIF

    # check every solved message in the corpus
    python3 enigma_k.py --self-test data/messages/
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus_sweep as cs

A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
PLAIN_RE = re.compile(r'<PLAIN:[^>]*>', re.I)   # clear-text inserts in a body are NOT enciphered


# ---------------------------------------------------------------- helpers
def clean(text):
    """Strip <PLAIN:...> inserts, then keep A-Z only (uppercased)."""
    return ''.join(c for c in PLAIN_RE.sub(' ', text).upper() if c in A)


def group(text, n=4):
    return ' '.join(text[i:i + n] for i in range(0, len(text), n))


def key4(s, what, origin=None):
    """origin names where the value came from, so the error points at the thing the
    user can actually fix -- a flag they typed, or a field in a message file."""
    s = s.strip().upper()
    if len(s) != 4 or any(c not in A for c in s):
        where = origin or f"--{what}"
        hint = ""
        if origin:
            hint = ("\n       the field must hold exactly 4 letters and nothing else; "
                    "put any commentary in a neighbouring note field")
        sys.exit(f"error: {where} must be exactly 4 letters A-Z, got {s!r}{hint}")
    return s


def parse_order(s):
    o = tuple(p.strip().upper() for p in s.replace('-', ' ').split())
    if sorted(o) != ['I', 'II', 'III']:
        sys.exit(f"error: --order must be a permutation of I II III (e.g. II-I-III), got {s!r}")
    return o


def apply_notch(spec):
    """--notch W=OFFSET[,W2=OFFSET2...]  |  --notch none"""
    if not spec:
        return
    if spec.strip().lower() == 'none':
        for d in [cs.NOTCH_OFFSET] + list(cs.NOTCH_BY_SET.values()):
            for k in d: d[k] = None
        return
    for part in spec.split(','):
        wheel, _, val = part.partition('=')
        wheel = wheel.strip().upper()
        if wheel not in ('I', 'II', 'III') or not val.strip().isdigit():
            sys.exit(f"error: --notch wants WHEEL=OFFSET, e.g. III=22 (got {part!r})")
        for d in [cs.NOTCH_OFFSET] + list(cs.NOTCH_BY_SET.values()):
            d[wheel] = int(val) % 26          # an offset asked for applies whatever the wiring


def apply_turnover(spec):
    """--turnover W=LETTER[,W2=LETTER2...]: window-letter turnover, Turing's frame."""
    if not spec:
        return
    for part in spec.split(','):
        wheel, _, val = part.partition('=')
        wheel = wheel.strip().upper(); val = val.strip().upper()
        if wheel not in ('I', 'II', 'III') or len(val) != 1 or val not in A:
            sys.exit(f"error: --turnover wants WHEEL=LETTER, e.g. III=B (got {part!r})")
        cs.WIN[wheel] = val
        for d in [cs.NOTCH_OFFSET] + list(cs.NOTCH_BY_SET.values()):
            d[wheel] = None                   # a window letter asked for explicitly wins


def run(wiring, order, windows, ring, text):
    """The one call that matters. decode_all is an involution: cipher in -> plain out,
    plain in -> cipher out. windows/ring are 4-letter ULMR strings."""
    if wiring not in cs.WIRINGS:
        sys.exit(f"error: wiring {wiring!r} not in wirings.json (have: {', '.join(sorted(cs.WIRINGS))})")
    uW, lW, mW, rW = [A.index(c) for c in windows]
    uR, lR, mR, rR = [A.index(c) for c in ring]
    ct = [A.index(c) for c in text]
    return cs.decode_all(wiring, order, (lW, mW, rW), uW, (uR, lR, mR, rR), ct)


def offsets(windows, ring):
    return ''.join(A[(A.index(w) - A.index(r)) % 26] for w, r in zip(windows, ring))


# ---------------------------------------------------------------- message JSON
def load_json(path):
    with open(path, encoding='utf-8') as fh:
        d = json.load(fh)
    if isinstance(d, list):          # a file may hold a one-element list
        d = d[0]
    sol = d.get('solution') or d.get('status') or {}
    block = 'solution' if d.get('solution') else ('status' if d.get('status') else None)
    key = {
        'path':    path,
        'block':   block,
        'wiring':  sol.get('wiring'),
        'order':   sol.get('rotor_order'),
        'windows': sol.get('windows_ULMR'),
        'ring':    sol.get('ringstellung_ULMR'),
        'grund':   sol.get('grundstellung') or d.get('grundstellung'),
        'body':    d.get('body', ''),
        'label':   d.get('label') or os.path.splitext(os.path.basename(path))[0],
        'plain':   sol.get('plaintext'),
        # Positions (1-indexed) where the message is KNOWN to diverge from its
        # plaintext for reasons outside the machine model -- transcription noise in a
        # twice-copied published source, or data anomalies in the printed vector.
        # Declared in the message file so the self-test can tell an expected
        # divergence from a regression instead of calling both a failure.
        'known_bad': sorted(int(x) for x in (d.get('divergences', {}) or {}).get('known_positions', [])),
    }
    return key


# ---------------------------------------------------------------- self-test
def self_test(path):
    files = ([os.path.join(path, f) for f in sorted(os.listdir(path)) if f.endswith('.json')]
             if os.path.isdir(path) else [path])
    import copy
    saved = dict(cs.NOTCH_OFFSET); saved_sets = copy.deepcopy(cs.NOTCH_BY_SET)
    ok = fail = skip = 0
    for f in files:
        k = load_json(f)
        if not (k['plain'] and k['wiring'] and k['order'] and k['ring'] and (k['windows'] or k['grund'])):
            print(f"  skip  {k['label']:<14} (no complete solution block)"); skip += 1; continue
        order = parse_order(k['order'])
        win = k['windows'] or k['grund']
        cs.NOTCH_OFFSET.update(saved)   # each message starts from the offsets in wirings.json
        for s_, d in saved_sets.items(): cs.NOTCH_BY_SET[s_].update(d)
        got = run(k['wiring'], order, win, k['ring'], clean(k['body']))
        exp = clean(k['plain'])
        n = min(len(got), len(exp))
        match = sum(a == b for a, b in zip(got[:n], exp[:n]))
        bad = [i + 1 for i in range(n) if got[i] != exp[i]]        # 1-indexed
        unexpected = [i for i in bad if i not in k['known_bad']]
        if not bad and n:
            print(f"  PASS  {k['label']:<14} {n}/{n} letters"); ok += 1
        elif n and not unexpected:
            print(f"  PASS  {k['label']:<14} {match}/{n} letters  "
                  f"({len(bad)} declared divergence{'s' if len(bad) != 1 else ''}, "
                  f"not a model defect)"); ok += 1
        else:
            print(f"  FAIL  {k['label']:<14} {match}/{n} letters  "
                  f"undeclared mismatch at {', '.join(map(str, unexpected[:10]))}"
                  f"{' ...' if len(unexpected) > 10 else ''}")
            fail += 1
    cs.NOTCH_OFFSET.update(saved)
    for s_, d in saved_sets.items(): cs.NOTCH_BY_SET[s_].update(d)
    print(f"\n{ok} passed, {fail} failed, {skip} skipped")
    return 1 if fail else 0


# ---------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(
        description="Encipher/decipher one Enigma K message with a known key "
                    "(self-reciprocal: one command does both).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Windows/ring are ULMR (reflector,left,middle,right). --grund takes group 3 "
               "as transmitted, which is already ULMR. Stepping: wirings.json, block 'stepping'.")
    p.add_argument('--json', help="message JSON; takes key + body from its solution block")
    p.add_argument('--text', help="text to run (ciphertext or plaintext); '-' reads stdin")
    p.add_argument('--wiring', help="rotor set: D or F")
    p.add_argument('--order', help="wheels in L-M-R slots, e.g. II-I-III")
    p.add_argument('--windows', help="4 letters, ULMR")
    p.add_argument('--grund', help="group 3 as transmitted; it is the windows, ULMR")
    p.add_argument('--ring', help="Ringstellung, 4 letters, ULMR")
    p.add_argument('--turnover', help="window-letter turnover override, e.g. 'III=N' or 'II=E,III=N'")
    p.add_argument('--notch', help="core-offset override, e.g. 'III=22', or 'none'")
    p.add_argument('--groups', type=int, default=4, help="output group size (default 4; 0 = no grouping)")
    p.add_argument('--raw', action='store_true', help="print the output only, ungrouped")
    p.add_argument('--self-test', metavar='PATH', help="verify against solved messages and exit")
    a = p.parse_args()

    apply_notch(a.notch)
    apply_turnover(a.turnover)

    if a.self_test:
        sys.exit(self_test(a.self_test))

    key = {'wiring': None, 'order': None, 'windows': None, 'ring': None, 'grund': None, 'body': ''}
    if a.json:
        key.update(load_json(a.json))

    wiring = (a.wiring or key['wiring'] or '').upper()
    order_s = a.order or key['order']
    ring = a.ring or key['ring']
    grund = a.grund or key['grund']
    windows = a.windows or (key['windows'] if not a.grund else None)
    text = a.text if a.text is not None else key['body']
    if text == '-':
        text = sys.stdin.read()

    # --- what is still missing, and what the file did supply -----------------
    need = [('wiring', wiring), ('order', order_s), ('ring', ring)]
    missing = [n for n, v in need if not v]
    if not (windows or grund):
        missing.append('windows (or --grund)')
    if missing:
        lines = [f"error: cannot build a key -- missing {', '.join(missing)}"]
        if a.json:
            blk = key.get('block')
            lines.append(f"       {a.json} has a {blk!r} block" if blk
                         else f"       {a.json} has no 'solution' or 'status' block")
            got = [f"{k}={key[k]!r}" for k in ('wiring', 'order', 'windows', 'ring', 'grund')
                   if key.get(k)]
            lines.append("       it supplies: " + (', '.join(got) if got else "nothing usable"))
            lines.append("       a solved message needs, inside its 'solution' block: "
                         "wiring, rotor_order, windows_ULMR (or a clean 4-letter "
                         "grundstellung), ringstellung_ULMR")
        lines.append("       supply the rest on the command line, e.g.")
        lines.append("         --wiring F --order I-III-II --windows MKCX --ring LJHU")
        sys.exit('\n'.join(lines))
    if not text or not clean(text):
        sys.exit(f"error: no text to run (use --text, or --json with a 'body' field)")

    order = parse_order(order_s)
    ring = key4(ring, 'ring', None if a.ring else f"{a.json}: ringstellung_ULMR")
    from_grund = False
    if windows:
        windows = key4(windows, 'windows', None if a.windows else f"{a.json}: windows_ULMR")
    else:
        # --grund is group 3 as transmitted, and that group IS the windows (U,L,M,R).
        grund = key4(grund, 'grund', None if a.grund else f"{a.json}: grundstellung")
        windows = grund
        from_grund = True

    ct = clean(text)
    out = run(wiring, order, windows, ring, ct)

    if a.raw:
        print(out); return
    nt = cs.notches(wiring)
    turn = ', '.join(f"{k}={cs.WIN[k]}" for k in ('I', 'II', 'III') if nt.get(k) is None)
    core = ', '.join(f"{k}={v}" for k, v in sorted(nt.items()) if v is not None)
    notch = f"window {turn}" + (f"; core-frame {core}" if core else '')
    if from_grund:
        print(f"grund {grund} (group 3 as transmitted)  =  windows {windows} (U,L,M,R)")
    print(f"wiring {wiring}   order {'-'.join(order)}   windows {windows} (ULMR)   ring {ring}   "
          f"offsets {offsets(windows, ring)}")
    print(f"turnover: {notch}   |   {len(ct)} letters\n")
    print("IN  " + (group(ct, a.groups) if a.groups else ct))
    print("OUT " + (group(out, a.groups) if a.groups else out))


if __name__ == '__main__':
    main()
