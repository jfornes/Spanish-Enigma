#!/usr/bin/env python3
"""lang_model.py -- how a candidate decrypt is judged to be Spanish.

The messages are short (eighty letters is common), telegraphic and padded with
W, and on such texts a statistic over the whole decrypt says little. The score
has three weighted terms, and a fourth is reported apart.

1. MAX TRIGRAM OVER AN EIGHT-LETTER WINDOW.
   The best eight-letter stretch, by mean smoothed trigram log-probability. A
   mean over the whole decrypt dilutes a short good stretch into nothing; a
   maximum finds it. Eight letters is the length at which a match stops being
   chance. On DHZB the winning window is OPORUNQU, across three word boundaries
   of OCHO POR UN QUINCE (tests/test_lang_model.py checks it).

2. THE SARMIENTO W RULE.
   The manual pads the last group of a paragraph with W, so a run of W should
   end on a multiple of four; in random text that happens a quarter of the
   time. The reading of DHZB has four runs and all four end on a multiple of
   four; the best noise candidate, none of four.

3. FRAGMENTS of military and naval Spanish (corpus_sweep.FRAG), at low weight.
   They carry LUIS, which has no W and a weak trigram score. DHZB, whose
   vocabulary (CORRIJA, PRIMERA, SERIE, GRUPO, ULTIMO, CATORCE) is not in the
   list, depends on the first two terms. No two of the three are enough.

4. RUNS OF W, reported apart and not weighted in: see RUN_EVIDENCE.

The index of coincidence is not part of the score: on eighty letters, among
millions of candidates, the largest IoC of a sweep is an order statistic and
not a reading.

The trigram model is built from data/lang/, public-domain Spanish prose with
no connection to this corpus; data/lang/README.md gives the measurements that
chose it.
"""
import math, os, re, unicodedata
from collections import Counter

A = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(_HERE, "..", "data", "lang")

WINDOW = 8          # letters; the length at which a match stops being chance
W_TRI = 1.00        # weight on the windowed trigram term
W_WRULE = 0.35      # weight on the Sarmiento W rule (alignment)
W_RUN = 0.00        # see RUN_EVIDENCE: reported separately, NOT folded in
W_FRAG = 0.020      # weight on the fragment score
SCALE = 100         # the caller wants an int

# Evidence carried by the LONGEST run of W, as a multiple of W_RUN. A single W
# is worth nothing: a wrong-key decrypt of 130 letters contains about five of
# them by chance. Two or three in a row is a different matter, because W is not
# a letter of Spanish, so a doubled W in a candidate plaintext cannot be text --
# it can only be padding, which is what the manual prescribes.
#
# MEASURED on 456,976 wrong-key decrypts of XMOT (n=132, all 17,576 rings of
# each of the 26 blocks, deliberately wrong wheel order):
#
#     a run of two or more W   17.51% of noise
#     a run of three or more    0.774% of noise
#
# Against that, the manual pads every paragraph end with one to three W, and
# four of the six readings carry a run of two or more. The likelihood ratios are
# therefore roughly 4 for a doubled W and 65 for a tripled one, and the values
# below are their logarithms, rounded down. They are deliberately blunt: the
# numerator rests on six messages and the rates depend on message length, so
# more precision here would be false precision.
RUN_EVIDENCE = {0: 0.0, 1: 0.0, 2: 1.3, 3: 4.2}     # longest run -> evidence
RUN_CAP = 3

# WHY W_RUN IS ZERO, AND THE TERM IS REPORTED SEPARATELY INSTEAD.
#
# This evidence is ONE-SIDED. A long run says the key is probably right; no run at
# all says nothing, because a message can simply have no paragraph end needing
# three letters of padding. LUIS has not one W in eighty letters and reads
# perfectly.
#
# A score does not have that asymmetry. Adding the term at weight 0.30 was
# measured over 62,400 candidates per message, with the correct arrangement:
#
#     XMOT   1 -> 1      MNAS   6 -> 1
#     DHZB  32 -> 1      MVNR   1 -> 1
#     LUIS  66 -> 477
#
# Four readings to first place, and the fifth pushed down by a factor of seven,
# for the only reason the term can push anything down: promoting the candidates
# that carry a W run demotes those that do not, and LUIS carries none. The
# ranking cannot express "strong evidence when present, no evidence when
# absent"; a second ranked list can. corpus_sweep therefore prints the ordinary
# ranking AND a ranking restricted to candidates carrying a run of two or more,
# where the true reading of all four W-bearing messages comes first. Nothing is
# traded away: a message with no W is unaffected, because it was never going to
# appear in the second list and its place in the first is unchanged.
#
# Set W_RUN nonzero to fold it in anyway; w_run() and w_run_batch() honour it.


