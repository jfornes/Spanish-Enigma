#!/usr/bin/env python3
"""rodslib.py -- locate and load the compiled Enigma K search library (librods).

Single loader shared by corpus_sweep.py, rods_frontend.py and buttonup.py. It
does NOT compile anything: build the library first with `make` (in src/), then
either place librods.{so,dylib} where the loader looks or point the environment
variable SPANISH_ENIGMA_LIB at it.

Search order (first hit wins):
  1. $SPANISH_ENIGMA_LIB  -- a file (used directly) or a directory (searched)
  2. next to this module  -- the python/ dir (flat layout)
  3. ../src/              -- alongside rods.c and the Makefile
  4. ../build/            -- an out-of-tree build dir
If none is found, load() raises RuntimeError with a build hint.

The C kernels take the wirings as parameters, so this module only locates and
binds the shared object; the wirings themselves live in data/wirings/wirings.json.
"""
import os, platform, ctypes

_LIBNAME = 'librods.dylib' if platform.system() == 'Darwin' else 'librods.so'
_lib = None


def library_path():
    """Return an absolute path to the compiled library, or raise RuntimeError."""
    cands = []
    env = os.environ.get('SPANISH_ENIGMA_LIB')
    if env:
        cands.append(env)                                   # may be the file itself
        cands.append(os.path.join(env, _LIBNAME))           # ...or a directory
    here = os.path.dirname(os.path.abspath(__file__))
    cands += [os.path.join(here, _LIBNAME),                 # python/ (flat layout)
              os.path.join(here, '..', 'src', _LIBNAME),    # repo: src/
              os.path.join(here, '..', 'build', _LIBNAME)]  # out-of-tree build
    for p in cands:
        if p and os.path.isfile(p):
            return os.path.abspath(p)
    raise RuntimeError(
        f"{_LIBNAME} not found. Build it with `make` in src/, then set "
        f"SPANISH_ENIGMA_LIB to the file (or its directory), or place it next to "
        f"the Python front-ends. Searched: " + ", ".join(c for c in cands if c))


def load():
    """Load librods and configure argtypes for every kernel the shared object
    actually exports. Cached (opened once per process). Missing kernels are skipped
    rather than fatal, so a front-end that needs only some of them still works with
    an older/partial librods.so; a kernel that is genuinely absent fails clearly only
    when a caller invokes it. lib.kernels lists what was found."""
    global _lib
    if _lib is not None:
        return _lib
    lib = ctypes.CDLL(library_path())
    P = ctypes.POINTER(ctypes.c_int); ci = ctypes.c_int
    sig = [P, P, P, P, P, P, ci, P, ci, ci, P, ci, ci, P, ci]  # rod_search / coupling / link (+notch)
    specs = {
        'rod_search': sig, 'coupling_search': sig, 'coupling_link_search': sig,
        'rod_search_sweep': [P, P, P, P, P, P, ci, P, ci, ci, ci, P, ci, ci, P, ci],
        'buttonup_anchor':  [P, P, P, P, ci, ci, P, ci, ci, ci, ci, P, ci],
    }
    lib.kernels = []
    for name, at in specs.items():
        fn = getattr(lib, name, None)                          # absent symbol -> None, not fatal
        if fn is not None:
            fn.argtypes = at; fn.restype = ci; lib.kernels.append(name)
    _lib = lib
    return lib
