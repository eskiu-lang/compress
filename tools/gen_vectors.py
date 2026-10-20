#!/usr/bin/env python3
# Writes the reference streams and archives in tests/data, made by Python's
# zlib, gzip and zipfile (and by the zip and ditto commands when present):
#
#     python3 -I tools/gen_vectors.py
#
# tests/data/streams.txt lists each stream as "FORMAT FILE INPUT", where
# FORMAT is raw, zlib or gzip and INPUT names the .bin file it decodes to.
# tests/data/zips.txt lists each archive entry as
# "ARCHIVE<TAB>NAME<TAB>SIZE<TAB>CRC<TAB>MTIME", MTIME in Unix seconds as the
# reader should report it. The inputs are generated from fixed seeds, so the
# output only changes with the zlib version.
import calendar
import gzip
import io
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "tests", "data")

WORDS = ("the of and to in is that for it as was with be by on not he this are or his from at which "
         "but have an they you were her she there one all we their been has would when if so no what "
         "compress window block length distance literal symbol stream header archive entry table code "
         "huffman tree match chain level stored fixed dynamic checksum adler crc gzip zlib deflate").split()


def text(n, seed):
    r = random.Random(seed)
    out = []
    size = 0
    while size < n:
        w = r.choice(WORDS)
        if r.random() < 0.08:
            w = w.capitalize()
        sep = " "
        x = r.random()
        if x < 0.05:
            sep = ".\n"
        elif x < 0.12:
            sep = ", "
        out.append(w + sep)
        size += len(w) + len(sep)
    return "".join(out).encode()[:n]


def binary(n, seed):
    # Little-endian records: a counter, a slowly varying value, noise bytes.
    r = random.Random(seed)
    b = bytearray()
    i = 0
    v = 1000
    while len(b) < n:
        v += r.randint(-3, 3)
        b += struct.pack("<IhB", i, v, r.randint(0, 255))
        i += 1
    return bytes(b[:n])


def runs(n, seed):
    r = random.Random(seed)
    b = bytearray()
    while len(b) < n:
        b += bytes([r.randint(0, 3)]) * r.randint(1, 300)
    return bytes(b[:n])


def raw(data, level, strategy=zlib.Z_DEFAULT_STRATEGY, wbits=15, flush_every=0):
    c = zlib.compressobj(level, zlib.DEFLATED, -wbits, 8, strategy)
    if flush_every == 0:
        return c.compress(data) + c.flush()
    out = b""
    for i in range(0, len(data), flush_every):
        out += c.compress(data[i:i + flush_every]) + c.flush(zlib.Z_SYNC_FLUSH)
    return out + c.flush()


def gzip_member(data, level=6, name=None, mtime=0, comment=None, extra=None, hcrc=False):
    # A gzip member with any of the optional header fields, which the gzip
    # module cannot all write.
    flg = 0
    tail = b""
    if extra is not None:
        flg |= 4
        tail += struct.pack("<H", len(extra)) + extra
    if name is not None:
        flg |= 8
        tail += name + b"\0"
    if comment is not None:
        flg |= 16
        tail += comment + b"\0"
    if hcrc:
        flg |= 2
    head = b"\x1f\x8b\x08" + bytes([flg]) + struct.pack("<I", mtime) + b"\x00\x03" + tail
    if hcrc:
        head += struct.pack("<H", zlib.crc32(head) & 0xFFFF)
    return head + raw(data, level) + struct.pack("<II", zlib.crc32(data), len(data) & 0xFFFFFFFF)


def write(name, b):
    with open(os.path.join(DATA, name), "wb") as f:
        f.write(b)


def entry_mtime(zi):
    # The extended timestamp field (0x5455) holds the Unix mtime; otherwise
    # the DOS fields, read as UTC.
    ex = zi.extra
    i = 0
    while i + 4 <= len(ex):
        tag, size = struct.unpack("<HH", ex[i:i + 4])
        body = ex[i + 4:i + 4 + size]
        if tag == 0x5455 and size >= 5 and body[0] & 1:
            return struct.unpack("<i", body[1:5])[0]
        i += 4 + size
    y, mo, d, h, mi, s = zi.date_time
    return calendar.timegm((y, max(mo, 1), max(d, 1), h, mi, s))


