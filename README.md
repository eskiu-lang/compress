<p align="center">
  <img src="https://raw.githubusercontent.com/eskiu-lang/eskiu/main/assets/logo.png" alt="Eskiu, a kitten with a ball of yarn" width="140">
</p>

<h2 align="center">compress</h2>
<p align="center">zlib, gzip, raw DEFLATE and ZIP archives for Eskiu, written in Eskiu.</p>
<p align="center"><sub>Part of the <a href="https://github.com/eskiu-lang">Eskiu</a> project</sub></p>
<p align="center">
  <a href="https://eskiu-lang.org">eskiu-lang.org</a> &nbsp;&middot;&nbsp;
  <a href="#modules">Modules</a> &nbsp;&middot;&nbsp;
  <a href="examples/">Examples</a> &nbsp;&middot;&nbsp;
  <a href="https://github.com/eskiu-lang/eskiu">The language</a>
</p>

<p align="center">
  <a href="https://github.com/eskiu-lang/compress/actions/workflows/ci.yml"><img src="https://github.com/eskiu-lang/compress/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/version-0.1.0-6448d4" alt="Version 0.1.0">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT"></a>
</p>

---

`compress` is an Eskiu package for DEFLATE compression and decompression, the zlib and
gzip formats built on it, and ZIP archives. It has no dependencies beyond the Eskiu
standard library: no zlib, no C code, and the same behavior on Linux, macOS and Windows.

- **DEFLATE at levels 0 to 9.** The encoder follows zlib's design (hash chains over a
  32 KB window, lazy matching from level 4) and writes each block in whichever form is
  smallest: stored, fixed Huffman codes or the block's own length-limited codes. The output
  is about the size zlib's is at the same level, usually a little smaller.
- **zlib and gzip.** Both directions, with the Adler-32 or CRC-32 and size checked on the
  way in. gzip files may have several members, a file name, a comment and a time.
- **ZIP archives.** Read from memory or a file, list the entries, read one by index or name,
  or extract them all into a directory. Write archives with directories and entries at any
  level. Stored and deflate entries, ZIP64 in both directions.
- **Safe on hostile input.** Every read is bounds checked, truncated data is an error, and
  output is capped by a size limit (1 GB unless you give one), so a small file cannot expand
  into all of memory.
- **Errors as `Result`.** Every call that can fail returns one, with a short message such as
  `gzip: checksum mismatch` or `inflate: truncated`.

## gzip and zlib

```eskiu
import <io>;
import <compress>;

Result<int, string> run(*uint8 data, uint64 n) {
    Bytes gz = gzip_compress(data, n, 9)?;
    defer gz.free();
    Bytes back = gzip_decompress(gz.data, (uint64)gz.len)?;
    defer back.free();
    printf("%llu -> %lld -> %lld bytes\n", n, gz.len, back.len);
    return Ok<int, string>(0);
}
```

`zlib_compress` and `zlib_decompress` work the same way. The gzip header can carry a name,
a comment and a modification time, and `gzip_header` reads them back:

```eskiu
GzipOptions o = GzipOptions{level: 6, name: "notes.txt", mtime: 1700000000};
Bytes gz = gzip_compress_with(data, n, &o)?;
GzipHeader h = gzip_header(gz.data, (uint64)gz.len)?;
printf("%s, modified %u\n", h.name.data, h.mtime);
h.free();
```

Decompressing a gzip file joins all its members, as `cat a.gz b.gz` would make them, and
ignores zero bytes after the last one. Each member's CRC-32 and size are checked.

## Raw DEFLATE and size limits

```eskiu
Bytes comp = deflate_raw(data, n, 6)?;
Bytes back = inflate_raw(comp.data, (uint64)comp.len)?;                   // at most 1 GB
Bytes small = inflate_raw_limit(comp.data, (uint64)comp.len, 1 << 20)?;   // at most 1 MB
uint64 got = inflate_raw_into(comp.data, (uint64)comp.len, buf, cap)?;    // into your buffer
```

A stream that would produce more than the limit fails with
`inflate: output exceeds the size limit` as soon as it crosses it. The `_limit` form exists for
zlib and gzip too, and `zlib_decompress_into` fills a buffer you sized, for formats such as
PNG that state the output size. `inflate_raw_append` decodes onto the end of an existing
`Bytes` and returns how many input bytes the stream took, for formats that put data after it.

## ZIP archives

```eskiu
ZipReader z = ZipReader_open("pack.zip")?;
defer z.close();
for (i in 0..z.count()) {
    ZipEntry* e = z.entry(i);
    printf("%10llu  %s\n", e.size, e.name.data);
}
Bytes readme = z.read_name("docs/readme.txt")?;
defer readme.free();
z.extract_all("out")?;
```

Each `ZipEntry` has the name, the sizes, the method, the CRC-32, the modification time
(Unix seconds) and whether it is a directory. Reading an entry checks its local header, its
size and its CRC-32. `ZipReader_from` opens an archive already in memory.

