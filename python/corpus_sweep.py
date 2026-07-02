#!/usr/bin/env python3
"""
corpus_sweep.py -- Caja 745 sweep with the CORRECTED-ETW Enigma K engine.

Two modes:
  (default)  ciphertext-only IoC (Index of Coincidence) + Spanish-fragment ranking.
  --crib STR exact known-plaintext crib-drag: finds the exact key (wiring, order,
             arrangement, Ringstellung, offset) reproducing STR, then prints the
             full decryption.

Message hygiene applied automatically:
  * <PLAIN: ...> blocks are removed (sent in clear, machine paused -> not cipher).
  * a trailing garble group equal to the reversed Grundstellung / garble_check
    is stripped (it is the in-clear garble check, not ciphertext).

Usage:
  python3 corpus_sweep.py tots.json --procs 8
  python3 corpus_sweep.py tots.json --procs 8 --all --wirings D,F
  python3 corpus_sweep.py tots.json --picker XMOT --crib PRECAUCIONES --procs 8
"""
import json, re, argparse, itertools, unicodedata, multiprocessing as mp
import os, platform, subprocess, ctypes
import numpy as np

A="ABCDEFGHIJKLMNOPQRSTUVWXYZ"; c2n={c:i for i,c in enumerate(A)}
WIRINGS={
 'D':{'I':"CIAHFQOYBXNUWJLVGEMSZKPDTR",'II':"KEDXVBSQHNCZTRUFLOAYWIPMJG",'III':"NUJPHWFMGDOBAVZQTXECLKYSIR"},
 'F':{'I':"HFOTWPDURMCGXJLQEIVZSKBNAY",'II':"MUHTASIPJYNCVKLOXFDZEGQBWR",'III':"DKWOJVUNGLFTZCSYIBEARHXQPM"},
}
UKW="IMETCGFRAYSQBZXWLHKDVUPOJN"; ETW="QWERTZUIOASDFGHJKPYXCVBNML"; WIN={'I':'Y','II':'E','III':'N'}
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
    """Load librods, compiling it from rods.c on first use. Returns the CDLL or
    None if no compiler / source is available (caller then falls back to numpy)."""
    name='librods.dylib' if platform.system()=='Darwin' else 'librods.so'
    here=os.path.dirname(os.path.abspath(__file__)); path=os.path.join(here,name)
    src=os.path.join(here,'rods.c')
    try:
        if not os.path.exists(path):
            if not os.path.exists(src): return None
            flag=['-dynamiclib','-arch','x86_64','-arch','arm64'] if platform.system()=='Darwin' else ['-shared','-fPIC']
            subprocess.check_call(['cc','-O3','-Wall',*flag,'-o',path,src,'-lpthread'])
        lib=ctypes.CDLL(path); P=ctypes.POINTER(ctypes.c_int); ci=ctypes.c_int
        lib.rod_search_sweep.argtypes=[P,P,P,P, P,ci, P,ci, ci,ci, P,ci,ci, P,ci]
        lib.rod_search_sweep.restype=ci
        return lib
    except Exception as e:
        print(f"[C bridge unavailable: {e} -> numpy fallback]"); return None
def crib_search_c(lib, wiring, ct, crib, grund, all_arr, threads):
    """Exact crib-drag over ALL offsets in C. Returns hits as
    (off, ai, oi, ukw_off, ringL, ringM, ringR)."""
    wfwd=np.concatenate([vec(WIRINGS[wiring][k]) for k in ('I','II','III')]).astype(np.int32)
    etwf=vec(ETW); ukwf=vec(UKW); turn=vec(''.join(WIN[k] for k in ('I','II','III')))
    ctn=np.asarray(ct,np.int32); crn=np.asarray(crib,np.int32); g=vec(grund)
    n=len(ctn); off_hi=n-len(crn)
    out=np.zeros(7*8192,np.int32); P=lambda arr: arr.ctypes.data_as(ctypes.POINTER(ctypes.c_int))
    nh=lib.rod_search_sweep(P(wfwd),P(etwf),P(ukwf),P(turn),P(ctn),n,P(crn),len(crn),
                            0,off_hi,P(g),1 if all_arr else 0,threads,P(out),8192)
    return [tuple(int(x) for x in out[7*i:7*i+7]) for i in range(nh)]

