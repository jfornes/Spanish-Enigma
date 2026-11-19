# data/messages/ — one file per message

Each file is one message: where it is, what the sheet looks like, the
cryptogram as typed, and, when it has been read, the key and the reading. The
files are meant to be cited and re-used on their own.

## Fields

| field | what it holds |
|---|---|
| `id` | the message's name: group 3 of its header, or the closing check reversed when the header is missing |
| `status` | `solved` (true/false) and a one-line `summary` |
| `classification` | `enigma_k`, `enigma_k_candidate` or `manual_worked_example` |
| `found_by` | who found the sheet, or the publication it comes from |
| `archive`, `signature` | where the document is |
| `sheet` | the physical sheet: the transmissions it carries and its receipt stamps |
| `date_transmission`, `date_interception`, `date_note` | the dates, and where each comes from |
| `sender`, `recipient` | as the transmission line or the clear preamble gives them |
| `preamble_clear` | text in clear before the cipher, where there is one |
| `header` | the four header groups as transmitted |
| `grundstellung` | the starting position, as transmitted (group 3) |
| `body` | the cryptogram as typed, in groups; passages sent in clear are marked `<PLAIN: ...>` |
| `garble_check` | the closing check (the starting position reversed); `garble_check_as_written` when the sheet differs from it |
| `reference` | the interceptor's reference |
| `n`, `ic` | enciphered letters (body less the check and the passages in clear), and index of coincidence |
| `notes` | what a reader needs to know about this message |
| `transcription` | doubtful letters and emendations against the original |
| `solution` | the key and the reading (below) |
| `divergences` | positions where the reading departs from the expected plaintext, and why |
| `negative_results` | searches that found nothing: what was swept, how it was scored, and what that means |
| `candidate` | a key that is reported but not counted as a reading |

## The key

All four-letter fields are in the order **U, L, M, R**: reflector, left,
middle, right.

| field | what it holds |
|---|---|
| `wiring` | a rotor set of `data/wirings/wirings.json` |
| `rotor_order` | rotors in the left, middle and right slots, e.g. `II-I-III` |
| `windows_ULMR` | group 3 as transmitted, read as the windows |
| `ringstellung_ULMR` | the Ringstellung those windows then require |
| `offsets_ULMR` | window minus Ringstellung: the rod positions, which a decrypt fixes |
| `plaintext` | the literal output of the key, letter for letter, garble included |
| `plaintext_emended` | where the source is damaged, the text with those positions emended |
| `reading` | the plaintext with word breaks; `[...]` marks letters that do not read or are restored, `«...»` a passage sent in clear |
| `command` | the search that recovers the key from the ciphertext |
| `verified_with` | the command that replays the reading from the stored key |

Under the reading of the header adopted in `wirings.json` (notch on the ring),
the stored Ringstellungen include a constant fixed for the period; the
decrypts are the same either way.

`tests/validate_messages.py` checks that every file follows this layout and that
every `plaintext` is what its key produces.
