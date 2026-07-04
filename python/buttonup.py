#!/usr/bin/env python3
"""
buttonup.py -- Knox-style "buttoning up": recover the FAST (right) rotor wiring
of a plugboard-free Enigma (commercial K, Spanish Civil War) from known-plaintext
cribs. Front-end + reference solver; reuses the machine model in corpus_sweep.

HISTORICAL PIPELINE (Knox / ISK, unsteckered Enigma):
    rodding  ->  buttoning-up
  * rodding (already in the toolkit as rod_search) finds the fast wheel + its
    start position from a crib, and yields a small coupling ANCHOR.
  * buttoning-up (here) recovers the fast-rotor WIRING by constraint propagation.

MATH (validated against wiring F, this file's --selftest):
  Within a stretch where the middle & left rotors do not step, the machine is
      c = ETW^-1 . R_o^-1 . B . R_o . ETW
  with R_o the right rotor conjugated by offset o=(window-ring), and B a FIXED
  point-free involution (the middle+left+UKW composite). Per crib letter:
      in  = (ETWR[p] + o) % 26 ,  out = (ETWR[c] + o) % 26
      B( (R[in]-o)%26 ) = (R[out]-o)%26
  A long crib spanning turnovers gives SEVERAL stretches: same R, one B each.
  Unknowns R (a permutation) and B_s (involutions) are solved by propagation +
  backtracking, seeded by a small anchor (2 rf values -- what rodding provides).

  Determination note: a single short stretch (all-distinct offsets) is
  UNDER-determined (~39 unknowns vs ~20 constraints). Multiple stretches from a
  long crib over-determine R and make recovery unique+fast.

SCOPE: Python is the front-end + reference solver. The heavy piece -- brute
forcing the 2-contact anchor (26x26 seeds x search) when rodding gives no anchor
-- is the kernel to move into librods (C). With an anchor supplied, this pure-
Python solver already recovers the rotor instantly.
"""
import sys, argparse
import corpus_sweep as cs
c2n = cs.c2n; A = cs.A; ETWR = cs.ETWR


def build_constraints(order, windows, uwin, rings, plain_ints, cipher_ints):
    """(cons, n_stretch, touched). cons entries: (in, out, o, stretch_id).
    windows=(L,M,R), rings=(U,L,M,R). Stretch id bumps when the middle window
    steps -- each stretch shares R but has its own involution B."""
    rR = rings[3]
    seq = cs.posseq(order, windows, len(plain_ints))     # (L,M,R) window per letter
    sid = []; cur = seq[0][1]; s = 0
    for (l, m, r) in seq:
        if m != cur:
            s += 1; cur = m
        sid.append(s)
    cons = []
    for t in range(len(plain_ints)):
        o = (seq[t][2] - rR) % 26
        cons.append(((ETWR[plain_ints[t]] + o) % 26,
                     (ETWR[cipher_ints[t]] + o) % 26, o, sid[t]))
    touched = sorted({i for i, j, o, s in cons} | {j for i, j, o, s in cons})
    return cons, max(sid) + 1, touched


def _propagate(cons, rf, B, used):
    """Fixpoint propagation. rf: length-26 (-1 unknown). B: list of length-26
    involutions per stretch. Returns False on any contradiction."""
    ch = True
    while ch:
        ch = False
        for (i, j, o, s) in cons:
            bi = B[s]; ri, rj = rf[i], rf[j]
            if ri != -1 and rj != -1:                 # both R ends known -> pin B pair
                a1 = (ri - o) % 26; a6 = (rj - o) % 26
                if a1 == a6:
                    return False                      # involution has no fixed point
                if bi[a1] == -1 and bi[a6] == -1:
                    bi[a1] = a6; bi[a6] = a1; ch = True
                elif bi[a1] != a6 or bi[a6] != a1:
                    return False
            elif ri != -1:                            # one R end + its B pair -> force other
                a1 = (ri - o) % 26
                if bi[a1] != -1:
                    v = (bi[a1] + o) % 26
                    if rj == -1:
                        if v in used:
                            return False              # R must stay a bijection
                        rf[j] = v; used.add(v); ch = True
                    elif rj != v:
                        return False
            elif rj != -1:
                a6 = (rj - o) % 26
                if bi[a6] != -1:
                    v = (bi[a6] + o) % 26
                    if rf[i] == -1:
                        if v in used:
                            return False
                        rf[i] = v; used.add(v); ch = True
                    elif rf[i] != v:
                        return False
    return True


