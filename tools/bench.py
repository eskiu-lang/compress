#!/usr/bin/env python3
# The same measurements as tools/bench.esk with Python's zlib (raw DEFLATE).
#     python3 -I tools/bench.py FILE 1 6 9
import sys
import time
import zlib


def main():
    data = open(sys.argv[1], "rb").read()
    levels = [int(a) for a in sys.argv[2:]] or list(range(10))
    for lv in levels:
        best_c = best_d = 1e9
        for _ in range(3):
            t0 = time.monotonic()
            c = zlib.compressobj(lv, zlib.DEFLATED, -15)
            packed = c.compress(data) + c.flush()
            t1 = time.monotonic()
            assert zlib.decompress(packed, -15) == data
            t2 = time.monotonic()
            best_c = min(best_c, t1 - t0)
            best_d = min(best_d, t2 - t1)
        print("level %d: %d -> %d (%.2f%%)  deflate %d ms  inflate %d ms" % (
            lv, len(data), len(packed), 100.0 * len(packed) / len(data), best_c * 1000, best_d * 1000))


main()
