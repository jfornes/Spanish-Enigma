#!/usr/bin/env python3
"""
mixed_rotors.py -- test whether a message used rotors MIXED from wiring sets D and F.

corpus_sweep tries the three rotors from ONE set (all-D or all-F). But rotors are
physical wheels: an operator holding both a D set and an F set could load any mix
(e.g. D-I, F-II, D-III). This drags a crib over all 8 combinations (rotors I, II,
III each independently from D or F), across all arrangements / orders / ring
settings, using the C engine. The two pure combos are the controls. Turnovers key
off the rotor NUMBER (Y/E/N for I/II/III), identical for D and F, so a mix is well
defined.

Usage: python3 mixed_rotors.py MESSAGE.json --crib MEREFIEROAERROREN [--procs 4]
"""
import sys, argparse, itertools, json
from collections import Counter
import corpus_sweep as cs
c2n = cs.c2n; A = cs.A


def _ioc(dec):
    s = [x for x in dec if x in A]; N = len(s)
    if N < 2:
        return 0.0
    c = Counter(s); return sum(v * (v - 1) for v in c.values()) / (N * (N - 1))


def run(path, crib, procs=4, all_arr=True):
    data = json.load(open(path, encoding="utf-8")); m = data[0] if isinstance(data, list) else data
    grund = m.get("grundstellung"); body, plains = cs.parse_body(m)
    ct = [c2n[c] for c in body]; cb = [c2n[c] for c in crib.upper() if c in A]
    arrlist = ([(p, q, r) for p in range(4) for q in range(4) for r in range(4) if len({p, q, r}) == 3]
               if all_arr else [(0, 1, 2)])
    lib = cs.load_lib()
    if lib is None:
        print("C engine unavailable (build librods.so / set SPANISH_ENIGMA_LIB)"); return
    print(f"message G={grund}  n={len(body)}  crib '{crib}'  "
          f"-- 8 rotor-set combos x {'all arrangements' if all_arr else 'canonical arrangement'}\n")
    sets = {'D': cs.WIRINGS['D'], 'F': cs.WIRINGS['F']}
    any_hit = False
    for combo in itertools.product("DF", repeat=3):                 # (set_I, set_II, set_III)
        cs.WIRINGS['_MIX'] = {'I': sets[combo[0]]['I'], 'II': sets[combo[1]]['II'], 'III': sets[combo[2]]['III']}
        hits = cs.crib_search_c(lib, '_MIX', ct, cb, grund, all_arr, procs)
        pure = combo in (('D', 'D', 'D'), ('F', 'F', 'F'))
        label = f"I<-{combo[0]} II<-{combo[1]} III<-{combo[2]}" + ("  (pure control)" if pure else "")
        if not hits:
            print(f"  [{label}]  0 matches"); continue
        any_hit = True
        best = None
        for off, ai, oi, u, rL, rM, rR in hits:
            triple = arrlist[ai]; miss = [i for i in range(4) if i not in triple][0]
            uwin = c2n[grund[miss]]; windows = tuple(c2n[grund[i]] for i in triple)
            rings = ((uwin - u) % 26, rL, rM, rR)
            dec = cs.decode_all('_MIX', cs.ORDERS[oi], windows, uwin, rings, ct)
            io = _ioc(dec)
            if best is None or io > best[0]:
                best = (io, cs.ORDERS[oi], windows, uwin, rings, dec)
        io, order, windows, uwin, rings, dec = best
        print(f"  [{label}]  {len(hits)} matches  best IoC={io:.4f}  "
              f"order {'-'.join(order)}  windows(U,L,M,R)={A[uwin] + ''.join(A[w] for w in windows)}  "
              f"rings={''.join(A[r] for r in rings)}")
        print(f"      {dec}")
    cs.WIRINGS.pop('_MIX', None)
    if not any_hit:
        print("\n=> No combo (pure or mixed) reproduces the crib. Mixed D/F rotors do NOT")
        print("   rescue this message with this crib (check the crib, or the wiring is a third set).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("message"); ap.add_argument("--crib", required=True); ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--arr", choices=["all", "canonical"], default="all")
    a = ap.parse_args()
    run(a.message, a.crib, a.procs, all_arr=(a.arr == "all"))
