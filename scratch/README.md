# scratch/

One-off exploratory scripts. **Not part of the toolkit**, not documented in the
paper, no stability guarantees. Kept so that negative results stay reproducible.

- `gen_sur_candidates.py` — generates the 26 `SUR`+A..Z Grundstellung variants of
  the SUR message (`data/messages/SUR.json`). `mixed_rotors.py` needs a concrete
  four-letter Grundstellung, so the missing fourth letter is brute-forced as 26
  separate message files rather than as a wildcard.
- `escombraSUR.sh`, `test_surI.sh` — drive the sweep over those variants.

The sweep came back **negative**; the outcome is recorded in the
`negative_results` field of `data/messages/SUR.json`. The 104 generated files
were deleted — regenerate them with these scripts if you want to re-run it.
