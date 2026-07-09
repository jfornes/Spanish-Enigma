/* rods.c  -- concurrent rod/click crib search for unsteckered Enigma K.
 *
 * ARCHITECTURE
 *   Python front-end owns I/O, JSON, statistics (IoC) and orchestration.
 *   This C library owns the parallel search. Concurrency = POSIX pthreads only
 *   (no OpenMP, no MPI), so it builds the same on Linux and macOS.
 *
 * METHOD (provenance)
 *   The kernel is the "click" / contradiction test from
 *     A. M. Turing, *Treatise on the Enigma* ("Prof's Book"), c.1940, Ch. IV
 *     ("Single-wheel processes (Unsteckered Enigma)"), pp. 71-73.
 *   A candidate configuration that reproduces every crib letter has ZERO
 *   contradictions (= the strongest possible chain of clicks). We test the crib
 *   letter by letter and abandon a configuration at the first contradiction.
 *   The wheel substitution is held as Turing's "rod square" (offset x contact
 *   lookup tables), built once. Stepping is A27: turnover keyed to the WINDOW
 *   letter, ring-independent (Turing pp. 4-5; Soler/Lopez-Brea/Weierud 2010).
 *
 * SCOPE / HONESTY
 *   NOT yet implemented: the coupling propagation past a turnover (Turing
 *   pp. 72-73) that lets rodding AVOID enumerating the Ringstellung. This kernel
 *   still enumerates the Ringstellung+UKW grid, but with the click early-exit
 *   and threads. The engine matches the validated Python oracle bit-for-bit
 *   (see the front-end's positive control) -- the brief's precondition before
 *   optimizing.
 */
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

#define AL 26
#define MAXSTEP 1024

