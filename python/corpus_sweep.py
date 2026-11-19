#!/usr/bin/env python3
"""
corpus_sweep.py -- the key search for Enigma K messages.

Two modes:
  (default)   blind search: every Ringstellung, for each wiring, rotor order and
              arrangement of the header letters, scored as Spanish
              (python/lang_model.py). Prints the best candidates and, apart,
              the candidates that carry a run of W.
  --crib STR  crib-drag: every key that turns some stretch of the ciphertext
              into STR, with the full decrypt.

Before the attack, passages sent in clear (<PLAIN: ...>) are removed, and the
closing group is stripped when it is the garble check (the starting position
reversed).

Usage, from the repository root:
  python3 python/corpus_sweep.py data/messages/XMOT.json --crib MOVIMIENTOBARCOS --wirings F
  python3 python/corpus_sweep.py data/messages/DHZB.json --wirings F
  python3 python/corpus_sweep.py data/messages/DHZB.json --wirings D,F --all
      (--all: all 24 arrangements of the header letters, not only the manual's)
"""
import json, re, argparse, itertools, unicodedata, multiprocessing as mp
import os, platform, subprocess, ctypes
import numpy as np
import rodslib
import sarmiento          # the manual's rules; see its docstring
import lang_model        # how a decrypt is scored as Spanish; see its docstring

A="ABCDEFGHIJKLMNOPQRSTUVWXYZ"; c2n={c:i for i,c in enumerate(A)}
def _load_wirings():
    """Machine wirings from data/wirings/wirings.json (searched next to this file
    and at ../data/wirings/ for the repo layout). Single source of truth for rotor
    wirings, ETW, UKW and turnovers; the C library receives these as parameters, so
    this one file feeds both the numpy and the C engines."""
    here=os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here,'wirings.json'),
                 os.path.join(here,'..','data','wirings','wirings.json'),
                 os.path.join(here,'data','wirings','wirings.json')):
        if os.path.exists(cand):
            with open(cand,encoding='utf-8') as fh: return json.load(fh)
    raise FileNotFoundError("wirings.json not found (looked next to the script and in ../data/wirings/)")
_WIR=_load_wirings()
WIRINGS={s:{r:d['wiring'] for r,d in rot.items()} for s,rot in _WIR['rotor_sets'].items()}
# Mixed sets: rotor I from one set, II from another, III from a third, named by the
# three letters in rotor order ('DFF' = I from D, II and III from F). A mixed name
# can be passed to --wirings like 'D' or 'F'. Built at import, so that worker
# processes -- forked or spawned -- all have them.
_SETS=sorted(WIRINGS)
for _c in __import__('itertools').product(_SETS, repeat=3):
    if len(set(_c))>1:
        WIRINGS[''.join(_c)]={'I':WIRINGS[_c[0]]['I'],'II':WIRINGS[_c[1]]['II'],'III':WIRINGS[_c[2]]['III']}
MIXED=[k for k in WIRINGS if len(k)==3]
UKW=_WIR['ukw']; ETW=_WIR['etw']; WIN=_WIR['turnovers']
NAMES=['I','II','III']
FRAG=["DE","LA","EN","QUE","EL","LOS","LAS","POR","CON","UNA","PARA","SOBRE","MENTE","CION",
      "ENTE","ADO","ENEMIG","FUERZA","ORDEN","BALEARES","PALMA","MALLORCA","MANDO","BUQUE",
      "CRUCERO","COLUMNA","POSICION","ATAQUE","ACCION","PRECAUCION","NACIONAL","GENERAL"]
def perm(s):
    f=np.array([c2n[c] for c in s]); r=np.empty(26,int); r[f]=np.arange(26); return f,r
ETWF,ETWR=perm(ETW); UKWF,_=perm(UKW)

# wheel orderings into (L,M,R) slots -- MUST match ORDERS[] in rods.c
ORDERS=[('I','II','III'),('I','III','II'),('II','I','III'),
        ('II','III','I'),('III','I','II'),('III','II','I')]

