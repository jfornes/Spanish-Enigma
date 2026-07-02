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
    const int *cipher; int n;
    const int *crib; int crib_len, crib_off;
    int off_lo, off_hi;          /* crib-offset sweep range (rod_search_sweep) */
    int grund[4];
    int arr[24][3]; int narr;   /* arrangements: indices into grund for (L,M,R) */
    int *out; int max_hits; int nhits;
    int nthreads;
    pthread_mutex_t lock;
} Ctx;

static int modp(int x){ x%=AL; return x<0?x+AL:x; }

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

/* window-position sequence (A27 stepping, ring-independent turnover) */
static void posseq(int Lw,int Mw,int Rw,int tM,int tR,int upto,
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

typedef struct { Ctx *c; int tid; } Targ;

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
        posseq(Lw,Mw,Rw,c->turn[wM],c->turn[wR],upto,Lp,Mp,Rp);
        for (int rL=0;rL<AL;rL++)
        for (int rM=0;rM<AL;rM++)
        for (int rR=0;rR<AL;rR++){
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
    return NULL;
}

/* Exported entry point. Returns number of hits; fills out[6*hit]. */
int rod_search(const int *wfwd, const int *etw_fwd, const int *ukw_fwd, const int *turn,
               const int *cipher, int n, const int *crib, int crib_len, int crib_off,
               const int *grund, int all_arr, int nthreads, int *out, int max_hits){
    Ctx c; memset(&c,0,sizeof(c));
    build_rods(&c,wfwd,etw_fwd,ukw_fwd,turn);
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
        posseq(Lw,Mw,Rw,c->turn[wM],c->turn[wR],upto,Lp,Mp,Rp);
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
                    const int *cipher, int n, const int *crib, int crib_len, int crib_off,
                    const int *grund, int all_arr, int nthreads, int *out, int max_hits){
    Ctx c; memset(&c,0,sizeof(c));
    build_rods(&c,wfwd,etw_fwd,ukw_fwd,turn);
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
        posseq(Lw,Mw,Rw,c->turn[wM],c->turn[wR],upto,Lp,Mp,Rp);
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
                         const int *cipher, int n, const int *crib, int crib_len, int crib_off,
                         const int *grund, int all_arr, int nthreads, int *out, int max_hits){
    Ctx c; memset(&c,0,sizeof(c));
    build_rods(&c,wfwd,etw_fwd,ukw_fwd,turn);
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
                posseq(Lw,Mw,Rw,c->turn[wM],c->turn[wR],upto,Lp,Mp,Rp);
                for (int u=0;u<AL;u++)
                for (int rL=0;rL<AL;rL++)
                for (int rM=0;rM<AL;rM++)
                for (int rR=0;rR<AL;rR++){
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
    return NULL;
}

/* Exported. Returns #hits; each hit = 7 ints (see above). */
int rod_search_sweep(const int *wfwd, const int *etw_fwd, const int *ukw_fwd, const int *turn,
                     const int *cipher, int n, const int *crib, int crib_len,
                     int off_lo, int off_hi,
                     const int *grund, int all_arr, int nthreads, int *out, int max_hits){
    Ctx c; memset(&c,0,sizeof(c));
    build_rods(&c,wfwd,etw_fwd,ukw_fwd,turn);
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