def posseq(order, windows, n):
    tM=c2n[WIN[order[1]]]; tR=c2n[WIN[order[2]]]; L,M,R=windows; s=[]
    for _ in range(n):
        if M==tM: M=(M+1)%26; L=(L+1)%26
        elif R==tR: M=(M+1)%26
        R=(R+1)%26; s.append((L,M,R))
    return s
def fscore(s): return sum(s.count(f)*len(f) for f in FRAG)

def decode_all(wiring, order, windows, uwin, rings, ct):
    W={k:perm(WIRINGS[wiring][k]) for k in('I','II','III')}
    lf,lr=W[order[0]]; mf,mr=W[order[1]]; rf,rr=W[order[2]]
    seq=posseq(order, windows, len(ct)); ru,rl,rm,rrr=rings; out=[]
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
    wiring, order, windows, uwin, ct_list, topk = task
    ct=np.array(ct_list); N=len(ct); W={k:perm(WIRINGS[wiring][k]) for k in('I','II','III')}
    lf,lr=W[order[0]]; mf,mr=W[order[1]]; rf,rr=W[order[2]]; seq=posseq(order,windows,N)
    g=np.arange(26); RL,RM,RR=(z.ravel() for z in np.meshgrid(g,g,g,indexing='ij')); V=RL.size
    out=np.empty((V,N),np.int8); u=uwin    # UKW ring fixed (gauge-equiv. to left ring while left rotor static); use --crib for full 26^4
    for t in range(N):
        L,M,R=seq[t]; oL=(L-RL)%26; oM=(M-RM)%26; oR=(R-RR)%26
        x=ETWR[int(ct[t])]
        x=(rf[(x+oR)%26]-oR)%26; x=(mf[(x+oM)%26]-oM)%26; x=(lf[(x+oL)%26]-oL)%26
        x=(UKWF[(x+u)%26]-u)%26
        x=(lr[(x+oL)%26]-oL)%26; x=(mr[(x+oM)%26]-oM)%26; x=(rr[(x+oR)%26]-oR)%26
        out[:,t]=ETWF[x]
    cnt=np.zeros((V,26),np.int32)
    for k in range(26): cnt[:,k]=(out==k).sum(1)
    io=(cnt*(cnt-1)).sum(1)/(N*(N-1)); idx=np.argpartition(io,-40)[-40:]; res=[]
    for i in idx:
        txt=''.join(A[v] for v in out[i])
        res.append((float(io[i]),fscore(txt),wiring,'-'.join(order),
                    (0,int(RL[i]),int(RM[i]),int(RR[i])),txt))
    res.sort(key=lambda z:(z[1],z[0]),reverse=True); return res[:topk]

# ---- crib mode worker ----
def crib_worker(task):
    wiring, order, windows, uwin, ct_list, crib_list = task
    ct=np.array(ct_list); cb=np.array(crib_list); cl=len(cb); N=len(ct)
    W={k:perm(WIRINGS[wiring][k]) for k in('I','II','III')}
    lf,lr=W[order[0]]; mf,mr=W[order[1]]; rf,rr=W[order[2]]; seq=posseq(order,windows,N)
    g=np.arange(26); RU,RL,RM,RR=(z.ravel() for z in np.meshgrid(g,g,g,g,indexing='ij')); V=RU.size
    hits=[]
    for off in range(0,N-cl+1):
        surv=np.arange(V)
        for j in range(cl):
            t=off+j; L,M,R=seq[t]
            u=(uwin-RU[surv])%26; oL=(L-RL[surv])%26; oM=(M-RM[surv])%26; oR=(R-RR[surv])%26
            x=ETWR[int(ct[t])]
            x=(rf[(x+oR)%26]-oR)%26; x=(mf[(x+oM)%26]-oM)%26; x=(lf[(x+oL)%26]-oL)%26
            x=(UKWF[(x+u)%26]-u)%26
            x=(lr[(x+oL)%26]-oL)%26; x=(mr[(x+oM)%26]-oM)%26; x=(rr[(x+oR)%26]-oR)%26
            surv=surv[ETWF[x]==cb[j]]
            if surv.size==0: break
        for i in surv:
            hits.append((wiring,'-'.join(order),windows,uwin,off,
                         (int(RU[i]),int(RL[i]),int(RM[i]),int(RR[i]))))
    return hits

