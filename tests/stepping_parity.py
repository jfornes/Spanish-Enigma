#!/usr/bin/env python3
"""stepping_parity.py -- both front-ends step every rotor set by the same rule.

corpus_sweep and rods_frontend (and through it the C kernels) must step every
rotor set by the same rule: each rotor by its own set's offsets in
data/wirings/wirings.json, a null meaning its window letter. Otherwise one
message searched on D would step differently depending on the tool.

Two checks, on D and on F:
  1. the Python step sequences agree (rods_frontend.py_windows_seq against
     corpus_sweep.posseq) over random orders, windows and rings;
  2. a text enciphered by corpus_sweep.decode_all is recovered by the C
     rod_search through rods_frontend, with the true setting among the hits.
"""
import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
import numpy as np
import rods_frontend as rf
import corpus_sweep as cs
c2n = rf.c2n; A = rf.A

def seq_check(wiring, trials=400, n=300):
    bad = 0
    for _ in range(trials):
        oi = random.randrange(6); order = cs.ORDERS[oi]
        win = tuple(random.randrange(26) for _ in range(3))
        rl, rm, rr = (random.randrange(26) for _ in range(3))
        a = rf.py_windows_seq(order, win, n, rm, rr, wiring)
        b = cs.posseq(order, win, n, (rl, rm, rr), wiring)
        bad += (a != b)
    return bad

def c_check(lib, wiring):
    order = ('I', 'III', 'II')                 # III in the middle: its offset drives the steps
    L0, M0, R0 = c2n['A'], c2n['Z'], c2n['C']
    rL, rM, rR, u = 4, 3, 6, 5                 # (M0 - rM) % 26 = 22: middle double-step at t=0 on F's offsets
    pt = "ADHESIONYLEALTADALCAUDILLOVIVAELGENERALISIMO"
    ct = cs.decode_all(wiring, order, (L0, M0, R0), 0, ((-u) % 26, rL, rM, rR),
                       [c2n[ch] for ch in pt])
    hits = rf.brute(lib, wiring, rf.vec(ct), rf.vec(pt[:24]), 0, "AZCA", False, os.cpu_count() or 1)
    return (0, 1, u, rL, rM, rR) in hits, len(hits)

def notch_window_check():
    """wirings.json: every rotor turns over at its notch letter + notch_to_window."""
    W = rf._WIR; off = W['notch_to_window']; bad = []
    for s, rot in W['rotor_sets'].items():
        for k, v in rot.items():
            if (c2n[v['notch_letter']] + off) % 26 != c2n[v['turnover_window']]: bad.append(f"{s}.{k}")
            if v['turnover_window'] != W['turnovers'][k]: bad.append(f"{s}.{k} vs turnovers")
    return bad

def main():
    random.seed(7); ok = True
    bad = notch_window_check()
    print(f"notch letter + 18 = turnover window, every rotor of every set: {not bad} {bad or ''}")
    ok &= not bad
    lib = rf.load_lib()
    for w in ('F', 'D'):
        bad = seq_check(w)
        found, nh = c_check(lib, w)
        print(f"wiring {w}: step sequences differing = {bad}/400; C recovers the corpus_sweep encipherment: {found} ({nh} hits)")
        ok &= (bad == 0 and found)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
