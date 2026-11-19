#!/usr/bin/env python3
"""lrs10_control.py -- the one real message on wiring D steps as the machines do.

LRS10 is a pencilled draft, cipher and plain, of a Spanish naval-attaché message
from J. R. Soler's archive, read by Michael Hörenberg ("The Spanish Enigma
message LRS10", enigma.hoerenberg.com). Key: wiring D, rotor order II-I-III,
windows WYAO, Ringstellung AAAH (U, L, M, R). Rotor III carries the middle rotor
on three times, so the message fixes where it turns over: at window N with ring
H. That is the window-letter rule wirings.json gives D (its core offsets are
null), and not the offsets measured on F, which garble the text after the first
turnover.

Checked through corpus_sweep.decode_all (the search engine) and through
rods_frontend.py_encipher (the oracle of the C kernels): 90 of 90 letters in
both, and not with F's offsets forced on.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
import corpus_sweep as cs
import rods_frontend as rf
c2n = cs.c2n; A = cs.A

CT = "OHACIPLYXTSIHJSBJCZXWYXPJJMUIWYFGVHTMALUTAEAVXHRXVQWDRVJKIMCYFRODNBXDISWSDIYXFJWVKHQHQMKZT"
PT = "RADIOSDEBENREGRESARAZZESPANAZZTANPRONTOLESSEAPOSIBLEXCONTESTOSURADIOKKQQTKKDEDIEZACTUALXXX"
ORDER = ('II', 'I', 'III')
U, L, M, R = (c2n[x] for x in "WYAO")
RU, RL, RM, RR = (c2n[x] for x in "AAAH")

def score(s): return sum(a == b for a, b in zip(s, PT))

def main():
    ct = [c2n[x] for x in CT]
    a = cs.decode_all('D', ORDER, (L, M, R), U, (RU, RL, RM, RR), ct)
    b = rf.py_encipher('D', ORDER, (L, M, R), (RL, RM, RR), (U - RU) % 26, CT)
    cs.SET_OF['_D_with_F_offsets'] = 'FFF'; cs.WIRINGS['_D_with_F_offsets'] = cs.WIRINGS['D']
    c = cs.decode_all('_D_with_F_offsets', ORDER, (L, M, R), U, (RU, RL, RM, RR), ct)
    print(f"corpus_sweep, D's own rule : {score(a)}/90")
    print(f"rods_frontend, D's own rule: {score(b)}/90")
    print(f"D with F's offsets forced  : {score(c)}/90  (must fail)")
    ok = score(a) == 90 and score(b) == 90 and score(c) < 90
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
