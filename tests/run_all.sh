#!/bin/sh
# run_all.sh -- everything that must be green before a release is tagged.
#
#   sh tests/run_all.sh
#
# Exits non-zero if anything fails, so it can gate a tag. Each line below is a
# test that can actually FAIL; the module __main__ blocks that print tables are
# deliberately not in here, because a check that always exits zero cannot gate
# anything and one of ours quietly did not for a year.
set -u
cd "$(dirname "$0")/.."
rc=0
run() {
  printf '\n=== %s\n' "$1"
  shift
  if "$@"; then :; else echo "   ^^ FAILED"; rc=1; fi
}

run "corpus is internally coherent"      python3 tests/validate_messages.py
run "Sarmiento's rules"                  python3 tests/test_sarmiento.py
run "triage criterion"                   python3 tests/test_lang_model.py
run "buttonup, synthetic"                python3 python/buttonup.py --selftest
run "buttonup, ARCHIVAL vector"          python3 python/buttonup.py --selftest-external
run "middle-notch regression"            python3 tests/midnotch_control.py
run "both front-ends step alike (D, F)"  python3 tests/stepping_parity.py
run "LRS10, the real message on D"      python3 tests/lrs10_control.py
run "a turnover outside December 1936"  python3 tests/turnover_sweep.py
run "HW 43/7: the rod square, pp. 16-19" python3 tests/hw43_rod_square.py
run "HW 43/7: the break of pp. 88-90"    python3 tests/hw43_p90_buttonup.py
run "buttonup on the real traffic"       python3 tests/corpus_buttonup.py

printf '\n=== engine replays every solved message\n'
for j in data/messages/*.json; do
  out=$(python3 python/enigma_k.py --self-test "$j" 2>&1 | tail -1)
  case "$out" in
    *"0 failed"*) ;;
    *) echo "   FAILED on $j: $out"; rc=1 ;;
  esac
done
echo "   $(for j in data/messages/*.json; do python3 python/enigma_k.py --self-test "$j" 2>&1 | tail -1; done \
        | awk '{p+=$1; f+=$3; s+=$5} END {print p" passed, "f" failed, "s" skipped"}')"

if [ "$rc" = "0" ]; then
  printf '\nALL GREEN\n'
else
  printf '\nSOMETHING FAILED -- do not tag\n'
fi
exit $rc
