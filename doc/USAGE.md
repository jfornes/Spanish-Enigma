# Spanish-Enigma — tool usage guide

Key and wiring recovery for the commercial Enigma K traffic (no plugboard, QWERTZ
ETW, settable reflector) of Caja 745. The search core is in C (`src/rods.c` →
`librods.so`), driven by Python front-ends. Wirings are passed as parameters; the
catalogue lives in `data/wirings/wirings.json`.

## Getting started

```bash
cd src && make && cd ..          # build librods.so
# optional, if the library is not in src/ or build/:
export SPANISH_ENIGMA_LIB=/path/to/librods.so
```

Every front-end starts with a **positive control** on wiring F: it must reproduce a
known decryption before any result is trusted. See `tests/run_examples.sh` for
runnable examples.

## Tools

### `corpus_sweep.py` — IoC triage and crib-drag
Without `--crib`: IoC-blind mode (sweeps wiring × arrangement × order × the 26⁴ ring
settings and scores each decryption by Index of Coincidence and Spanish fragments).
With `--crib`: drags a probable word and finds the exact keys that reproduce it.

```bash
# crib-drag (pin the key) -- use a crib from a clean stretch:
python3 python/corpus_sweep.py data/messages/XMOT.json \
        --crib MOVIMIENTOBARCOS --wirings F --all --procs 8
# IoC-blind (no crib):
python3 python/corpus_sweep.py data/messages/LUIS.json --wirings D F --procs 8
```

### `mixed_rotors.py` — mixed rotors, IoC-blind and consensus
Tries rotors drawn from different wiring sets (`--mix`). With `--crib` it crib-drags
(a single word or a file of words); without `--crib`, IoC-blind. With `--consensus` it
merges the top decryptions into a consensus reading. Ranks and flags by count of real
**Spanish words** (not by IoC, which can be inflated by degeneracy).

```bash
python3 python/mixed_rotors.py data/messages/XMOT.json --mix --arr all --consensus --procs 12
python3 python/mixed_rotors.py data/messages/DHZB.json \
        --crib data/cribs/cribs_navales.txt --mix --arr all --procs 12
```

### `buttonup.py` — rotor wiring recovery
Buttoning-up of the fast rotor and recovery of the interior rotors. Positive controls
on F:

```bash
python3 python/buttonup.py --selftest-c        # right rotor
python3 python/buttonup.py --selftest-middle    # middle rotor
python3 python/buttonup.py --selftest-left      # left rotor
```

### `message_eval.py` — archive triage
Per-message card (structure, Grundstellung, left-rotor position, cribs, recoverability)
and depth planning across a directory.

```bash
python3 python/message_eval.py data/messages/
```

## Notes

- **Numbers** in this traffic are spelled out (`CUATRO`, `SIETE`, `OCHO`), not encoded
  with `NR/XK`.
- **Stepping**: the turnover model of these machines is calibrated in the tools, which
  is why messages read cleanly from a single key. (Details and validation: paper in
  preparation.)
- **Message format**: JSON in `data/messages/` with `grundstellung`, `body` (cipher
  groups, with `<PLAIN: ...>` inserts for in-clear text), `found_by` (credit to whoever
  located the message) and `solution` (key, plaintext and a reproducible command).
```