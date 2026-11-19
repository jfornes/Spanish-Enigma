#!/usr/bin/env python3
"""test_lang_model.py -- does the triage criterion actually separate?

Positive controls with a threshold. The important one is the last: for every
message read, the true plaintext must score above the 99th percentile of its
own letters shuffled. Shuffling keeps the letter frequencies exactly and
destroys the word structure, so passing means the score responds to Spanish
and not to an unusual letter distribution, which is what the index of
coincidence responds to.

    Run:  python3 tests/test_lang_model.py          (about 20 s)
          python3 tests/test_lang_model.py --quick  (fewer shuffles)
"""
import glob
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "python"))
import lang_model
import corpus_sweep as cs

FAIL = []


def check(cond, what):
    print(f"  {'ok  ' if cond else 'FAIL'}  {what}")
    if not cond:
        FAIL.append(what)


def solved(here):
    """(name, literal engine decrypt) for every message with a stored key."""
    out = []
    for f in sorted(glob.glob(os.path.join(here, "..", "data", "messages", "*.json"))):
        d = json.load(open(f))
        for m in (d if isinstance(d, list) else [d]):
            s = m.get("solution") or {}
            if not s.get("plaintext") or not s.get("wiring"):
                continue
            body, _ = cs.parse_body(m)
            if not body:
                continue
            order = tuple(s["rotor_order"].split("-"))
            w = [cs.c2n[c] for c in s["windows_ULMR"]]
            r = tuple(cs.c2n[c] for c in s["ringstellung_ULMR"])
            out.append((os.path.basename(f)[:-5],
                        cs.decode_all(s["wiring"], order, (w[1], w[2], w[3]),
                                      w[0], r, [cs.c2n[c] for c in body])))
    return out


def main():
    quick = "--quick" in sys.argv
    nshuf = 200 if quick else 1000
    random.seed(19361207)
    here = os.path.dirname(os.path.abspath(__file__))

    print("The corpus loads")
    lm = lang_model.LangModel()
    check(lm.n > 100000, f"language model built: {lm.n:,} letters")
    check(len(lm.sources) >= 1, f"from {len(lm.sources)} file(s): {lm.sources}")
    check(all(c in lang_model.A for c in "ABC"), "alphabet sane")
    check(lang_model.normalise("Ñoño, ¡qué día!") == "NONOQUEDIA",
          "normalise strips accents, folds N-tilde, drops spaces")

    print("\nThe Sarmiento W rule counts what it says it counts")
    check(lang_model.LangModel.w_rule("ABCW") == 1.0,
          "a W run ending at position 4 obeys the rule")
    check(lang_model.LangModel.w_rule("ABWD") == 0.0,
          "one ending at position 3 does not")
    check(lang_model.LangModel.w_rule("ABCDEFGH") == 0.0,
          "no W runs at all returns 0.0, not an error")
    check(lang_model.LangModel.w_rule("ABWWABCW") == 1.0,
          "two runs, both on a boundary")

    print("\nSpanish scores above noise")
    good = "ENEMIGOCARECEMUNICIONESAPRESAMOSLE"
    junk = "QXZJKVBHFGWYXQZJKVBHFGWYXQZJKVBHFG"
    check(lm.score(good) > lm.score(junk), "real Spanish beats consonant soup")
    check(lm.window_trigram(good) > lm.window_trigram(junk),
          "and the trigram term is what does it")

    print("\nDHZB: the window the criterion finds is the one the paper names")
    # Pinned on purpose: the technical paper names the winning window (in "What
    # the criterion costs: DHZB"), so if the corpus or the weighting changes and
    # another window wins, this is where it shows.
    dz = [p for n, p in solved(here) if n == "DHZB"]
    if dz:
        p = dz[0]
        best = max(range(len(p) - 7),
                   key=lambda i: lm.window_trigram(p[i:i + 8], 8))
        check(p[best:best + 8] == "OPORUNQU",
              f"best 8-letter window is OPORUNQU (got {p[best:best+8]})")
        check(p.find("OPORUNQU") >= 0 and "OCHOPORUNQUI" in p,
              "and it spans OCHO / POR / UN / QUINCE -- three word boundaries")
    else:
        check(False, "DHZB not found in data/messages")

    print(f"\nPOSITIVE CONTROL: true plaintext vs {nshuf} shuffles of itself")
    print("  (shuffling keeps the letter frequencies and destroys the words,")
    print("   so this asks whether the score sees Spanish or just a histogram)")
    for name, plain in solved(here):
        s = lm.score(plain)
        base = list(plain)
        beat = 0
        for _ in range(nshuf):
            random.shuffle(base)
            if s > lm.score("".join(base)):
                beat += 1
        pct = 100.0 * beat / nshuf
        check(pct >= 99.0, f"{name}: above {pct:.1f}% of its own shuffles")

    print(f"\n{len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
