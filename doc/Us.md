# Spanish-Enigma — guia d'ús de les eines

Tot s'executa des de l'arrel del repositori, després de compilar la biblioteca
en C:

```bash
cd src && make && cd ..          # librods.so (Linux) o librods.dylib (macOS)
# només si la biblioteca no és a src/ ni a build/:
export SPANISH_ENIGMA_LIB=/ruta/a/librods.so
```

Els cablejats són dades, a `data/wirings/wirings.json`; cap eina no els porta
escrits al codi.

## `enigma_k.py` — la màquina

Xifra o desxifra un text amb una clau donada; l'Enigma és recíproca, o sigui
que una sola ordre fa les dues coses. Les claus de quatre lletres van en
l'ordre U, L, M, R (reflector, esquerre, mig, dret).

```bash
python3 python/enigma_k.py --wiring F --order II-I-III \
        --windows LUIS --ring UFSF --text "HORAS HOY ACCION"    # OBAL XWWB JUKR UF
python3 python/enigma_k.py --json data/messages/XMOT.json        # torna a llegir un missatge
python3 python/enigma_k.py --json data/messages/LUIS.json --ring AMIF   # canvia part de la clau
python3 python/enigma_k.py --self-test data/messages/            # tots els missatges llegits
```

## `corpus_sweep.py` — la cerca de la clau

Amb `--crib`, totes les claus que converteixen un tram del criptograma en el
mot probable, amb el desxifrat sencer. Sense, una cerca cega sobre tots els
Ringstellungen, puntuada com a castellà (`lang_model.py`); escriu els millors
candidats i, a part, els que porten una tanda de W.

```bash
python3 python/corpus_sweep.py data/messages/XMOT.json --crib MOVIMIENTOBARCOS --wirings F
python3 python/corpus_sweep.py data/messages/DHZB.json --wirings F
```

Opcions: `--wirings D,F` (jocs de rotors), `--all` (les 24 assignacions de les
lletres de la capçalera, no només la del manual), `--grund XXXX` (posició
inicial per a un missatge sense capçalera), `--top N`, `--procs N`,
`--notch III=22,II=15` (el stepping a mà: posicions de rod, una lletra de
finestra com `III=N`, o `none`), `--sweep-turnover right|middle|both` (prova
també el turnover a cadascuna de les 26 posicions de rod; 26 o 676 vegades el
cost). Sense aquestes dues opcions, el stepping és el de
`data/wirings/wirings.json`.

## `buttonup.py` — el cablejat d'un rotor a partir d'un mot probable

El *buttoning-up* de Knox recupera el cablejat del rotor dret; el del mig i
l'esquerre en surten amb més text conegut. Les autoproves són sobre el
cablejat F:

```bash
python3 python/buttonup.py --selftest            # rotor dret, Python
python3 python/buttonup.py --selftest-c          # rotor dret, nucli en C
python3 python/buttonup.py --selftest-middle     # rotor del mig
python3 python/buttonup.py --selftest-left       # rotor esquerre
python3 python/buttonup.py --selftest-external   # contra els parells d'arxiu
python3 tests/corpus_buttonup.py                 # sobre el trànsit real
```

## `rods_frontend.py` — la prova dels *rods* i els acoblaments

Els nuclis de `librods` amb línia d'ordres: `brute` (mot probable exacte sobre
tots els anells), `coupling` (acoblaments de Turing per tram) i `link`
(acoblaments enllaçats a través dels avanços). Primer s'executen els controls
positius.

```bash
python3 python/rods_frontend.py data/messages/XMOT.json --crib MOVIMIENTOBARCOS --wirings F
```

## Proves

```bash
sh tests/run_all.sh          # ha de passar abans de cada versió
sh tests/compat_check.sh     # compila, passa les proves i cronometra dues cerques
python3 tests/hw43_rod_square.py     # el rod square de la secció Knox, HW 43/7 pp. 16-19
python3 tests/hw43_p90_buttonup.py   # el seu trencament de les pp. 88-90, refet
```

## Fitxers de missatge

`data/messages/README.md` en descriu els camps. Els números d'aquest trànsit
van lletrejats (`CUATRO`, `SIETE`, `OCHO`); els claudàtors `NR`…`XK` del manual
només surten al seu propi exemple.
