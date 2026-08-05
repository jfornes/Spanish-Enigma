#!/bin/bash
for f in data/messages/SUR_cand_*.json; do
    echo "=== $f ==="
    python3 python/mixed_rotors.py "$f" \
        --crib data/cribs/cribs_navales.txt \
        --mix --arr all --procs 12 \
        | tee "${f%.json}.log"
done

