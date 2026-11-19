#!/usr/bin/env python3
"""test_sarmiento.py -- the manual's rules, asserted rather than printed.

Each check prints its line and fails the run if it does not hold. Two of them
check the code against the SOURCE rather than against itself:

  * the syllabic and digit rules are verified on the manual's OWN worked
    example -- initial HPNE giving third group HIPAN and last group EKNEP. If
    the reading of the rule were wrong, this fails.
  * rule 1 (the indicator in clear at group 3) is checked against every message
    file that has a header, and it must hold for all of them. It does: 4 of 4
    (DHZB, LUIS, MVNR, XMOT).
  * rule 3 (the last group is the indicator reversed) is checked against every
    read message that carries one: the indicator it gives, through the header
    when there is one, must be the windows of the key that reads the message.
    It holds for 5 of 5; MKCX, which has no header, is read from it alone.

    Run:  python3 tests/test_sarmiento.py
"""
import json
import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "python"))
import sarmiento as S

FAIL = []


def check(cond, what):
    print(f"  {'ok  ' if cond else 'FAIL'}  {what}")
    if not cond:
        FAIL.append(what)


def main():
    here = os.path.dirname(os.path.abspath(__file__))

    print("Digit code (rule 7): NR...XK, keyed on the top row QWERTZUIOP")
    check(S.digits_to_letters(22) == "WW", "22 -> WW")
    check(S.letters_to_digits("WW") == "22", "WW -> 22")
    check(S.digits_to_letters(0) == "P", "0 -> P (zero is the tenth key)")
    check(S.letters_to_digits(S.digits_to_letters(1936)) == "1936",
          "round trip on 1936")
    check(S.expand_digit_runs("NRWWXK") == "22", "NRWWXK expands to 22")
    check(S.expand_digit_runs("ABCNRWWXKDEF") == "ABC22DEF",
          "expansion leaves the surrounding text alone")

    print("\nSyllabic form (rule 5), on the manual's own example: HPNE")
    # "Si la combinacion de partida es HPNE, el tercer grupo quinario podra ser
    #  HIPAN, y el ultimo del despacho EKNEP."
    check(S.strip_syllabic(["HIPAN"]) == ["HPN"],
          "HIPAN -> HPN (letters 2 and 4 struck)")
    check(S.strip_syllabic(["EKNEP"]) == ["ENP"], "EKNEP -> ENP")
    check(S.strip_syllabic(["HIPAN"])[0] == "HPNE"[:3],
          "and HPN is the first three letters of the quaternary")
    check(S.strip_syllabic(["EKNEP"])[0] == "HPNE"[1:][::-1],
          "and ENP is its last three, reversed")
    check(S.strip_syllabic(["ABCD"]) == ["ABCD"],
          "a four-letter group is left alone")

    print("\nIndicator position (rules 1 and 2)")
    check(S.indicator_position(["ABCD", "EFGH", "IJKL"]) == 2,
          "third group by default")
    check(S.indicator_position(["COLOC", "ABCD", "EFGH", "IJKL"]) == 3,
          "fourth group when COLOC leads")

    print("\nArrangement and wheel order are ORDERINGS, not restrictions")
    arr = S.arrangements()
    check(len(arr) == 24, "24 arrangements, none dropped")
    check(len(set(arr)) == 24, "all distinct")
    check(arr[0] == (0, 1, 2), "the documented one comes first")
    orders = S.wheel_orders("1936-12-07")
    check(len(orders) == 6 and len(set(orders)) == 6, "6 wheel orders, all kept")
    check(orders[0] == ("II", "I", "III"), "December 1936's order comes first")
    check(len(S.wheel_orders(None)) == 6, "6 orders with no date either")
    check(S.windows_from_indicator("MKCX") == "MKCX",
          "the transmitted group IS the ULMR windows (rule 4)")
    check(S.kernel_indicator("XMOT") == "MOTX",
          "the kernels get it as (L,M,R,U)")

    print("\nRule 1 against the corpus: header group 3 IS the Grundstellung")
    n = 0
    for f in sorted(glob.glob(os.path.join(here, "..", "data", "messages", "*.json"))):
        d = json.load(open(f))
        for m in (d if isinstance(d, list) else [d]):
            h = [x.upper() for x in (m.get("header") or [])
                 if isinstance(x, str) and x.isalpha()]
            g = (m.get("grundstellung") or "").upper()
            i = S.indicator_position(h)
            if len(h) <= i or len(h[i]) != 4 or len(g) != 4:
                continue
            n += 1
            check(h[i] == g,
                  f"{os.path.basename(f)[:-5]}: header[{i}]={h[i]} == {g}")
    check(n >= 4, f"and it was testable on at least four messages (was {n})")

    print("\nRule 3 against the read messages: the last group, reversed, gives the windows")
    n = 0
    for f in sorted(glob.glob(os.path.join(here, "..", "data", "messages", "*.json"))):
        d = json.load(open(f))
        for m in (d if isinstance(d, list) else [d]):
            sol = m.get("solution") or {}
            w = (sol.get("windows_ULMR") or "").upper()
            last = (m.get("garble_check") or "").upper()
            if not (m.get("status") or {}).get("solved") or len(w) != 4 or len(last) != 4:
                continue
            h = [x.upper() for x in (m.get("header") or [])
                 if isinstance(x, str) and x.isalpha()]
            r = S.read_indicator(header=h or None, last_group=last)
            n += 1
            check(r["value"] == w and r["agrees"],
                  f"{os.path.basename(f)[:-5]}: {last} reversed is {r['check']}, "
                  f"windows {w} ({r['source']})")
    check(n >= 5, f"and it was testable on at least five messages (was {n})")

    print(f"\n{len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
