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
enigma_k.py -- straight encipher/decipher for one Enigma K message, given the key.

This is the plain simulator (no search): you supply the full key, it runs the text.
Enigma is self-reciprocal, so the SAME command enciphers and deciphers -- there is no
--encrypt / --decrypt flag, and none is needed.

It deliberately does NOT reimplement the machine: it imports decode_all/posseq from
corpus_sweep, i.e. the exact kernel the searches use. If the two ever disagree, the bug
is in one implementation -- so there is only one.

KEY CONVENTIONS (project-wide, see data/messages/*.json)
  --windows / --ring   4 letters in U,L,M,R order (reflector, left, middle, right).
  --grund              the 4-letter group as TRANSMITTED, i.e. (L,M,R,U); it is rotated
                       right by one to give windows (U,L,M,R). --grund XMOT == --windows TXMO.
                       Only ONE of --windows / --grund is needed.
  --order              wheels in L-M-R slots, e.g. II-I-III.
  Gauge note: only (window - ring) mod 26 is invariant per wheel. Different
  (windows, ring) pairs with the same 4 offsets are the SAME key and decode identically.

NOTCH
  Core-notch offsets come from corpus_sweep.NOTCH_OFFSET (turnover fires when
  (window - ring) % 26 == offset). Any wheel left at None falls back to the legacy
  window-letter turnover from wirings.json. Override per run without touching the
  library, e.g. a calibrated (unpublished) value for some wheel W:
      --notch W=OFFSET
      --notch W=OFFSET,X=OFFSET2
      --notch none          (force legacy window turnovers for every wheel)

USAGE
    # decipher a raw ciphertext
    python3 enigma_k.py --wiring F --order II-I-III --grund XMOT --ring WXGA \
        --text "AGSZ FAEQ LHDF URWM PHEF FFNR"

    # encipher a plaintext (same command, Enigma is its own inverse)
    python3 enigma_k.py --wiring F --order II-I-III --grund XMOT --ring WXGA \
        --text "PONERQUEMOVIMIENTOBARCOS"

    # run a message JSON straight from data/messages/ (uses its own solution block if present)
    python3 enigma_k.py --json data/messages/XMOT.json
    python3 enigma_k.py --json data/messages/MKCX.json --notch II=OFFSET   # II rides right in MKCX;
                                                                            # needs its core-notch offset to step correctly

    # override any part of the stored key
    python3 enigma_k.py --json data/messages/LUIS.json --ring BWEV

    # regression check against every solved message in the corpus
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


def key4(s, what):
    s = s.strip().upper()
    if len(s) != 4 or any(c not in A for c in s):
        sys.exit(f"error: --{what} must be exactly 4 letters A-Z, got {s!r}")
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
        for k in cs.NOTCH_OFFSET:
            cs.NOTCH_OFFSET[k] = None
        return
    for part in spec.split(','):
        wheel, _, val = part.partition('=')
        wheel = wheel.strip().upper()
        if wheel not in ('I', 'II', 'III') or not val.strip().isdigit():
            sys.exit(f"error: --notch wants WHEEL=OFFSET, e.g. III=22 (got {part!r})")
        cs.NOTCH_OFFSET[wheel] = int(val) % 26


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
    if isinstance(d, list):          # XMOT.json is a 1-element list
        d = d[0]
    sol = d.get('solution') or d.get('status') or {}
    key = {
        'wiring':  sol.get('wiring'),
        'order':   sol.get('rotor_order'),
        'windows': sol.get('windows_ULMR'),
        'ring':    sol.get('ringstellung_ULMR'),
        'grund':   sol.get('grundstellung') or d.get('grundstellung'),
        'body':    d.get('body', ''),
        'label':   d.get('label') or os.path.splitext(os.path.basename(path))[0],
        'plain':   sol.get('plaintext'),
    }
    return key


# ---------------------------------------------------------------- self-test
def self_test(path):
    files = ([os.path.join(path, f) for f in sorted(os.listdir(path)) if f.endswith('.json')]
             if os.path.isdir(path) else [path])
    saved = dict(cs.NOTCH_OFFSET)
    ok = fail = skip = 0
    for f in files:
        k = load_json(f)
        if not (k['plain'] and k['wiring'] and k['order'] and k['ring'] and (k['windows'] or k['grund'])):
            print(f"  skip  {k['label']:<14} (no complete solution block)"); skip += 1; continue
        order = parse_order(k['order'])
        win = k['windows'] or (k['grund'][-1] + k['grund'][:-1])
        cs.NOTCH_OFFSET.update(saved)   # None stays None here: legacy window turnover is the
                                          # documented default, not a defect -- pass --notch
                                          # yourself for messages that need a calibrated wheel.
        got = run(k['wiring'], order, win, k['ring'], clean(k['body']))
        exp = clean(k['plain'])
        n = min(len(got), len(exp))
        match = sum(a == b for a, b in zip(got[:n], exp[:n]))
        bad = [i + 1 for i in range(n) if got[i] != exp[i]]        # 1-indexed
        if not bad and n:
            print(f"  PASS  {k['label']:<14} {n}/{n} letters"); ok += 1
        else:
            print(f"  FAIL  {k['label']:<14} {match}/{n} letters  "
                  f"mismatch at {', '.join(map(str, bad[:10]))}"
                  f"{' ...' if len(bad) > 10 else ''}")
            fail += 1
    cs.NOTCH_OFFSET.update(saved)
    print(f"\n{ok} passed, {fail} failed, {skip} skipped")
    return 1 if fail else 0


# ---------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(
        description="Encipher/decipher one Enigma K message with a known key "
                    "(self-reciprocal: one command does both).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Windows/ring are ULMR (reflector,left,middle,right). --grund takes the "
               "TRANSMITTED group (L,M,R,U) and rotates it. Only (window-ring) matters.")
    p.add_argument('--json', help="message JSON; takes key + body from its solution block")
    p.add_argument('--text', help="text to run (ciphertext or plaintext); '-' reads stdin")
    p.add_argument('--wiring', help="rotor set: D or F")
    p.add_argument('--order', help="wheels in L-M-R slots, e.g. II-I-III")
    p.add_argument('--windows', help="4 letters, ULMR")
    p.add_argument('--grund', help="4 letters as transmitted (LMRU); rotated to give windows")
    p.add_argument('--ring', help="Ringstellung, 4 letters, ULMR")
    p.add_argument('--notch', help="core-notch override, e.g. 'III=22' or 'none'")
    p.add_argument('--groups', type=int, default=4, help="output group size (default 4; 0 = no grouping)")
    p.add_argument('--raw', action='store_true', help="print the output only, ungrouped")
    p.add_argument('--self-test', metavar='PATH', help="verify against solved messages and exit")
    a = p.parse_args()

    apply_notch(a.notch)

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

    missing = [n for n, v in (('wiring', wiring), ('order', order_s), ('ring', ring)) if not v]
    if missing:
        sys.exit(f"error: missing {', '.join('--' + m for m in missing)} "
                 f"(supply them, or use --json with a solved message)")
    if not (windows or grund):
        sys.exit("error: need --windows or --grund")
    if not text or not clean(text):
        sys.exit("error: no text (use --text, or --json with a body)")

    order = parse_order(order_s)
    ring = key4(ring, 'ring')
    if windows:
        windows = key4(windows, 'windows')
    else:
        grund = key4(grund, 'grund')
        windows = grund[-1] + grund[:-1]          # (L,M,R,U) -> (U,L,M,R)

    ct = clean(text)
    out = run(wiring, order, windows, ring, ct)

    if a.raw:
        print(out); return
    notch = ', '.join(f"{k}={v}" for k, v in sorted(cs.NOTCH_OFFSET.items()) if v is not None) or 'none (legacy windows)'
    print(f"wiring {wiring}   order {'-'.join(order)}   windows {windows} (ULMR)   ring {ring}   "
          f"offsets {offsets(windows, ring)}")
    print(f"notch offsets: {notch}   |   {len(ct)} letters\n")
    print("IN  " + (group(ct, a.groups) if a.groups else ct))
    print("OUT " + (group(out, a.groups) if a.groups else out))


if __name__ == '__main__':
    main()