# ---------- C bridge (librods.so / .dylib, POSIX pthreads) ----------
def vec(s): return np.array([c2n[c] for c in s], np.int32)
def load_lib():
    """Return the librods CDLL (kernel argtypes are configured in librods.load),
    or None so the caller falls back to the numpy engine. No autocompilation:
    build with `make` and/or set SPANISH_ENIGMA_LIB (see rodslib.py)."""
    try:
        return rodslib.load()
    except Exception as e:
        print(f"[C bridge unavailable: {e} -> numpy fallback]"); return None
def crib_search_c(lib, wiring, ct, crib, grund, all_arr, threads, nov=None):
    """Exact crib-drag over ALL offsets in C. Returns hits as
    (off, ai, oi, ukw_off, ringL, ringM, ringR)."""
    wfwd=np.concatenate([vec(WIRINGS[wiring][k]) for k in ('I','II','III')]).astype(np.int32)
    etwf=vec(ETW); ukwf=vec(UKW); turn=vec(''.join(WIN[k] for k in ('I','II','III')))
    ctn=np.asarray(ct,np.int32); crn=np.asarray(crib,np.int32); g=vec(grund)
    nt=notches(wiring,nov)
    notch=np.array([nt.get(k) if nt.get(k) is not None else -1
                    for k in ('I','II','III')], np.int32)   # core offsets, -1 = turnover at the window letter
    n=len(ctn); off_hi=n-len(crn)
    out=np.zeros(7*8192,np.int32); P=lambda arr: arr.ctypes.data_as(ctypes.POINTER(ctypes.c_int))
    nh=lib.rod_search_sweep(P(wfwd),P(etwf),P(ukwf),P(turn),P(notch),P(ctn),n,P(crn),len(crn),
                            0,off_hi,P(g),1 if all_arr else 0,threads,P(out),8192)
    return [tuple(int(x) for x in out[7*i:7*i+7]) for i in range(nh)]

# Turnover offsets: a rotor carries its left neighbour on when
# (window - ring) % 26 equals its offset. The values are data, read from
# data/wirings/wirings.json, block "stepping", which also states the reading of
# the header they stand for and the messages each was measured on. A rotor whose
# offset is null there (I) turns over at its window letter (WIN).
#
# Each rotor steps by the offsets of its own set. They are measured on wiring F;
# wiring D has none (null), so its rotors turn over at their window letters, as
# the "condition" in wirings.json says and as the one real message on D, LRS10,
# requires (tests/lrs10_control.py). A mixed set ('DFF') takes each rotor's rule
# from that rotor's set.
def _load_core_notches(default={'III': 22, 'II': 15, 'I': None}, measured_set='F'):
    try:
        n = _WIR['stepping']['core_notches'][measured_set]
    except (KeyError, TypeError):
        return dict(default)                       # older wirings.json: keep the built-ins
    return {w: (int(n[w]) % 26 if n.get(w) is not None else None) for w in NAMES}
NOTCH_OFFSET = _load_core_notches()
# The other sets, read the same way. F is always NOTCH_OFFSET itself, so the tools
# that override or rebind it (enigma_k --notch, buttonup) still act.
NOTCH_BY_SET = {s: {w: (int(v[w]) % 26 if v.get(w) is not None else None) for w in NAMES}
                for s, v in ((_WIR.get('stepping') or {}).get('core_notches') or {}).items()}
SET_OF = {}   # a wiring registered under another name ('_MIX'): its three set letters

def notches(wiring='F', nov=None):
    """Core offset of each rotor (None = turnover at its window letter) for a wiring:
    a set ('D', 'F'), a mixed set ('DFF': I from D, II and III from F), or a name
    registered in SET_OF. An unknown name gets the F offsets. nov overrides it per
    rotor ({'III': 22}, {'II': None}): --notch and --sweep-turnover pass it."""
    sets = SET_OF.get(wiring, wiring)
    if len(sets) == 1: sets = sets * 3
    if len(sets) != 3: nt = dict(NOTCH_OFFSET)
    else: nt = {w: (NOTCH_OFFSET.get(w) if sets[i] == 'F'
                    else NOTCH_BY_SET.get(sets[i], {}).get(w)) for i, w in enumerate(NAMES)}
    if nov: nt.update(nov)
    return nt