def main():
    os.makedirs(DATA, exist_ok=True)
    for f in os.listdir(DATA):
        if f.endswith((".bin", ".deflate", ".zz", ".gz", ".zip", ".txt")):
            os.remove(os.path.join(DATA, f))

    inputs = {
        "text": text(24000, 1),
        "binary": binary(12000, 2),
        "runs": runs(30000, 3),
        "empty": b"",
        "one": b"A",
    }
    for k, v in inputs.items():
        write(k + ".bin", v)

    streams = []
    configs = [
        ("l0", 0, zlib.Z_DEFAULT_STRATEGY, 15),
        ("l1", 1, zlib.Z_DEFAULT_STRATEGY, 15),
        ("l6", 6, zlib.Z_DEFAULT_STRATEGY, 15),
        ("l9", 9, zlib.Z_DEFAULT_STRATEGY, 15),
        ("filtered", 6, zlib.Z_FILTERED, 15),
        ("huffman", 6, zlib.Z_HUFFMAN_ONLY, 15),
        ("rle", 6, zlib.Z_RLE, 15),
        ("fixed", 6, zlib.Z_FIXED, 15),
        ("w9", 9, zlib.Z_DEFAULT_STRATEGY, 9),
    ]
    for k in ("text", "binary", "runs"):
        for tag, level, strategy, wbits in configs:
            f = "%s_%s.deflate" % (k, tag)
            write(f, raw(inputs[k], level, strategy, wbits))
            streams.append(("raw", f, k))
        f = "%s_flush.deflate" % k
        write(f, raw(inputs[k], 6, flush_every=1000))
        streams.append(("raw", f, k))
        for level in (1, 9):
            f = "%s_l%d.zz" % (k, level)
            write(f, zlib.compress(inputs[k], level))
            streams.append(("zlib", f, k))
        f = "%s.gz" % k
        write(f, gzip.compress(inputs[k], 6, mtime=0))
        streams.append(("gzip", f, k))
    for k in ("empty", "one"):
        for level in (0, 6):
            f = "%s_l%d.deflate" % (k, level)
            write(f, raw(inputs[k], level))
            streams.append(("raw", f, k))
        write(k + ".zz", zlib.compress(inputs[k]))
        streams.append(("zlib", k + ".zz", k))
        write(k + ".gz", gzip.compress(inputs[k], mtime=0))
        streams.append(("gzip", k + ".gz", k))

    # Multi-member gzip, decoding to text + binary.
    write("multi.bin", inputs["text"] + inputs["binary"])
    write("multi.gz", gzip.compress(inputs["text"], 9, mtime=0) + gzip.compress(inputs["binary"], 1, mtime=0))
    streams.append(("gzip", "multi.gz", "multi"))
    # Every optional header field (extra, name, comment, header CRC).
    write("fields.gz", gzip_member(inputs["text"], 6, b"notes.txt", 1700000000, b"a comment", b"AB\x02\x00xy", True))
    streams.append(("gzip", "fields.gz", "text"))
    # The gzip module's own header: a file name and a time.
    buf = io.BytesIO()
    with gzip.GzipFile("named.txt", "wb", 6, buf, mtime=1234567890) as g:
        g.write(inputs["runs"])
    write("named.gz", buf.getvalue())
    streams.append(("gzip", "named.gz", "runs"))
    # Zero padding after the last member.
    write("padded.gz", gzip.compress(inputs["binary"], mtime=0) + b"\0" * 37)
    streams.append(("gzip", "padded.gz", "binary"))

    with open(os.path.join(DATA, "streams.txt"), "w") as f:
        for s in streams:
            f.write("%s %s %s\n" % s)

    zips = []

    def note(path):
        with zipfile.ZipFile(path) as z:
            for zi in z.infolist():
                zips.append((os.path.basename(path), zi.filename, zi.file_size, zi.CRC, entry_mtime(zi)))

    when = (2021, 3, 4, 5, 6, 8)

    def info(name, method, level=None):
        zi = zipfile.ZipInfo(name, when)
        zi.compress_type = method
        if level is not None:
            zi._compresslevel = level
        zi.external_attr = 0o644 << 16
        return zi

    p = os.path.join(DATA, "py_stored.zip")
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(info("text.txt", zipfile.ZIP_STORED), inputs["text"])
        z.writestr(info("empty.txt", zipfile.ZIP_STORED), b"")
        z.writestr(info("binary.bin", zipfile.ZIP_STORED), inputs["binary"])
    note(p)

    p = os.path.join(DATA, "py_deflated.zip")
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(info("text1.txt", zipfile.ZIP_DEFLATED, 1), inputs["text"])
        z.writestr(info("text9.txt", zipfile.ZIP_DEFLATED, 9), inputs["text"])
        z.writestr(info("runs.bin", zipfile.ZIP_DEFLATED), inputs["runs"])
        z.writestr(info("one.txt", zipfile.ZIP_DEFLATED), b"A")
        z.writestr(info("empty.txt", zipfile.ZIP_DEFLATED), b"")
        z.writestr(info("caf\u00e9/na\u00efve.txt", zipfile.ZIP_DEFLATED), b"unicode name\n")
        z.comment = b"an archive comment"
    note(p)

    p = os.path.join(DATA, "py_dirs.zip")
    with zipfile.ZipFile(p, "w") as z:
        for d in ("docs/", "docs/sub/", "src/"):
            zi = zipfile.ZipInfo(d, when)
            zi.external_attr = (0o40755 << 16) | 0x10
            z.writestr(zi, b"")
        z.writestr(info("docs/readme.txt", zipfile.ZIP_DEFLATED), inputs["text"][:3000])
        z.writestr(info("docs/sub/deep.bin", zipfile.ZIP_DEFLATED), inputs["binary"][:500])
        z.writestr(info("src/main.esk", zipfile.ZIP_STORED), b"int main() { return 0; }\n")
    note(p)

    # Streamed entries: the sizes and CRC follow the data in a descriptor.
    class Unseekable:
        def __init__(self):
            self.b = bytearray()

        def write(self, x):
            self.b += x
            return len(x)

        def flush(self):
            pass

    sink = Unseekable()
    with zipfile.ZipFile(sink, "w") as z:
        with z.open(info("streamed.txt", zipfile.ZIP_DEFLATED), "w") as f:
            f.write(inputs["text"])
        with z.open(info("big64.bin", zipfile.ZIP_DEFLATED), "w", force_zip64=True) as f:
            f.write(inputs["runs"])
    write("py_stream.zip", bytes(sink.b))
    note(os.path.join(DATA, "py_stream.zip"))

    # ZIP64 end records and extra fields, forced by lowering the limits that
    # make zipfile write them.
    saved = (zipfile.ZIP64_LIMIT, zipfile.ZIP_FILECOUNT_LIMIT)
    zipfile.ZIP64_LIMIT = 1000
    zipfile.ZIP_FILECOUNT_LIMIT = 2
    try:
        p = os.path.join(DATA, "py_zip64.zip")
        with zipfile.ZipFile(p, "w", allowZip64=True) as z:
            z.writestr(info("a.txt", zipfile.ZIP_DEFLATED), inputs["text"])
            z.writestr(info("b.bin", zipfile.ZIP_STORED), inputs["binary"])
            z.writestr(info("c.txt", zipfile.ZIP_DEFLATED), b"small")
    finally:
        zipfile.ZIP64_LIMIT, zipfile.ZIP_FILECOUNT_LIMIT = saved
    note(p)

    # An archive after a 100-byte stub, as in a self-extracting file.
    with open(os.path.join(DATA, "py_deflated.zip"), "rb") as f:
        body = f.read()
    write("prefixed.zip", b"#!stub\n" + b"x" * 93 + body)
    note(os.path.join(DATA, "prefixed.zip"))

    # Names that must not be extracted.
    p = os.path.join(DATA, "unsafe.zip")
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(info("fine.txt", zipfile.ZIP_STORED), b"fine")
        z.writestr(info("../evil.txt", zipfile.ZIP_STORED), b"evil")
    note(p)
    for tag, name in (("abs", "/abs.txt"), ("deep", "a/b/../../../x.txt"), ("back", "a\\..\\..\\x.txt"), ("drive", "C:/x.txt")):
        p = os.path.join(DATA, "unsafe_%s.zip" % tag)
        with zipfile.ZipFile(p, "w") as z:
            zi = info("placeholder", zipfile.ZIP_STORED)
            zi.filename = name
            z.writestr(zi, b"evil")
        note(p)

    # The zip and ditto commands, on a small tree with a fixed mtime.
    tree = tempfile.mkdtemp()
    try:
        root = os.path.join(tree, "tree")
        os.makedirs(os.path.join(root, "sub"))
        files = {"a.txt": inputs["text"][:5000], "sub/b.bin": inputs["binary"][:2000], "sub/empty": b""}
        for n, b in files.items():
            with open(os.path.join(root, n), "wb") as f:
                f.write(b)
        for d, _, fs in os.walk(root):
            for n in fs + [""]:
                os.utime(os.path.join(d, n), (1700000000, 1700000000))
        if shutil.which("zip"):
            p = os.path.join(DATA, "cli_zip.zip")
            subprocess.run(["zip", "-q", "-r", p, "tree"], cwd=tree, check=True)
            note(p)
        if shutil.which("ditto") and sys.platform == "darwin":
            p = os.path.join(DATA, "cli_ditto.zip")
            subprocess.run(["ditto", "-c", "-k", "--norsrc", "--keepParent", "tree", p], cwd=tree, check=True)
            note(p)
    finally:
        shutil.rmtree(tree)

    with open(os.path.join(DATA, "zips.txt"), "w") as f:
        for z in zips:
            f.write("%s\t%s\t%d\t%u\t%d\n" % z)
    print("wrote %d streams and %d archive entries" % (len(streams), len(zips)))


main()
