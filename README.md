# Spanish-Enigma
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21208383.svg)](https://doi.org/10.5281/zenodo.21208383)

Data and software for reading the Enigma K traffic of the Spanish Civil War:
the intercepts with their archival provenance, the machine as the engine models
it, the search that recovers keys, and the keys and readings it has produced.

It accompanies two manuscripts submitted for publication (J. Fornés and
A. Rebull, 2026): a technical paper on the readings and their keys, and a
historical paper on the Republican signals-intelligence service that took the
traffic down.

The machines are commercial Enigma K: no plugboard, a QWERTZ entry wheel and a
settable reflector, so the key has four starting letters and four
Ringstellungen. Two rotor wirings are in print, D and F; every message read here
is on F.

---

## The messages

| file | date (1936) | link | status | key: wiring, rotor order, windows, Ringstellung |
|---|---|---|---|---|
| `LUIS` | 6 Dec | Palma → Salamanca | read | F, II-I-III, `LUIS`, `UFSF` |
| `DHZB` | 7 Dec | Salamanca → Palma | read, 80 of 80 | F, II-I-III, `DHZB`, `UFSF` |
| `MVNR` | 9 Dec | Terminus → Moroccan command | read, 188 of 192 | F, II-I-III, `MVNR`, `UFSF` |
| `XMOT` | 11 Dec | Salamanca → Palma | read, 132 of 132 | F, II-I-III, `XMOT`, `AMIF` |
| `MKCX` | undated | Palma → Salamanca | read, letters 34–142 | F, I-III-II, `MKCX`, `LJHU` |
| `SUR` | 6 Dec | Mallorca → Salamanca | candidate | (see the file) |
| `MNAS` | — | the manual's worked example | validation, 66 of 68 | F, II-III-I, `MNAS`, `QDRR` |

All but `MVNR` and `MNAS` come
from Caja 745 of the Centro Documental de la Memoria Histórica (Salamanca).
`MVNR` was published with a plaintext by Núñez de Prado (1992), whose cryptogram
it follows, and reprinted by Soler Fuensanta and López-Brea Espiau (2008); `MNAS` is the worked example
of Sarmiento's manual (Salamanca, November 1936).

Each file in `data/messages/` holds the sheet, the cryptogram, the key, the
reading, the searches that failed, and the name of whoever found the sheet.
[`data/messages/README.md`](data/messages/README.md) describes the fields.

## What else is here

```
data/
  messages/   one file per message (above)
  wirings/    wirings.json: entry wheel, reflector, rotor sets D and F, stepping; every datum with its source
  cribs/      cribs_navales.txt: probable words
  lang/       public-domain Spanish prose that scores decrypts (README gives the measurements)
  serials/    machine_registry.json: machines and stations of the Spanish theatre
src/          rods.c, Makefile: the search library librods (C, POSIX threads)
python/
  enigma_k.py       the machine: enciphers or deciphers a text with a given key
  corpus_sweep.py   the key search, blind or with a crib
  lang_model.py     how a decrypt is scored as Spanish
  sarmiento.py      the operating rules of the Spanish manual, as code
  buttonup.py       Knox's buttoning-up: rotor wiring from a crib
  rods_frontend.py  rod test and Turing's couplings, on librods
  rodslib.py        loader for librods
tests/        run_all.sh and the checks it runs, including two vectors from TNA HW 43/7
doc/          USAGE.md (English), Us.md (Catalan)
```

## Build

The C library needs a C compiler and POSIX threads; the Python tools need
Python 3 and NumPy.

```bash
cd src && make && cd ..      # librods.so (Linux) or librods.dylib (macOS)
pip install numpy
```

`rodslib.py` finds the library through `$SPANISH_ENIGMA_LIB`, then `python/`,
`src/` and `build/`.

## Try it

The engine is the machine: with the key of `LUIS`, the first words of its
plaintext give back the opening of the cryptogram as it stands on the sheet,
`OBAL XWWB JUKR UF`.

```bash
python3 python/enigma_k.py --wiring F --order II-I-III \
        --windows LUIS --ring UFSF --text "HORAS HOY ACCION"
python3 python/enigma_k.py --json data/messages/XMOT.json     # replay a stored reading
```

The search goes the other way and recovers the key from the ciphertext:

| message | command | the key is |
|---|---|---|
| `XMOT` | `python3 python/corpus_sweep.py data/messages/XMOT.json --crib MOVIMIENTOBARCOS --wirings F` | the only match |
| `LUIS` | `python3 python/corpus_sweep.py data/messages/LUIS.json --crib CUATROPROSEGUIR --wirings F` | the only match |
| `MVNR` | `python3 python/corpus_sweep.py data/messages/MVNR.json --crib LASROZAS --wirings F` | the only match |
| `DHZB` | `python3 python/corpus_sweep.py data/messages/DHZB.json --wirings F` | first among the runs of W |
| `MKCX` | `python3 python/corpus_sweep.py data/messages/MKCX.json --wirings F` | first by score |

Without a crib the search prints its best candidates and, apart, those that
carry a run of W, the padding Sarmiento's manual prescribes. A blind sweep of
one wiring takes about six seconds for eighty letters on eight cores.

For a message of another period, let the search also place the rotors' turnover
(see *Stepping* below): `--sweep-turnover right` tries the right rotor's turnover
at each of the 26 rod positions, at 26 times the cost; `middle` does the same
for the middle rotor and `both` tries the 676 combinations. `--notch` fixes the
stepping by hand (`III=22,II=15`, a window letter such as `III=N`, or `none`).
Without these options the search uses the values of `wirings.json`.

```bash
python3 python/corpus_sweep.py data/messages/SUR.json --wirings F --sweep-turnover right
```

## Tests

```bash
sh tests/run_all.sh          # everything that must pass before a release
sh tests/compat_check.sh     # builds, runs run_all.sh, times two reference searches
```

`run_all.sh` checks that the message files are coherent and that the engine
replays every solved message from its file; asserts the manual's rules on its
own examples; checks that the scoring separates the true readings from their
letters shuffled; runs the buttoning-up on a synthetic crib, on the archival
pairs and on the real traffic; checks the stepping of a middle rotor in the C
kernel; checks that the Python search and the C kernels step every rotor set
alike, that `LRS10`, the one real message on wiring D, reads with D's stepping,
and that `--sweep-turnover` finds a key whose turnover falls outside the values of
December 1936; and replays two vectors from the history of the Knox section (TNA
HW 43/7): the rod square of pp. 16-19 and the break of pp. 88-90, which the
entry wheel in keyboard order reproduces at 99 of 99 letters.

## The machine model

**Indicator.** Group 3 of the header, sent in clear, gives the windows in the
order reflector, left, middle, right, as in the manual's worked example. Read
that way, three messages of 6, 7 and 9 December on three links share one
Ringstellung, `UFSF`, and `XMOT` of 11 December has `AMIF`: rotor order and
Ringstellung were set for a period, as the manual prescribes.

**Stepping.** On the Enigma K the notch is cut in the alphabet ring, so a
rotor carries its neighbour on at a fixed window letter (Y, E, N for I, II,
III), 18 positions after the ring letter of its notch (G, M, V) on every rotor
of both sets. What a decrypt depends on is the rod position at which the turnover falls,
window less ring, and that depends on the Ringstellung. With the header letters
taken as the windows, the engine places it as follows:

- Wiring F: at rod position 22 for III and 15 for II, rotor I at window Y. This
  is where the turnover falls in the traffic of December 1936, and it reproduces
  every message from the header as transmitted. With the notch at N, as Turing
  describes and the two surviving machines show, it means a Ringstellung of R
  for III and header letters displaced from the windows by a constant fixed for
  the period; the traffic alone cannot exclude that the header gives the
  windows themselves and the turnover is fixed to the core.
- Wiring D: at the window letters Y, E, N. `LRS10`, a naval-attaché message on
  D read by M. Hörenberg, reads 90 of 90 letters this way and not with F's
  offsets (`tests/lrs10_control.py`).
- A mixed set (`--wirings DFF`) takes each rotor's rule from its own set.

Both are the values of one period or one message. Traffic of another period,
with another Ringstellung, turns over elsewhere: `--sweep-turnover` and `--notch`
(above) free the turnover. `data/wirings/wirings.json` (block `stepping`) records
the readings, the offsets and the messages they were measured on; the method
and the evidence are in the technical paper.

## More traffic

The Caja 745 messages come from a fonds of 97 boxes, of which five have been
examined. A sheet in four-letter groups whose third header group comes back,
reversed, at the end of the body is a candidate. Whoever meets one can try it
against the keys and the search above, or send it to us; every message file
names whoever found the sheet. Contributions of transcriptions, wirings or
methods are welcome: please open an issue first, and give the archival
reference (archive, fonds, signature) of every primary source.

## License

The **source code** is under the GNU General Public License v3.0 (see
[LICENSE](LICENSE)). The **transcriptions and metadata** in `data/` are
released under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); the
documents themselves are public records in the Spanish state archives. Please
cite the archival source recorded in each file.

## Citation

Please cite the software and the accompanying papers; machine-readable
metadata is in [`CITATION.cff`](CITATION.cff).

```
Fornés, J., & Rebull, A. (2026). Spanish-Enigma: A research toolkit for the
cryptanalysis of Spanish Enigma K traffic (1936–1945) (Version 1.1.0). Zenodo.
https://doi.org/10.5281/zenodo.21208383
```

## Acknowledgments

Builds on the published work of Frode Weierud, José Ramón Soler Fuensanta,
Arturo Quirantes Sierra, Geoff Sullivan and others on the Spanish Enigma. The
wirings and procedures published in their work are reproduced here as data,
with attribution.

An AI assistant (Claude, Anthropic) was used in developing the software and in
preparing the papers: for drafting code, for running analyses, for
methodological discussion and for editing text. The architecture of the
software and the choice of methods are the authors'. The generated code is
verified by the tests in `tests/`, against vectors independent of it and
against the readings themselves; every result is reproducible from this
release. The archival research, the historical interpretation and all final
decisions are the authors' responsibility.

---

*Maintained by Jordi Fornés (UPC-BarcelonaTech).*