def parse_notch(spec):
    """--notch 'III=22,II=15' (rod position of each rotor's turnover) or 'III=N'
    (window letter: turnover at that letter whatever the ring) or 'none' (every
    rotor at its window letter). Returns the override for notches(), or None."""
    if not spec: return None
    if spec.strip().lower() == 'none': return {w: None for w in NAMES}
    nov = {}
    for part in spec.split(','):
        w, _, v = part.partition('='); w = w.strip().upper(); v = v.strip().upper()
        if w not in NAMES or not v: raise SystemExit(f"--notch wants ROTOR=OFFSET or ROTOR=LETTER (got {part!r})")
        if v.isdigit(): nov[w] = int(v) % 26
        elif len(v) == 1 and v in A: WIN[w] = v; nov[w] = None
        else: raise SystemExit(f"--notch: bad value {v!r}")
    return nov

def turnover_variants(order, mode, base=None):
    """The stepping overrides a sweep tries for one rotor order. mode None: only
    base (the values of wirings.json, or --notch). 'right': the right rotor's turnover
    at each of the 26 rod positions. 'middle': the same for the middle rotor.
    'both': the 676 combinations. The first variant is always base itself, so a
    sweep never loses the default reading."""
    base = dict(base or {})
    out = [base]
    slots = {'right': [2], 'middle': [1], 'both': [1, 2]}.get(mode, [])
    if not slots: return out
    import itertools as _it
    for vals in _it.product(range(26), repeat=len(slots)):
        v = dict(base); v.update({order[k]: vals[i] for i, k in enumerate(slots)})
        if v != base: out.append(v)
    return out

def nov_label(nov):
    return '' if not nov else '[' + ','.join(f"{k}={'win' if v is None else v}" for k, v in sorted(nov.items())) + ']'

# How many candidates of each of the 26 ring blocks go on to the full composite
# score. The cut is made on the windowed trigram, over all 17,576 candidates of
# the block. A negative from a blind sweep therefore means: no candidate among
# the best KEEP_PER_BLOCK of any block, by windowed trigram, scored well on the
# composite. (Ranked by index of coincidence instead, the true reading of MNAS
# is 116th in its own block.)
KEEP_PER_BLOCK = 400

def posseq(order, windows, n, rings=None, wiring='F', nov=None):
    L,M,R=windows; s=[]
    if rings is None:                                   # turnover at a window letter
        tM=c2n[WIN[order[1]]]; tR=c2n[WIN[order[2]]]
        for _ in range(n):
            if M==tM: M=(M+1)%26; L=(L+1)%26
            elif R==tR: M=(M+1)%26
            R=(R+1)%26; s.append((L,M,R))
    else:                                               # core-based: (window - ring) == notch_offset
        rl,rm,rr=rings                                  # (L,M,R) rings
        nt=notches(wiring,nov); nM=nt.get(order[1]); nR=nt.get(order[2])
        tM=c2n[WIN[order[1]]]; tR=c2n[WIN[order[2]]]    # window letter where no core offset is known
        for _ in range(n):
            mAt=((M-rm)%26==nM) if nM is not None else (M==tM)
            rAt=((R-rr)%26==nR) if nR is not None else (R==tR)
            if mAt: M=(M+1)%26; L=(L+1)%26
            elif rAt: M=(M+1)%26
            R=(R+1)%26; s.append((L,M,R))
    return s
def fscore(s): return sum(s.count(f)*len(f) for f in FRAG)

_LM=None
def _lm():
    """The language model, loaded once per worker process.

    Built lazily rather than at import so that a run which never reaches the
    blind path -- a crib search, or --help -- does not pay for reading the
    corpus, and so that multiprocessing forks do not each carry a copy made
    before the fork."""
    global _LM
    if _LM is None: _LM=lang_model.default_model()
    return _LM

