# data/lang/ — the Spanish corpus that scores decrypts

Three public-domain texts (Project Gutenberg), normalised to **A–Z**: accents
removed, Ñ→N, and **no spaces or punctuation**, because the plaintexts of the
traffic have none.

| file | work | letters |
|---|---|---|
| `es_lazarillo.txt` | *Lazarillo de Tormes* (anonymous, 1554) | 82,617 |
| `es_trafalgar.txt` | Benito Pérez Galdós, *Trafalgar* (1873), naval | 235,527 |
| `es_bailen.txt` | Benito Pérez Galdós, *Bailén* (1873), land war | 295,266 |

`python/lang_model.py` concatenates all three.

## Why outside text

A model built from the corpus's own plaintexts and used to find more of them
invites the charge of circularity; an earlier public text does not, and anyone
can rebuild it. It also works better. Margin of the worst of the six readings
over the 99th percentile of 3,000 random texts, with the model always built
without the message being scored:

    the corpus's own plaintexts    +0.021
    these three texts              +0.498

## What the choice rests on

Margins over five noise seeds:

| corpus | margin |
|---|---|
| *Lazarillo* (1554) | +0.448 ± 0.033 |
| *Bailén* (1873) | +0.459 ± 0.041 |
| all three | **+0.498 ± 0.032** |

The register of the text buys nothing measurable: at the level of trigrams,
Spanish is dominated by morphology and phonotactics (CION, ENTE, QUE, ADO,
LOS), the same in the sixteenth century as in the nineteenth. Joining the
texts helps because the margin is set by the worst message, and each text has
a different worst message (MNAS for *Lazarillo*, DHZB for *Bailén*).

A fourth text was measured and left out: Vicente Blasco Ibáñez, *Los cuatro
jinetes del Apocalipsis* (1916), 642,648 letters. Alone it gives
+0.177 ± 0.027; added to the three it lowers the margin to +0.350 ± 0.033. It
helps the four long messages and sinks the two short telegraphic ones (DHZB,
LUIS). A candidate text has to be measured against the worst message before it
is added.

## How much text

The margin flattens between 20,000 and 40,000 letters. These files hold
613,410.
