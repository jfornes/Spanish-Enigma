#!/usr/bin/env python3
"""
calibrate_notch2.py -- brute-force a candidate core-notch offset for ONE wheel
(default: II), jointly with the ring space that its stepping actually depends
on, optionally across ALL 24 indicator arrangements and/or several orders/wirings.

WHY THE JOINT (RM,RR) SWEEP: posseq() in corpus_sweep.py already supports two
SIMULTANEOUS core-based notches (e.g. III fixed at 22 plus a candidate for II),
but neither corpus_sweep.py's ioc_worker nor mixed_rotors.py's _ioc_full_worker
sweep BOTH the mid-ring (RM) and the right-ring (RR) together -- each only
sweeps one axis and fixes the other at 0. Whichever slot(s) carry an active
notch, this script always sweeps RM and RR jointly (26x26) and vectorises
(RU,RL) (26x26); that is a safe superset regardless of which wheel sits where,
so it works for any order/notch-wheel combination without special-casing.

This subsumes what corpus_sweep.py --all / mixed_rotors.py --arr all already do
(sweeping arrangements) PLUS the notch calibration they can't do -- one script,
not two. --arr canonical is the default (cheap); pass --arr all to also sweep
the 24 arrangements (24x heavier -- budget a few minutes with --procs 12+).

Usage:
    # canonical arrangement only, calibrate II's notch, order/wiring already known:
    python3 calibrate_notch2.py MSG.json --procs 12

    # also sweep all 24 arrangements (the next thing to try for MKCX):
    python3 calibrate_notch2.py MSG.json --arr all --procs 12

    # generalise to another message/order/wiring/wheel:
    python3 calibrate_notch2.py MSG.json --wiring D,F --order all --notch-wheel I --arr all --procs 12
"""
import json, argparse, itertools, multiprocessing as mp
import numpy as np
import corpus_sweep as cs

A = cs.A
c2n = cs.c2n
ALL_ORDERS = list(itertools.permutations(['I', 'II', 'III']))


def worker(task):
    offset, notch_wheel, wiring, order, windows, uwin, ct_list, arr_label = task
    cs.NOTCH_OFFSET[notch_wheel] = offset  # candidate under test, this call only
    ct = np.array(ct_list)
    N = len(ct)
    W = {k: cs.perm(cs.WIRINGS[wiring][k]) for k in ('I', 'II', 'III')}
    lf, lr = W[order[0]]
    mf, mr = W[order[1]]
    rf, rr = W[order[2]]
    g = np.arange(26)
    RU, RL = (z.ravel() for z in np.meshgrid(g, g, indexing='ij'))
    V = RU.size
    ETWR = cs.ETWR
    ETWF = cs.ETWF
    UKWF = cs.UKWF
    best = None
    for RMv in range(26):
        for RRv in range(26):
            seq = cs.posseq(order, windows, N, (0, RMv, RRv))  # joint (RM,RR): safe for any notch combo
            out = np.empty((V, N), np.int8)
            for t in range(N):
                L, M, R = seq[t]
                oL = (L - RL) % 26
                oM = (M - RMv) % 26
                oR = (R - RRv) % 26
                u = (uwin - RU) % 26
                x = ETWR[int(ct[t])]
                x = (rf[(x + oR) % 26] - oR) % 26
                x = (mf[(x + oM) % 26] - oM) % 26
                x = (lf[(x + oL) % 26] - oL) % 26
                x = (UKWF[(x + u) % 26] - u) % 26
                x = (lr[(x + oL) % 26] - oL) % 26
                x = (mr[(x + oM) % 26] - oM) % 26
                x = (rr[(x + oR) % 26] - oR) % 26
                out[:, t] = ETWF[x]
            cnt = np.zeros((V, 26), np.int32)
            for k in range(26):
                cnt[:, k] = (out == k).sum(1)
            io = (cnt * (cnt - 1)).sum(1) / (N * (N - 1))
            idx = np.argpartition(io, -5)[-5:]
            for i in idx:
                txt = ''.join(A[v] for v in out[i])
                fs = cs.fscore(txt)
                cand = (fs, float(io[i]), int(RU[i]), int(RL[i]), RMv, RRv, txt)
                if best is None or cand[0] > best[0]:
                    best = cand
    return (offset, wiring, '-'.join(order), arr_label, best)


def parse_orders(spec):
    if spec == "all":
        return ALL_ORDERS
    return [tuple(spec.split("-"))]


def parse_offsets(spec):
    if not spec:
        return list(range(26))
    out = []
    for x in spec.split(","):
        x = x.strip()
        out.append(c2n[x] if x.isalpha() else int(x))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--wiring", default="F", help="comma list, e.g. F or D,F")
    ap.add_argument("--order", default="I-III-II", help="e.g. I-III-II, or 'all' for all 6")
    ap.add_argument("--notch-wheel", default="II", choices=["I", "II", "III"],
                     help="which wheel's notch offset to calibrate (default II)")
    ap.add_argument("--offsets", default=None,
                     help="comma list of candidate offsets (letters or numbers); default: all 26")
    ap.add_argument("--arr", choices=["canonical", "all"], default="canonical",
                     help="canonical: (L,M,R)=grund[0,1,2], UKW=grund[3] only (cheap); "
                          "all: also sweep all 24 indicator arrangements (24x heavier)")
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--top", type=int, default=10, help="how many best results to print")
    a = ap.parse_args()

    data = json.load(open(a.json))
    m = data[0] if isinstance(data, list) else data
    grund = m["grundstellung"]
    body, plains = cs.parse_body(m)
    ct = [c2n[c] for c in body]
    gl = [c2n[c] for c in grund]

    wirings = a.wiring.split(",")
    orders = parse_orders(a.order)
    offsets = parse_offsets(a.offsets)
    arrs = ([(p, q, r) for p in range(4) for q in range(4) for r in range(4) if len({p, q, r}) == 3]
            if a.arr == "all" else [(0, 1, 2)])

    print(f"message G={grund}  n={len(ct)}  wirings={wirings}  orders={len(orders)}  "
          f"notch-wheel={a.notch_wheel}  offsets={len(offsets)}  "
          f"arrangements={'all24' if a.arr=='all' else 'canonical'}  "
          f"-- {len(wirings)*len(orders)*len(offsets)*len(arrs)} tasks\n")

    tasks = []
    for arr in arrs:
        windows = tuple(gl[i] for i in arr)
        uwin_idx = [i for i in range(4) if i not in arr][0]
        uwin = gl[uwin_idx]
        arr_label = A[uwin] + ''.join(A[w] for w in windows)  # (U,L,M,R)
        for wiring in wirings:
            for order in orders:
                for o in offsets:
                    tasks.append((o, a.notch_wheel, wiring, order, windows, uwin, ct, arr_label))

    with mp.Pool(a.procs) as pool:
        results = pool.map(worker, tasks)

    results.sort(key=lambda r: r[4][0], reverse=True)
    print(f"{'offset':>6} {'wiring':>6} {'order':>9} {'arr(ULMR)':>10} {'frag':>5} {'IoC':>7}  "
          f"rings(U,L,M,R)  decode")
    for offset, wiring, order, arr_label, (fs, io, ru, rl, rm, rr, txt) in results[:a.top]:
        print(f"{A[offset]:>6} {wiring:>6} {order:>9} {arr_label:>10} {fs:5d} {io:7.4f}  "
              f"{A[ru]}{A[rl]}{A[rm]}{A[rr]}          {txt}")


if __name__ == "__main__":
    main()
