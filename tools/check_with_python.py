#!/usr/bin/env python3
# Builds and runs tools/samples.esk, then reads everything it wrote with
# Python's zlib, gzip and zipfile (and with `unzip -t` and `gzip -t` when they
# are installed). Run it from the package root:
#
#     python3 -I tools/check_with_python.py
#
# ESKIUC picks the compiler (eskiuc by default).
import gzip
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib

failures = 0


def fail(what):
    global failures
    failures += 1
    print("FAIL", what)


def gzip_name_mtime(b):
    flg = b[3]
    mtime = struct.unpack("<I", b[4:8])[0]
    i = 10
    if flg & 4:
        i += 2 + struct.unpack("<H", b[i:i + 2])[0]
    name = None
    if flg & 8:
        j = b.index(b"\0", i)
        name = b[i:j]
    return name, mtime


def main():
    eskiuc = os.environ.get("ESKIUC", "eskiuc")
    out = tempfile.mkdtemp(prefix="compress_samples")
    try:
        exe = os.path.join(out, "samples")
        subprocess.run([eskiuc, "-O2", "tools/samples.esk", "-o", exe], check=True)
        data = os.path.join(out, "data")
        subprocess.run([exe, data], check=True)
        check(data)
    finally:
        shutil.rmtree(out)
    if failures:
        print("%d failures" % failures)
        sys.exit(1)
    print("check_with_python: ok")


def read(d, name):
    with open(os.path.join(d, name), "rb") as f:
        return f.read()


def check(d):
    text = read(d, "text.bin")
    noise = read(d, "noise.bin")
    n = 0
    for lv in range(10):
        if zlib.decompress(read(d, "text_%d.deflate" % lv), -15) != text:
            fail("raw level %d" % lv)
        if zlib.decompress(read(d, "text_%d.zz" % lv)) != text:
            fail("zlib level %d" % lv)
        if gzip.decompress(read(d, "text_%d.gz" % lv)) != text:
            fail("gzip level %d" % lv)
        n += 3
    if zlib.decompress(read(d, "noise_9.zz")) != noise:
        fail("zlib noise")
    named = read(d, "named.gz")
    if gzip.decompress(named) != text:
        fail("gzip named")
    if gzip_name_mtime(named) != (b"text.bin", 1700000000):
        fail("gzip header %r" % (gzip_name_mtime(named),))
    n += 2
    if shutil.which("gzip"):
        for lv in (0, 1, 6, 9):
            r = subprocess.run(["gzip", "-t", os.path.join(d, "text_%d.gz" % lv)])
            if r.returncode != 0:
                fail("gzip -t level %d" % lv)

    inputs = {"text.bin": text, "noise.bin": noise}
    expect = {}
    for line in read(d, "manifest.txt").decode().splitlines():
        archive, rest = line.split(" ", 1)
        name, src, length = rest.rsplit(" ", 2)
        expect.setdefault(archive, []).append((name, src, int(length)))
    for archive, entries in sorted(expect.items()):
        path = os.path.join(d, archive)
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad is not None:
                fail("%s: testzip %s" % (archive, bad))
            names = set(z.namelist())
            for name, src, length in entries:
                if name not in names:
                    fail("%s: no %s" % (archive, name))
                    continue
                info = z.getinfo(name)
                got = z.read(name)
                if src == "-":
                    if not info.is_dir() or got != b"":
                        fail("%s: %s is not a directory" % (archive, name))
                elif src == "=":
                    if got != name.encode():
                        fail("%s: %s" % (archive, name))
                elif got != inputs[src][:length]:
                    fail("%s: %s" % (archive, name))
                n += 1
            if archive == "many.zip" and len(z.infolist()) != 70000:
                fail("many.zip: %d entries" % len(z.infolist()))
        if shutil.which("unzip"):
            r = subprocess.run(["unzip", "-tqq", path])
            if r.returncode != 0:
                fail("unzip -t %s" % archive)
    print("checked %d streams and entries" % n)


main()
