#!/usr/bin/env python3
"""rods_frontend.py -- Python front-end for the C rod-search library (librods).

The front-end does I/O, JSON parsing, statistics (IoC) and orchestration; the C
library (librods.so/.dylib, POSIX pthreads) does the concurrent search. Two
search kernels are exposed:
  brute     -- exact-crib match over order x arrangement x UKW x 26^3 rings
               (the "click"/contradiction test, full enumeration).
  coupling  -- Turing's coupling method (Treatise Ch.IV pp.71-73): derive the
               per-stretch coupling involution from the crib and keep rod starts
               with no contradiction. Searches order x arrangement x RIGHT-wheel
               ring only -- it does NOT enumerate the L/M rings or the UKW.
Provenance of the methods is documented in rods.c.
"""
import sys, os, json, re, argparse, itertools, unicodedata, ctypes, subprocess, platform
import numpy as np
import rodslib

A="ABCDEFGHIJKLMNOPQRSTUVWXYZ"; c2n={c:i for i,c in enumerate(A)}
def _load_wirings():
    """Machine wirings from data/wirings/wirings.json (searched next to this file
    and at ../data/wirings/ for the repo layout) -- shared single source of truth
    with corpus_sweep.py; the C library receives these as parameters."""
    here=os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here,'wirings.json'),
                 os.path.join(here,'..','data','wirings','wirings.json'),
                 os.path.join(here,'data','wirings','wirings.json')):
        if os.path.exists(cand):
            with open(cand,encoding='utf-8') as fh: return json.load(fh)
    raise FileNotFoundError("wirings.json not found (looked next to the script and in ../data/wirings/)")
_WIR=_load_wirings()
WIRINGS={s:{r:d['wiring'] for r,d in rot.items()} for s,rot in _WIR['rotor_sets'].items()}
UKW=_WIR['ukw']; ETW=_WIR['etw']; WIN=_WIR['turnovers']
# Core-notch offsets (turnover fires when (window-ring)%26==offset). Only III is
# validated (22=W); I/II unknown -> -1 = fall back to window turnover. Keep in sync
# with corpus_sweep.NOTCH_OFFSET until wirings.json carries the field.
NOTCH_OFFSET={'III':22,'I':None,'II':None}
def _notchvec(): return np.array([NOTCH_OFFSET.get(k) if NOTCH_OFFSET.get(k) is not None else -1
                                  for k in ('I','II','III')], np.int32)
ORDERS=[(0,1,2),(0,2,1),(1,0,2),(1,2,0),(2,0,1),(2,1,0)]   # must match rods.c
NAMES=['I','II','III']
def vec(s): return np.array([c2n[c] for c in s], dtype=np.int32)
def perm(s):
    f=[c2n[c] for c in s]; r=[0]*26
    for i,v in enumerate(f): r[v]=i
    return f,r

# ---------- Python oracle (validated vs Enigma I) ----------
def py_windows_seq(order, windows, n):
    tM=c2n[WIN[order[1]]]; tR=c2n[WIN[order[2]]]; L,M,R=windows; seq=[]
    for _ in range(n):
        m=(M==tM); r=(R==tR)
        if m: M=(M+1)%26; L=(L+1)%26
        elif r: M=(M+1)%26
        R=(R+1)%26; seq.append((L,M,R))
    return seq
def py_encipher(wiring, order, windows, rings, u, text):
    W={k:perm(WIRINGS[wiring][k]) for k in('I','II','III')}
    lf,lr=W[order[0]]; mf,mr=W[order[1]]; rf,rr=W[order[2]]
    etwf,etwr=perm(ETW); ukwf,_=perm(UKW)
    seq=py_windows_seq(order,windows,len(text)); rL,rM,rR=rings; out=[]
    for t,ch in enumerate(text):
        L,M,R=seq[t]
        x=etwr[c2n[ch]]
        oR=(R-rR)%26; x=(rf[(x+oR)%26]-oR)%26
        oM=(M-rM)%26; x=(mf[(x+oM)%26]-oM)%26
        oL=(L-rL)%26; x=(lf[(x+oL)%26]-oL)%26
        x=(ukwf[(x+u)%26]-u)%26
        x=(lr[(x+oL)%26]-oL)%26; x=(mr[(x+oM)%26]-oM)%26; x=(rr[(x+oR)%26]-oR)%26
        out.append(A[etwf[x]])
    return ''.join(out)
