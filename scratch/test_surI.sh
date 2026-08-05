for f in data/messages/SUR_full_*.json; do
    echo "=== $f ==="
    python3 python/mixed_rotors.py "$f" \
        --crib data/cribs/cribs_navales.txt \
        --mix --arr all --procs 8 \
        | tee "${f%.json}.log"
done

grep -l "SPANISH-LIKE" data/messages/SUR_full_*.log 2>/dev/null

