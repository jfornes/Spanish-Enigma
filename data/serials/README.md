# data/serials/ — machine & station registry

`machine_registry.json` catalogues the Enigma machines and cipher stations of the
Spanish theatre so intercepts from the Caja 745 (and beyond) can be attributed.

## Two independent axes
- **Machine type** (chassis): `commercial_unsteckered` (Spanish/Italian "Dora"
  family, **no plugboard** — the toolkit's domain), `funkschluessel_M` (German
  naval, plugboard), `legion_condor_numbered` (German, plugboard, **numbers** on
  the rotors).
- **Wiring** (rotor *Schaltung*, German phonetic names): **C** = Cäsar
  (unpublished — the DHZB/LUIS recovery target), **D** = Dora (Schaltung D), **F**
  = Friedrich. A single commercial chassis could carry D, F or C by batch/channel.
  Note: *Schaltung D (Dora)* is a **wiring**, not a machine model, and is distinct
  from reflector *UKW D*.

## Discipline
Every entry carries `source` and `confidence` (`sourced` / `likely` / `inferred`).
Keep inferences flagged; do not promote a hypothesis to a fact without a document.

## Filling it from the archive
For each new find, record: serial (if any), type, plugboard, wiring, holder, place,
period, and the **document reference** (box/folio). Serial numbers with an assigned
wiring (like the Italian A1236/1238/1250 on wiring D) are the most valuable: they
pin which wiring operated on which link.