```eskiu
ZipWriter w = ZipWriter_new();
defer w.free();
w.add_dir("docs")?;
w.add("docs/readme.txt", (*uint8)text, strlen(text), 9)?;
w.add_file("logo.png", "assets/logo.png", 0)?;      // level 0 stores it
w.finish_file("pack.zip")?;                          // or w.finish() for the bytes
```

An entry that does not get smaller when deflated is stored. Names with non-ASCII characters
are marked as UTF-8. Entries get the time of `ZipWriter_new` unless `w.mtime` is set, and
ZIP64 records are written when an archive needs them (an entry or offset of 4 GB or more,
or 65535 entries or more), or always with `w.zip64 = true`.

What the reader refuses, with an error:

- encrypted entries, methods other than stored and deflate, and archives split over disks;
- an entry whose data inflates past the size its directory states, or whose stated size is
  over the reader's limit (`z.limit`, 1 GB by default);
- for `extract_all`, any entry name that is empty, absolute (`/x`, `\x`, `C:x`) or has a
  `..` component with either separator. All names are checked before anything is written.
  Symbolic links are written as regular files holding the link target.

ZIP times are stored in DOS format, which has 2-second steps, no time zone and the years
1980 to 2107. This package reads and writes them as UTC. When an entry carries the
extended timestamp field (as Info-ZIP's `zip` writes), its exact Unix time is used.

## Size and speed

Raw DEFLATE on an Apple Silicon Mac, against Python 3.10's zlib (zlib 1.3.2), best of three
runs, built with `-O2`. The text corpus is 4.1 MB of Eskiu's documentation and compiler
sources; the binary corpus is the first 8 MB of a Mach-O executable.

| Corpus | Level | `compress` size | zlib size | `compress` deflate | zlib deflate | `compress` inflate | zlib inflate |
|---|---|---|---|---|---|---|---|
| text | 1 | 1,295,304 (31.34%) | 1,303,171 (31.53%) | 19 ms | 21 ms | 9 ms | 7 ms |
| text | 6 | 1,044,478 (25.27%) | 1,045,715 (25.30%) | 91 ms | 69 ms | 7 ms | 6 ms |
| text | 9 | 1,033,756 (25.01%) | 1,034,430 (25.03%) | 298 ms | 214 ms | 8 ms | 6 ms |
| binary | 1 | 3,299,386 (41.24%) | 3,354,024 (41.93%) | 51 ms | 60 ms | 22 ms | 18 ms |
| binary | 6 | 2,967,556 (37.09%) | 2,972,015 (37.15%) | 182 ms | 191 ms | 19 ms | 16 ms |
| binary | 9 | 2,961,369 (37.02%) | 2,963,169 (37.04%) | 260 ms | 254 ms | 19 ms | 16 ms |

`tools/bench.esk` and `tools/bench.py` make these measurements for any file.

## Install

In an Eskiu package (Eskiu 0.12 or newer):

```bash
eskiuc add compress --git https://github.com/eskiu-lang/compress --rev v0.1.0
```

Then `import <compress>;`, or only the module you need.

## Modules

| Module | What it has |
|---|---|
| `<compress>` | all the modules below |
| `<compress/checksum>` | `crc32`, `crc32_update`, `adler32`, `adler32_update` |
| `<compress/inflate>` | `inflate_raw`, `inflate_raw_limit`, `inflate_raw_into`, `inflate_raw_append`, `INFLATE_DEFAULT_LIMIT` |
| `<compress/deflate>` | `deflate_raw`, `deflate_raw_append`, `deflate_bound` |
| `<compress/zlib>` | `zlib_compress`, `zlib_decompress`, `zlib_decompress_limit`, `zlib_decompress_into` |
| `<compress/gzip>` | `gzip_compress`, `gzip_compress_with` and `GzipOptions`, `gzip_decompress`, `gzip_decompress_limit`, `gzip_header` and `GzipHeader` |
| `<compress/zip>` | `ZipReader` (`open`, `from`, `count`, `entry`, `find`, `read`, `read_name`, `extract_all`, `close`), `ZipEntry`, `ZipWriter` (`new`, `add`, `add_dir`, `add_file`, `finish`, `finish_file`, `free`), `zip_name_is_safe` |

Compressed and decompressed data comes back in a `Bytes` from the standard library's
`<bytes>`, which the caller frees. Levels outside 0 to 9 are clamped.

## Contributing

Bug reports are welcome; please include the input that fails, if you can share it, and the
`eskiuc --version` output. The tests and tools run from the package root:

```bash
eskiuc test                                  # every tests/*.esk
python3 -I tools/gen_vectors.py              # regenerates tests/data with Python and zip/ditto
python3 -I tools/check_with_python.py        # checks what the package writes with Python
eskiuc -O2 tools/bench.esk -o build/bench && build/bench FILE 1 6 9
```

`tests/corrupt.esk` cuts and corrupts streams and archives and checks that each one fails
cleanly; raising its `ITERATIONS` and building it with `--asan --safe` makes a longer fuzz
run. CI runs the tests on Linux, macOS and Windows, and the Python check on Linux and macOS.

## License

MIT. See [LICENSE](LICENSE).
