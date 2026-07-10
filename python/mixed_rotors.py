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
skipped (default 8, see --min-crib). A summary ranked by IoC is printed at the end -- ideal for an overnight
sweep of a crib catalogue (redirect stdout to a log file).

Usage:
  python3 mixed_rotors.py MSG.json --crib MEREFIEROAERROREN --mix --arr all --procs 12
  python3 mixed_rotors.py MSG.json --crib cribs_navales.txt  --mix --procs 12  > night.log
"""
import sys, os, argparse, itertools, json
from collections import Counter
import corpus_sweep as cs
c2n = cs.c2n; A = cs.A

MIN_CRIB = 8           # default min crib length; >=8 is spurious-free. Override with --min-crib
FRAG_RATIO = 0.12      # frag-score per letter above this = real Spanish (XMOT break ~0.24; degeneracy <0.08)


def _ioc(dec):
    s = [x for x in dec if x in A]; N = len(s)
    if N < 2:
        return 0.0
    c = Counter(s); return sum(v * (v - 1) for v in c.values()) / (N * (N - 1))


def _spanish(fs, n):
    """Flag on frag-score PER LETTER, not IoC: real Spanish shows many Spanish
    fragments, while a degenerate decode (one dominant letter) can have high IoC
    but almost no fragments -- exactly the DHZB false positives."""
    return n > 0 and fs / n >= FRAG_RATIO


LONGWORDS = ("MOVIMIENTO", "BARCOS", "PRECAUCION", "TELEGRAMA", "COMANDANTE", "SITUACION",
             "GENERALISIMO", "SUBMARINO", "DESEMBARCO", "BALEARES", "MALLORCA", "FORMENTERA",
             "CARTAGENA", "BARCELONA", "ACORAZADO", "DESTRUCTOR", "LONGITUD", "PRECAUCIONES",
             "NUESTRO", "REFIERO", "COMUNICO", "HONOR")
def _has_word(txt):
    """Robust break signal, immune to extreme-value inflation: over ~500M ring
    decodes the best FAKES high IoC/frag by chance (scattered EL/DE/LA), but an 8+
    letter dictionary word essentially never occurs at random. Real breaks contain
    connected words; noise does not."""
    return next((w for w in LONGWORDS if w in txt), None)


CWORDS = LONGWORDS + ("CONSECUENCIA", "DESEMBARCO", "ENEMIGO", "INTENTASE", "ALGUNA", "ACCION",
                      "PORSIENE", "SOBRE", "OIBIZA", "IBIZA", "MOVIMIENTOBARCOS", "TOMEPRECAUCIONES",
                      "CUATRO", "SIETE", "OCHO", "PROSEGUIR", "HORAS", "FECHA", "ORDENADA", "AERONAVAL",
                      "CACAREADO", "MALLORCAOIBIZA")
def _consensus(decodes):
    """Merge several partial decodes of one message into a consensus reading. The
    garble is turnover-adjacent and moves with the key, so different keys read
    different regions cleanly; per position we take the letter that falls inside a
    recognised Spanish word (else the majority). Returns (text, confident[]) where
    confident marks agreed/word-backed positions (shown UPPER; uncertain lower)."""
    ds = list(dict.fromkeys(d for d in decodes if d))
    if not ds:
        return "", []
    n = len(ds[0]); ds = [d for d in ds if len(d) == n]
    masks = []
    for d in ds:
        m = [False] * n
        for w in CWORDS:
            i = d.find(w)
            while i != -1:
                for j in range(i, i + len(w)):
                    m[j] = True
                i = d.find(w, i + 1)
        masks.append(m)
    out = []; conf = []
    for p in range(n):
        cov = [k for k in range(len(ds)) if masks[k][p]]
        if cov:
            c = Counter(ds[k][p] for k in cov); out.append(c.most_common(1)[0][0]); conf.append(True)
        else:
            c = Counter(d[p] for d in ds); ltr, ct = c.most_common(1)[0]
            out.append(ltr if ct > 1 else ltr.lower()); conf.append(ct > 1)
    return ''.join(out), conf


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


def run(path, cribs, procs=4, all_arr=True, mix=False, min_crib=MIN_CRIB):
    data = json.load(open(path, encoding="utf-8")); m = data[0] if isinstance(data, list) else data
    grund = m.get("grundstellung")
    if not grund or len(grund) != 4:
        print(f"ERROR: {path} has no 4-letter Grundstellung (got {grund!r}); cannot search."); return
    body, plains = cs.parse_body(m)
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
        if len(cb) < min_crib:
            print(f"[skip crib '{crib}' -- {len(cb)}<{min_crib} letters; lower with --min-crib if you accept noise]"); continue
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
                io = _ioc(dec); fs = cs.fscore(dec)
                if best is None or fs > best[0]:
                    cfg = (f"order {'-'.join(cs.ORDERS[oi])}  win(U,L,M,R)={A[uwin] + ''.join(A[w] for w in windows)}"
                           f"  rings={''.join(A[r] for r in rings)}")
                    best = (fs, io, cfg, dec)
            fs, io, cfg, dec = best
            flag = "  <== SPANISH-LIKE" if _spanish(fs, len(dec)) else ""
            print(f"    [{label}]  {len(hits)} matches  frag={fs} IoC={io:.4f}{flag}")
            results.append((fs, io, crib, label, cfg, dec))
    cs.WIRINGS.pop('_MIX', None)
    print("\n" + "=" * 64)
    print("BEST OF THE RUN  (ranked by frag-score/letter; real Spanish ~0.24, noise <0.08)")
    print("=" * 64)
    if not results:
        print("no combo reproduced any crib."); return
    results.sort(reverse=True)                                     # (fs, io, ...) -> frag first
    for fs, io, crib, label, cfg, dec in results[:12]:
        flag = "  <== SPANISH-LIKE (real candidate)" if _spanish(fs, len(dec)) else ""
        print(f"  frag={fs} IoC={io:.4f}  crib '{crib}'  [{label}]{flag}")
        print(f"      {cfg}")
        print(f"      {dec}")
    tfs, tdec = results[0][0], results[0][5]
    print()
    if _spanish(tfs, len(tdec)):
        print("=> POSSIBLE BREAK: the top line has real Spanish fragments. READ it to confirm.")
    else:
        print(f"=> Nothing broke: best frag-score {tfs} (~{tfs/max(len(tdec),1):.3f}/letter) is degeneracy/")
        print(f"   noise, NOT Spanish (a real break scores ~0.24/letter -- e.g. XMOT gives 32).")
        print(f"   {'Mixed' if mix else 'Pure'} D/F rotors do not decode this message.")


def _ioc_init(defs):
    """Pool initializer: inject the mixed wiring sets into each worker process
    (needed because macOS 'spawn' re-imports corpus_sweep fresh, without them)."""
    import corpus_sweep as _cs
    _cs.WIRINGS.update(defs)


def _ioc_full_worker(task):
    """Score every full decode by IoC over the FULL 26^4 ring space.

    BUGFIX (was: always looped RR, fixed rm=0): the ring that must be swept in
    the OUTER loop (the one posseq() needs to recompute the step sequence) is
    whichever SLOT actually carries a core-based (offset) notch right now --
    that is the rotor sitting in order[1] (middle slot) if IT has a known notch
    (e.g. III in the middle, as in HUEQ's I-III-II), because then it is the
    middle wheel's OWN notch -- keyed off RM -- that fires its double-step, not
    the right wheel's. Only if the middle slot's rotor has no known notch does
    the right slot's notch (keyed off RR) drive stepping, as before (XMOT's
    II-I-III: III is in the RIGHT slot, so this is unchanged, RR still swept).
    The other three rings never affect stepping, only offsets, so they can
    always be vectorised together over 26^3.
    """
    import numpy as np
    wiring, order, windows, uwin, ct_list, topk = task
    ct = np.array(ct_list); N = len(ct)
    W = {k: cs.perm(cs.WIRINGS[wiring][k]) for k in ('I', 'II', 'III')}
    lf, lr = W[order[0]]; mf, mr = W[order[1]]; rf, rr = W[order[2]]
    g = np.arange(26)
    ETWR = cs.ETWR; ETWF = cs.ETWF; UKWF = cs.UKWF; A = cs.A
    mid_notch = cs.NOTCH_OFFSET.get(order[1]) is not None   # middle-slot rotor's own notch known?
    RU, RL, R2 = (z.ravel() for z in np.meshgrid(g, g, g, indexing='ij'))  # 26^3 vectorised rings
    V = RU.size
    res = []
    for sweep in range(26):
        if mid_notch:
            RM = np.full(V, sweep, np.int64); RR = R2       # stepping keyed off RM -> sweep RM
            seq = cs.posseq(order, windows, N, (0, sweep, 0))
        else:
            RM = R2; RR = np.full(V, sweep, np.int64)        # stepping keyed off RR -> sweep RR (as before)
            seq = cs.posseq(order, windows, N, (0, 0, sweep))
        out = np.empty((V, N), np.int8)
        for t in range(N):
            L, M, R = seq[t]
            oL = (L - RL) % 26; oM = (M - RM) % 26; oR = (R - RR) % 26; u = (uwin - RU) % 26
            x = ETWR[int(ct[t])]
            x = (rf[(x + oR) % 26] - oR) % 26; x = (mf[(x + oM) % 26] - oM) % 26; x = (lf[(x + oL) % 26] - oL) % 26
            x = (UKWF[(x + u) % 26] - u) % 26
            x = (lr[(x + oL) % 26] - oL) % 26; x = (mr[(x + oM) % 26] - oM) % 26; x = (rr[(x + oR) % 26] - oR) % 26
            out[:, t] = ETWF[x]
        cnt = np.zeros((V, 26), np.int32)
        for k in range(26):
            cnt[:, k] = (out == k).sum(1)
        io = (cnt * (cnt - 1)).sum(1) / (N * (N - 1))
        idx = np.argpartition(io, -40)[-40:]
        for i in idx:
            txt = ''.join(A[v] for v in out[i])
            res.append((float(io[i]), cs.fscore(txt), wiring, '-'.join(order),
                        (int(RU[i]), int(RL[i]), int(RM[i]), int(RR[i])), txt))
    res.sort(key=lambda z: (z[1], z[0]), reverse=True); return res[:topk]


def ioc_run(path, procs=4, all_arr=True, mix=False, topk=3, consensus=False):
    """IoC-blind mode (no crib): for each rotor-set combo, sweep arrangements /
    orders / the FULL 26^4 rings and score each full decode by IoC. Finds ANY setting
    that yields Spanish, without assuming known plaintext. Judge by IoC (Spanish
    ~0.075, random ~0.045)."""
    import multiprocessing as mp
    data = json.load(open(path, encoding="utf-8")); m = data[0] if isinstance(data, list) else data
    grund = m.get("grundstellung")
    if not grund or len(grund) != 4:
        print(f"ERROR: {path} has no 4-letter Grundstellung (got {grund!r}); cannot search."); return
    body, plains = cs.parse_body(m); ct = [c2n[c] for c in body]
    combos = list(itertools.product("DF", repeat=3)) if mix else [('D', 'D', 'D'), ('F', 'F', 'F')]
    sets = {'D': cs.WIRINGS['D'], 'F': cs.WIRINGS['F']}
    mixdefs = {}; names = []
    for i, combo in enumerate(combos):
        n = f"_MIX{i}"; names.append((n, combo))
        mixdefs[n] = {'I': sets[combo[0]]['I'], 'II': sets[combo[1]]['II'], 'III': sets[combo[2]]['III']}
    label = {n: f"I<-{c[0]} II<-{c[1]} III<-{c[2]}" for n, c in names}
    tasks = cs.build_tasks(ct, grund, all_arr, [n for n, _ in names], (topk,))
    print(f"message G={grund}  n={len(body)}  arrangements={'all' if all_arr else 'canonical'}  "
          f"combos={'8 (pure+mixed)' if mix else '2 (pure D,F)'}  IoC-blind (no crib)  "
          f"-- {len(tasks)} tasks x 26^4 rings\n")
    with mp.Pool(procs, initializer=_ioc_init, initargs=(mixdefs,)) as pool:
        allres = [r for sub in pool.map(_ioc_full_worker, tasks) for r in sub]
    best = {}
    for io, fs, w, order, rings, txt in allres:
        if w not in best or fs > best[w][1]:
            best[w] = (io, fs, order, rings, txt)
    for n, c in names:
        if n in best:
            io, fs, order, rings, txt = best[n]
            w2 = _has_word(txt)
            print(f"  [{label[n]}]  best frag={fs}  IoC={io:.4f}" + (f"  <== has '{w2}'" if w2 else ""))
    print("\n" + "=" * 64)
    print("BEST OF THE RUN  (IoC-blind; ranked by frag-score/letter, real Spanish ~0.24)")
    print("=" * 64)
    allres.sort(key=lambda z: (z[1], z[0]), reverse=True)         # frag first, IoC tiebreak
    for io, fs, w, order, rings, txt in allres[:10]:
        wd = _has_word(txt)
        print(f"  frag={fs} IoC={io:.4f}  [{label.get(w, w)}]  order {order}  "
              f"rings(U,L,M,R)={''.join(A[r] for r in rings)}" + (f"  <== CONTAINS '{wd}'" if wd else ""))
        print(f"      {txt}")
    for n, _ in names:
        cs.WIRINGS.pop(n, None)
    if consensus:
        distinct = []
        for _io, _fs, _w, _o, _r, txt in allres:
            if txt not in distinct:
                distinct.append(txt)
            if len(distinct) >= 20:
                break
        merged, cf = _consensus(distinct)
        print("\n" + "=" * 64)
        print(f"CONSENSUS over {len(distinct)} distinct decodes (UPPER=confident, lower=uncertain)")
        print("=" * 64)
        print("   ", merged)
        print(f"    confident positions: {sum(cf)}/{len(cf)}")
    hit = next(((z[5], _has_word(z[5])) for z in allres[:50] if _has_word(z[5])), None)
    print()
    if hit:
        print(f"=> CANDIDATE: a top decode contains the real word '{hit[1]}'. READ it and confirm with --crib.")
    else:
        tfs = allres[0][1] if allres else 0; tn = len(allres[0][5]) if allres else 1
        print(f"=> Nothing broke. The best frag-scores (~{tfs/max(tn,1):.2f}/letter) are EXTREME-VALUE noise:")
        print(f"   over {len(tasks)} tasks x 26^4 the best random decode fakes frag ~0.2 with scattered EL/DE/LA,")
        print(f"   but contains NO connected words (a real break shows e.g. MOVIMIENTOBARCOS). No")
        print(f"   {'mixed ' if mix else ''}D/F setting decodes this message -> consistent with wiring C (Caesar).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("message")
    ap.add_argument("--crib", help="a literal crib, or a file of cribs (one per line). OMIT for IoC-blind mode.")
    ap.add_argument("--mix", action="store_true", help="also try the 6 mixed rotor combos")
    ap.add_argument("--arr", choices=["all", "canonical"], default="all")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--min-crib", type=int, default=MIN_CRIB,
                    help=f"skip cribs shorter than this (default {MIN_CRIB}; >=8 is spurious-free)")
    ap.add_argument("--top", type=int, default=3, help="IoC-blind mode: keep this many settings per task")
    ap.add_argument("--consensus", action="store_true", help="IoC-blind: merge the top decodes into a consensus reading")
    a = ap.parse_args()
    if a.crib:
        run(a.message, load_cribs(a.crib), a.procs, all_arr=(a.arr == "all"), mix=a.mix, min_crib=a.min_crib)
    else:
        ioc_run(a.message, a.procs, all_arr=(a.arr == "all"), mix=a.mix, topk=a.top, consensus=a.consensus)