def decode_all(wiring, order, windows, uwin, rings, ct, nov=None):
    W={k:perm(WIRINGS[wiring][k]) for k in('I','II','III')}
    lf,lr=W[order[0]]; mf,mr=W[order[1]]; rf,rr=W[order[2]]
    ru,rl,rm,rrr=rings; seq=posseq(order, windows, len(ct), (rl,rm,rrr), wiring, nov); out=[]
    for t in range(len(ct)):
        L,M,R=seq[t]; u=(uwin-ru)%26; oL=(L-rl)%26; oM=(M-rm)%26; oR=(R-rrr)%26
        x=ETWR[int(ct[t])]
        x=(rf[(x+oR)%26]-oR)%26; x=(mf[(x+oM)%26]-oM)%26; x=(lf[(x+oL)%26]-oL)%26
        x=(UKWF[(x+u)%26]-u)%26
        x=(lr[(x+oL)%26]-oL)%26; x=(mr[(x+oM)%26]-oM)%26; x=(rr[(x+oR)%26]-oR)%26
        out.append(A[ETWF[x]])
    return ''.join(out)

# ---- IoC mode worker ----
def ioc_worker(task):
    """Blind sweep over the ring space for one (wiring, order, arrangement).

    The space is cut into 26 blocks of 17,576 ring settings. In each block every
    decrypt gets the windowed trigram score (lang_model.window_trigram_batch),
    and the best KEEP_PER_BLOCK go on to the composite score of lang_model,
    which adds the W rule and the fragment count. The index of coincidence is
    reported but not used to cut: on messages of eighty letters it ranks true
    readings too low (data/messages/DHZB.json, negative_results).

    Each block computes the stepping from one ring, Lv: the middle ring when the
    middle rotor has a core offset, otherwise the right ring. When both stepping
    rotors have one (with the offsets in wirings.json, the orders with rotor I
    on the left) that stepping is approximate, so the survivors of the block are
    decoded again, exactly, with their own four rings before they are scored,
    ranked and printed. The cut that picks them still sees the approximate text.
    """
    wiring, order, windows, uwin, ct_list, topk, *rest = task
    nov = rest[0] if rest else None
    ct=np.array(ct_list); N=len(ct); W={k:perm(WIRINGS[wiring][k]) for k in('I','II','III')}
    lf,lr=W[order[0]]; mf,mr=W[order[1]]; rf,rr=W[order[2]]
    g=np.arange(26); RU,RL,Ro=(z.ravel() for z in np.meshgrid(g,g,g,indexing='ij')); V=RU.size
    nt = notches(wiring, nov)
    mid_off = nt.get(order[1]) is not None   # middle core-notch -> stepping depends on RM
    # Both stepping rotors carry a core offset: the block below computes the
    # stepping from Lv alone, so the survivors are decoded again with their
    # own four rings before they are scored (see the docstring).
    both = mid_off and nt.get(order[2]) is not None
    res=[]
    for Lv in range(26):     # Lv is RM if mid_off else RR (the ring that drives the stepping)
        if mid_off: seq=posseq(order,windows,N,(0,Lv,0),wiring,nov); RMc=Lv; RRc=Ro
        else:       seq=posseq(order,windows,N,(0,0,Lv),wiring,nov); RRc=Lv; RMc=Ro
        out=np.empty((V,N),np.int8)
        for t in range(N):
            L,M,R=seq[t]; oL=(L-RL)%26; oM=(M-RMc)%26; oR=(R-RRc)%26; u=(uwin-RU)%26
            x=ETWR[int(ct[t])]
            x=(rf[(x+oR)%26]-oR)%26; x=(mf[(x+oM)%26]-oM)%26; x=(lf[(x+oL)%26]-oL)%26
            x=(UKWF[(x+u)%26]-u)%26
            x=(lr[(x+oL)%26]-oL)%26; x=(mr[(x+oM)%26]-oM)%26; x=(rr[(x+oR)%26]-oR)%26
            out[:,t]=ETWF[x]
        cnt=np.zeros((V,26),np.int32)
        for k in range(26): cnt[:,k]=(out==k).sum(1)
        io=(cnt*(cnt-1)).sum(1)/(N*(N-1))
        # The cut is made on the windowed trigram, computed on the whole block;
        # KEEP_PER_BLOCK bounds how many survivors get the full composite score
        # (W rule and fragments as well). The index of coincidence is not used
        # to cut: see the docstring.
        tri=_lm().window_trigram_batch(out)
        k=min(KEEP_PER_BLOCK,V); idx=np.argpartition(tri,-k)[-k:]
        sub=out[idx]
        if both:
            sub=np.array([[c2n[ch] for ch in decode_all(
                    wiring,order,windows,uwin,(int(RU[i]),int(RL[i]),Lv,int(Ro[i])),ct,nov)]
                    for i in idx],np.int8)
            c2=np.zeros((len(idx),26),np.int32)
            for k_ in range(26): c2[:,k_]=(sub==k_).sum(1)
            io=io.copy(); io[idx]=(c2*(c2-1)).sum(1)/(N*(N-1))
        texts=[''.join(A[v] for v in row) for row in sub]
        sc=_lm().score_batch(sub,frag=np.array([fscore(t) for t in texts],np.float32))
        run=[max((len(r) for r in re.findall(r'W+',t)),default=0) for t in texts]
        for j,i in enumerate(idx):
            rmv=Lv if mid_off else int(Ro[i]); rrv=int(Ro[i]) if mid_off else Lv
            res.append((float(io[i]),float(sc[j]),wiring+nov_label(nov),'-'.join(order),
                        (int(RU[i]),int(RL[i]),rmv,rrv),texts[j],run[j]))
    res.sort(key=lambda z:(z[1],z[0]),reverse=True); return res[:topk]

