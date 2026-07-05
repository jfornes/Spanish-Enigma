#!/usr/bin/env python3

# Spanish-Enigma: A research toolkit for the cryptanalysis of Spanish
# Enigma K traffic (1936-1945)
# Copyright (C) 2026  Jordi Fornés, Alba Rebull
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
    """Load librods and configure argtypes for every exported kernel. Cached, so
    the shared object is opened once per process even across the three front-ends."""
    global _lib
    if _lib is not None:
        return _lib
    lib = ctypes.CDLL(library_path())
    P = ctypes.POINTER(ctypes.c_int); ci = ctypes.c_int
    # rod_search / coupling_search / coupling_link_search share one signature
    sig = [P, P, P, P, P, ci, P, ci, ci, P, ci, ci, P, ci]
    for name in ('rod_search', 'coupling_search', 'coupling_link_search'):
        fn = getattr(lib, name); fn.argtypes = sig; fn.restype = ci
    lib.rod_search_sweep.argtypes = [P, P, P, P, P, ci, P, ci, ci, ci, P, ci, ci, P, ci]
    lib.rod_search_sweep.restype = ci
    lib.buttonup_anchor.argtypes = [P, P, P, P, ci, ci, P, ci, ci, ci, ci, P, ci]
    lib.buttonup_anchor.restype = ci
    _lib = lib
    return lib
