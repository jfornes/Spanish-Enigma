#!/usr/bin/env python3
"""
hw43_rod_square.py -- the rod square of the Knox section, rebuilt and checked.

Source: TNA HW 43/7, history of the Intelligence Services Knox section,
chapter I, pp. 16-19. The text gives the rule that generates the square
("tA will become rO"):

    square[i][p+1] = shift_D( square[i+1][p], -1 )

where D = QWERTZUIOASDFGHJKPYXCVBNML is the "diagonal": the order in which the
rods are named and the alphabet along which a rod shifts. The whole 26 x 26
square therefore follows from its FIRST COLUMN alone. D is the keyboard order
of the commercial entry wheel, the same string as 'etw' in wirings.json.

Checked against data the document prints separately:
  1. the generated column 2 equals the row of 'Pins' on p. 16;
  2. columns 1-3 and the whole rods q, w and h agree with the printed square;
  3. every upright carries the 26 letters once;
  4. every rod has the same number of repeats (the text says 2);
  5. the worked message of p. 18: twenty positions with their pairs of rods.
     Fifteen agree exactly; the other five differ from the computed pair by a
     single letter, a typing slip;
  6. the beetles the text gives as examples (NE at 2,3; NX at 12,13 in clear;
     EQ and SM in cipher) fall on one rod.

Run from the repository root:  python3 tests/hw43_rod_square.py
"""
import sys
from collections import Counter

D = "QWERTZUIOASDFGHJKPYXCVBNML"
iD = {c: i for i, c in enumerate(D)}
shD = lambda c, k: D[(iD[c] + k) % 26]
ROWS = list(D)

COL1 = "Z M T Y A B P J I F N V S C U R E D W L G K Q X H O".split()
PINS = "N R P O V K H U D B C A X Z E W S Q M F J L Y G I T".split()
GIVEN = {"Q": "Z N E J Z P D O L R G S M I Y H F C A U X V T B K A",
         "W": "M R K U Y F A Q T H D L O X J G V S I C B Z N P S U",
         "H": "U E Q O N C I A Y S T N X D K R X Z L B G P W M F V",
         "E": "T P I", "R": "Y O C", "T": "A V J", "Z": "B K G", "U": "P H Z", "I": "J U S",
         "O": "I D V", "A": "F B X", "S": "N C O", "D": "V A Y", "F": "S X T", "G": "C Z W",
         "J": "R W A", "K": "E S L", "P": "D Q N", "Y": "W M D", "X": "L F H", "C": "G J M",
         "V": "K L P", "B": "Q Y F", "N": "X G U", "M": "H I R", "L": "O T B"}
PLAIN = "X N E U N V I E R X A N X S A B I N E X".split()
CIPHER = "Q E Q S Z F D D E E M S M L I M W P M W".split()
PRINTED_PAIRS = "bn qh qh pw gh pu gh bn at is gj qh qh bn bn ez ko io vr kc".split()
SLIPS = {5, 6, 7, 10, 17}          # positions where the printed pair has one letter mistyped

FAIL = []


def check(cond, what):
    print(f"  {'ok  ' if cond else 'FAIL'}  {what}")
    if not cond:
        FAIL.append(what)


def build(col1):
    sq = [[None] * 26 for _ in range(26)]
    for i in range(26):
        sq[i][0] = col1[i]
    for p in range(1, 26):
        for i in range(26):
            sq[i][p] = shD(sq[(i + 1) % 26][p - 1], -1)
    return sq


def main():
    sq = build(COL1)
    check([sq[i][1] for i in range(26)] == PINS, "column 2 generated from column 1 == the printed 'Pins'")
    bad = [(r, p + 1) for r, v in GIVEN.items() for p, ch in enumerate(v.split())
           if sq[ROWS.index(r)][p] != ch]
    check(not bad, f"every printed entry agrees with the rule ({sum(len(v.split()) for v in GIVEN.values())} entries)")
    check(all(len({sq[i][p] for i in range(26)}) == 26 for p in range(26)),
          "every upright carries the 26 letters once")
    reps = {sum(1 for c in set(r) if r.count(c) > 1)
            for r in ([sq[i][p] for p in range(26)] for i in range(26))}
    check(reps == {2}, "every rod has two repeats, as the text says")

    rod_of = lambda letter, pos: ROWS[[sq[i][pos - 1] for i in range(26)].index(letter)]
    calc = ["".join(sorted((rod_of(PLAIN[p - 1], p), rod_of(CIPHER[p - 1], p)))).lower()
            for p in range(1, 21)]
    exact = {p for p in range(1, 21) if calc[p - 1] == "".join(sorted(PRINTED_PAIRS[p - 1]))}
    check(len(exact) == 15, f"p. 18: {len(exact)} of the 20 printed rod pairs agree exactly")
    one_letter = all(len(set(calc[p - 1]) & set(PRINTED_PAIRS[p - 1])) == 1 for p in SLIPS)
    check(set(range(1, 21)) - exact == SLIPS and one_letter,
          "the other five (positions 5, 6, 7, 10, 17) differ by one letter")
    cnt = Counter(calc)
    check(cnt["hq"] == 6 and cnt["bn"] == 4, "qh six times and bn four times, as the text says")
    for l1, p1, l2, p2, lab in (("N", 2, "E", 3, "NE in clear"), ("N", 12, "X", 13, "NX in clear"),
                                ("E", 2, "Q", 3, "EQ in cipher"), ("S", 12, "M", 13, "SM in cipher")):
        check(rod_of(l1, p1) == rod_of(l2, p2), f"beetle {lab} falls on one rod")
    print(f"\n{len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
