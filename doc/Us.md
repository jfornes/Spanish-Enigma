# Spanish-Enigma — guia d'ús de les eines

Recuperació de clau i de cablejat per al tràfic Enigma K comercial (sense clavilles,
ETW QWERTZ, reflector ajustable) de la Caja 745. El nucli de cerca és en C
(`src/rods.c` → `librods.so`), invocat des de front-ends en Python. Els cablejats es
passen com a paràmetres; el catàleg viu a `data/wirings/wirings.json`.

## Posada en marxa

```bash
cd src && make && cd ..          # compila librods.so
# opcional, si la lib no és a src/ o build/:
export SPANISH_ENIGMA_LIB=/ruta/a/librods.so
```

Cada front-end comença amb un **control positiu** sobre el cablejat F: ha de reproduir
un desxifrat conegut abans de confiar en cap resultat. Vegeu `tests/run_examples.sh`
per a exemples executables.

## Eines

### `corpus_sweep.py` — triatge per IoC i *crib-drag*
Sense `--crib`: mode IoC cec (escombra cablejat × arranjament × ordre × 26⁴ anells i
puntua cada desxifrat per Índex de Coincidència i fragments castellans). Amb `--crib`:
arrossega un mot probable i troba les claus exactes que el reprodueixen.

```bash
# crib-drag (fixa la clau) -- amb un mot d'un tram net:
python3 python/corpus_sweep.py data/messages/XMOT.json \
        --crib MOVIMIENTOBARCOS --wirings F --all --procs 8
# IoC cec (sense crib):
python3 python/corpus_sweep.py data/messages/LUIS.json --wirings D F --procs 8
```

### `mixed_rotors.py` — rotors barrejats, IoC cec i consens
Prova rotors carregats de jocs de cablejat diferents (`--mix`). Amb `--crib` fa
crib-drag (accepta un mot o un fitxer de mots); sense `--crib`, IoC cec. Amb
`--consensus` fusiona els millors desxifrats en una lectura de consens. Ordena i marca
per recompte de **paraules castellanes reals** (no per IoC, que pot ser degeneració).

```bash
python3 python/mixed_rotors.py data/messages/XMOT.json --mix --arr all --consensus --procs 12
python3 python/mixed_rotors.py data/messages/DHZB.json \
        --crib data/cribs/cribs_navales.txt --mix --arr all --procs 12
```

### `buttonup.py` — recuperació del cablejat dels rotors
*Buttoning-up* del rotor ràpid i recuperació dels rotors interiors. Controls positius
sobre F:

```bash
python3 python/buttonup.py --selftest-c        # rotor dret
python3 python/buttonup.py --selftest-middle    # rotor del mig
python3 python/buttonup.py --selftest-left      # rotor esquerre
```

### `message_eval.py` — triatge d'arxiu
Fitxa per missatge (estructura, Grundstellung, posició esquerra, cribs, recuperabilitat)
i planificació de profunditat per directori.

```bash
python3 python/message_eval.py data/messages/
```

## Notes

- **Nombres**: en aquest tràfic van lletrejats (`CUATRO`, `SIETE`, `OCHO`), no amb `NR/XK`.
- **Stepping**: el model de turnover d'aquestes màquines està calibrat a les eines; per
  això els missatges es llegeixen nets d'una sola clau. (Detalls i validació: article en
  preparació.)
- **Format dels missatges**: JSON a `data/messages/` amb `grundstellung`, `body`
  (grups xifrats, amb inserts `<PLAIN: ...>` per al text en clar), `found_by` (crèdit a
  qui el va localitzar) i `solution` (clau, text pla i command reproduïble).