def py_coupling_decode(wiring, order, windows, ringR, cipher_ints, crib, crib_off, lo, hi):
    """Derive per-stretch couplings from the crib, then decode positions [lo,hi)."""
    rf,rr=perm(WIRINGS[wiring][order[2]]); etwf,etwr=perm(ETW)
    seq=py_windows_seq(order, windows, max(hi, crib_off+len(crib)))
    rfwd=lambda o,x:(rf[(x+o)%26]-o)%26; rrev=lambda o,x:(rr[(x+o)%26]-o)%26
    coup={}
    for j,ch in enumerate(crib):
        t=crib_off+j; L,M,R=seq[t]; pair=coup.setdefault((M,L),[-1]*26)
        rho=(R-ringR)%26
        a=rfwd(rho,etwr[c2n[ch]]); b=rfwd(rho,etwr[cipher_ints[t]])
        if a==b: return None
        if pair[a]==-1 and pair[b]==-1: pair[a]=b; pair[b]=a
        elif pair[a]!=b: return None
    out=[]
    for t in range(lo,hi):
        L,M,R=seq[t]; pair=coup.get((M,L)); rho=(R-ringR)%26
        b=rfwd(rho,etwr[cipher_ints[t]])
        out.append(A[etwf[rrev(rho,pair[b])]] if (pair and pair[b]!=-1) else '?')
    return ''.join(out)
def py_link_decode(wiring, order, windows, ringR, ringM, cipher_ints, crib, crib_off, lo, hi):
    """Accumulate one involution P per left-window from the crib (cross-turnover
    linking, Turing pp.72-73), then decode positions [lo,hi)."""
    rf,rr=perm(WIRINGS[wiring][order[2]]); mf,mr=perm(WIRINGS[wiring][order[1]]); etwf,etwr=perm(ETW)
    seq=py_windows_seq(order, windows, max(hi, crib_off+len(crib)))
    at=lambda p,o,x:(p[(x+o)%26]-o)%26
    Pby={}
    for j,ch in enumerate(crib):
        t=crib_off+j; L,M,R=seq[t]; rho=(R-ringR)%26; mu=(M-ringM)%26
        a=at(rf,rho,etwr[c2n[ch]]); b=at(rf,rho,etwr[cipher_ints[t]])
        if a==b: return None
        AA=at(mf,mu,a); BB=at(mf,mu,b); P=Pby.setdefault(L,[-1]*26)
        if P[AA]==-1 and P[BB]==-1: P[AA]=BB; P[BB]=AA
        elif P[AA]!=BB: return None
    out=[]
    for t in range(lo,hi):
        L,M,R=seq[t]; rho=(R-ringR)%26; mu=(M-ringM)%26; P=Pby.get(L)
        b=at(rf,rho,etwr[cipher_ints[t]]); B=at(mf,mu,b)
        out.append(A[etwf[at(rr,rho,at(mr,mu,P[B]))]] if (P and P[B]!=-1) else '?')
    return ''.join(out)
def ioc(s):
    from collections import Counter
    n=len(s); c=Counter(s)
    return sum(v*(v-1) for v in c.values())/(n*(n-1)) if n>1 else 0.0

# ---------- C bridge ----------
def load_lib():
    """Return the librods CDLL with all kernels' argtypes configured. No auto-
    compilation: build with `make` and/or set SPANISH_ENIGMA_LIB (see rodslib.py)."""
    return rodslib.load()
def _call(fn, wiring, cipher, crib, crib_off, grund, all_arr, threads, stride):
    wfwd=np.concatenate([vec(WIRINGS[wiring][k]) for k in('I','II','III')]).astype(np.int32)
    etwf=vec(ETW); ukwf=vec(UKW); turn=vec(''.join(WIN[k] for k in('I','II','III')))
    ct=np.asarray(cipher,np.int32); cr=np.asarray(crib,np.int32); g=vec(grund)
    out=np.zeros(stride*8192,np.int32); P=lambda a:a.ctypes.data_as(ctypes.POINTER(ctypes.c_int))
    nt=_notchvec()
    nh=fn(P(wfwd),P(etwf),P(ukwf),P(turn),P(nt),P(ct),len(ct),P(cr),len(cr),crib_off,
          P(g),1 if all_arr else 0,threads,P(out),8192)
    return [tuple(int(x) for x in out[stride*i:stride*i+stride]) for i in range(nh)]