# ---- crib mode worker ----
def crib_worker(task):
    """Drag a crib along the message and keep every ring setting that produces it.

    The stepping depends on the rings of the rotors that carry a core offset,
    and those rings are what this function sweeps, so they sit in an outer loop
    and everything inside it is vectorised. The number of candidates is 26^4
    either way. Two stepping rotors with core offsets (the orders with rotor I
    on the left) are handled exactly."""
    wiring, order, windows, uwin, ct_list, crib_list, *rest = task
    nov = rest[0] if rest else None
    ct=np.array(ct_list); cb=np.array(crib_list); cl=len(cb); N=len(ct)
    W={k:perm(WIRINGS[wiring][k]) for k in('I','II','III')}
    lf,lr=W[order[0]]; mf,mr=W[order[1]]; rf,rr=W[order[2]]
    nt=notches(wiring,nov); nM=nt.get(order[1]); nR=nt.get(order[2])
    # Only a wheel with a core notch makes the stepping depend on its ring; one
    # whose notch is unknown falls back to the window letter and is ring-free.
    mRange=range(26) if nM is not None else (0,)
    rRange=range(26) if nR is not None else (0,)
    g=np.arange(26); RU,RL,RM,RR=(z.ravel() for z in np.meshgrid(g,g,g,g,indexing='ij')); V=RU.size
    hits=[]
    for sM in mRange:
        for sR in rRange:
            # Inside this block the stepping is fixed, so restrict the sweep to
            # the ring values consistent with it.
            keep=np.ones(V,bool)
            if nM is not None: keep &= (RM==sM)
            if nR is not None: keep &= (RR==sR)
            base=np.flatnonzero(keep)
            if base.size==0: continue
            seq=posseq(order,windows,N,(0,sM,sR),wiring,nov)
            for off in range(0,N-cl+1):
                surv=base
                for j in range(cl):
                    t=off+j; L,M,R=seq[t]
                    u=(uwin-RU[surv])%26; oL=(L-RL[surv])%26
                    oM=(M-RM[surv])%26; oR=(R-RR[surv])%26
                    x=ETWR[int(ct[t])]
                    x=(rf[(x+oR)%26]-oR)%26; x=(mf[(x+oM)%26]-oM)%26; x=(lf[(x+oL)%26]-oL)%26
                    x=(UKWF[(x+u)%26]-u)%26
                    x=(lr[(x+oL)%26]-oL)%26; x=(mr[(x+oM)%26]-oM)%26; x=(rr[(x+oR)%26]-oR)%26
                    surv=surv[ETWF[x]==cb[j]]
                    if surv.size==0: break
                for i in surv:
                    hits.append((wiring,'-'.join(order),windows,uwin,off,
                                 (int(RU[i]),int(RL[i]),int(RM[i]),int(RR[i])),nov))
    return hits

