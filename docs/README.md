# compress documentation

Guides and reference for compress. The [README](../README.md) has the overview.

<!-- pages -->
- [API reference](api.md): every public function and type
<!-- /pages -->

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

## Platforms

The package is plain Eskiu with no native library, so it builds for every target Eskiu has:
macOS, Linux and Windows, iOS and Android, WebAssembly, and freestanding builds. Its tests
pass on macOS, Linux and Windows in CI, under node as WebAssembly (emscripten) and on an
Android arm64 emulator.

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

Every public function and type, with its documentation, is in the [API reference](api.md).

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
