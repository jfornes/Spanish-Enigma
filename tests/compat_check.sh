#!/bin/sh
# compat_check.sh -- does this machine reproduce the toolkit's results, and how fast?
#
#   sh tests/compat_check.sh [PROCS]        (default: all hardware threads)
#
# Builds librods, runs the release gate (run_all.sh), then two reference searches
# whose answers are known, and times them:
#   1. exact crib-drag, XMOT, crib MOVIMIENTOBARCOS, wiring F
#      -> must print windows XMOT, Ringstellung AMIF
#   2. blind sweep, DHZB, wiring F, six rotor orders, whole ring space
#      -> the reading (Ringstellung UFSF) must appear in the W-run list, score 881.4
# Exit status 0 only if everything matches.
set -u
cd "$(dirname "$0")/.."
P=${1:-$(nproc 2>/dev/null || sysctl -n hw.ncpu)}
rc=0
echo "== machine";  uname -srm; (lscpu 2>/dev/null | grep -m1 'Model name') || sysctl -n machdep.cpu.brand_string
echo "   threads used: $P"
python3 -c "import sys, numpy; print('   python', sys.version.split()[0], ' numpy', numpy.__version__)" || rc=1
${CC:-cc} --version | head -1

echo "== build"
(cd src && make -s -B) || { echo "   BUILD FAILED"; exit 1; }
ls -l src/librods.* | sed 's/^/   /'

echo "== release gate"
sh tests/run_all.sh > /tmp/compat_runall.log 2>&1 && echo "   ALL GREEN" || { echo "   FAILED (see /tmp/compat_runall.log)"; rc=1; }

echo "== reference 1: crib-drag XMOT"
t0=$(date +%s)
out=$(python3 python/corpus_sweep.py data/messages/XMOT.json --crib MOVIMIENTOBARCOS --wirings F --procs "$P" 2>&1)
t1=$(date +%s)
echo "$out" | grep -q "windows(U,L,M,R)=XMOT Ringstellung(U,L,M,R)=AMIF" \
  && echo "   OK  XMOT / AMIF  ($((t1-t0)) s)" || { echo "   MISMATCH"; echo "$out" | tail -5; rc=1; }

echo "== reference 2: blind sweep DHZB"
t0=$(date +%s)
out=$(python3 python/corpus_sweep.py data/messages/DHZB.json --wirings F --top 3 --procs "$P" 2>&1)
t1=$(date +%s)
echo "$out" | grep -q "score=  881.4 IoC=0.0595 W3 wiring F order II-I-III   rings(U,L,M,R)=UFSF" \
  && echo "   OK  UFSF in the W-run list, score 881.4  ($((t1-t0)) s)" || { echo "   MISMATCH"; echo "$out" | tail -8; rc=1; }

[ "$rc" = 0 ] && printf "\nCOMPATIBLE\n" || printf "\nNOT COMPATIBLE\n"
exit $rc