def solve(cons, ns, touched, anchors, max_sol=20, cap=2_000_000):
    """anchors: {contact: value} (from rodding). Returns (solutions, nodes).
    Each solution is a length-26 list = recovered right-rotor forward wiring on
    the touched contacts (untouched contacts stay -1)."""
    per = {k: sum(1 for i, j, o, s in cons if i == k or j == k) for k in touched}
    found = []; counter = [0]

    def rec(rf, B, used):
        if len(found) >= max_sol or counter[0] > cap:
            return
        counter[0] += 1
        rf = rf[:]; B = [b[:] for b in B]; used = set(used)
        if not _propagate(cons, rf, B, used):
            return
        un = [k for k in touched if rf[k] == -1]
        if not un:
            found.append(rf[:]); return
        k = max(un, key=lambda k: per[k])             # most-constrained contact next
        for v in range(26):
            if v in used:
                continue
            rf2 = rf[:]; rf2[k] = v
            rec(rf2, B, used | {v})
            if len(found) >= max_sol:
                return

    rf0 = [-1] * 26; used0 = set()
    for k, v in anchors.items():
        rf0[k] = v; used0.add(v)
    rec(rf0, [[-1] * 26 for _ in range(ns)], used0)
    return found, counter[0]


def brute_anchor(cons, ns, touched, max_sol=50, cap_each=200_000):
    """No rodding anchor available: brute-force the two most-constrained contacts.
    (Reference implementation -- this is the loop destined for the C kernel.)"""
    per = {k: sum(1 for i, j, o, s in cons if i == k or j == k) for k in touched}
    a, b = sorted(touched, key=lambda k: -per[k])[:2]
    sols = []
    for va in range(26):
        for vb in range(26):
            if va == vb:
                continue
            f, _ = solve(cons, ns, touched, {a: va, b: vb}, max_sol=2, cap=cap_each)
            sols.extend(f)
            if len(sols) >= max_sol:
                return sols, (a, b)
    return sols, (a, b)


# --------------------------------------------------------------------------- #
def _synthetic_F(nletters=70):
    """Build a synthetic wiring-F crib (we control everything -> positive control).
    Returns (cons, n_stretch, touched, rfF, n_letters)."""
    order = ('II', 'I', 'III'); W = cs.WIRINGS['F']
    rfF = cs.perm(W[order[2]])[0]
    windows = (c2n['A'], c2n['C'], c2n['O']); uwin = c2n['T']
    rings = (c2n['B'], c2n['D'], c2n['G'], c2n['Q'])
    plain = ("SEHACONFIRMADOELMOVIMIENTODEBARCOSENEMIGOSHACIALASBALEARESTOMENSE" * 3)[:nletters]
    p = [c2n[ch] for ch in plain]
    cipher = cs.decode_all('F', order, windows, uwin, rings, p)   # Enigma reciprocal -> encodes
    c = [c2n[ch] for ch in cipher]
    cons, ns, touched = build_constraints(order, windows, uwin, rings, p, c)
    return cons, ns, touched, rfF, len(plain)


# ---- C kernel binding: buttonup_anchor via the shared rodslib loader ----------
import ctypes, rodslib
def _load_lib():
    """librods CDLL with buttonup_anchor's argtypes configured (see rodslib.py)."""
    return rodslib.load()