def brute(lib,*a):    return _call(lib.rod_search,*a,6)
def coupling(lib,*a): return _call(lib.coupling_search,*a,3)
def link(lib,*a):     return _call(lib.coupling_link_search,*a,4)
def sweep_offsets(lib, wiring, cipher, crib, grund, all_arr, threads):
    """Offsets where the crib is satisfiable (crib position unknown). Returns a
    list of offsets with multiplicity (one per consistent arrangement/ring)."""
    wfwd=np.concatenate([vec(WIRINGS[wiring][k]) for k in('I','II','III')]).astype(np.int32)
    etwf=vec(ETW); ukwf=vec(UKW); turn=vec(''.join(WIN[k] for k in('I','II','III')))
    ct=np.asarray(cipher,np.int32); cr=np.asarray(crib,np.int32); g=vec(grund)
    out=np.zeros(7*8192,np.int32); P=lambda x:x.ctypes.data_as(ctypes.POINTER(ctypes.c_int))
    nt=_notchvec()
    nh=lib.rod_search_sweep(P(wfwd),P(etwf),P(ukwf),P(turn),P(nt),P(ct),len(ct),P(cr),len(cr),
                            0,len(ct)-len(cr),P(g),1 if all_arr else 0,threads,P(out),8192)
    return [int(out[7*i]) for i in range(nh)]
def order_name(oi): return '-'.join(NAMES[w] for w in ORDERS[oi])
def arr_letters(ai, grund, all_arr):
    arr=[(a,b,d) for a in range(4) for b in range(4) for d in range(4) if len({a,b,d})==3] if all_arr else [(0,1,2)]
    return ''.join(grund[i] for i in arr[ai])

# ---------- corpus parsing ----------
def norm(s):
    return ''.join(ch for ch in unicodedata.normalize('NFKD',s).upper() if ch in A)
def get_cipher(msg):
    """Continuous cipher from EITHER schema: body_cipher_only (rods_frontend) or
    body (<PLAIN: ...> in-clear blocks + trailing garble, corpus_sweep)."""
    if msg.get('body_cipher_only'):
        return ''.join(c for c in msg['body_cipher_only'].upper() if c in A)
    raw=re.sub(r'<PLAIN:.*?>','', msg.get('body') or '', flags=re.S)
    c=''.join(ch for ch in raw.upper() if ch in A)
    gc=''.join(ch for ch in (msg.get('garble_check') or (msg.get('grundstellung') or '')[::-1]).upper() if ch in A)
    if gc and c.endswith(gc): c=c[:-len(gc)]
    return c
def load_message(path,picker=None):
    data=json.load(open(path))
    if isinstance(data,dict): data=[data]
    for m in data:
        if (picker is None or picker in str(m.get('signature','')) or picker==m.get('grundstellung')) \
           and (m.get('body_cipher_only') or m.get('body')): return m
    return data[0]
def build_cribs(msg):
    cipher=get_cipher(msg); al=msg.get('plaintext_cipher_alignment') or {}
    cribs=[]; off=0
    for key in sorted(k for k in al if k.startswith('block_')):
        b=al[key]; clen=b['cipher_letters']
        np_=norm(re.sub(r'\[.*?\]','',b.get('plaintext_before_break') or b.get('plaintext_to_end') or ''))
        if len(np_)==clen: cribs.append((off,np_))
        off+=clen
    return cipher, msg.get('grundstellung'), cribs

