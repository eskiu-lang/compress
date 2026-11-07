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

## Documentation

- [Raw DEFLATE and size limits](docs/README.md#raw-deflate-and-size-limits)
- [ZIP archives](docs/README.md#zip-archives)
- [Size and speed](docs/README.md#size-and-speed)
- [Platforms](docs/README.md#platforms)
- [Modules](docs/README.md#modules)
- [Contributing](docs/README.md#contributing)
- [API reference](docs/api.md): every public function and type

## Install

In an Eskiu package (Eskiu 0.12 or newer):

```bash
eskiuc add compress --git https://github.com/eskiu-lang/compress --rev v0.1.0
```

Then `import <compress>;`, or only the module you need.

## License

MIT. See [LICENSE](LICENSE).
