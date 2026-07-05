# Spanish-Enigma

A research toolkit for the cryptanalysis of Spanish Enigma K traffic
(1936–1945), accompanying the work *Uns pocs republicans espanyols a
l'Équipe D del Coronel Bertrand* (J. Fornés & A. Rebull, 2026).

> **Status:** active development. The `data/` archive is stable and citable.
> The C/Python cryptanalytic toolkit is **functional and validated** against
> known wirings (see *Quick validation* below); some C-acceleration paths are
> still in progress.

---

## Scope

The Nationalist side of the Spanish Civil War (1936–1939) operated a variant
of the commercial Enigma K machine, distinguished from the German military
Enigma by a **settable reflector** (four-letter *Grundstellung*), **no
plugboard**, and a small number of custom wirings (variants A through F
documented by Soler Fuensanta, Quirantes Sierra, and Weierud). This
repository collects:

- **Primary-source data**: transcriptions of intercepted ciphertexts from the
  *Centro Documental de la Memoria Histórica* (CDMH, Salamanca), procurement
  records from the *Archivo Histórico Nacional* (AHN), distribution records
  from the *Archivo General Militar de Ávila* (AGMAV), and cross-referenced
  serial-number lists.
- **Reference cryptographic data**: rotor wirings (where published), reflector
  configurations, notch positions, and procedural conventions (garble-check
  format, message-key handling).
- **Analysis code**: an Enigma K search engine in C (POSIX pthreads) with a
  Python front-end for I/O, statistics (index of coincidence, Spanish-fragment
  scoring) and orchestration; plus Knox-style *rodding* and *buttoning-up*
  solvers for the unsteckered machine.

## Why a dedicated toolkit

Existing open-source Enigma simulators target the German military variants
(Wehrmacht I, M3, M4) and assume a fixed reflector. The Spanish K requires a
different parameter space (**settable UKW × 3 rotors × ring settings × wiring
variant × rotor order**) and a different statistical reference (Spanish 1930s
frequencies, not English or German). The data and procedures gathered here
support reproducible analysis of a corpus that is still largely unpublished.

---

## Repository structure
```
spanish-enigma/
├── data/
│   ├── wirings/       wirings.json        # ETW, UKW, rotor sets, wiring variants + sources
│   ├── frequencies/                       # IC reference profiles (in progress)
│   ├── messages/      *.json              # intercepted ciphertexts with archival metadata
│   └── serials/       machine_registry.json + README   # machine/station registry
├── src/              rods.c, Makefile     # C search engine (librods.so / .dylib)
├── python/           rodslib.py, rods_frontend.py, corpus_sweep.py,
│                     message_eval.py, buttonup.py
├── tests/                                 # (in progress)
└── doc/                                   # (in progress)
```
The `data/` tree is the stable, citable core. The `src/` and `python/` trees
are tooling that may evolve.

---

## Build

The C library has no external dependencies beyond a C compiler and POSIX
threads; it builds identically on Linux and macOS.

```bash
cd src
make            # -> librods.so (Linux) or librods.dylib (macOS)
```

The Python front-end needs Python 3 and (for the rod front-end) NumPy:

```bash
pip install numpy
```

`rodslib.py` locates the compiled library automatically (it looks at
`$SPANISH_ENIGMA_LIB`, then `python/`, then `../src/`, then `../build/`), so
running the Python tools from `python/` after `make` in `src/` works out of the
box.

## Tools

