# Spanish-Enigma

A research toolkit for the cryptanalysis of Spanish Enigma K traffic
(1936–1945), accompanying the work *Uns pocs republicans espanyols a
l'Équipe D del Coronel Bertrand* (J. Fornés i A. Rebull, 2026).

> **Status:** early development. The repository is currently a data
> archive; the C/Python toolkit is planned for late 2026.

---

## Scope

The Nationalist side of the Spanish Civil War (1936–1939) operated a
variant of the commercial Enigma K machine, distinguished from the
German military Enigma by a settable reflector (four-letter
*Grundstellung*) and a small number of custom wirings (variants A
through F documented by Soler Fuensanta, Quirantes Sierra, and
Weierud). This repository collects:

- **Primary-source data**: transcriptions of intercepted ciphertexts
  from the *Centro Documental de la Memoria Histórica* (CDMH,
  Salamanca), procurement records from the *Archivo Histórico
  Nacional* (AHN), distribution records from the *Archivo General
  Militar de Ávila* (AGMAV), and cross-referenced serial-number lists.
- **Reference cryptographic data**: rotor wirings (where published),
  reflector configurations, notch positions, and procedural
  conventions (garble-check format, message-key handling).
- **Analysis code** (planned): an Enigma K simulator in C with Python
  bindings, statistical tools (index of coincidence, χ², frequency
  matching against period-Spanish corpora), and adaptations of the
  Sullivan–Weierud and Gillogly hill-climbing attacks to the
  Spanish-variant parameter space.

## Why a dedicated toolkit

Existing open-source Enigma simulators target the German military
variants (Wehrmacht I, M3, M4) and assume a fixed reflector. The
Spanish K requires a different parameter space (settable UKW × 3
rotors × ring settings × wiring variant × rotor order) and a different
statistical reference (Spanish 1930s frequencies, not English or
German). The data and procedures gathered here support reproducible
analysis of a corpus that is still largely unpublished.

---

## Repository structure (planned)
```
spanish-enigma/
├── data/
│   ├── wirings/          # rotor wirings A–F, ETW, UKW (JSON)
│   ├── frequencies/      # IC reference profiles per language/period
│   ├── messages/         # intercepted ciphertexts with archival metadata
│   └── serials/          # serial number → owner/date cross-reference
├── src/                  # C: Enigma K core, statistics, search
├── python/               # Python bindings and analysis notebooks
├── tests/
└── doc/
```
The `data/` tree is the stable, citable core. The `src/` and
`python/` trees are tooling that may evolve.

## Data format

Each ciphertext in `data/messages/` is a JSON document with the
fields:

```json
{
  "archive": "CDMH",
  "signature": "Caja 745",
  "date_transmission": "1936-12-06",
  "date_interception": "1936-12-08",
  "sender": "Cuartel General del Estado Mayor (Salamanca)",
  "recipient": "Comandante Militar de Baleares (Palma de Mallorca)",
  "header": ["YPSQ", "VHRH", "DHZB", "NWTC"],
  "body": "WREO DAVV WOQR ...",
  "garble_check": "BZHD",
  "reference": "ref 3644",
  "notes": "Repetition of an earlier message (\"me refiero a error en\")"
}
```

The archival metadata travels with the data so each ciphertext is
re-citable independently of the toolkit.

---

## License

The source code is distributed under the GNU General Public License
v3.0. See [LICENSE](LICENSE).

The transcribed primary-source data are not subject to copyright (the
documents themselves are public records in the Spanish state
archives), but the transcriptions and metadata in this repository
should be cited as indicated below.

## Citation

If you use this repository in academic work, please cite both the
software and the accompanying paper:
```
Fornés, J., and Rebull, A. (2026). Spanish-Enigma: A research toolkit for the
cryptanalysis of Spanish Enigma K traffic.
https://github.com/jfornes/Spanish-Enigma
[DOI pending: Zenodo registration in preparation]
``
## Contributing

Contributions of additional transcriptions, corrected wirings, or
analytical methods are welcome. Please open an issue before submitting
a pull request, and ensure all primary-source contributions include
the corresponding archival reference (archive, fund, signature).

## Acknowledgments

Builds on the published work of José Ramón Soler Fuensanta, Arturo
Quirantes Sierra, Frode Weierud, Geoff Sullivan and others on the
Spanish Enigma. This repository complements rather than replaces
their contributions; the wirings and procedures published in their
work are reproduced here as data (with attribution) for reproducible
analysis.
AI assistants (Anthropic Claude) were used during development for
code drafting, text editing, and methodological discussion. All
archival research, historical interpretation, and final decisions
are the authors' responsibility.

---

*Repository maintained by Jordi Fornés (UPC-BarcelonaTech).*