def build_tasks(ct, grund, all_arr, wirings, extra):
    gl=[c2n[c] for c in grund]; arrs=list(itertools.permutations(range(4),3)) if all_arr else [(0,1,2)]
    tasks=[]
    for w in wirings:
        for order in itertools.permutations(['I','II','III']):
            for arr in arrs:
                windows=(gl[arr[0]],gl[arr[1]],gl[arr[2]]); uwin=gl[[i for i in range(4) if i not in arr][0]]
                tasks.append((w,order,windows,uwin,ct)+extra)
    return tasks

def parse_body(m):
    """Return (cipher, plains). Accepts EITHER schema: body_cipher_only (the
    continuous cipher, rods_frontend) or body (with <PLAIN: ...> in-clear blocks
    and a trailing garble group, corpus_sweep). <PLAIN> blocks are removed from
    the cipher and recorded with their offset for display; the garble group
    (garble_check / reversed Grundstellung) is stripped."""
    if m.get('body_cipher_only'):                                 # rods_frontend schema
        return ''.join(c for c in m['body_cipher_only'].upper() if c in A), []
    parts=re.split(r'<PLAIN:(.*?)>', m.get('body') or '', flags=re.S)
    body=''; plains=[]
    for i,seg in enumerate(parts):
        if i%2==0: body+=''.join(c for c in seg.upper() if c in A)
        else: plains.append((len(body),' '.join(seg.split())))
    gc=''.join(c for c in (m.get('garble_check') or (m.get('grundstellung') or '')[::-1]).upper() if c in A)
    if gc and body.endswith(gc): body=body[:-len(gc)]         # drop in-clear garble check
    return body, plains

def norm(s):
    s=unicodedata.normalize('NFKD', s or '')
    return ''.join(c for c in s.upper() if c in A)

