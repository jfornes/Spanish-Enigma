#!/usr/bin/env python3
"""sarmiento.py -- the operating rules of the Spanish manual, in one place.

Source: "INSTRUCCIONES GENERALES PARA EL MANEJO DE LAS MAQUINAS" and, for
everything about indicators, "ADVERTENCIAS PARTICULARES PARA EL USO DE LAS
CLAVES MECANICAS DE LAS SERIES A y K POR LAS COMISIONES DEL EXTRANJERO PARA SU
INTELIGENCIA CON LA SECRETARIA GENERAL DE ESTADO", Salamanca, November 1936,
signed by Comandante Antonio Sarmiento.

The rules of the manual that bear on a search are gathered here. Each is
quoted, with code attached, and says what it saves.

--------------------------------------------------------------------------
THE RULES, AND WHAT EACH ONE SAVES
--------------------------------------------------------------------------

1. THE INDICATOR IS IN CLEAR, IN THIRD PLACE.
   "teniendo cuidado de poner en tercer lugar el grupo cuaternario inicial sin
   cifrar, que se repetira tambien pero con las letras invertidas ocupando el
   ultimo lugar."
   Verified on every message in the corpus that has a header: 4 of 4. The last
   group, reversed, gives the windows of all five read messages that carry one.
   SAVES: the four letters are read, not searched -- 26^4 = 456,976x.

2. IF THE FIRST GROUP IS "COLOC", THE INDICATOR MOVES TO FOURTH PLACE.
   "En los telegramas que comiencen por la palabra COLOC el grupo que se emplea
   para dar a conocer las tres primeras cifras de la clave ocupara en este caso
   el cuarto lugar." COLOC is a cover for foreign telegraph clerks who demand a
   codebook name, and "en la interpretacion no ha de intervenir para nada".
   No message in this corpus uses it. Implemented so that one does not have to
   be diagnosed by hand the day it turns up.

3. THE LAST GROUP IS THE INDICATOR REVERSED.
   A free garble check on the whole transmission, and the only way to recover
   the indicator when the header is missing (MKCX).

4. THE QUATERNARY IS (UKW, LEFT, MIDDLE, RIGHT) -- THE WINDOWS AS SET.
   The manual's worked example gives its windows as MNAS for drums 0,1,2,3
   from left to right, reflector first. Read the traffic the same way and the
   Ringstellung stops moving: LUIS (6 Dec 1936), DHZB (7 Dec) and MVNR (9 Dec)
   all need UFSF, on all four drums, and XMOT (11 Dec) needs AMIF, the right
   drum still on F. By chance that is about 26^-8. This matches rule 9: the
   internal settings are fixed for the period, the quaternary per dispatch.
   SAVES: 24 arrangements -> 1, and with a known period Ringstellung the whole
   key is read off the header.
   HOW IT IS USED: as an ORDERING, never as a restriction. arrangements()
   returns all 24 with the documented one first, so a search is 24x faster on
   the usual case and still exhaustive. Guessing right is worth a lot;
   assuming right can cost a message.

5. FIVE-LETTER SYLLABIC GROUPS: STRIKE LETTERS 2 AND 4.
   "entre la primera y segunda letras y entre esta y la tercera se
   intercalaran vocales o consonantes, al arbitrio del operador... la segunda y
   cuarta letras no hay que tenerlas en cuenta para descifrar y pueden tacharse
   preliminarmente."
   In this form the indicator is carried by the first THREE letters, and the
   fourth arrives via the last group, which repeats "las tres ultimas letras de
   la CUATERNARIA INICIAL PERO PUESTAS EN ORDEN INVERSO" -- so letters 2 and 3
   appear twice, giving a consistency check for free.
   Manual's example: initial HPNE -> third group HIPAN, last group EKNEP.
   NO MESSAGE IN THIS CORPUS IS IN THIS FORM; all are quaternary. Implemented
   anyway, because feeding syllabic padding to the engine as ciphertext would
   fail in a way that looks like a hard message rather than a parsing bug.

6. W PADS THE LAST GROUP OF AN INDEPENDENT PARAGRAPH TO FOUR LETTERS.
   "En las terminaciones de parrafos independientes se completaran los grupos
   de cuatro letras bajando la tecla W el numero de veces que sea preciso."
   Already the strongest term in lang_model's triage score.

7. DIGITS ARE BRACKETED BY NR AND XK, KEYED ON THE TOP ROW.
   "USANDO LAS COMBINACIONES NR Y XK CIFRADAS AL PRINCIPIO Y AL FINAL...  DE
   AQUELLAS LETRAS QUE HAYAN DE INTERPRETARSE POR LOS GUARISMOS DE 0 A 9
   SITUADOS EN SU MISMA TECLA O VENTANILLA." QWERTZUIO = 1-9, P = 0.

8. THE TEXT ENDS WITH THE NUMBER OF GROUPS.
   "terminar todos los textos antes de la firma, con un numero que represente
   el de agrupaciones de letras que contenga el telegrama." A length check on a
   candidate reading, and it is spelled with rule 7.

--------------------------------------------------------------------------
WHAT THE MANUAL DOES NOT SAY, AND IT MATTERS
--------------------------------------------------------------------------
A footnote to the indicator section reads:

    "Vease, aparte, convenio definitivo, en cada caso sobre el modo de elegir y
     dar a conocer la COMBINACION EXTERIOR que sirve para cifrar y descifrar
     cada despacho."

So the four transmitted letters are governed by a SEPARATE agreement which we
do not have, and which was expected to vary. Nothing here establishes that the
transmitted group is literally the window setting. With the notch on the ring,
as on the surviving machines, the group gives the windows displaced by a
constant fixed for the period (data/wirings/wirings.json, block 'stepping').
"""
import re

A = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
COLOC = "COLOC"
DIGIT_OPEN, DIGIT_CLOSE = "NR", "XK"
DIGIT_ROW = "QWERTZUIOP"          # 1..9 then 0, by keyboard position


def digits_to_letters(n):
    """22 -> 'WW'. The top row is 1-9 then P for zero."""
    return "".join(DIGIT_ROW[(int(d) - 1) % 10] for d in str(n))


def letters_to_digits(s):
    """'WW' -> '22'. Non-row letters come back as '?'."""
    return "".join(str((DIGIT_ROW.index(c) + 1) % 10) if c in DIGIT_ROW else "?"
                   for c in s)


def expand_digit_runs(plain):
    """Turn NR...XK runs into digits: rule 7. Returns the readable text."""
    def sub(m):
        return letters_to_digits(m.group(1))
    return re.sub(DIGIT_OPEN + r"(.*?)" + DIGIT_CLOSE, sub, plain)


def strip_syllabic(groups):
    """Rule 5: in five-letter syllabic groups, letters 2 and 4 are padding.

    Applied only to groups that are actually five long, because a transmission
    can mix them -- a four-letter group is already bare."""
    out = []
    for g in groups:
        g = g.upper()
        out.append(g[0] + g[2] + g[4] if len(g) == 5 else g)
    return out


def indicator_position(groups):
    """Rules 1 and 2: which group carries the indicator. Returns an index."""
    return 3 if groups and groups[0].upper() == COLOC else 2


def read_indicator(header=None, groups=None, last_group=None):
    """Recover the four-letter indicator, and say how, and whether it checks.

    Returns a dict: value, source, check (the reversal, or None), agrees.
    Never raises and never guesses silently -- an unresolved case comes back
    with value None so the caller has to decide, rather than being handed a
    plausible wrong answer."""
    out = {"value": None, "source": None, "check": None, "agrees": None}
    seq = [g.upper() for g in (header or groups or []) if g.isalpha()]
    i = indicator_position(seq)
    if len(seq) > i and len(seq[i]) in (3, 4):
        out["value"] = seq[i] if len(seq[i]) == 4 else None
        out["source"] = f"group {i + 1} in clear" + (
            " (COLOC in first place)" if i == 3 else "")
        if len(seq[i]) == 3:
            out["source"] += "; syllabic form, fourth letter from the last group"
    if last_group and len(last_group) == 4:
        rev = last_group.upper()[::-1]
        out["check"] = rev
        if out["value"] is None:                    # rule 3 as the fallback
            out["value"] = rev
            out["source"] = "last group reversed (no header)"
        out["agrees"] = (rev == out["value"])
    return out


# The transmitted group is already in ULMR order (rule 4).
DOCUMENTED_ARRANGEMENT = (0, 1, 2, 3)


def kernel_indicator(ind):
    """The search kernels (rods.c and the Python paths that mirror it) index the
    indicator as (L, M, R, U): arrangement (0,1,2) sets the left, middle and right
    windows from letters 0,1,2 and leaves letter 3 to the reflector. That layout is
    kept so that a compiled librods (.so / .dylib) does not have to be rebuilt.
    Hand the kernels this rotation of the transmitted group, and the documented
    arrangement (0,1,2) is rule 4: windows = group 3 read (U, L, M, R)."""
    ind = ind.upper()
    return ind[1:] + ind[0] if len(ind) == 4 else ind