def solve_c(cons, ns, touched, nthreads=1, max_sols=400):
    """Brute-force the anchor in C (no anchor needed). Returns (unique_sols, (a,b)).
    Each solution is a length-26 list = recovered right-rotor forward wiring."""
    import numpy as np
    lib = _load_lib(); IP = ctypes.POINTER(ctypes.c_int)
    cin = np.array([x[0] for x in cons], dtype=np.int32)
    cout = np.array([x[1] for x in cons], dtype=np.int32)
    co = np.array([x[2] for x in cons], dtype=np.int32)
    cst = np.array([x[3] for x in cons], dtype=np.int32)
    tou = np.array(touched, dtype=np.int32)
    per = {k: sum(1 for i, j, o, s in cons if i == k or j == k) for k in touched}
    a, b = sorted(touched, key=lambda k: -per[k])[:2]
    out = np.zeros(max_sols * 26, dtype=np.int32)
    n = lib.buttonup_anchor(
        cin.ctypes.data_as(IP), cout.ctypes.data_as(IP),
        co.ctypes.data_as(IP), cst.ctypes.data_as(IP), len(cons),
        int(ns), tou.ctypes.data_as(IP), len(touched),
        int(a), int(b), int(nthreads), out.ctypes.data_as(IP), max_sols)
    if n < 0:
        raise RuntimeError(f"buttonup_anchor: nstr={ns} exceeds kernel MAXSTR")
    seen = {}
    for i in range(n):
        s = [int(x) for x in out[i*26:(i+1)*26]]
        seen[tuple(s[k] for k in touched)] = s
    return list(seen.values()), (a, b)


def _selftest(nthreads=1, use_c=False):
    """Recover the wiring-F right rotor from a synthetic crib.
    python path: rodding anchor (2 true values).  C path: anchor brute-forced."""
    cons, ns, touched, rfF, nlet = _synthetic_F()
    per = {k: sum(1 for i, j, o, s in cons if i == k or j == k) for k in touched}
    a, b = sorted(touched, key=lambda k: -per[k])[:2]
    tag = "C" if use_c else "py"
    if use_c:
        sols, (a, b) = solve_c(cons, ns, touched, nthreads=nthreads); nodes = None
    else:
        sols, nodes = solve(cons, ns, touched, {a: rfF[a], b: rfF[b]})
    match = [s for s in sols if all(s[k] == rfF[k] for k in touched)]
    ok = len(match) >= 1
    detail = (f"nodes={nodes}; anchor from rodding"
              if nodes is not None
              else f"threads={nthreads}; anchor brute-forced 26x26")
    print(f"[selftest {tag}]  {nlet} letters, {ns} stretches, "
          f"{len(touched)} contacts, {len(cons)} constraints")
    print(f"[selftest {tag}]  anchor contacts {a},{b}; {detail}; solutions={len(sols)}")
    print(f"[selftest {tag}]  recovered right rotor == true wiring F: {ok}")
    return ok


# --------------------------------------------------------------------------- #
# Middle rotor: Rejewski-style recovery from the per-offset involutions.
# Once the right rotor rf is known, peeling it off leaves, within a stretch where
# the LEFT rotor is static, the middle rotor mf plus a FIXED involution C
# (left+UKW composite). At each middle-rotor offset o the crib yields an involution
#   E_o = mf_o^-1 . C . mf_o           (mf_o = the middle wheel conjugated by o)
# Writing Q_o = shift_o . E_o . shift_-o gives Q_o = mf^-1 . C_o . mf, and for
# CONSECUTIVE offsets  Q_{o+1} = M . Q_o . M^-1  with  M = mf^-1 . (+1) . mf, a
# single 26-cycle. Propagating M over well-covered consecutive offsets recovers it;
# mf then follows from M's cycle (mf(M(x)) = mf(x)+1), unique up to the global gauge
# shift (harmless -- absorbed by the neighbouring rotor). Pure 26-point combinatorics.

def build_middle_involutions(order, windows, uwin, rings, rf, plain_ints, cipher_ints):
    """Peel the known right rotor rf; tabulate, per middle offset, the involution
    E_o pairing the middle rotor's external contacts. Returns {offset: {a: b}}."""
    rR, rM = rings[3], rings[2]
    seq = cs.posseq(order, windows, len(plain_ints))
    E = {}
    for t in range(len(plain_ints)):
        oR = (seq[t][2] - rR) % 26; oM = (seq[t][1] - rM) % 26
        a1 = (rf[(ETWR[plain_ints[t]] + oR) % 26] - oR) % 26
        a6 = (rf[(ETWR[cipher_ints[t]] + oR) % 26] - oR) % 26
        d = E.setdefault(oM, {}); d[a1] = a6; d[a6] = a1
    return E

