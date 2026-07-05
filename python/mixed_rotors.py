#!/usr/bin/env python3
"""
mixed_rotors.py -- crib-drag a message across wiring sets D and F, optionally with
the three rotors MIXED from either set. Rotors are physical wheels: an operator with
both a D and an F set could load any mix (e.g. D-I, F-II, D-III). Turnovers key off
the rotor NUMBER (Y/E/N for I/II/III), identical for D and F, so a mix is well defined.

  --mix        also try the 6 MIXED rotor combos (default: only pure D and F)
  --crib X     X is a literal crib OR, if it names an existing file, a crib CATALOGUE
               (one crib per line; '#' comments and blank lines ignored)
  --arr        canonical | all           (default all)
  --procs N    threads for the C engine

Judge by IoC (Spanish ~0.075, random ~0.045), NOT by match count: a short crib is
reproduced by hundreds of settings purely by chance. Cribs under 12 letters are
skipped. A summary ranked by IoC is printed at the end -- ideal for an overnight
sweep of a crib catalogue (redirect stdout to a log file).

Usage:
  python3 mixed_rotors.py MSG.json --crib MEREFIEROAERROREN --mix --arr all --procs 12
  python3 mixed_rotors.py MSG.json --crib cribs_navales.txt  --mix --procs 12  > night.log
"""
import sys, os, argparse, itertools, json
from collections import Counter
import corpus_sweep as cs
c2n = cs.c2n; A = cs.A

MIN_CRIB = 12          # shorter cribs only yield chance coincidences -> skipped
SPANISH  = 0.060       # flag hint; a clean break is higher, a garbled real break ~0.055-0.060


def _ioc(dec):
    s = [x for x in dec if x in A]; N = len(s)
    if N < 2:
        return 0.0
    c = Counter(s); return sum(v * (v - 1) for v in c.values()) / (N * (N - 1))


def load_cribs(arg):
    """Return a list of cribs. arg is a literal crib, unless it names an existing
    file, in which case each non-comment line is a crib. If arg LOOKS like a path
    (has a separator or a .txt/.lst extension) but does not exist, fail loudly --
    do not silently turn a mistyped filename into a phantom crib."""
    if os.path.isfile(arg):
        out = []
        for line in open(arg, encoding="utf-8"):
            s = line.split("#", 1)[0].strip().upper()
            s = "".join(ch for ch in s if ch in A)
            if s:
                out.append(s)
        print(f"[read {len(out)} crib(s) from {arg}]")
        return out
    looks_like_path = ("/" in arg) or ("\\" in arg) or arg.lower().endswith((".txt", ".lst", ".cribs"))
    if looks_like_path:
        sys.exit(f"ERROR: '{arg}' looks like a file but does not exist (cwd: {os.getcwd()}). "
                 f"Check the path, or pass a literal crib without a / or .txt.")
    return ["".join(ch for ch in arg.upper() if ch in A)]


def run(path, cribs, procs=4, all_arr=True, mix=False):
    data = json.load(open(path, encoding="utf-8")); m = data[0] if isinstance(data, list) else data
    grund = m.get("grundstellung"); body, plains = cs.parse_body(m)
    ct = [c2n[c] for c in body]
    arrlist = ([(p, q, r) for p in range(4) for q in range(4) for r in range(4) if len({p, q, r}) == 3]
               if all_arr else [(0, 1, 2)])
    lib = cs.load_lib()
    if lib is None:
        print("C engine unavailable (build librods.so / set SPANISH_ENIGMA_LIB)"); return
    combos = list(itertools.product("DF", repeat=3)) if mix else [('D', 'D', 'D'), ('F', 'F', 'F')]
    sets = {'D': cs.WIRINGS['D'], 'F': cs.WIRINGS['F']}
    print(f"message G={grund}  n={len(body)}  arrangements={'all' if all_arr else 'canonical'}  "
          f"combos={'8 (pure+mixed)' if mix else '2 (pure D,F)'}  cribs={len(cribs)}\n")
    results = []                                                   # (io, crib, label, cfg, decode)
    for crib in cribs:
        cb = [c2n[c] for c in crib]
        if len(cb) < MIN_CRIB:
            print(f"[skip crib '{crib}' -- {len(cb)}<{MIN_CRIB} letters, would only yield noise]"); continue
        print(f"crib '{crib}' ({len(cb)}):")
        for combo in combos:
            cs.WIRINGS['_MIX'] = {'I': sets[combo[0]]['I'], 'II': sets[combo[1]]['II'], 'III': sets[combo[2]]['III']}
            hits = cs.crib_search_c(lib, '_MIX', ct, cb, grund, all_arr, procs)
            label = f"I<-{combo[0]} II<-{combo[1]} III<-{combo[2]}"
            if not hits:
                print(f"    [{label}]  0"); continue
            best = None
            for off, ai, oi, u, rL, rM, rR in hits:
                triple = arrlist[ai]; miss = [i for i in range(4) if i not in triple][0]
                uwin = c2n[grund[miss]]; windows = tuple(c2n[grund[i]] for i in triple)
                rings = ((uwin - u) % 26, rL, rM, rR)
                dec = cs.decode_all('_MIX', cs.ORDERS[oi], windows, uwin, rings, ct)
                io = _ioc(dec)
                if best is None or io > best[0]:
                    cfg = (f"order {'-'.join(cs.ORDERS[oi])}  win(U,L,M,R)={A[uwin] + ''.join(A[w] for w in windows)}"
                           f"  rings={''.join(A[r] for r in rings)}")
                    best = (io, cfg, dec)
            io, cfg, dec = best
            flag = "  <== SPANISH-LIKE" if io >= SPANISH else ""
            print(f"    [{label}]  {len(hits)} matches  IoC={io:.4f}{flag}")
            results.append((io, crib, label, cfg, dec))
    cs.WIRINGS.pop('_MIX', None)
    print("\n" + "=" * 64)
    print("BEST OF THE RUN  (ranked by IoC; Spanish ~0.075, random ~0.045)")
    print("=" * 64)
    if not results:
        print("no combo reproduced any crib."); return
    results.sort(reverse=True)
    for io, crib, label, cfg, dec in results[:12]:
        flag = "  <== SPANISH-LIKE (real candidate)" if io >= SPANISH else ""
        print(f"  IoC={io:.4f}  crib '{crib}'  [{label}]{flag}")
        print(f"      {cfg}")
        print(f"      {dec}")
    top = results[0][0]
    print()
    if top >= SPANISH:
        print("=> POSSIBLE BREAK: the top line looks Spanish-like. READ IT to confirm real words.")
    else:
        print(f"=> Best IoC {top:.4f}, below the flag ({SPANISH}). Probably no break with these")
        print(f"   {'mixed' if mix else 'pure'} D/F rotors -- but SCAN the top decodes above anyway: a heavily")
        print(f"   garbled real break can sit near 0.055-0.060; a clean one would be clearly higher.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("message")
    ap.add_argument("--crib", required=True, help="a literal crib, or a file of cribs (one per line)")
    ap.add_argument("--mix", action="store_true", help="also try the 6 mixed rotor combos")
    ap.add_argument("--arr", choices=["all", "canonical"], default="all")
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    run(a.message, load_cribs(a.crib), a.procs, all_arr=(a.arr == "all"), mix=a.mix)