def normalise(text):
    """A-Z only: accents stripped, N-tilde folded, spaces and punctuation gone.
    The last of those is not cosmetic. The plaintexts have no spaces, so a model
    built on spaced text and applied to unspaced text is worthless."""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("Ñ", "N").replace("ñ", "n")
    return "".join(c for c in t.upper() if c in A)


class LangModel:
    def __init__(self, corpus_path=None, extra_text=""):
        """corpus_path may be one file or a directory; the default is the whole
        of data/lang. All of it is concatenated; data/lang/README.md gives the
        measurements behind that choice."""
        import glob as _glob
        path = corpus_path or CORPUS_DIR
        files = ([path] if os.path.isfile(path)
                 else sorted(_glob.glob(os.path.join(path, "*.txt"))))
        text = ""
        for f in files:
            try:
                text += normalise(open(f, encoding="utf-8").read())
            except OSError:
                pass
        text += normalise(extra_text)
        self.sources = [os.path.basename(f) for f in files]
        if len(text) < 3:
            raise RuntimeError(
                f"language corpus empty or missing: {path}. It ships with the "
                f"repository; see data/lang/README.md.")
        self.n = len(text)
        self.tri, self.bi = Counter(), Counter()
        for i in range(self.n - 2):
            self.tri[text[i:i+3]] += 1
            self.bi[text[i:i+2]] += 1

    def window_trigram(self, s, k=WINDOW):
        """Best k-letter stretch, by mean smoothed trigram log-probability."""
        if len(s) < k:
            k = len(s)
        if k < 3:
            return -99.0
        tri, bi = self.tri, self.bi
        best = -99.0
        for i in range(len(s) - k + 1):
            w = s[i:i+k]
            v = sum(math.log((tri[w[j:j+3]] + 1) / (bi[w[j:j+2]] + 26))
                    for j in range(k - 2)) / (k - 2)
            if v > best:
                best = v
        return best

    @staticmethod
    def w_rule(s):
        """Fraction of W runs that end on a four-letter group boundary, which is
        what the Sarmiento manual prescribes. Returns 0.0 when there are no W
        runs at all: absence is not evidence either way (LUIS has none)."""
        runs = list(re.finditer(r"W+", s))
        if not runs:
            return 0.0
        return sum(1 for m in runs if m.end() % 4 == 0) / len(runs)

    @staticmethod
    def w_run(s):
        """Evidence from the LONGEST run of W. See RUN_EVIDENCE.

        One-sided on purpose: a long run is evidence that the key is right, and no
        run at all is not evidence that it is wrong. LUIS has no W in eighty
        letters and reads perfectly; MKCX has two singles and reads. The term
        can only add."""
        longest = max((len(m.group()) for m in re.finditer(r"W+", s)), default=0)
        return RUN_EVIDENCE[min(longest, RUN_CAP)]

    def score(self, s, frag=0, w_tri=W_TRI, w_wrule=W_WRULE, w_frag=W_FRAG,
              w_run=W_RUN):
        """Composite, as an int so it can stand in for a plain fragment score.

        `frag` is the fragment score, computed by the caller. The terms know
        different things and no two of them are enough:

          LUIS has no W at all and a weak trigram; the naval fragment list,
          domain knowledge a sixteenth-century novel cannot supply, carries it.
          Scored without the fragment term it falls to third.

          DHZB is the opposite. Its vocabulary matches nothing in the fragment
          list, which on its own puts the true reading below the noise; general
          Spanish and the W rule carry it."""
        return int(round(SCALE * (w_tri * self.window_trigram(s)
                                  + w_wrule * self.w_rule(s)
                                  + w_run * self.w_run(s)
                                  + w_frag * frag))) + 1000


    # ---------------- batch scoring, for use inside a sweep ----------------
    #
    # A sweep produces 17,576 candidates per ring block, too many for a Python
    # loop. These methods score every row of a (V, N) array of letter indices at
    # once, so the cut inside a block can be made on the language score itself
    # rather than on the index of coincidence.

    def _logtri(self):
        """26x26x26 of log((tri+1)/(bi+26)), built once and cached.

        The same smoothed quantity window_trigram computes one trigram at a
        time; laid out so a decrypt matrix can index it directly."""
        if getattr(self, "_lt", None) is None:
            import numpy as _np
            bi = _np.empty((26, 26), _np.float64)
            for i, a in enumerate(A):
                for j, b in enumerate(A):
                    bi[i, j] = self.bi[a + b] + 26
            tri = _np.empty((26, 26, 26), _np.float64)
            for i, a in enumerate(A):
                for j, b in enumerate(A):
                    for k, c in enumerate(A):
                        tri[i, j, k] = self.tri[a + b + c] + 1
            self._lt = _np.log(tri / bi[:, :, None]).astype(_np.float32).ravel()
        return self._lt

    def window_trigram_batch(self, out, k=WINDOW):
        """window_trigram for every row of an (V, N) array of letter indices.

        Returns a float32 vector of length V. Equivalent to calling
        window_trigram on each row; tests/test_lang_model.py checks that on
        real decrypts, which is the only guarantee worth having."""
        import numpy as _np
        V, N = out.shape
        kk = min(k, N)
        if kk < 3:
            return _np.full(V, -99.0, _np.float32)
        o = out.astype(_np.int32)
        idx = o[:, :-2] * 676 + o[:, 1:-1] * 26 + o[:, 2:]        # (V, N-2)
        lp = self._logtri()[idx]                                   # (V, N-2)
        m = kk - 2                                                 # trigrams per window
        cs = _np.concatenate([_np.zeros((V, 1), _np.float32),
                              _np.cumsum(lp, axis=1, dtype=_np.float32)], axis=1)
        sums = cs[:, m:] - cs[:, :-m]                              # every window
        return (sums.max(axis=1) / m).astype(_np.float32)

    @staticmethod
    def w_rule_batch(out):
        """w_rule for every row of an (V, N) array of letter indices.

        A run of W ends at position p when out[p-1] == W and out[p] != W; the
        rule asks that p be a multiple of four. Same definition as w_rule, and
        rows with no W run return 0.0 for the same reason."""
        import numpy as _np
        W = c2n_W = A.index("W")
        isw = (out == W)
        V, N = out.shape
        nxt = _np.concatenate([isw[:, 1:], _np.zeros((V, 1), bool)], axis=1)
        ends = isw & ~nxt                                          # last W of a run
        pos = _np.arange(1, N + 1)                                 # run ends AFTER this index
        good = (ends & (pos % 4 == 0)).sum(axis=1)
        total = ends.sum(axis=1)
        return _np.where(total > 0, good / _np.maximum(total, 1), 0.0).astype(_np.float32)

    @staticmethod
    def w_run_batch(out):
        """w_run for every row of an (V, N) array of letter indices."""
        import numpy as _np
        W = A.index("W")
        isw = (out == W)
        V, N = out.shape
        run = _np.zeros(V, _np.int16); cur = _np.zeros(V, _np.int16)
        for t in range(N):                       # N passes over V, not V loops
            cur = _np.where(isw[:, t], cur + 1, 0)
            run = _np.maximum(run, cur)
            if (run >= RUN_CAP).all(): 
                run[:] = _np.minimum(run, RUN_CAP); break
        run = _np.minimum(run, RUN_CAP)
        lut = _np.array([RUN_EVIDENCE[i] for i in range(RUN_CAP + 1)], _np.float32)
        return lut[run]

    def score_batch(self, out, frag=None,
                    w_tri=W_TRI, w_wrule=W_WRULE, w_frag=W_FRAG, w_run=W_RUN):
        """The composite of score(), for an (V, N) array of letter indices."""
        import numpy as _np
        tri = self.window_trigram_batch(out)
        wr = self.w_rule_batch(out)
        rn = self.w_run_batch(out)
        fr = _np.zeros(len(tri), _np.float32) if frag is None else _np.asarray(frag, _np.float32)
        return (SCALE * (w_tri * tri + w_wrule * wr + w_run * rn
                         + w_frag * fr)).astype(_np.float32) + 1000.0


_default = None


def default_model():
    """The shipped corpus, loaded once per process."""
    global _default
    if _default is None:
        _default = LangModel()
    return _default


def score(s, **kw):
    """Module-level convenience using the shipped corpus, loaded once."""
    return default_model().score(s, **kw)


if __name__ == "__main__":
    import sys, json, glob
    m = LangModel()
    print(f"corpus: {m.n:,} letters, {len(m.tri):,} distinct trigrams\n")
    print(f"{'message':8s} {'n':>4s} {'window trigram':>15s} {'W rule':>8s} {'score':>7s}")
    for f in sorted(glob.glob(os.path.join(_HERE, "..", "data", "messages", "*.json"))):
        d = json.load(open(f))
        for msg in (d if isinstance(d, list) else [d]):
            pt = (msg.get("solution") or {}).get("plaintext")
            if not pt:
                continue
            print(f"{os.path.basename(f)[:-5]:8s} {len(pt):4d} "
                  f"{m.window_trigram(pt):15.3f} {m.w_rule(pt):8.2f} "
                  f"{m.score(pt):7d}")