def recover_middle(E, min_cov=22):
    """Recover the middle-rotor wiring from the per-offset involutions E. Returns a
    list of mf candidates (length-26 lists), each valid up to a global gauge shift.
    Needs enough well-covered CONSECUTIVE offsets for the M-propagation to span all
    26 contacts (transitivity); a short crib (few offsets) is under-determined."""
    cov = {o: len(E[o]) for o in E}
    def build_Q(Ed, o):
        Ec = dict(Ed); miss = [x for x in range(26) if x not in Ec]
        if len(miss) == 2: a, b = miss; Ec[a] = b; Ec[b] = a   # a 2-gap involution completes uniquely
        return [(Ec[(y - o) % 26] + o) % 26 if (y - o) % 26 in Ec else None for y in range(26)]
    Q = {o: build_Q(E[o], o) for o in E}
    rel = [(o, (o + 1) % 26) for o in range(26)
           if o in Q and (o + 1) % 26 in Q and cov.get(o, 0) >= min_cov and cov.get((o + 1) % 26, 0) >= min_cov]
    def propagate(sv):
        M = [None] * 26; M[0] = sv; used = [False] * 26; used[sv] = True; ch = True
        while ch:
            ch = False
            for x in range(26):
                if M[x] is None: continue
                for oa, ob in rel:
                    if Q[oa][x] is not None and Q[ob][M[x]] is not None:
                        nx, nv = Q[oa][x], Q[ob][M[x]]
                        if M[nx] is None:
                            if used[nv]: return None
                            M[nx] = nv; used[nv] = True; ch = True
                        elif M[nx] != nv: return None
        return M
    out = []
    for sv in range(26):
        M = propagate(sv)
        if not M or any(v is None for v in M) or len(set(M)) != 26: continue
        x, n = 0, 0                                             # require a single 26-cycle
        while True:
            x = M[x]; n += 1
            if x == 0: break
        if n != 26: continue
        mf = [0] * 26; cc, val = 0, 0
        for _ in range(26): mf[cc] = val % 26; cc = M[cc]; val += 1
        if mf not in out: out.append(mf)
    return out

def _selftest_middle():
    """Positive control: recover the wiring-F middle rotor (right rotor given)."""
    order = ('II', 'I', 'III'); Wf = cs.WIRINGS['F']
    rf = cs.perm(Wf[order[2]])[0]; mfT = list(cs.perm(Wf[order[1]])[0])
    windows = (c2n['A'], c2n['C'], c2n['O']); uwin = c2n['T']
    rings = (c2n['B'], c2n['D'], c2n['G'], c2n['Q'])
    plain = ("SEHACONFIRMADOELMOVIMIENTODEBARCOSENEMIGOSHACIALASBALEARESTOMENSEATAQUEINMINENTEALASBALEARES" * 4)[:300]
    p = [c2n[ch] for ch in plain]
    c = [c2n[ch] for ch in cs.decode_all('F', order, windows, uwin, rings, p)]
    E = build_middle_involutions(order, windows, uwin, rings, rf, p, c)
    cands = recover_middle(E)
    ok = any(len({(m[k] - mfT[k]) % 26 for k in range(26)}) == 1 for m in cands)
    print(f"[selftest middle]  {len(plain)} letters, offsets {sorted(E)}")
    print(f"[selftest middle]  candidates {len(cands)}; middle rotor recovered up to gauge: {ok}")
    return ok


# --------------------------------------------------------------------------- #
# Left rotor: recovery across messages at DISTINCT left-window positions.
# The left rotor steps only ~once per 676 letters, so a normal message holds it
# static (one offset). Peeling off the known R and M, each crib letter links two
# left contacts through the KNOWN reflector: L[bb] = g_oL(L[a]). At a single left
# offset these edges form a matching (under-determined); distinct left offsets from
# several messages connect the graph. In practice ~3 left-window positions suffice.
# Because the reflector is fixed, the left rotor is pinned EXACTLY -- no gauge.

