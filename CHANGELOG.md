# Changelog

## v1.1.0 — 2026-11-19

The release that accompanies the two papers.

### Readings

- `DHZB` and `MKCX` read; `MVNR`, published in 1992 with a plaintext, read from
  its ciphertext (188 of 192 letters; cryptogram of the thesis of Núñez de Prado,
  1992, p. 195). `SUR` recorded as a candidate: one key reads letters 26 to 64,
  and under the Ringstellung of `LUIS` it gives an indicator, `FRBY`, that
  stands in the typed text, so the header is read as run into it.
- Every message file now carries its sheet, the key, the reading, the command
  that recovers the key (`solution.command`) and the one that replays it
  (`verified_with`). The fields are described in `data/messages/README.md`.
- `manual_example.json` is merged into `MNAS.json`.

### Machine model

- Group 3 of the header is read as the windows in the order reflector, left,
  middle, right, the convention of the manual's worked example. v1.0.0 read it
  as (left, middle, right, reflector); the keys are restated (`XMOT`: windows
  `XMOT`, Ringstellung `AMIF`, formerly `TXMO`/`WXGA`).
- The stepping is data, in `data/wirings/wirings.json`, block `stepping`: core
  offsets 22 for III and 15 for II on wiring F; rotor I at window Y. The block
  states the two readings of the header that fit the traffic and the one
  adopted (notch on the ring).
- The turnover letters in `turnovers` are the catch letters of the surviving
  machines A1242 and A-1233 (Y, E, N).
- `wirings.json` records each rotor's notch letter on the ring (G, M, V) beside
  its turnover window (Y, E, N): the window is the notch + 18 on every rotor of D
  and F (Soler, López-Brea and Weierud 2010, figs. 17-18). Checked by
  `tests/stepping_parity.py`.
- `wirings.json`: the source of wirings D and F is cited correctly.
- Each rotor steps by the rule of its own set: F by the offsets above, D at its
  window letters (Y, E, N), as the one real message on D, `LRS10`, requires; a
  mixed set rotor by rotor. `corpus_sweep`, `enigma_k` and `rods_frontend`
  agree (`tests/stepping_parity.py`, `tests/lrs10_control.py`).
- `--notch` (`corpus_sweep`, `rods_frontend`) sets the stepping by hand, and
  `--sweep-turnover` (`corpus_sweep`) tries the turnover at every rod position,
  for traffic of a period other than December 1936
  (`tests/turnover_sweep.py`).

### Search

- `python/lang_model.py`: decrypts are scored by the best eight-letter
  trigram window, Sarmiento's W rule and a list of military fragments, on a
  corpus of public-domain Spanish (`data/lang/`). The blind search ranks by it
  and prints, apart, the candidates that carry a run of W.
- The blind search cuts each ring block by the trigram score, not by the index
  of coincidence.
- Fix: with both stepping rotors carrying a core offset (the rotor orders with I
  on the left), the blind search computed the stepping from one ring. The
  survivors of each block are now decoded again with their own four rings
  before they are scored.
- The crib search steps each rotor from its own ring.
- `python/sarmiento.py`: the operating rules of the manual as code (indicator
  position, COLOC, closing check, syllabic groups, W padding, NR/XK numerals,
  group count).
- `python/enigma_k.py`: encipher or decipher with a given key, replay a message
  file, and check every solved message (`--self-test`).
- `python/rods_frontend.py`: the Python oracle steps as the C kernels do, with
  the offsets of each rotor set.

### Tests

- `tests/run_all.sh` gates a release: message files, the manual's rules, the
  scoring, the buttoning-up (synthetic, archival and on the real traffic), the
  middle-rotor stepping in C, the replay of every solved message, and two
  vectors from TNA HW 43/7: the rod square of pp. 16-19
  (`tests/hw43_rod_square.py`) and the break of pp. 88-90
  (`tests/hw43_p90_buttonup.py`).
- `tests/test_sarmiento.py` also checks the manual's rule 3 on every read
  message: the closing group, reversed, gives the windows of the key that
  reads it.
- `tests/compat_check.sh` builds, runs the gate and times two reference
  searches.

### Removed from the tree

`calibrate_notch.py`, `mixed_rotors.py`, `message_eval.py`, `scratch/` and
`tests/run_examples.sh` (its examples are in the README). The message files
`CEVM`, `RXVT`, `LAHP` and `ZXNE`, two intercepts in two transcriptions each:
measured, they are not Enigma traffic. All of these remain in v1.0.0.

## v1.0.0

First public release.
