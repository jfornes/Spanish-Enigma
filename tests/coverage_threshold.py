#!/usr/bin/env python3
"""
coverage_threshold.py -- how much crib does inner-rotor recovery actually need?

Recovering the MIDDLE rotor by mu-propagation (buttonup.recover_middle) only
reaches all 26 contacts if the crib spans enough CONSECUTIVE middle-rotor
offsets. This script measures where that threshold sits, using wiring F as a
positive control: encipher a known plaintext, truncate it to a range of
lengths, and ask the solver to recover the middle rotor from each.

Run from the repository root:  python3 tests/coverage_threshold.py

Result (wiring F, order II-I-III):

    crib len  offsets  cands  recovered
          40        2      0  no
          60        3      0  no
          80        4      0  no
         104        5      1  YES     <-- threshold
         190        8      1  YES
         300       12      1  YES

Five consecutive middle offsets -- about 104 crib letters -- suffice, and the
solution is unique. This is the number that decides whether a given archival
message can carry a wiring recovery on its own.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import corpus_sweep as cs
from buttonup import build_middle_involutions, recover_middle, c2n

LENGTHS = (40, 60, 80, 104, 130, 156, 182, 190, 208, 234, 260, 300)

def main():
    order = ('II', 'I', 'III'); Wf = cs.WIRINGS['F']
    rf = cs.perm(Wf[order[2]])[0]; mfT = list(cs.perm(Wf[order[1]])[0])
    windows = (c2n['A'], c2n['C'], c2n['O']); uwin = c2n['T']
    rings = (c2n['B'], c2n['D'], c2n['G'], c2n['Q'])
    base = ("SEHACONFIRMADOELMOVIMIENTODEBARCOSENEMIGOSHACIALASBALEARES"
            "TOMENSEATAQUEINMINENTEALASBALEARES" * 8)

    print(f"{'crib len':>9} {'offsets':>8} {'cands':>6}  recovered")
    print("-" * 44)
    first = None
    for L in LENGTHS:
        p = [c2n[ch] for ch in base[:L]]
        c = [c2n[ch] for ch in cs.decode_all('F', order, windows, uwin, rings, p)]
        E = build_middle_involutions(order, windows, uwin, rings, rf, p, c)
        cands = recover_middle(E)
        ok = any(len({(m[k] - mfT[k]) % 26 for k in range(26)}) == 1 for m in cands)
        if ok and first is None:
            first = (L, len(E))
        print(f"{L:>9} {len(E):>8} {len(cands):>6}  {'YES' if ok else 'no'}")
    if first:
        print(f"\nthreshold: {first[1]} consecutive middle offsets (~{first[0]} crib letters)")
    return 0 if first else 1

if __name__ == "__main__":
    sys.exit(main())