def crib_from_alignment(m):
    """If the message carries a plaintext_cipher_alignment (rods_frontend schema),
    return the longest clean 1:1 block as a crib (uppercase A-Z); else ''."""
    al=m.get('plaintext_cipher_alignment') or {}; best=''
    for k in sorted(x for x in al if x.startswith('block_')):
        b=al[k]; clen=b.get('cipher_letters')
        pt=norm(re.sub(r'\[.*?\]','', b.get('plaintext_before_break') or b.get('plaintext_to_end') or ''))
        if clen and len(pt)==clen and len(pt)>len(best): best=pt
    return best

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
    ap.add_argument("--crib",help="known-plaintext fragment -> exact crib-drag + full decode")
    ap.add_argument("--engine",choices=["c","py"],default="c",
                    help="crib search backend: c=librods (pthreads, default), py=numpy")
    a=ap.parse_args()
    data=json.load(open(a.json));  data=[data] if isinstance(data,dict) else data
    wl=a.wirings.split(','); crib0=''.join(c for c in (a.crib or '').upper() if c in A)
    for m in data:
        if a.picker and a.picker not in (str(m.get('grundstellung'))+str(m.get('signature',''))): continue
        grund=m.get('grundstellung'); body,plains=parse_body(m)
        crib=crib0 or crib_from_alignment(m)        # fall back to the in-JSON alignment crib
        if not grund or len(grund)!=4 or len(body)<(len(crib) if crib else a.min_n):
            if not a.picker: print(f"[skip] G={grund} class={m.get('classification')} n={len(body)}")
            continue
        ct=[c2n[c] for c in body]
        if crib:
            print(f"\n=== {m.get('classification')}  G={grund}  n={len(body)}  CRIB '{crib}' "
                  f"arr={'all24' if a.all else 'canonical'} engine={a.engine} wirings={wl} ===")
            cb=[c2n[c] for c in crib]
            arrlist=([(p,q,r) for p in range(4) for q in range(4) for r in range(4) if len({p,q,r})==3]
                     if a.all else [(0,1,2)])
            hits=[]                                    # unified: (w, order, windows, uwin, off, rings)
            lib=load_lib() if a.engine=='c' else None
            if a.engine=='c' and lib is None: a.engine='py'
            if a.engine=='c':
                for w in wl:
                    for off,ai,oi,u,rL,rM,rR in crib_search_c(lib,w,ct,cb,grund,a.all,a.procs):
                        triple=arrlist[ai]; miss=[i for i in range(4) if i not in triple][0]
                        uwin=c2n[grund[miss]]                      # 4th Grund letter = UKW window
                        windows=tuple(c2n[grund[i]] for i in triple)
                        hits.append((w,ORDERS[oi],windows,uwin,off,((uwin-u)%26,rL,rM,rR)))
            else:                                                  # numpy fallback
                tasks=build_tasks(ct,grund,a.all,wl,(cb,))
                with mp.Pool(a.procs) as p:
                    for sub in p.map(crib_worker,tasks):
                        for w,order,windows,uwin,off,rings in sub:
                            hits.append((w,tuple(order.split('-')),windows,uwin,off,rings))
            print(f"exact matches: {len(hits)}")
            # A crib pins only the per-wheel OFFSETS over its own span, not the
            # absolute window/ring split. Because turnovers key off the ABSOLUTE
            # window, the surviving settings decode identically across the crib but
            # differ OUTSIDE it. So rank the exact matches by the residual IoC of the
            # decrypt outside the crib (higher = more Spanish-like = better key;
            # Spanish ~0.075, random ~0.038), and flag the one using the standard
            # indicator arrangement -- (L,M,R)=grund[0,1,2], UKW=grund[3] -- because
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
            for w,order,windows,uwin,off,rings in hits:
                full=decode_all(w,order,windows,uwin,rings,ct)
                if full in seen: continue                          # dedupe gauge-equivalent hits
                seen.add(full)
                canon=(windows==canon_win and uwin==canon_u)
                ranked.append((_resioc(full,off,len(cb)),canon,w,order,windows,uwin,off,rings,full))
            ranked.sort(key=lambda z:z[0],reverse=True)            # most readable first
            for rank,(rio,canon,w,order,windows,uwin,off,rings,full) in enumerate(ranked,1):
                start=''.join(A[x] for x in (uwin,)+windows)
                tag=' [canonical arrangement]' if canon else ''
                print(f"  #{rank}  resIoC={rio:.4f}  wiring {w} order {'-'.join(order)} "
                      f"windows(U,L,M,R)={start} Ringstellung(U,L,M,R)={''.join(A[x] for x in rings)} off={off}{tag}")
                print(f"  DECODE: {render(full,plains)}")
            if not hits: print("  -> no exact match (check crib spelling / transcription / dedupe repeats)")
        else:
            print(f"\n=== {m.get('classification')}  G={grund}  n={len(body)}  "
                  f"arr={'all24' if a.all else 'canonical'} wirings={wl} ===")
            tasks=build_tasks(ct,grund,a.all,wl,(a.top,))
            with mp.Pool(a.procs) as p: allr=[r for sub in p.map(ioc_worker,tasks) for r in sub]
            allr.sort(key=lambda z:(z[1],z[0]),reverse=True)
            for io,fs,w,order,rings,txt in allr[:a.top]:
                print(f"  IoC={io:.4f} frag={fs:3d} wiring {w} order {order:<10} "
                      f"rings(U,L,M,R)={''.join(A[x] for x in rings)}\n     {txt}")

if __name__=="__main__":
    main()
