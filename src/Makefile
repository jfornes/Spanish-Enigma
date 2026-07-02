# Build the rod-search C library. POSIX pthreads only (no OpenMP, no MPI),
# so it builds identically on Linux and macOS.
UNAME := $(shell uname)
CC    ?= cc
CFLAGS = -O3 -fPIC -Wall

ifeq ($(UNAME), Darwin)
  LIB    = librods.dylib
  SHARED = -dynamiclib
  ARCH   = -arch x86_64 -arch arm64
else
  LIB    = librods.so
  SHARED = -shared
  ARCH   =
endif

$(LIB): rods.c
	$(CC) $(CFLAGS) $(ARCH) $(SHARED) -o $(LIB) rods.c -lpthread

run: $(LIB)
	python3 rods_frontend.py soler_terminus_mvnr.json

clean:
	rm -f librods.so librods.dylib

.PHONY: run clean