def windows_from_indicator(ind, arrangement=DOCUMENTED_ARRANGEMENT):
    """Rule 4. ind is the transmitted four letters; returns ULMR."""
    return "".join(ind[i] for i in arrangement)


def arrangements():
    """All 24, DOCUMENTED FIRST. An ordering, not a restriction -- see rule 4.

    corpus_sweep.build_tasks enumerates arrangements as 3-permutations of the
    four indicator letters for the rotor windows, the leftover going to the UKW.
    Returning the documented one first makes the usual case come out 24x sooner
    without narrowing the search by a single configuration."""
    import itertools
    first = (0, 1, 2)          # on kernel_indicator(): L, M, R, and UKW = index 3 (rule 4)
    rest = [p for p in itertools.permutations(range(4), 3) if p != first]
    return [first] + rest


# --------------------------------------------------------------------------- #
# 9. PERIOD KEY AND MESSAGE KEY
#
# "una vez establecidas de antemano las combinaciones internas correspondientes
#  a las operaciones 1a y 2a que detallan las INSTRUCCIONES GENERALES... se
#  elegira para trabajar en cada despacho (TERCERA OPERACION) una combinacion
#  cuaternaria cualquiera"
#
# The manual divides the key: the internal settings -- rotor order and
# Ringstellung -- are agreed in advance and hold for the period, and only the
# quaternary is chosen per dispatch.
#
# Observed, December 1936: LUIS (6th), DHZB (7th), MVNR (9th) and XMOT (11th)
# all read on rotor order II-I-III; the first three on Ringstellung UFSF, XMOT
# on AMIF. Only the rotor order is used as a hint below.
PERIOD_ORDER = {"1936-12": ("II", "I", "III")}


def wheel_orders(date=None):
    """Six wheel orders, the period's first if we know one. Ordering, not
    restriction -- same discipline as arrangements()."""
    import itertools
    all6 = list(itertools.permutations(["I", "II", "III"]))
    hint = PERIOD_ORDER.get((date or "")[:7])
    return [hint] + [o for o in all6 if o != hint] if hint else all6


def check_w_rule(plain):
    """Rule 6: fraction of W runs ending on a four-letter boundary."""
    runs = list(re.finditer(r"W+", plain))
    return sum(1 for m in runs if m.end() % 4 == 0) / len(runs) if runs else None


if __name__ == "__main__":
    import json, glob, os, sys
    here = os.path.dirname(os.path.abspath(__file__))
    print("Sarmiento's rules against the corpus.\n")
    print("A header group 3 is an indicator. A BODY group 3 is not, unless the")
    print("body happens to include the header groups -- so only real headers are")
    print("used here, and the reversal is reported beside it, not merged into it.\n")
    print(f"{'msg':14s} {'hdr g3':7s} {'last':6s} {'reversed':8s} {'recorded':8s} verdict")
    for f in sorted(glob.glob(os.path.join(here, "..", "data", "messages", "*.json"))):
        d = json.load(open(f))
        for m in (d if isinstance(d, list) else [d]):
            name = os.path.basename(f)[:-5]
            h = [x.upper() for x in (m.get("header") or []) if isinstance(x, str) and x.isalpha()]
            raw = re.sub(r"<PLAIN:[^>]*>", "",
                         str(m.get("body") or m.get("body_cipher_only") or ""))
            g = [x.upper() for x in re.split(r"\s+", raw.strip()) if x.isalpha()]
            rec = (m.get("grundstellung") or "").upper()
            i = indicator_position(h)
            g3 = h[i] if len(h) > i and len(h[i]) == 4 else ""
            last = g[-1] if g and len(g[-1]) == 4 else ""
            rev = last[::-1] if last else ""
            v = []
            if g3: v.append("g3==rec" if g3 == rec else f"g3 says {g3}")
            if rev: v.append("rev==rec" if rev == rec else f"rev says {rev}")
            if not h: v.append("no header")
            print(f"{name:14s} {g3 or '-':7s} {last or '-':6s} {rev or '-':8s} "
                  f"{rec or '-':8s} {'; '.join(v)}")
    print("\nDigit code:  22 ->", digits_to_letters(22),
          "  'WW' ->", letters_to_digits("WW"),
          "  NRWWXK ->", expand_digit_runs("NRWWXK"))
    print("Syllabic:    HIPAN EKNEP ->", strip_syllabic(["HIPAN", "EKNEP"]),
          "(manual's example: initial HPNE)")
