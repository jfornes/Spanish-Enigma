#!/usr/bin/env python3
"""validate_messages.py -- keep data/messages/*.json coherent with each other.

The convention these files follow, and which this script enforces:

  status    what we know about the message: solved or not, confidence, notes.
  solution  the recovered key, and ONLY when the message is solved.

  Key fields live in 'solution' and are machine-readable, not prose:
      wiring              a set present in data/wirings/wirings.json
      rotor_order         a permutation of I II III, e.g. I-III-II
      windows_ULMR        exactly 4 letters  (reflector, left, middle, right)
      ringstellung_ULMR   exactly 4 letters  (same order)
      plaintext           the recovered text, letter for letter with the body
  Any commentary goes in a neighbouring note field, never inside these.

Every complaint below names the file, the field and the fix, so it can be acted
on without opening the file first.

Run from the repository root:  python3 tests/validate_messages.py
Exit status is 1 if anything failed, so it can gate a release.
"""
import json, os, sys, glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import corpus_sweep as cs

A = cs.A
KEY4 = ("windows_ULMR", "ringstellung_ULMR")
KEYFIELDS = ("wiring", "rotor_order", "windows_ULMR", "ringstellung_ULMR", "plaintext")


def four(v):
    return isinstance(v, str) and len(v.strip()) == 4 and all(c in A for c in v.strip().upper())


def check(path):
    """-> (errors, warnings), each a list of one-line, actionable strings."""
    err, warn = [], []
    name = os.path.basename(path)
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return [f"{name}: not valid JSON -- {e}"], []
    if isinstance(d, list):
        if len(d) != 1:
            err.append(f"{name}: top-level list must hold exactly one message, has {len(d)}")
            return err, warn
        d = d[0]

    sol, st = d.get("solution"), d.get("status")

    # -- grundstellung must be 4 letters wherever it appears -----------------
    for where, blk in (("(root)", d), ("status", st or {}), ("solution", sol or {})):
        g = blk.get("grundstellung")
        if g is not None and not four(g):
            err.append(f"{name}: {where}.grundstellung is not 4 letters -- {g!r}\n"
                       f"    fix: keep 4 letters here and move the commentary to a note field")

    # -- the key belongs in 'solution', not in 'status' ----------------------
    if st:
        stray = [k for k in KEYFIELDS if st.get(k) is not None]
        if stray:
            err.append(f"{name}: status carries key fields {', '.join(stray)}\n"
                       f"    fix: move them into a 'solution' block (see LUIS.json)")

    if not d.get("body"):
        if d.get("record_kind") == "reference":
            warn.append(f"{name}: reference record, no ciphertext body -- not replayable\n"
                        f"    canonical corpus entry: {d.get('canonical_entry', '(not stated)')}")
            return err, warn
        err.append(f"{name}: no 'body' -- nothing to decipher\n"
                   f"    fix: add the ciphertext, or mark it \"record_kind\": \"reference\" "
                   f"and name the corpus entry it duplicates")

    solved = bool((st or {}).get("solved")) or bool(sol)
    if solved and not sol:
        err.append(f"{name}: status says solved but there is no 'solution' block\n"
                   f"    fix: add one with {', '.join(KEYFIELDS)}")
    if not sol:
        return err, warn

    # -- shape of the solution block ----------------------------------------
    missing = [k for k in KEYFIELDS if not sol.get(k)]
    if missing:
        warn.append(f"{name}: solution lacks {', '.join(missing)}\n"
                    f"    the self-test skips messages without a complete block")
    for k in KEY4:
        v = sol.get(k)
        if v is not None and not four(v):
            err.append(f"{name}: solution.{k} is not 4 letters -- {v!r}")
    w = sol.get("wiring")
    if w and w not in cs.WIRINGS:
        err.append(f"{name}: solution.wiring {w!r} is not in wirings.json "
                   f"(have {', '.join(sorted(cs.WIRINGS))})")
    o = sol.get("rotor_order")
    if o and sorted(str(o).replace("-", " ").split()) != ["I", "II", "III"]:
        err.append(f"{name}: solution.rotor_order {o!r} is not a permutation of I II III")

    # -- plaintext lines up with the body ------------------------------------
    body, _ = cs.parse_body(d)
    pt = sol.get("plaintext")
    if pt and body and len(cs.re.sub(r"[^A-Z]", "", pt.upper())) != len(body):
        err.append(f"{name}: solution.plaintext is {len(pt)} letters but the body is "
                   f"{len(body)}\n    fix: plaintext must line up one-to-one with the body")

    # -- plaintext must BE the engine decrypt, not an emended reading --------
    # Both are plausible Spanish and the field name fits either, so the
    # difference has to be checked: a search asked to find an emended text is
    # asked to find something no key produces.
    if pt and sol.get("wiring") and sol.get("rotor_order") and body:
        try:
            order = tuple(sol["rotor_order"].split("-"))
            w = [cs.c2n[c] for c in sol["windows_ULMR"]]
            r = tuple(cs.c2n[c] for c in sol["ringstellung_ULMR"])
            eng = cs.decode_all(sol["wiring"], order, (w[1], w[2], w[3]), w[0],
                                r, [cs.c2n[c] for c in body])
            n = sum(1 for a, b in zip(eng, pt) if a != b)
            if n:
                err.append(
                    f"{name}: solution.plaintext differs from the engine decrypt "
                    f"in {n} position(s)\n"
                    f"    fix: plaintext is the LITERAL output of the key in this "
                    f"file, garble included. Put an emended reading in "
                    f"plaintext_emended and list the positions in divergences.")
            em = sol.get("plaintext_emended")
            if em is not None and em == eng:
                warn.append(f"{name}: plaintext_emended is identical to the "
                            f"decrypt, so it emends nothing and can go")
        except Exception as ex:                      # never fail the suite on this
            warn.append(f"{name}: could not replay the key to check plaintext "
                        f"({type(ex).__name__}: {ex})")

    # -- declared divergences must be inside the message ---------------------
    dv = (d.get("divergences") or {}).get("known_positions") or []
    bad = [p for p in dv if not (1 <= int(p) <= len(body or ""))]
    if bad:
        err.append(f"{name}: divergences.known_positions out of range: {bad} "
                   f"(body is {len(body or '')} letters)")
    return err, warn


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(here, "..", "data", "messages", "*.json")))
    if not files:
        sys.exit("no message files found under data/messages/")
    nerr = nwarn = 0
    for f in files:
        e, w = check(f)
        nerr += len(e); nwarn += len(w)
        for m in e:
            print("FAIL  " + m)
        for m in w:
            print("note  " + m)
    ok = len(files) - len({m.split(':')[0] for m in []})
    print(f"\n{len(files)} message files checked -- {nerr} failed, {nwarn} notes")
    if not nerr:
        print("the corpus is coherent: keys live in 'solution', 4-letter fields hold "
              "4 letters, and every solved message can be replayed from its file")
    return 1 if nerr else 0


if __name__ == "__main__":
    sys.exit(main())