| Tool | Purpose |
|------|---------|
| `corpus_sweep.py` | Ciphertext-only **IoC + Spanish-fragment ranking**, or exact **known-plaintext crib-drag** (`--crib`) that recovers the full key (wiring, order, arrangement, *Ringstellung*, offset) and prints the decryption. Applies message hygiene automatically (removes `<PLAIN: …>` blocks; strips the reversed-*Grundstellung* garble-check group). |
| `rods_frontend.py` | Front-end for the C rod-search library. Two kernels: `brute` (exact-crib full enumeration) and `coupling` (Turing's coupling method, *Treatise* Ch. IV pp. 71–73). |
| `buttonup.py` | Knox-style **buttoning-up**: recovers the fast (right) rotor **wiring** from cribs by constraint propagation. `--selftest` reproduces the recovery of wiring **F** as a positive control. |
| `message_eval.py` | Field triage: for each intercept, reports what it contributes to recovering an unknown wiring (right/middle/left-rotor gauges, depth sets) without cracking it. |
| `rodslib.py` | Shared loader for `librods` (not a CLI). |

---

## Quick validation

The engine ships with a self-contained positive control. After building:

```bash
cd python
python3 buttonup.py --selftest
# -> [selftest py] recovered right rotor == true wiring F: True
```

A successful selftest means the machine model and the constraint solver agree
with a known wiring (F) recovered from a crib — the precondition before running
anything on real traffic.

## Reproducing the analysis

The certified December-1936 intercepts live in `data/messages/`. To rank
candidate decryptions of a message by index of coincidence and Spanish-fragment
score:

```bash
cd python
python3 corpus_sweep.py ../data/messages/XMOT.json          # IoC / fragment ranking
```

To recover the exact key from a known-plaintext crib and print the decryption
(here the XMOT message, message nº 116, Salamanca→Palma):

```bash
python3 corpus_sweep.py ../data/messages/XMOT.json --picker XMOT --crib MALLORCA --procs 8
```

> **Note.** The crib-drag key search currently falls back to a NumPy reference
> when the optional C anchor symbol (`buttonup_anchor`) is absent from the built
> library; it is correct but slow. The parallel C acceleration of the crib path
> is in progress (see the scope note in `src/rods.c`).

---

## Method & provenance

The search kernel is the **click / contradiction test** from A. M. Turing,
*Treatise on the Enigma* ("Prof's Book", c. 1940), Ch. IV, *Single-wheel
processes (Unsteckered Enigma)*, pp. 71–73: a candidate configuration that
reproduces every crib letter has zero contradictions; the crib is tested
letter by letter and abandoned at the first contradiction. Wheel stepping
follows the **A27** convention (turnover keyed to the window letter,
ring-independent; Turing pp. 4–5, and Soler/López-Brea/Weierud 2010). Wiring
recovery follows the historical Knox / ISK pipeline for the unsteckered
Enigma: **rodding → buttoning-up**. The wirings themselves are held as data in
`data/wirings/wirings.json`, with their published sources cited there.

---

## Data format

Each ciphertext in `data/messages/` is a JSON document carrying its archival
provenance, so it is re-citable independently of the toolkit:

```json
{
  "archive": "CDMH",
  "signature": "Caja 745",
  "date_transmission": "1936-12-11",
  "sender": "Generalísimo, Cuartel General (Salamanca)",
  "recipient": "Comandante Militar de Baleares (Palma de Mallorca)",
  "header": ["ZYPY", "VZRY", "XMOT", "RSPG"],
  "grundstellung": "XMOT",
  "body": "AGSZ FAEQ LHDF ... <PLAIN: de que me da cuenta en sus telegramas es> ... UJRA TOMX",
  "garble_check": "TOMX",
  "classification": "enigma_k_certified",
  "ic": 0.0392,
  "notes": "…"
}
```

The `data/serials/` and `data/wirings/` registries follow the same discipline:
every entry carries a `source` and a `confidence` tag (`sourced` / `likely` /
`inferred`). Inferences are kept flagged and never promoted to fact without a
document.

---

## License

The **source code** is distributed under the GNU General Public License v3.0.
See [LICENSE](LICENSE).

The **transcribed primary-source data** are not subject to copyright (the
documents are public records in the Spanish state archives); the transcriptions
and metadata in `data/` are released for reuse under
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) — please cite the
archival source (archive, fund, signature) as recorded in each file.

## Citation

If you use this repository in academic work, please cite both the software and
the accompanying paper. Machine-readable metadata is in
[`CITATION.cff`](CITATION.cff).

```
Fornés, J., & Rebull, A. (2026). Spanish-Enigma: A research toolkit for the
cryptanalysis of Spanish Enigma K traffic. Zenodo.
https://doi.org/10.5281/zenodo.XXXXXXX
```
*(DOI assigned on the first Zenodo release; update the value above accordingly.)*

## Contributing

Contributions of additional transcriptions, corrected wirings, or analytical
methods are welcome. Please open an issue before submitting a pull request, and
ensure every primary-source contribution includes its archival reference
(archive, fund, signature).

## Acknowledgments

Builds on the published work of José Ramón Soler Fuensanta, Arturo Quirantes
Sierra, Frode Weierud, Geoff Sullivan and others on the Spanish Enigma. This
repository complements rather than replaces their contributions; the wirings
and procedures published in their work are reproduced here as data (with
attribution) for reproducible analysis.

AI assistants (Anthropic Claude) were used during development for code
drafting, text editing, and methodological discussion. All archival research,
historical interpretation, and final decisions are the authors' responsibility.

---

*Repository maintained by Jordi Fornés (UPC-BarcelonaTech).*