/* the six orderings of wheels {I,II,III} into (left,mid,right) slots */
static const int ORDERS[6][3] = {{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};

typedef struct {
    int rodfwd[3][AL][AL];   /* rod square (forward) : wheel, offset, contact -> out */
    int rodrev[3][AL][AL];   /* rod square (return path) */
    int ukwat[AL][AL];       /* reflector at UKW offset u */
    int etwf[AL], etwr[AL];  /* entry wheel forward / inverse */
    int turn[3];             /* window turnover letter per wheel (I,II,III) */
    int notch[3];            /* core-notch OFFSET per wheel, or -1 = fall back to window turnover */
    const int *cipher; int n;
    const int *crib; int crib_len, crib_off;
    int off_lo, off_hi;          /* crib-offset sweep range (rod_search_sweep) */
    int grund[4];
    int arr[24][3]; int narr;   /* arrangements: indices into grund for (L,M,R) */
    int *out; int max_hits; int nhits;
    int nthreads;
    pthread_mutex_t lock;
} Ctx;

/* modp(x): x mod 26, forced non-negative (C's % yields negatives for negative x). */
static int modp(int x){ x%=AL; return x<0?x+AL:x; }

/* build_rods: precompute Turing's "rod squares" once per search. For each wheel w
 * and every core offset o, tabulate rodfwd[w][o][x] = the wheel permutation as seen
 * at that offset (the wiring conjugated by the shift o) and rodrev = its inverse;
 * likewise ukwat[u] for the reflector at offset u, plus the ETW forward/inverse
 * maps. This reduces the inner crib test to pure array lookups (no arithmetic). */
static void build_rods(Ctx *c, const int *wfwd, const int *etw_fwd,
                       const int *ukw_fwd, const int *turn) {
    for (int w=0; w<3; w++) {
        int fwd[AL], rev[AL];
        for (int i=0;i<AL;i++) fwd[i]=wfwd[w*AL+i];
        for (int i=0;i<AL;i++) rev[fwd[i]]=i;
        for (int o=0;o<AL;o++)
            for (int x=0;x<AL;x++) {
                c->rodfwd[w][o][x] = modp(fwd[(x+o)%AL]-o);
                c->rodrev[w][o][x] = modp(rev[(x+o)%AL]-o);
            }
        c->turn[w]=turn[w];
    }
    for (int u=0;u<AL;u++)
        for (int x=0;x<AL;x++)
            c->ukwat[u][x] = modp(ukw_fwd[(x+u)%AL]-u);
    for (int i=0;i<AL;i++){ c->etwf[i]=etw_fwd[i]; c->etwr[etw_fwd[i]]=i; }
}

/* posseq: fill Lp/Mp/Rp[0..upto) with the (left,mid,right) WINDOW letters at each
 * keystroke, from start windows Lw/Mw/Rw and the mid/right turnover letters tM/tR.
 * A27 stepping: a wheel turns when its WINDOW reaches its turnover letter (ring-
 * independent); the middle wheel double-steps. Rings are applied later as offsets. */
static void __attribute__((unused)) posseq(int Lw,int Mw,int Rw,int tM,int tR,int upto,
                   int *Lp,int *Mp,int *Rp){
    int L=Lw,M=Mw,R=Rw;
    for (int t=0;t<upto;t++){
        int m=(M==tM), r=(R==tR);
        if (m){ M=(M+1)%AL; L=(L+1)%AL; }
        else if (r){ M=(M+1)%AL; }
        R=(R+1)%AL;
        Lp[t]=L; Mp[t]=M; Rp[t]=R;
    }
}

/* posseq_off: like posseq but the turnover is CORE-based -- a wheel steps when its
 * OFFSET (window-ring) reaches the notch offset nM/nR. Falls back to the window
 * turnover (tM/tR) for any wheel whose notch offset is <0 (not yet determined).
 * Since the RIGHT turnover now depends on rR, callers must recompute this per rR. */
static void posseq_off(int Lw,int Mw,int Rw,int tM,int tR,int nM,int nR,int rM,int rR,int upto,
                       int *Lp,int *Mp,int *Rp){
    int L=Lw,M=Mw,R=Rw;
    for (int t=0;t<upto;t++){
        int m = (nM>=0) ? (modp(M-rM)==nM) : (M==tM);
        int r = (nR>=0) ? (modp(R-rR)==nR) : (R==tR);
        if (m){ M=(M+1)%AL; L=(L+1)%AL; }
        else if (r){ M=(M+1)%AL; }
        R=(R+1)%AL;
        Lp[t]=L; Mp[t]=M; Rp[t]=R;
    }
}

typedef struct { Ctx *c; int tid; } Targ;   /* per-thread arg: shared context + thread id */

/* worker (for rod_search): each thread strides over the outer units
 * arrangement x order x UKW-offset; for each it sweeps all 26^3 L/M/R ring settings
 * and runs the crib "click" test -- decrypt every crib letter, and the first letter
 * that fails to reproduce the crib is a contradiction (abandon this setting). A
 * setting with zero contradictions is recorded (under the mutex) as a hit. */
static void *worker(void *p){
    Targ *ta=(Targ*)p; Ctx *c=ta->c;
    int upto=c->crib_off+c->crib_len;
    int Lp[MAXSTEP],Mp[MAXSTEP],Rp[MAXSTEP];
    long total=(long)c->narr*6*AL;           /* outer units: arrangement x order x UKW */
    for (long idx=ta->tid; idx<total; idx+=c->nthreads){
        int u=idx%AL; long q=idx/AL;
        int oi=q%6; int ai=q/6;
        int Lw=c->grund[c->arr[ai][0]], Mw=c->grund[c->arr[ai][1]], Rw=c->grund[c->arr[ai][2]];
        int wL=ORDERS[oi][0], wM=ORDERS[oi][1], wR=ORDERS[oi][2];
        for (int rR=0;rR<AL;rR++){
            posseq_off(Lw,Mw,Rw,c->turn[wM],c->turn[wR],c->notch[wM],c->notch[wR],0,rR,upto,Lp,Mp,Rp);
            for (int rL=0;rL<AL;rL++)
            for (int rM=0;rM<AL;rM++){
                int ok=1;
                for (int j=0;j<c->crib_len;j++){
                    int t=c->crib_off+j;
                    int oR=modp(Rp[t]-rR), oM=modp(Mp[t]-rM), oL=modp(Lp[t]-rL);
                    int x=c->etwr[c->cipher[t]];
                    x=c->rodfwd[wR][oR][x];
                    x=c->rodfwd[wM][oM][x];
                    x=c->rodfwd[wL][oL][x];
                    x=c->ukwat[u][x];
                    x=c->rodrev[wL][oL][x];
                    x=c->rodrev[wM][oM][x];
                    x=c->rodrev[wR][oR][x];
                    x=c->etwf[x];
                    if (x!=c->crib[j]){ ok=0; break; }     /* contradiction -> abandon */
                }
                if (ok){                                    /* zero contradictions: a hit */
                    pthread_mutex_lock(&c->lock);
                    if (c->nhits<c->max_hits){
                        int *o=c->out+c->nhits*6;
                        o[0]=ai; o[1]=oi; o[2]=u; o[3]=rL; o[4]=rM; o[5]=rR;
                        c->nhits++;
                    }
                    pthread_mutex_unlock(&c->lock);
                }
            }
        }
    }
    return NULL;
}

/* rod_search (EXPORTED): full exact-crib search. Builds the rod tables, sets the
 * arrangement set (canonical (0,1,2) with UKW=grund[3], or all 24 if all_arr!=0),
 * launches nthreads workers and joins them. Returns #hits; each hit = 6 ints
 * [arrangement, order, ukw_offset, ringL, ringM, ringR]. */
int rod_search(const int *wfwd, const int *etw_fwd, const int *ukw_fwd, const int *turn,
               const int *notch,
               const int *cipher, int n, const int *crib, int crib_len, int crib_off,
               const int *grund, int all_arr, int nthreads, int *out, int max_hits){
    Ctx c; memset(&c,0,sizeof(c));
    build_rods(&c,wfwd,etw_fwd,ukw_fwd,turn);
    for (int i=0;i<3;i++) c.notch[i]=notch[i];
    c.cipher=cipher; c.n=n; c.crib=crib; c.crib_len=crib_len; c.crib_off=crib_off;
    for (int i=0;i<4;i++) c.grund[i]=grund[i];
    c.out=out; c.max_hits=max_hits; c.nhits=0;
    c.nthreads = nthreads>0 ? nthreads : 1;
    if (c.nthreads>256) c.nthreads=256;
    pthread_mutex_init(&c.lock,NULL);

    if (all_arr){
        int k=0;
        for (int a=0;a<4;a++) for (int b=0;b<4;b++) for (int d=0;d<4;d++)
            if (a!=b&&a!=d&&b!=d){ c.arr[k][0]=a; c.arr[k][1]=b; c.arr[k][2]=d; k++; }
        c.narr=k;                                       /* 24 */
    } else {
        c.arr[0][0]=0; c.arr[0][1]=1; c.arr[0][2]=2;    /* canonical: L,M,R=g[0,1,2]; UKW=g[3] (offset free) */
        c.narr=1;
    }

    pthread_t th[256]; Targ ta[256];
    for (int i=0;i<c.nthreads;i++){ ta[i].c=&c; ta[i].tid=i; pthread_create(&th[i],NULL,worker,&ta[i]); }
    for (int i=0;i<c.nthreads;i++) pthread_join(th[i],NULL);
    pthread_mutex_destroy(&c.lock);
    return c.nhits;
}

/* ------------------------------------------------------------------------- *
 * COUPLING METHOD (Turing, Treatise Ch. IV pp. 71-73)
 *
 * Within a turnover-free stretch the L/M/UKW block is a FIXED involution Q (the
 * "coupling") on the right-wheel boundary contacts; only the right wheel moves.
 * For each crib letter we form the two boundary points
 *     a = R_rho( ETW(plain) ),   b = R_rho( ETW(cipher) )
 * (R_rho = right wheel at core position rho = window - ring). Q must pair a<->b.
 * Building Q incrementally, a fixed point (a==b) or a conflicting pairing is a
 * CONTRADICTION that rejects the rod start. Q resets at every stretch boundary
 * (when the M or L window changes). This needs NO L/M ring or UKW enumeration:
 * the search is order x arrangement x right-wheel-ring only (24*6*26).
 *
 * NOTE (scope): this is the per-stretch coupling-consistency filter. Linking Q
 * across a turnover through the middle-wheel rods (pp. 72-73), which pins the
 * middle-wheel position, is the further refinement and is not done here.
 * ------------------------------------------------------------------------- */
/* cworker (for coupling_search): strides over arrangement x order x right-ring;
 * builds the per-stretch coupling involution Q from the crib and rejects the rod
 * start on any fixed point (a==b) or conflicting pairing (see method note above). */
static void *cworker(void *p){
    Targ *ta=(Targ*)p; Ctx *c=ta->c;
    int upto=c->crib_off+c->crib_len;
    int Lp[MAXSTEP],Mp[MAXSTEP],Rp[MAXSTEP];
    long total=(long)c->narr*6*AL;
    for (long idx=ta->tid; idx<total; idx+=c->nthreads){
        int ringR=idx%AL; long q=idx/AL; int oi=q%6; int ai=q/6;
        int Lw=c->grund[c->arr[ai][0]], Mw=c->grund[c->arr[ai][1]], Rw=c->grund[c->arr[ai][2]];
        int wL=ORDERS[oi][0], wM=ORDERS[oi][1], wR=ORDERS[oi][2];
        (void)wL;
        posseq_off(Lw,Mw,Rw,c->turn[wM],c->turn[wR],c->notch[wM],c->notch[wR],0,ringR,upto,Lp,Mp,Rp);
        int pair[AL]; for (int i=0;i<AL;i++) pair[i]=-1;
        int prevM=Mp[c->crib_off], prevL=Lp[c->crib_off], ok=1;
        for (int j=0;j<c->crib_len;j++){
            int t=c->crib_off+j;
            if (Mp[t]!=prevM || Lp[t]!=prevL){        /* new stretch -> new coupling */
                for (int i=0;i<AL;i++) pair[i]=-1;
                prevM=Mp[t]; prevL=Lp[t];
            }
            int rho=modp(Rp[t]-ringR);
            int a=c->rodfwd[wR][rho][ c->etwr[ c->crib[j] ] ];
            int b=c->rodfwd[wR][rho][ c->etwr[ c->cipher[t] ] ];
            if (a==b){ ok=0; break; }                 /* fixed point: impossible */
            if (pair[a]==-1 && pair[b]==-1){ pair[a]=b; pair[b]=a; }
            else if (pair[a]==b){ /* click: already consistent */ }
            else { ok=0; break; }                     /* conflicting pairing */
        }
        if (ok){
            pthread_mutex_lock(&c->lock);
            if (c->nhits<c->max_hits){
                int *o=c->out+c->nhits*3; o[0]=ai; o[1]=oi; o[2]=ringR; c->nhits++;
            }
            pthread_mutex_unlock(&c->lock);
        }
    }
    return NULL;
}

/* Exported. Returns #hits; each hit = 3 ints [arrangement, order, right-ring]. */
int coupling_search(const int *wfwd, const int *etw_fwd, const int *ukw_fwd, const int *turn,
                    const int *notch,
                    const int *cipher, int n, const int *crib, int crib_len, int crib_off,
                    const int *grund, int all_arr, int nthreads, int *out, int max_hits){
    Ctx c; memset(&c,0,sizeof(c));
    build_rods(&c,wfwd,etw_fwd,ukw_fwd,turn);
    for (int i=0;i<3;i++) c.notch[i]=notch[i];
    c.cipher=cipher; c.n=n; c.crib=crib; c.crib_len=crib_len; c.crib_off=crib_off;
    for (int i=0;i<4;i++) c.grund[i]=grund[i];
    c.out=out; c.max_hits=max_hits; c.nhits=0;
    c.nthreads = nthreads>0 ? nthreads : 1; if (c.nthreads>256) c.nthreads=256;
    pthread_mutex_init(&c.lock,NULL);
    if (all_arr){
        int k=0;
        for (int a=0;a<4;a++) for (int b=0;b<4;b++) for (int d=0;d<4;d++)
            if (a!=b&&a!=d&&b!=d){ c.arr[k][0]=a; c.arr[k][1]=b; c.arr[k][2]=d; k++; }
        c.narr=k;
    } else { c.arr[0][0]=0; c.arr[0][1]=1; c.arr[0][2]=2; c.narr=1; }
    pthread_t th[256]; Targ ta[256];
    for (int i=0;i<c.nthreads;i++){ ta[i].c=&c; ta[i].tid=i; pthread_create(&th[i],NULL,cworker,&ta[i]); }
    for (int i=0;i<c.nthreads;i++) pthread_join(th[i],NULL);
    pthread_mutex_destroy(&c.lock);
    return c.nhits;
}

/* ------------------------------------------------------------------------- *
 * COUPLING-LINKING across turnovers (Turing, Treatise Ch. IV pp. 72-73)
 *
 * Within a turnover-free stretch Q = M_mu^-1 . P . M_mu, where P (the L+UKW
 * block) stays fixed while only the middle wheel advances. So every crib letter,
 * whatever stretch it is in, contributes the SAME P a pairing
 *     A <-> B  with  A = M_mu( R_rho(ETW(plain)) ),  B = M_mu( R_rho(ETW(cipher)) )
 * (mu = middle core position = window - ringM). Accumulating all crib letters
 * into one involution P (per left-wheel window) makes the cross-turnover linking
 * implicit: a wrong (ringR,ringM) produces a contradictory P and is rejected.
 * This recovers BOTH the right and middle rings; L-ring and UKW remain folded
 * into P (recoverable only past a -- rare -- left-wheel turnover).
 * ------------------------------------------------------------------------- */
/* lworker (for coupling_link_search): strides over arrangement x order x ringR x
 * ringM; accumulates ONE involution P per left-window across ALL crib letters
 * (cross-turnover linking) and rejects on contradiction. Pins both ringR and ringM. */
static void *lworker(void *p){
    Targ *ta=(Targ*)p; Ctx *c=ta->c;
    int upto=c->crib_off+c->crib_len;
    int Lp[MAXSTEP],Mp[MAXSTEP],Rp[MAXSTEP];
    int P[AL][AL];                              /* P[left-window][contact] involution */
    long total=(long)c->narr*6*AL*AL;           /* arr x order x ringR x ringM */
    for (long idx=ta->tid; idx<total; idx+=c->nthreads){
        int rM=idx%AL; long q=idx/AL;
        int rR=q%AL; q/=AL;
        int oi=q%6; int ai=q/6;
        int Lw=c->grund[c->arr[ai][0]], Mw=c->grund[c->arr[ai][1]], Rw=c->grund[c->arr[ai][2]];
        int wM=ORDERS[oi][1], wR=ORDERS[oi][2];
        posseq_off(Lw,Mw,Rw,c->turn[wM],c->turn[wR],c->notch[wM],c->notch[wR],rM,rR,upto,Lp,Mp,Rp);
        for (int i=0;i<AL;i++) for (int k=0;k<AL;k++) P[i][k]=-1;
        int ok=1;
        for (int j=0;j<c->crib_len;j++){
            int t=c->crib_off+j;
            int rho=modp(Rp[t]-rR), mu=modp(Mp[t]-rM);
            int a=c->rodfwd[wR][rho][ c->etwr[ c->crib[j] ] ];
            int b=c->rodfwd[wR][rho][ c->etwr[ c->cipher[t] ] ];
            if (a==b){ ok=0; break; }                    /* plain==cipher: impossible */
            int AA=c->rodfwd[wM][mu][a], BB=c->rodfwd[wM][mu][b]; /* lift into P-space */
            int *PP=P[ Lp[t] ];
            if (PP[AA]==-1 && PP[BB]==-1){ PP[AA]=BB; PP[BB]=AA; }
            else if (PP[AA]!=BB){ ok=0; break; }         /* P contradiction */
        }
        if (ok){
            pthread_mutex_lock(&c->lock);
            if (c->nhits<c->max_hits){
                int *o=c->out+c->nhits*4; o[0]=ai; o[1]=oi; o[2]=rR; o[3]=rM; c->nhits++;
            }
            pthread_mutex_unlock(&c->lock);
        }
    }
    return NULL;
}

/* Exported. Returns #hits; each hit = 4 ints [arrangement, order, ringR, ringM]. */
int coupling_link_search(const int *wfwd, const int *etw_fwd, const int *ukw_fwd, const int *turn,
                         const int *notch,
                         const int *cipher, int n, const int *crib, int crib_len, int crib_off,
                         const int *grund, int all_arr, int nthreads, int *out, int max_hits){
    Ctx c; memset(&c,0,sizeof(c));
    build_rods(&c,wfwd,etw_fwd,ukw_fwd,turn);
    for (int i=0;i<3;i++) c.notch[i]=notch[i];
    c.cipher=cipher; c.n=n; c.crib=crib; c.crib_len=crib_len; c.crib_off=crib_off;
    for (int i=0;i<4;i++) c.grund[i]=grund[i];
    c.out=out; c.max_hits=max_hits; c.nhits=0;
    c.nthreads = nthreads>0 ? nthreads : 1; if (c.nthreads>256) c.nthreads=256;
    pthread_mutex_init(&c.lock,NULL);
    if (all_arr){
        int k=0;
        for (int a=0;a<4;a++) for (int b=0;b<4;b++) for (int d=0;d<4;d++)
            if (a!=b&&a!=d&&b!=d){ c.arr[k][0]=a; c.arr[k][1]=b; c.arr[k][2]=d; k++; }
        c.narr=k;
    } else { c.arr[0][0]=0; c.arr[0][1]=1; c.arr[0][2]=2; c.narr=1; }
    pthread_t th[256]; Targ ta[256];
    for (int i=0;i<c.nthreads;i++){ ta[i].c=&c; ta[i].tid=i; pthread_create(&th[i],NULL,lworker,&ta[i]); }
    for (int i=0;i<c.nthreads;i++) pthread_join(th[i],NULL);
    pthread_mutex_destroy(&c.lock);
    return c.nhits;
}

/* ---------------------------------------------------------------------------
 * rod_search_sweep : like rod_search but sweeps the crib over ALL offsets in
 * [off_lo, off_hi]. Used by the corpus survey tool when the crib position is
 * unknown. Threads partition the offsets; each thread runs the full
 * arrangement x order x 26^4 enumeration per offset. Hit = 7 ints:
 *   [crib_off, arrangement, order, ukw_offset, ringL, ringM, ringR]
 * ------------------------------------------------------------------------- */
/* worker_sweep (for rod_search_sweep): threads partition the crib offsets; each runs
 * the full arrangement x order x 26^4 (UKW + 3 rings) click test at its offsets. */
static void *worker_sweep(void *p){
    Targ *ta=(Targ*)p; Ctx *c=ta->c;
    int Lp[MAXSTEP],Mp[MAXSTEP],Rp[MAXSTEP];
    for (int co=c->off_lo+ta->tid; co<=c->off_hi; co+=c->nthreads){
        int upto=co+c->crib_len;
        if (upto>c->n) continue;
        for (int ai=0; ai<c->narr; ai++){
            int Lw=c->grund[c->arr[ai][0]], Mw=c->grund[c->arr[ai][1]], Rw=c->grund[c->arr[ai][2]];
            for (int oi=0; oi<6; oi++){
                int wL=ORDERS[oi][0], wM=ORDERS[oi][1], wR=ORDERS[oi][2];
                for (int rR=0;rR<AL;rR++){
                    /* core-based turnover depends on rR -> recompute the step sequence per rR.
                     * (rM passed as 0: the middle notch is window-based for I/II; when a middle
                     * rotor gets an offset notch, move this inside the rM loop too.) */
                    posseq_off(Lw,Mw,Rw,c->turn[wM],c->turn[wR],c->notch[wM],c->notch[wR],0,rR,upto,Lp,Mp,Rp);
                    for (int u=0;u<AL;u++)
                    for (int rL=0;rL<AL;rL++)
                    for (int rM=0;rM<AL;rM++){
                        int ok=1;
                        for (int j=0;j<c->crib_len;j++){
                            int t=co+j;
                            int oR=modp(Rp[t]-rR), oM=modp(Mp[t]-rM), oL=modp(Lp[t]-rL);
                            int x=c->etwr[c->cipher[t]];
                            x=c->rodfwd[wR][oR][x];
                            x=c->rodfwd[wM][oM][x];
                            x=c->rodfwd[wL][oL][x];
                            x=c->ukwat[u][x];
                            x=c->rodrev[wL][oL][x];
                            x=c->rodrev[wM][oM][x];
                            x=c->rodrev[wR][oR][x];
                            x=c->etwf[x];
                            if (x!=c->crib[j]){ ok=0; break; }
                        }
                        if (ok){
                            pthread_mutex_lock(&c->lock);
                            if (c->nhits<c->max_hits){
                                int *o=c->out+c->nhits*7;
                                o[0]=co; o[1]=ai; o[2]=oi; o[3]=u; o[4]=rL; o[5]=rM; o[6]=rR;
                                c->nhits++;
                            }
                            pthread_mutex_unlock(&c->lock);
                        }
                    }
                }
            }
        }
    }
    return NULL;
}

/* Exported. Returns #hits; each hit = 7 ints (see above). */
int rod_search_sweep(const int *wfwd, const int *etw_fwd, const int *ukw_fwd, const int *turn,
                     const int *notch,
                     const int *cipher, int n, const int *crib, int crib_len,
                     int off_lo, int off_hi,
                     const int *grund, int all_arr, int nthreads, int *out, int max_hits){
    Ctx c; memset(&c,0,sizeof(c));
    build_rods(&c,wfwd,etw_fwd,ukw_fwd,turn);
    for (int i=0;i<3;i++) c.notch[i]=notch[i];
    c.cipher=cipher; c.n=n; c.crib=crib; c.crib_len=crib_len;
    c.off_lo = off_lo<0 ? 0 : off_lo;
    c.off_hi = off_hi>n-crib_len ? n-crib_len : off_hi;
    for (int i=0;i<4;i++) c.grund[i]=grund[i];
    c.out=out; c.max_hits=max_hits; c.nhits=0;
    c.nthreads = nthreads>0 ? nthreads : 1;
    if (c.nthreads>256) c.nthreads=256;
    pthread_mutex_init(&c.lock,NULL);
    if (all_arr){
        int k=0;
        for (int a=0;a<4;a++) for (int b=0;b<4;b++) for (int d=0;d<4;d++)
            if (a!=b&&a!=d&&b!=d){ c.arr[k][0]=a; c.arr[k][1]=b; c.arr[k][2]=d; k++; }
        c.narr=k;                                       /* 24 */
    } else {
        c.arr[0][0]=0; c.arr[0][1]=1; c.arr[0][2]=2;    /* canonical: L,M,R=g[0,1,2]; UKW=g[3] (offset free) */
        c.narr=1;
    }
    pthread_t th[256]; Targ ta[256];
    for (int i=0;i<c.nthreads;i++){ ta[i].c=&c; ta[i].tid=i; pthread_create(&th[i],NULL,worker_sweep,&ta[i]); }
    for (int i=0;i<c.nthreads;i++) pthread_join(th[i],NULL);
    pthread_mutex_destroy(&c.lock);
    return c.nhits;
}

/* ===========================================================================
 * buttonup_anchor : Knox-style "buttoning up" of the FAST rotor wiring.
 *
 * The Python front-end reduces a crib to per-letter constraints
 *     B_s[(rf[in]-o)%26] = (rf[out]-o)%26
 * where rf is the (unknown) right-rotor forward wiring shared across the crib,
 * o=(window-ring) the right-rotor offset, s the turnover-free stretch index,
 * and B_s a fixed point-free involution per stretch (mid+left+UKW composite).
 * This kernel brute-forces the two most-constrained contacts (the anchor that
 * rodding would otherwise supply) over all 26x26 value pairs; for each it runs
 * constraint propagation + backtracking to recover rf. Threads partition the
 * 676 anchor seeds. Each full, consistent rf is written (26 ints) to out.
 *
 * Backtracking state is copied by value (simple + correct); if profiling on
 * many cores shows this dominates, switch to undo-based propagation.
 * ------------------------------------------------------------------------- */
#define MAXSTR 8
#define BU_NODECAP 2000000L

typedef struct {
    int  rf[AL];           /* -1 = unknown */
    int  B[MAXSTR][AL];    /* -1 = unknown; one involution per stretch */
    char used[AL];         /* used[v]=1 once value v is assigned to some contact */
} BState;

typedef struct {
    const int *cin, *cout, *co, *cs;   /* constraint arrays, length ncons */
    int ncons, nstr;
    const int *touched; int ntouched;
    int percon[AL];                    /* per-contact constraint count (ordering) */
    int a, b;                          /* anchor contacts */
    int *out; int max_sols; int nsols;
    int nthreads;
    pthread_mutex_t lock;
} BuCtx;

typedef struct { BuCtx *c; int tid; } Btarg;

/* bu_propagate: constraint propagation to a fixpoint over the partial state st.
 * Each constraint links two rf contacts through the per-stretch involution B and an
 * offset o. If both rf ends are known it pins a B pair; if one rf end plus its B
 * value are known it forces the other rf entry. Returns 0 on any contradiction
 * (B fixed point, non-involution, or a repeated rf value breaking bijectivity). */
static int bu_propagate(BState *st, BuCtx *c){
    int changed=1;
    while (changed){
        changed=0;
        for (int t=0;t<c->ncons;t++){
            int i=c->cin[t], j=c->cout[t], o=c->co[t], s=c->cs[t];
            int *bi=st->B[s];
            int ri=st->rf[i], rj=st->rf[j];
            if (ri!=-1 && rj!=-1){
                int a1=modp(ri-o), a6=modp(rj-o);
                if (a1==a6) return 0;                    /* involution: no fixed point */
                if (bi[a1]==-1 && bi[a6]==-1){ bi[a1]=a6; bi[a6]=a1; changed=1; }
                else if (bi[a1]!=a6 || bi[a6]!=a1) return 0;
            } else if (ri!=-1){
                int a1=modp(ri-o);
                if (bi[a1]!=-1){
                    int v=modp(bi[a1]+o);
                    if (rj==-1){
                        if (st->used[v]) return 0;
                        st->rf[j]=v; st->used[v]=1; changed=1;
                    } else if (rj!=v) return 0;
                }
            } else if (rj!=-1){
                int a6=modp(rj-o);
                if (bi[a6]!=-1){
                    int v=modp(bi[a6]+o);
                    if (st->rf[i]==-1){
                        if (st->used[v]) return 0;
                        st->rf[i]=v; st->used[v]=1; changed=1;
                    } else if (st->rf[i]!=v) return 0;
                }
            }
        }
    }
    return 1;
}

/* bu_rec: depth-first backtracking search (state passed BY VALUE so each branch has
 * its own copy). Propagate; if that survives, pick the still-unassigned contact with
 * the most constraints and try every unused value for it, recursing. A complete,
 * consistent rf is written to the shared output. nodes is a per-anchor budget guard. */
static void bu_rec(BState st, BuCtx *c, long *nodes){
    if (*nodes > BU_NODECAP) return;
    (*nodes)++;
    if (!bu_propagate(&st,c)) return;
    int k=-1, best=-1;                                   /* most-constrained unassigned contact */
    for (int ti=0; ti<c->ntouched; ti++){
        int cc=c->touched[ti];
        if (st.rf[cc]==-1 && c->percon[cc]>best){ best=c->percon[cc]; k=cc; }
    }
    if (k==-1){                                          /* complete rf */
        pthread_mutex_lock(&c->lock);
        if (c->nsols < c->max_sols){
            memcpy(c->out + (long)c->nsols*AL, st.rf, AL*sizeof(int));
            c->nsols++;
        }
        pthread_mutex_unlock(&c->lock);
        return;
    }
    for (int v=0; v<AL; v++){
        if (st.used[v]) continue;
        BState st2=st;
        st2.rf[k]=v; st2.used[v]=1;
        bu_rec(st2,c,nodes);
    }
}

/* bu_worker: each thread takes a slice of the 26x26 anchor seeds. For each pair of
 * values (va,vb) it seeds the two anchor contacts a,b, initialises an empty state,
 * and launches bu_rec. Threads share only the output buffer (mutex-guarded). */
static void *bu_worker(void *p){
    Btarg *ta=(Btarg*)p; BuCtx *c=ta->c;
    for (long idx=ta->tid; idx<AL*AL; idx+=c->nthreads){
        int va=idx/AL, vb=idx%AL;
        if (va==vb) continue;
        BState st;
        for (int i=0;i<AL;i++) st.rf[i]=-1;
        for (int s=0;s<c->nstr;s++) for (int i=0;i<AL;i++) st.B[s][i]=-1;
        for (int i=0;i<AL;i++) st.used[i]=0;
        st.rf[c->a]=va; st.used[va]=1;
        st.rf[c->b]=vb; st.used[vb]=1;
        long nodes=0;
        bu_rec(st,c,&nodes);
    }
    return NULL;
}

/* Exported. Returns #solutions (or -1 if nstr>MAXSTR); each solution = 26 ints
 * (recovered rf). Anchor contacts a,b chosen by the front-end (most-constrained). */
int buttonup_anchor(const int *cin,const int *cout,const int *co,const int *cs,int ncons,
                    int nstr, const int *touched,int ntouched, int a,int b,
                    int nthreads, int *out,int max_sols){
    if (nstr>MAXSTR) return -1;
    BuCtx c; memset(&c,0,sizeof(c));
    c.cin=cin; c.cout=cout; c.co=co; c.cs=cs; c.ncons=ncons; c.nstr=nstr;
    c.touched=touched; c.ntouched=ntouched;
    for (int t=0;t<ncons;t++){ c.percon[cin[t]]++; c.percon[cout[t]]++; }
    c.a=a; c.b=b; c.out=out; c.max_sols=max_sols; c.nsols=0;
    c.nthreads = nthreads>0 ? nthreads : 1;
    if (c.nthreads>256) c.nthreads=256;
    pthread_mutex_init(&c.lock,NULL);
    pthread_t th[256]; Btarg ta[256];
    for (int i=0;i<c.nthreads;i++){ ta[i].c=&c; ta[i].tid=i; pthread_create(&th[i],NULL,bu_worker,&ta[i]); }
    for (int i=0;i<c.nthreads;i++) pthread_join(th[i],NULL);
    pthread_mutex_destroy(&c.lock);
    return c.nsols;
}
