#!/usr/bin/env python3
"""
hw43_p90_buttonup.py -- a complete break printed by the Knox section, replayed.

Source: TNA HW 43/7, history of the Intelligence Services Knox section,
pp. 88-90: the Spanish military attache's Enigma, broken on the crib
DIVISIONNOHADADOHOYPARTENOVEDADES. Two cryptograms of 33 letters thought to be
at the same rod position are "buttoned up" with the crib, and p. 90 prints the
result: one row per cryptogram and one for the crib, the graph of rod pairings
that follows, and the upright of the fast rotor.

Buttoning up a letter at position p takes it through the entry wheel and the
rod position p - 1: the same step as buttonup.py and the engine, with the entry
wheel of wirings.json. Checked:
  1. with the entry wheel in keyboard order the three printed rows come back at
     99 of 99 letters; with it reversed, at 8 of 99;
  2. the two cryptograms agree at exactly two positions, 19 and 22, the two
     letters underlined in each on p. 89, and there the buttoned pairs coincide
     (the "click" of p. 90);
  3. the nine edges of the graph on p. 90 are pairings the buttoned rows show
     (the edge printed 'g4' is read 'a4': only (a) and (b) are in play);
  4. position 11 of cryptogram (a) is Y, as in the table of p. 88; p. 89 types
     X, which gives 98 of 99.

Run from the repository root:  python3 tests/hw43_p90_buttonup.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))
import corpus_sweep as cs

A, c2n, F, R = cs.A, cs.c2n, cs.ETWF, cs.ETWR

CRIB = "DIVISIONNOHADADOHOYPARTENOVEDADES"
CA = "EPFPMANTWIYIHTOIARSLTMCKKEJJHDVBH"      # 11/3 1635, p. 88 (p. 89 has X at 11)
CB = "NAZEWXBGYFQXQELBESSCOMGTMAIBWXOWP"      # 12/6 1552
PRINTED = {"a": "EYHCEHRDAKEYQPBBLCEYMXKGHWJKKHLWC",
           "b": "NSIZZMECQVSTFJGDYWEGEXAWBOINRBFUN",
           "crib": "DONSHFHTZPMCNBLNTLSSRMQLVIVRGFJIK"}
EDGES = [("b", 7, "EQ", "HZ"), ("b", 21, "EQ", "RA"), ("a", 7, "RA", "HZ"),
         ("a", 11, "EQ", "MN"), ("b", 11, "SF", "MN"), ("b", 4, "ZM", "SF"),
         ("a", 9, "AE", "ZM"), ("a", 4, "CH", "SF"), ("b", 9, "QS", "ZM")]

FAIL = []


def check(cond, what):
    print(f"  {'ok  ' if cond else 'FAIL'}  {what}")
    if not cond:
        FAIL.append(what)


def keyboard(x, o):                      # entry wheel as in wirings.json
    return A[F[(R[c2n[x]] + o) % 26]]


def reversed_ew(x, o):                   # the same wheel, the other way round
    return A[R[(F[c2n[x]] + o) % 26]]


def button(text, mu):
    return "".join(mu(x, p) for p, x in enumerate(text))     # rod position p - 1


def score(mu, ca=CA):
    rows = {"a": button(ca, mu), "b": button(CB, mu), "crib": button(CRIB, mu)}
    return sum(x == y for k in rows for x, y in zip(rows[k], PRINTED[k])), rows


def main():
    good, rows = score(keyboard)
    check(good == 99, f"entry wheel in keyboard order: {good} of 99 printed letters")
    bad, _ = score(reversed_ew)
    check(bad == 8, f"entry wheel reversed: {bad} of 99")

    agree = [p + 1 for p, (x, y) in enumerate(zip(CA, CB)) if x == y]
    check(agree == [19, 22], f"the two cryptograms agree at positions {agree} (underlined on p. 89)")
    check(all(rows["a"][p - 1] == rows["b"][p - 1] for p in agree),
          "and there the buttoned pairs coincide: the click")

    def pair(m, p):
        return {rows[m][p - 1], rows["crib"][p - 1]}
    ok = [len(pair(m, p) & set(n1)) == 1 and len(pair(m, p) & set(n2)) == 1
          for m, p, n1, n2 in EDGES]
    check(all(ok), f"the {sum(ok)} edges of the graph on p. 90 hold")

    x11, _ = score(keyboard, CA[:10] + "X" + CA[11:])
    check(x11 == 98, f"with p. 89's X at position 11: {x11} of 99")
    print(f"\n{len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