# ---------- help ----------
def usage(parser):
    parser.print_help()
    print("""
Examples:
  python3 rods_frontend.py soler_terminus_mvnr.json
  python3 rods_frontend.py soler_terminus_mvnr.json --method link --all
  python3 rods_frontend.py corpus.json --picker MVNR --wirings D,F --threads 8

Notes:
  * The message (cipher, Grundstellung, plaintext/cipher block alignment) is read
    from the JSON; nothing about the message is hard-coded.
  * 'link'     = coupling method with cross-turnover linking: recovers ringR AND
                 ringM and reads plaintext past the turnover (Turing pp.72-73).
  * 'coupling' = per-stretch coupling consistency (recovers ringR only).
  * 'brute'    = full (ring+UKW) exact-crib enumeration.
  * Wiring tables D and F are built in; add 'C' to WIRINGS once it is known.""")

def main():
    p=argparse.ArgumentParser(description="Rod/coupling crib search for unsteckered Enigma K.",
                              add_help=True)
    p.add_argument("json", nargs='?', help="corpus JSON with body_cipher_only + plaintext_cipher_alignment")
    p.add_argument("--picker", help="select a message by signature substring or Grundstellung")
    p.add_argument("--method", choices=["link","coupling","brute"], default="link")
    p.add_argument("--all", action="store_true", help="sweep all 24 Grundstellung arrangements")
    p.add_argument("--threads", type=int, default=os.cpu_count())
    p.add_argument("--wirings", default="D,F")
    p.add_argument("--crib", help="known-plaintext crib; its offset is found by sweep (robust to cipher edits)")
    a=p.parse_args()
    if not a.json: usage(p); sys.exit(0)
    lib=load_lib()

    # ---- positive controls: C kernels must match the validated Python oracle ----
    pt="ATACARALAMANECERPOSICIONESENEMIGASALSURDEPALMA"   # 46 letters
    win=(c2n['V'],c2n['N'],c2n['R']); rings=(3,7,11); u=c2n['Q']
    cti=vec(py_encipher('F',('I','II','III'),win,rings,u,pt))
    seq=py_windows_seq(('I','II','III'),win,len(pt))
    bnd=next((t for t in range(1,len(pt)) if seq[t][:2]!=seq[t-1][:2]), len(pt))  # first stretch end
    b=brute(lib,'F',cti,vec(pt[:30]),0,"VNRM",False,a.threads)
    okb=any((ai,oi,uu,rl,rm,rr)==(0,0,u,3,7,11) for (ai,oi,uu,rl,rm,rr) in b)
    clen=12                                                       # short crib, well inside stretch 1
    cc=coupling(lib,'F',cti,vec(pt[:clen]),0,"VNRM",False,a.threads)
    okc=any((ai,oi)==(0,0) and rR==rings[2] for (ai,oi,rR) in cc)
    dec=py_coupling_decode('F',('I','II','III'),win,rings[2],list(cti),pt[:clen],0,clen,bnd)
    extra=sum(1 for d in (dec or '') if d!='?')
    beyond_ok = dec is not None and all(d=='?' or d==pt[clen+i] for i,d in enumerate(dec)) and extra>0
    print(f"[control] brute kernel    == oracle: {okb}")
    print(f"[control] coupling kernel == oracle: {okc}")
    print(f"[control] {clen}-letter crib -> coupling reads {extra} further letters: '{dec}'  (plain '{pt[clen:bnd]}')")
    ll=link(lib,'F',cti,vec(pt[:25]),0,"VNRM",False,a.threads)
    okl=len(ll)==1 and (ll[0]==(0,0,rings[2],rings[1]))           # unique, both rings pinned
    full=py_link_decode('F',('I','II','III'),win,rings[2],rings[1],list(cti),pt[:25],0,0,len(pt))
    full_ok = full is not None and all(d=='?' or d==pt[i] for i,d in enumerate(full)) and sum(d!='?' for d in full)>=44
    print(f"[control] link kernel pins both rings uniquely: {okl}  -> {ll}")
    print(f"[control] link reads FULL message from 25-letter crib: {full_ok}")
    # external regression vectors that EXERCISE the QWERTZ ETW (Enigma I does not):
    #   manual example = wiring F; Hörenberg LRS10 = wiring D (real message).
    manF=py_encipher('F',('II','III','I'),(c2n['N'],c2n['A'],c2n['S']),(c2n['D'],c2n['R'],c2n['R']),
                     (c2n['M']-c2n['Q'])%26,"ENEMIGOCARECEMUNICIONESAPRESEMOSLE")
    extF=sum(x==y for x,y in zip(manF,"RCHBFZZKNVJXTUAYNZKWRUHCHPSXKKWLZM"))>=33
    LRS="OHACIPLYXTSIHJSBJCZXWYXPJJMUIWYFGVHTMALUTAEAVXHRXVQWDRVJKIMCYFRODNBXDISWSDIYXFJWVKHQHQMKZT"
    extD=py_encipher('D',('II','I','III'),(c2n['Y'],c2n['A'],c2n['O']),(0,0,7),
                     (c2n['W']-c2n['A'])%26,LRS).startswith("RADIOSDEBENREGRESARA")
    print(f"[control] external vector: manual wiring F (>=33/34): {extF}")
    print(f"[control] external vector: LRS10 wiring D (real msg): {extD}")
    if not (okb and okc and beyond_ok and okl and full_ok and extF and extD):
        sys.exit("CONTROL FAILED -- do not trust results")

    # ---- real message ----
    msg=load_message(a.json,a.picker); cipher,grund,cribs=build_cribs(msg); cti=vec(cipher)
    print(f"\n# {msg.get('signature','?')}  G={grund}  cipher_len={len(cipher)}")
    print(f"# IoC (computed here) = {ioc(cipher):.4f}  (JSON quotes {msg.get('ic')})")
    if a.crib:                                          # --crib overrides alignment; offset by sweep
        crib=norm(a.crib); from collections import Counter; offs=[]
        for w in a.wirings.split(','):
            offs+=sweep_offsets(lib,w,cti,vec(crib),grund,a.all,a.threads)
        if not offs: sys.exit(f"crib '{crib}' not found at any offset (check spelling / --wirings)")
        off=Counter(offs).most_common(1)[0][0]; cribs=[(off,crib)]
        print(f"# crib '{crib}' located @offset {off} by sweep")
    if not cribs: sys.exit("no cleanly-aligned crib block")
    off,crib=max(cribs,key=lambda z:len(z[1]))
    print(f"# crib @offset {off} ({len(crib)}): {crib}")
    print(f"# method={a.method}  arrangements={'all 24' if a.all else 'canonical'}  threads={a.threads}\n")
    for w in a.wirings.split(','):
        if a.method=="brute":
            hits=brute(lib,w,cti,vec(crib),off,grund,a.all,a.threads)
            print(f"wiring {w}: {len(hits)} exact match(es)")
            for ai,oi,uu,rl,rm,rr in hits[:8]:
                print(f"    start={arr_letters(ai,grund,a.all)} UKW={A[uu]} order={order_name(oi)} rings=({rl},{rm},{rr})")
        elif a.method=="coupling":
            hits=coupling(lib,w,cti,vec(crib),off,grund,a.all,a.threads)
            print(f"wiring {w}: {len(hits)} coupling-consistent rod start(s)")
            for ai,oi,rR in hits[:8]:
                start=arr_letters(ai,grund,a.all)
                windows=tuple(c2n[ch] for ch in start)
                read=py_coupling_decode(w,tuple(NAMES[x] for x in ORDERS[oi]),windows,rR,
                                        list(cti),crib,off,off,min(len(cipher),off+len(crib)+12))
                print(f"    start={start} order={order_name(oi)} rightRing={A[rR]}  reads: {read}")
        else:  # link
            hits=link(lib,w,cti,vec(crib),off,grund,a.all,a.threads)
            print(f"wiring {w}: {len(hits)} (ringR,ringM)-consistent setting(s)")
            for ai,oi,rR,rM in hits[:8]:
                start=arr_letters(ai,grund,a.all); windows=tuple(c2n[ch] for ch in start)
                read=py_link_decode(w,tuple(NAMES[x] for x in ORDERS[oi]),windows,rR,rM,
                                    list(cti),crib,off,off,min(len(cipher),off+len(crib)+20))
                print(f"    start={start} order={order_name(oi)} ringR={A[rR]} ringM={A[rM]}  reads: {read}")
        if not hits: print("    -> none")

if __name__=="__main__":
    main()
