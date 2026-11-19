# Spanish-Enigma — using the tools

Run everything from the repository root, after building the C library:

```bash
cd src && make && cd ..          # librods.so (Linux) or librods.dylib (macOS)
# only if the library is not in src/ or build/:
export SPANISH_ENIGMA_LIB=/path/to/librods.so
```

The wirings are data, in `data/wirings/wirings.json`; no tool hard-codes them.

## `enigma_k.py` — the machine

Enciphers or deciphers a text with a given key; the Enigma is reciprocal, so
one command does both. Four-letter keys are in the order U, L, M, R
(reflector, left, middle, right).

```bash
python3 python/enigma_k.py --wiring F --order II-I-III \
        --windows LUIS --ring UFSF --text "HORAS HOY ACCION"    # OBAL XWWB JUKR UF
python3 python/enigma_k.py --json data/messages/XMOT.json        # replay a stored reading
python3 python/enigma_k.py --json data/messages/LUIS.json --ring AMIF   # change part of the key
python3 python/enigma_k.py --self-test data/messages/            # every solved message
```

## `corpus_sweep.py` — the key search

With `--crib`, every key that turns a stretch of the ciphertext into the crib,
with the full decrypt. Without it, a blind search over every Ringstellung,
scored as Spanish (`lang_model.py`); it prints the best candidates and, apart,
those that carry a run of W.

```bash
python3 python/corpus_sweep.py data/messages/XMOT.json --crib MOVIMIENTOBARCOS --wirings F
python3 python/corpus_sweep.py data/messages/DHZB.json --wirings F
```

Options: `--wirings D,F` (sets to try), `--all` (all 24 arrangements of the
header letters, not only the manual's), `--grund XXXX` (a starting position
for a message without a header), `--top N`, `--procs N`,
`--notch III=22,II=15` (the stepping by hand: rod positions, a window letter
such as `III=N`, or `none`), `--sweep-turnover right|middle|both` (also try the
turnover at each of the 26 rod positions; 26 or 676 times the cost). Without the
last two, the stepping is that of `data/wirings/wirings.json`.

## `buttonup.py` — rotor wiring from a crib

Knox's buttoning-up recovers the right rotor's wiring; the middle and left
rotors follow from more crib. The self-tests run on wiring F:

```bash
python3 python/buttonup.py --selftest            # right rotor, Python
python3 python/buttonup.py --selftest-c          # right rotor, C kernel
python3 python/buttonup.py --selftest-middle     # middle rotor
python3 python/buttonup.py --selftest-left       # left rotor
python3 python/buttonup.py --selftest-external   # against the archival pairs
python3 tests/corpus_buttonup.py                 # on the real traffic
```

## `rods_frontend.py` — rod test and couplings

The kernels of `librods` behind a command line: `brute` (exact crib over all
rings), `coupling` (Turing's per-stretch couplings) and `link` (couplings
linked across turnovers). Positive controls run first.

```bash
python3 python/rods_frontend.py data/messages/XMOT.json --crib MOVIMIENTOBARCOS --wirings F
```

## Tests

```bash
sh tests/run_all.sh          # must pass before a release
sh tests/compat_check.sh     # build, gate and two timed reference searches
python3 tests/hw43_rod_square.py     # the Knox section's rod square, HW 43/7 pp. 16-19
python3 tests/hw43_p90_buttonup.py   # its break of pp. 88-90, replayed
```

## Message files

`data/messages/README.md` describes the fields. Numbers in this traffic are
spelled out (`CUATRO`, `SIETE`, `OCHO`); the manual's `NR`…`XK` brackets
appear only in its own example.
