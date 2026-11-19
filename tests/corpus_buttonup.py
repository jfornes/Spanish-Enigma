#!/usr/bin/env python3
"""
corpus_buttonup.py -- does the wiring recovery work on the real traffic?

buttonup.py's own self-tests encipher a text with our model and then recover
the rotor from it. This test uses the archive instead: for each message of the
corpus that has been read, the ciphertext as it stands on the sheet and the
plaintext we read from it are handed to the solver as a crib, and the solver
is asked for the rotors WITHOUT being given any wiring.

  right rotor   buttoning-up (C kernel, anchor brute-forced 26x26)
  middle rotor  mu-propagation over consecutive rod positions, starting from a
                right rotor the first step returned -- not from the true one

A rotor is recovered up to a constant shift ("wheel twist and clip
difference"), so the right rotor comes back as 26 solutions, each the true
wiring with its output shifted, and the middle rotor as the true wiring with
its input rotated and its output shifted.

WHAT THIS IS AND IS NOT. The plaintexts were read on wiring F, so the
constraints agree with F by construction: this checks the PROCEDURE on real
lengths and real stepping. It is not an independent confirmation of the wiring
(the Spanish text is), and it is not the recovery of an unknown wiring.

The unread ends of a message (solution.unread_ends) are left out of the crib.

Run from the repository root:  python3 tests/corpus_buttonup.py
Needs librods (cd src && make).

Result:

    msg    crib  right        middle
    LUIS     76  III  yes     I    no   (4 rod positions)
    DHZB     80  III  yes     I    no   (4 rod positions)
    MVNR    192  III  yes     I    yes  (8 rod positions)
    XMOT    132  III  yes     I    yes  (6 rod positions, coverage 20)
    MKCX    109  II   yes     III  yes  (5 rod positions)

Between them the five messages return all three rotors of wiring F.
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
import corpus_sweep as cs
import buttonup as bu
c2n = cs.c2n

TRAFFIC = ("LUIS", "DHZB", "MVNR", "XMOT", "MKCX")
# Contacts that must be paired at a middle rod position for it to count.
# recover_middle's default is 22; XMOT needs 20 and the table says so.
COVERAGE = (22, 20)
# What the archive gives today: the coverage at which the middle rotor comes
# back, or None. A change here is a change in the solver or in a transcription.
EXPECT_MIDDLE = {"LUIS": None, "DHZB": None, "MVNR": 22, "XMOT": 20, "MKCX": 22}


def load(name):
    d = json.load(open(os.path.join(HERE, "..", "data", "messages", name + ".json")))
    m = d[0] if isinstance(d, list) else d
    return m, m["solution"]


def same_up_to_gauge(got, true):
    """got[k] == true[(k + c) % 26] + d for some constants c, d."""
    return any(all(got[k] == (true[(k + c) % 26] + d) % 26 for k in range(26))
               for c in range(26) for d in range(26))


def one(name):
    m, s = load(name)
    body, _ = cs.parse_body(m)
    plain = s["plaintext"]
    n = min(len(body), len(plain))
    ends = s.get("unread_ends") or {}
    lo, hi = ends.get("head_letters", 0), n - ends.get("tail_letters", 0)
    P = [c2n[c] for c in plain[:n]]
    C = [c2n[c] for c in body[:n]]
    order = tuple(s["rotor_order"].split("-"))
    w = [c2n[c] for c in s["windows_ULMR"]]
    rings = tuple(c2n[c] for c in s["ringstellung_ULMR"])
    W = cs.WIRINGS[s["wiring"]]
    true_r = cs.perm(W[order[2]])[0]
    true_m = list(cs.perm(W[order[1]])[0])

    # ---- right rotor: no wiring supplied -------------------------------
    cons, ns, touched = bu.build_constraints(order, (w[1], w[2], w[3]), w[0], rings, P, C)
    cons = cons[lo:hi]
    sid = {x: i for i, x in enumerate(sorted({c[3] for c in cons}))}
    cons = [(i, j, o, sid[st]) for i, j, o, st in cons]
    touched = sorted({i for i, j, o, st in cons} | {j for i, j, o, st in cons})
    sols, _ = bu.solve_c(cons, len(sid), touched, nthreads=os.cpu_count() or 1)
    shifts = set()
    for x in sols:
        d = {(x[k] - true_r[k]) % 26 for k in touched}
        if len(d) != 1:
            shifts = None
            break
        shifts.add(d.pop())
    right_ok = (shifts is not None and len(touched) == 26
                and len(sols) == 26 and shifts == set(range(26)))

    # ---- middle rotor: from a right rotor the solver returned ----------
    mid_cov, npos = None, 0
    if right_ok:
        # deliberately not the true one: a solution with a non-zero shift
        r = next(x for x in sols if (x[0] - true_r[0]) % 26 != 0)
        seq = cs.posseq(order, (w[1], w[2], w[3]), n, rings[1:])
        E = {}
        for t in range(lo, hi):
            oR = (seq[t][2] - rings[3]) % 26
            oM = (seq[t][1] - rings[2]) % 26
            a = (r[(bu.ETWR[P[t]] + oR) % 26] - oR) % 26
            b = (r[(bu.ETWR[C[t]] + oR) % 26] - oR) % 26
            e = E.setdefault(oM, {})
            e[a] = b
            e[b] = a
        npos = len(E)
        for cov in COVERAGE:
            cands = bu.recover_middle(E, min_cov=cov)
            if cands:
                if all(same_up_to_gauge(c, true_m) for c in cands) and len(cands) == 1:
                    mid_cov = cov
                else:
                    mid_cov = "WRONG"
                break
    return dict(name=name, n=hi - lo, right=order[2], right_ok=right_ok,
                middle=order[1], mid_cov=mid_cov, npos=npos)


def main():
    try:
        bu._load_lib()
    except OSError as e:
        print("corpus_buttonup: librods not found -- build it (cd src && make).", e)
        return 2
    print(f"{'msg':6s} {'crib':>5s}  {'right':12s} {'middle':s}")
    print("-" * 60)
    ok = True
    recovered = set()
    for name in TRAFFIC:
        r = one(name)
        if r["right_ok"]:
            recovered.add(r["right"])
        mid = r["mid_cov"]
        if mid in COVERAGE:
            recovered.add(r["middle"])
        note = f"({r['npos']} rod positions" + (f", coverage {mid})" if mid == 20 else ")")
        print(f"{r['name']:6s} {r['n']:5d}  {r['right']:4s} {'yes' if r['right_ok'] else 'NO ':3s}"
              f"     {r['middle']:4s} {'yes' if mid in COVERAGE else ('WRONG' if mid == 'WRONG' else 'no '):3s}  {note}")
        if not r["right_ok"] or mid != EXPECT_MIDDLE[name]:
            ok = False
    print(f"\nrotors of the wiring returned by the traffic: {', '.join(sorted(recovered, key=len))}")
    if not ok:
        print("corpus_buttonup: result differs from the recorded one (EXPECT_MIDDLE, right rotor).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