def build_tasks(ct, grund, all_arr, wirings, extra, date=None):
    """Enumerate (wiring, order, arrangement) tasks for a blind sweep.

    Ordered by the manual, not narrowed by it. Sarmiento's rules predict that
    the transmitted group gives the windows (reflector, left, middle, right)
    and that the rotor order is fixed for a period (II-I-III in December 1936).
    grund arrives here as sarmiento.kernel_indicator() of the transmitted group,
    so arrangement (0,1,2) is that prediction. The predicted case goes first and
    every other case is still enumerated: the space searched is the same, and
    the answer usually comes up to 24 times sooner on arrangements and 6 times
    on orders."""
    gl=[c2n[c] for c in grund]
    arrs=sarmiento.arrangements() if all_arr else [(0,1,2)]
    tasks=[]
    for w in wirings:
        for order in sarmiento.wheel_orders(date):
            for arr in arrs:
                windows=(gl[arr[0]],gl[arr[1]],gl[arr[2]]); uwin=gl[[i for i in range(4) if i not in arr][0]]
                tasks.append((w,order,windows,uwin,ct)+extra)
    return tasks

def parse_body(m):
    """Return (cipher, plains) from a message's body. <PLAIN: ...> passages
    are removed from the cipher and recorded with their offset for display;
    the closing garble check is stripped."""
    raw=m.get('body') or ''
    parts=re.split(r'<PLAIN:(.*?)>', raw, flags=re.S)
    body=''; plains=[]
    for i,seg in enumerate(parts):
        if i%2==0: body+=''.join(c for c in seg.upper() if c in A)
        else: plains.append((len(body),' '.join(seg.split())))
    # The closing garble check is sent in clear and is not ciphertext. Three
    # forms are tried: the group as the sheet types it (garble_check_as_written,
    # when the typist slipped: LUIS has SIVL for SIUL), the stated value, and
    # the starting position reversed, which is what Sarmiento's rule 3 prescribes.
    for gc in (m.get('garble_check_as_written'), m.get('garble_check'),
               (m.get('grundstellung') or '')[::-1]):
        gc=''.join(c for c in (gc or '').upper() if c in A)
        if gc and body.endswith(gc): body=body[:-len(gc)]; break
    return body, plains

def norm(s):
    s=unicodedata.normalize('NFKD', s or '')
    return ''.join(c for c in s.upper() if c in A)


