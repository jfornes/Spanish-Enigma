#!/usr/bin/env python3
"""Standalone positive control for the middle-wheel core-notch stepping in the C
kernel (the `rm=0` bug). NOT part of the repo — a before/after probe.

Construction: encipher a known plaintext with an order that puts III in the MIDDLE
(so the middle wheel's core notch, offset 22, drives the stepping and the position
sequence depends on ringM). Starting M is placed exactly on III's core notch for the
TRUE ringM, so keystroke 0 is a middle double-step for the true key but NOT for the
rm=0 (buggy) sequence -> the two models diverge immediately.

Then ask the C rod_search (brute) to recover the setting from a crib. Only a kernel
that recomputes the step sequence with the correct ringM can find it.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
import numpy as np
import rods_frontend as rf
c2n = rf.c2n; A = rf.A; vec = rf.vec

# ---- core-notch encipher oracle (mirrors corpus_sweep.decode_all stepping) ----
def core_seq(order, windows, rings, n):
    nM = rf.NOTCH_OFFSET.get(order[1]); nR = rf.NOTCH_OFFSET.get(order[2])
    tM = c2n[rf.WIN[order[1]]]; tR = c2n[rf.WIN[order[2]]]
    rL, rM, rR = rings; L, M, R = windows; seq = []
    for _ in range(n):
        mAt = ((M-rM) % 26 == nM) if nM is not None else (M == tM)
        rAt = ((R-rR) % 26 == nR) if nR is not None else (R == tR)
        if mAt: M = (M+1) % 26; L = (L+1) % 26
        elif rAt: M = (M+1) % 26
        R = (R+1) % 26; seq.append((L, M, R))
    return seq

def core_encipher(wiring, order, windows, rings, u, text):
    W = {k: rf.perm(rf.WIRINGS[wiring][k]) for k in ('I', 'II', 'III')}
    lf, lr = W[order[0]]; mf, mr = W[order[1]]; rf_, rr = W[order[2]]
    etwf, etwr = rf.perm(rf.ETW); ukwf, _ = rf.perm(rf.UKW)
    seq = core_seq(order, windows, rings, len(text)); rL, rM, rR = rings; out = []
    for t, ch in enumerate(text):
        L, M, R = seq[t]
        x = etwr[c2n[ch]]
        oR = (R-rR) % 26; x = (rf_[(x+oR) % 26]-oR) % 26
        oM = (M-rM) % 26; x = (mf[(x+oM) % 26]-oM) % 26
        oL = (L-rL) % 26; x = (lf[(x+oL) % 26]-oL) % 26
        x = (ukwf[(x+u) % 26]-u) % 26
        x = (lr[(x+oL) % 26]-oL) % 26; x = (mr[(x+oM) % 26]-oM) % 26; x = (rr[(x+oR) % 26]-oR) % 26
        out.append(A[etwf[x]])
    return ''.join(out)

def main():
    lib = rf.load_lib()
    order = ('I', 'III', 'II')            # III in the MIDDLE  -> oi == 1
    L0, M0, R0 = c2n['A'], c2n['Z'], c2n['C']   # M0=Z=25
    rings = (4, 3, 6)                     # rM = 3  ->  (M0 - rM) % 26 = 22 = III core-notch
    u = 5                                 # UKW offset
    windows = (L0, M0, R0)
    pt = "ADHESIONYLEALTADALCAUDILLOVIVAELGENERALISIMO"   # 44 letters
    ct = core_encipher('F', order, windows, rings, u, pt)

    # sanity: middle double-steps at keystroke 0 for the true key (L advances immediately)
    s = core_seq(order, windows, rings, 3)
    stepped0 = (s[0][0] == (L0+1) % 26)

    crib = pt[:24]
    hits = rf.brute(lib, 'F', vec(ct), vec(crib), 0, "AZCA", False, os.cpu_count() or 1)
    want = (0, 1, u, 4, 3, 6)             # (arr, oi, ukw, rL, rM, rR)
    found = any(h == want for h in hits)
    print(f"middle double-step at t=0 (true key): {stepped0}")
    print(f"target setting: arr=0 oi=1(I-III-II) UKW={A[u]} rings=(4,3,6)")
    print(f"brute hits: {len(hits)}  ->  target recovered: {found}")
    if hits and not found:
        print("  (kernel returned hits but NOT the true setting -> rm=0 bug)")
        for h in hits[:5]: print("   ", h)
    print("RESULT:", "PASS" if found else "FAIL")
    return 0 if found else 1

if __name__ == "__main__":
    sys.exit(main())