def build_left_edges(order, windows, uwin, rings, R, Mid, plain_ints, cipher_ints):
    """Peel the known right rotor R and middle rotor Mid; return left-rotor edges
    (a, bb, oL) for ONE message. windows=(L,M,R), rings=(U,L,M,R)."""
    rR, rM, rL = rings[3], rings[2], rings[1]
    seq = cs.posseq(order, windows, len(plain_ints))
    def conj(perm, off, x): return (perm[(x + off) % 26] - off) % 26
    edges = []
    for t in range(len(plain_ints)):
        oR = (seq[t][2] - rR) % 26; oM = (seq[t][1] - rM) % 26; oL = (seq[t][0] - rL) % 26
        b1 = conj(Mid, oM, conj(R, oR, ETWR[plain_ints[t]]))
        b6 = conj(Mid, oM, conj(R, oR, ETWR[cipher_ints[t]]))
        edges.append(((b1 + oL) % 26, (b6 + oL) % 26, oL))
    return edges

def recover_left(edges, u):
    """Recover the left-rotor wiring from edges pooled across messages. u = the
    reflector offset (shared). Returns full L candidates (length-26 lists); exact,
    no gauge. A single left offset is under-determined; pool several distinct ones."""
    UKWF = cs.UKWF
    def g(v, oL): return (UKWF[((v - oL) % 26 + u) % 26] - u + oL) % 26
    a0 = edges[0][0]; out = []
    for v0 in range(26):
        L = [None] * 26; L[a0] = v0; used = [False] * 26; used[v0] = True; ch = True; bad = False
        while ch and not bad:
            ch = False
            for a, bb, oL in edges:
                for x, y in ((a, bb), (bb, a)):
                    if L[x] is not None:
                        nv = g(L[x], oL)
                        if L[y] is None:
                            if used[nv]: bad = True; break
                            L[y] = nv; used[nv] = True; ch = True
                        elif L[y] != nv: bad = True; break
                if bad: break
        if not bad and all(x is not None for x in L) and len(set(L)) == 26 and L not in out:
            out.append(L)
    return out

def _selftest_left():
    """Positive control: recover the wiring-F LEFT rotor (R and M given) from three
    messages at distinct left-window positions."""
    order = ('II', 'I', 'III'); Wf = cs.WIRINGS['F']
    R = cs.perm(Wf[order[2]])[0]; Mid = cs.perm(Wf[order[1]])[0]; Lt = list(cs.perm(Wf[order[0]])[0])
    uwin = c2n['T']; rings = (c2n['B'], c2n['D'], c2n['G'], c2n['Q']); u = (uwin - rings[0]) % 26
    plain = ("SEHACONFIRMADOELMOVIMIENTODEBARCOSENEMIGOSHACIALASBALEARESTOMENSEATAQUE" * 2)[:96]
    p = [c2n[ch] for ch in plain]; edges = []
    for Lw in (c2n['A'], c2n['F'], c2n['K']):
        windows = (Lw, c2n['C'], c2n['O'])
        c = [c2n[ch] for ch in cs.decode_all('F', order, windows, uwin, rings, p)]
        edges += build_left_edges(order, windows, uwin, rings, R, Mid, p, c)
    cands = recover_left(edges, u)
    ok = any(L == Lt for L in cands)
    print(f"[selftest left]  3 left positions; candidates {len(cands)}; "
          f"left rotor recovered exactly (no gauge): {ok}")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Buttoning-up: recover the fast-rotor wiring.")
    ap.add_argument("--selftest", action="store_true",
                    help="python reference: recover wiring F (rodding anchor)")
    ap.add_argument("--selftest-c", action="store_true",
                    help="C kernel: recover wiring F (anchor brute-forced 26x26)")
    ap.add_argument("--selftest-middle", action="store_true",
                    help="recover the wiring-F MIDDLE rotor from consecutive E_o involutions")
    ap.add_argument("--selftest-left", action="store_true",
                    help="recover the wiring-F LEFT rotor from 3 messages at distinct left positions")
    ap.add_argument("--procs", type=int, default=1, help="threads for the C kernel (default 1)")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if _selftest(use_c=False) else 1)
    if a.selftest_c:
        sys.exit(0 if _selftest(nthreads=a.procs, use_c=True) else 1)
    if a.selftest_middle:
        sys.exit(0 if _selftest_middle() else 1)
    if a.selftest_left:
        sys.exit(0 if _selftest_left() else 1)
    ap.print_help()
