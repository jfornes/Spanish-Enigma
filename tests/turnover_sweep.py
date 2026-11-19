#!/usr/bin/env python3
"""turnover_sweep.py -- --sweep-turnover finds a key whose right rotor turns
over at a rod position other than the one in wirings.json.

wirings.json fixes the turnover of rotor III at rod position 22: that is where it
falls in the traffic of December 1936, with the notch on the ring at N and the
Ringstellung of III at R. In a period with another Ringstellung the turnover falls
elsewhere. A text enciphered with III turning over at rod position 5 is therefore
not found by the default crib search, and is found once the right rotor's turnover
is swept.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
import corpus_sweep as cs
c2n = cs.c2n; A = cs.A

def main():
    lib = cs.load_lib()
    order = ('II', 'I', 'III'); windows = (c2n['H'], c2n['Q'], c2n['T']); uwin = c2n['K']
    rings = (3, 9, 14, 2)                       # U, L, M, R
    nov = {'III': 5}                            # the turnover of this "period"
    pt = "ENEMIGOCARECEMUNICIONESAPRESEMOSLEPOSICIONESALSURDEPALMA"
    ct = [c2n[c] for c in cs.decode_all('F', order, windows, uwin, rings, [c2n[c] for c in pt], nov)]
    grund = A[windows[0]] + A[windows[1]] + A[windows[2]] + A[uwin]    # kernel order (L,M,R,U)
    crib = [c2n[c] for c in pt[:30]]
    want = lambda h: h[0] == 0 and cs.ORDERS[h[2]] == order and (h[4], h[5], h[6]) == rings[1:]
    default = [h for h in cs.crib_search_c(lib, 'F', ct, crib, grund, False, os.cpu_count() or 1) if want(h)]
    swept = []
    for v in range(26):
        swept += [(v, h) for h in cs.crib_search_c(lib, 'F', ct, crib, grund, False, os.cpu_count() or 1, {'III': v}) if want(h)]
    found = sorted({v for v, _ in swept})
    print(f"default stepping (III at 22) finds the key: {bool(default)}")
    print(f"sweeping III's turnover finds it at rod position(s): {found}")
    ok = (not default) and 5 in found
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
