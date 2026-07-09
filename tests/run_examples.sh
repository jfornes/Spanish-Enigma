#!/usr/bin/env bash
# tests/run_examples.sh -- runnable examples that double as a smoke test.
# Run from the repository root:  bash tests/run_examples.sh
# Exercises the positive controls (F wiring) and a full crib break of XMOT.
set -e
cd "$(dirname "$0")/.."          # repo root

echo "== Building the C kernel =="
( cd src && make >/dev/null ) && echo "librods.so OK"

echo
echo "== Positive controls: rotor-wiring recovery on F =="
python3 python/buttonup.py --selftest-c
python3 python/buttonup.py --selftest-middle
python3 python/buttonup.py --selftest-left

echo
echo "== Example 1: crib-drag XMOT (expected: clean read from one key) =="
# The #1 hit (ranked by residual IoC) should decode to:
#   PONERQUE MOVIMIENTO BARCOS <de que me da cuenta...> ... SOBRE MALLORCA O IBIZA
python3 python/corpus_sweep.py data/messages/XMOT.json \
        --crib MOVIMIENTOBARCOS --wirings F --all --procs 8

echo
echo "== Example 2: crib-drag LUIS (naval-air order; spelled-out numbers) =="
python3 python/corpus_sweep.py data/messages/LUIS.json \
        --crib CUATROPROSEGUIR --wirings F --all --procs 8

echo
echo "== Example 3: IoC-blind + consensus over mixed rotor combos (heavier) =="
echo "   (uncomment to run; wants many cores)"
# python3 python/mixed_rotors.py data/messages/XMOT.json --mix --arr all --consensus --procs 12

echo
echo "== Done. If the three selftests are True and XMOT/LUIS read as Spanish, the"
echo "   toolkit (incl. the core-based turnover) is working end to end. =="