def render(dec, plains):
    out=''; prev=0
    for off,txt in plains: out+=dec[prev:off]+f" «{txt}» "; prev=off
    return out+dec[prev:]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("--procs",type=int,default=8)
    ap.add_argument("--all",action="store_true"); ap.add_argument("--wirings",default="D,F")
    ap.add_argument("--top",type=int,default=3); ap.add_argument("--min-n",type=int,default=40)
    ap.add_argument("--picker",help="select message by Grundstellung or signature substring")
    ap.add_argument("--grund",help="override the Grundstellung, for a message whose header "
                    "does not carry one (SUR). In a BLIND sweep the choice is immaterial: "
                    "the ring sweep covers the whole offset space, so any fixed window is "
                    "equivalent to any other. It is NOT immaterial with --crib, which pins "
                    "the windows and solves for rings.")
    ap.add_argument("--crib",help="known-plaintext fragment -> exact crib-drag + full decode")
    ap.add_argument("--engine",choices=["c","py"],default="c",
                    help="crib search backend: c=librods (pthreads, default), py=numpy")
    ap.add_argument("--notch",help="stepping of each rotor, overriding wirings.json: "
                    "'III=22,II=15' (rod position at which the rotor carries its neighbour), "
                    "'III=N' (window letter, whatever the ring) or 'none' (every rotor at its "
                    "window letter). Default: the values of wirings.json")
    ap.add_argument("--sweep-turnover",choices=["right","middle","both"],
                    help="also try the turnover of the right rotor ('right'), of the middle one "
                    "('middle') or of both at each of the 26 rod positions. wirings.json fixes "
                    "them for the traffic of December 1936; a message of another period, with "
                    "another Ringstellung, may turn over elsewhere. 'right' costs 26 times the "
                    "default, 'both' 676. Default: off")
    a=ap.parse_args()
    base_nov=parse_notch(a.notch)
    data=json.load(open(a.json));  data=[data] if isinstance(data,dict) else data
    wl=a.wirings.split(','); crib0=''.join(c for c in (a.crib or '').upper() if c in A)
    for m in data:
        if a.picker and a.picker not in (str(m.get('grundstellung'))+str(m.get('signature',''))): continue
        grund=a.grund or m.get('grundstellung'); body,plains=parse_body(m); gshow=grund
        if grund and len(grund)==4: grund=sarmiento.kernel_indicator(grund)  # kernels index (L,M,R,U); see sarmiento.kernel_indicator
        crib=crib0
        if not grund or len(grund)!=4 or len(body)<(len(crib) if crib else a.min_n):
            if not a.picker: print(f"[skip] G={gshow} class={m.get('classification')} n={len(body)}")
            continue
        ct=[c2n[c] for c in body]
        if crib:
            print(f"\n=== {m.get('classification')}  G={gshow}  n={len(body)}  CRIB '{crib}' "
                  f"arr={'all24' if a.all else 'canonical'} engine={a.engine} wirings={wl} ===")
            cb=[c2n[c] for c in crib]
            arrlist=([(p,q,r) for p in range(4) for q in range(4) for r in range(4) if len({p,q,r})==3]
                     if a.all else [(0,1,2)])
            hits=[]                                    # unified: (w, order, windows, uwin, off, rings)
            lib=load_lib() if a.engine=='c' else None
            if a.engine=='c' and lib is None: a.engine='py'
            if a.engine=='c':
                # The kernel takes one offset per rotor (I, II, III), not per slot, so
                # a sweep varies one rotor at a time ('right'/'middle': 78 calls,
                # which covers that rotor in whichever slot it sits) or two ('both').
                vlist=[base_nov]
                if a.sweep_turnover:
                    import itertools as _it
                    k=2 if a.sweep_turnover=='both' else 1
                    for ws in _it.combinations(NAMES,k):
                        for vals in _it.product(range(26),repeat=k):
                            v=dict(base_nov or {}); v.update(dict(zip(ws,vals))); vlist.append(v)
                for w in wl:
                    for nov in vlist:
                        for off,ai,oi,u,rL,rM,rR in crib_search_c(lib,w,ct,cb,grund,a.all,a.procs,nov):
                            triple=arrlist[ai]; miss=[i for i in range(4) if i not in triple][0]
                            uwin=c2n[grund[miss]]                      # 4th Grund letter = UKW window
                            windows=tuple(c2n[grund[i]] for i in triple)
                            hits.append((w,ORDERS[oi],windows,uwin,off,((uwin-u)%26,rL,rM,rR),nov))
            else:                                                  # numpy fallback
                tasks=[t+(v,) for t in build_tasks(ct,grund,a.all,wl,(cb,),date=m.get('date_transmission'))
                       for v in turnover_variants(t[1],a.sweep_turnover,base_nov)]
                with mp.Pool(a.procs) as p:
                    for sub in p.map(crib_worker,tasks):
                        for w,order,windows,uwin,off,rings,nov in sub:
                            hits.append((w,tuple(order.split('-')),windows,uwin,off,rings,nov))
            print(f"exact matches: {len(hits)}")
            # A crib pins only the per-wheel OFFSETS over its own span, not the
            # absolute window/ring split. Because turnovers key off the ABSOLUTE
            # window, the surviving settings decode identically across the crib but
            # differ OUTSIDE it. So rank the exact matches by the residual IoC of the
            # decrypt outside the crib (higher = more Spanish-like = better key;
            # Spanish ~0.075, random ~0.038), and flag the one using the standard
            # indicator arrangement -- windows = the transmitted group (U,L,M,R), i.e.
            # (L,M,R)=grund[0,1,2], UKW=grund[3] on the kernel rotation -- because
            # that convention is the real tie-breaker for the TRUE key: a non-canonical
            # arrangement can read marginally cleaner by coincidence of turnover
            # placement, so IoC alone may not point at the historically-correct key.
            from collections import Counter as _Ctr
            def _resioc(dec, off, clen):                            # IoC outside the crib span
                s=[dec[i] for i in range(len(dec)) if not (off<=i<off+clen)]
                if len(s)<2: return 0.0
                cnt=_Ctr(s); return sum(v*(v-1) for v in cnt.values())/(len(s)*(len(s)-1))
            canon_win=tuple(c2n[grund[i]] for i in (0,1,2)); canon_u=c2n[grund[3]]
            ranked=[]; seen=set()
            for w,order,windows,uwin,off,rings,nov in hits:
                full=decode_all(w,order,windows,uwin,rings,ct,nov)
                if full in seen: continue                          # dedupe gauge-equivalent hits
                seen.add(full)
                canon=(windows==canon_win and uwin==canon_u)
                ranked.append((_resioc(full,off,len(cb)),canon,w+nov_label(nov),order,windows,uwin,off,rings,full))
            ranked.sort(key=lambda z:z[0],reverse=True)            # most readable first
            for rank,(rio,canon,w,order,windows,uwin,off,rings,full) in enumerate(ranked,1):
                start=''.join(A[x] for x in (uwin,)+windows)
                tag=' [canonical arrangement]' if canon else ''
                print(f"  #{rank}  resIoC={rio:.4f}  wiring {w} order {'-'.join(order)} "
                      f"windows(U,L,M,R)={start} Ringstellung(U,L,M,R)={''.join(A[x] for x in rings)} off={off}{tag}")
                print(f"  DECODE: {render(full,plains)}")
            if not hits: print("  -> no exact match (check crib spelling / transcription / dedupe repeats)")
        else:
            print(f"\n=== {m.get('classification')}  G={gshow}  n={len(body)}  "
                  f"arr={'all24' if a.all else 'canonical'} wirings={wl} ===")
            # Each worker returns POOL candidates, not a.top. a.top is how many
            # are printed; the pool is what the W-run list is drawn from, and a
            # run of two or more turns up in about a sixth of noise, so drawing
            # it from a handful would show a handful of noise and hide the point.
            POOL=max(a.top,400)
            tasks=[t+(v,) for t in build_tasks(ct,grund,a.all,wl,(POOL,),date=m.get('date_transmission'))
                   for v in turnover_variants(t[1],a.sweep_turnover,base_nov)]
            with mp.Pool(a.procs) as p: allr=[r for sub in p.map(ioc_worker,tasks) for r in sub]
            allr.sort(key=lambda z:(z[1],z[0]),reverse=True)
            def show(rows):
                for io,sc,w,order,rings,txt,run in rows:
                    flag=f" W{run}" if run>=2 else "   "
                    print(f"  score={sc:7.1f} IoC={io:.4f}{flag} wiring {w} order {order:<10} "
                          f"rings(U,L,M,R)={''.join(A[x] for x in rings)}\n     {txt}")
            show(allr[:a.top])
            # SECOND LIST: candidates carrying a run of two or more W. W is not a
            # letter of Spanish, so a doubled W cannot be text -- it can only be
            # the padding Sarmiento prescribes. Measured on 456,976 wrong-key
            # decrypts, a run of three occurs in 0.77% of them. This evidence is
            # one-sided and so cannot be folded into the ranking without demoting
            # messages that legitimately have no W at all (LUIS): see the note at
            # lang_model.RUN_EVIDENCE. It is shown instead.
            wr=sorted((r for r in allr if r[6]>=2),
                      key=lambda z:(min(z[6],lang_model.RUN_CAP),z[1]),reverse=True)
            # Sorted by RUN LENGTH (capped at RUN_CAP) and then by score. Sorting this
            # list by score would defeat it: a run of two turns up in about a
            # sixth of noise and a run of three in under one per cent, so a
            # high-scoring W2 would bury a W3, which is the rarer event by two
            # orders of magnitude and the one worth looking at.
            hist={k:sum(1 for r in allr if min(r[6],9)==k) for k in range(2,4)}
            hist[4]=sum(1 for r in allr if r[6]>=4)
            print(f"\n  -- W runs among {len(allr)} candidates: "
                  f"WW {hist[2]} ({100.0*hist[2]/max(len(allr),1):.1f}%, noise ~17%)  "
                  f"WWW {hist[3]} ({100.0*hist[3]/max(len(allr),1):.2f}%, noise ~0.8%)  "
                  f"WWWW+ {hist[4]} --")
            if wr: show(wr[:a.top])
            else:  print("     none.")

if __name__=="__main__":
    main()
