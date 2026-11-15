# Chaos test: a hostile folder

`tests/test_chaos.py` (in `tests/run_suite.py`, on Linux and macOS in CI) sorts a folder that holds:

- a file whose name is **255 Unicode characters** (`é` × 251 + `.txt`, 506 bytes). Linux allows 255 bytes
  in a name, so there the name is cut to the longest one that fits.
- a **symbolic link loop**: `A -> B`, `B -> A`.
- **files that cannot be moved**: `locked.pdf` is marked immutable (`chflags uchg`, macOS; moving it needs
  the flag cleared, which a sandboxed program cannot do), and `photo.jpg` goes to an `Images/` folder that
  is read-only (both systems; skipped when the test runs as root).

**Pass condition**: no Python traceback, a clean message, **no file lost**. After every run the contents of
all the files are still in the folder, and both links are still links.

| Case | Dry run | `--apply` |
| --- | --- | --- |
| 255-character name | `would … -> Documents/…` | moved, exit 0 |
| cannot be moved | listed | `FAILED  photo.jpg  (FileError: rename(): Permission denied)`, the file stays, the rest is sorted, `failed 1` (2 on macOS), exit 0 |
| link loop | exit 0, warns `2 symbolic link(s) here lead to somewhere inside this folder … A real run will refuse to start` | exit 1, `Nova_Sort: the program stopped: … nothing was moved`, folder unchanged |
| all at once | as above | as above: refused, nothing moved, nothing lost |

## Where this differs from "skip the weird file, sort the rest"

Two tests state that condition as asked for and are marked `expectedFailure`, so the suite stays green and
the gap stays visible. Each will report "unexpected success" if the design changes.

1. **A real run refuses to start while a link inside the folder exists**, a loop included. It does not skip
   the link and go on. This is the G-032 design: a link that points at a file in this folder would break
   when that file is moved, so the whole run stops before anything moves. The check uses `std:files.is_link`
   (`links_inside` in `sort.nova`). For a loop the refusal is stricter than it needs to be: neither link's
   target is a file that would be moved.
2. **The dry run plans to move the links** (`would   A  ->  review/A`) while warning that a real run will refuse.

`std:files.is_dir` is false for both links (a loop resolves to nothing), so neither is mistaken for a folder.

**Exit status**: a run with `FAILED` lines still exits 0, and the summary counts the failures.
