# GAPS.md - where NovaLang struggled building Nova_Sort

The second proof of concept, after Nova_Stats. Nova_Stats tested the language; this one tests the **M11 sandbox**:
a file organizer that runs in the `restricted` profile with `files.read` and `files.write` granted for one folder
and nothing else, under the rule that it must never delete a file. Numbering continues from Nova_Stats (G-001 to
G-026), so these start at G-027 and the ecosystem has one list.

Written against NovaLang v2.2.0 (`develop` at f458f1d). Entries marked **M13** are the ones to fix there.

**Update for NovaLang 2.4 (`develop` at 34a6256):** G-030 and G-031 are closed by the standard library. `sort.nova` now
imports `std:files` (`is_dir`) and `std:text` (`splitext`) and the hand-written versions are gone; the output and the
resulting folder are byte for byte the same as before on all three engines (99 awkward names, dry run and real run).
G-032 is closed the same way: the link guard moved from `host.py` into `sort.nova` (`std:files.is_link`).

**How to read an entry.** *Tried* is what was attempted and the exact result. *Workaround* says what the code does
instead and **who does the work**: `program` (sort.nova), `host` (host.py) or `none` (cannot be done). *Probe* is a
reproducible check in `tests/`; the ones marked "gap probe" pass while the gap exists and fail the day NovaLang is
fixed, so this log cannot rot.

**Severity:** LIMIT (the sandbox cannot express what is needed) - BLOCKER (needs the host) - FRICTION (worked around
in the program) - minor.

| # | Gap | Severity | Who works around it | M13 |
| --- | --- | --- | --- | --- |
| G-027 | `files.write` also grants `remove` and `delete` | LIMIT | program rule + test | yes |
| G-028 | `rename` silently replaces an existing file | LIMIT | program (`exists` first) | yes |
| G-029 | No way to ask which capabilities were granted | FRICTION | program (probe a name) | |
| G-030 | No `isdir` or `stat`: a folder is "a path `listdir` accepts" | FRICTION, **closed in 2.4** | `std:files.is_dir` | yes |
| G-031 | No `splitext`/`basename`: the extension is split by hand | minor, **closed in 2.4** | `std:text.splitext` | yes |
| G-032 | No `lstat`/`islink`: a link cannot be told from a file | BLOCKER (for links), **closed in 2.4** | `std:files.is_link` | yes |
| G-033 | The target folder can only arrive through the working directory | FRICTION | host | |
| G-034 | The CLI reads the flag after `--bootstrap` as the program; the self-hosted engine cannot be embedded | FRICTION | tests | |
| G-035 | No way to learn whether the file system ignores case | minor | program (assumes it does) | |

---

## G-027 `files.write` also grants `remove` and `delete` - LIMIT (M13)
- **Tried:** granted `files.write` for one folder and ran `remove("doomed.txt")` and `delete("doomed2.txt")`. Both
  worked, on the VM and on the self-hosted engine (`remove`). The capability table in `docs/spec/16-sandbox.md` says it
  plainly: `files.write` defines `write`, `mkdir`, `remove`, `rename`, `copy`, the file form of `append` and the
  `delete` statement of a file. There is no grant for "move and create, but never destroy".
- **Why it matters:** "this program may only reorganise" is the commonest thing to want from a file tool, and the
  sandbox cannot say it. The grant is a folder, not an action.
- **Workaround (program):** the rule is kept in the application. `sort.nova` uses only `rename`, `mkdir`, `exists`,
  `listdir`; `tests/test_safety.py` strips comments and strings from the source and fails if `remove`, `delete`,
  `write`, `copy` or `append` (or `python`, `regex`, `exit`) appears as code, and also scans `host.py`. This is a
  convention enforced by a test, not by the sandbox: a program that did not run the test is not constrained.
- **Suggested for M13:** split the capability: `files.move` (create folders and rename inside the grant, never over
  an existing file), `files.append` (for logs), `files.write` (replace contents) and `files.delete` as its own grant.
- **Probe:** `tests/test_safety.py` `test_G027_a_write_grant_defines_remove_and_delete` (gap probe, both engines).

## G-028 `rename` silently replaces an existing file - LIMIT (M13)
- **Tried:** with `one.txt` ("one") and `two.txt` ("two"), `rename("one.txt", "two.txt")` printed nothing, and
  `two.txt` now held "one". The old `two.txt` is gone with no error, on both engines. The sandbox checks that both
  paths are inside the grant and nothing more, so this is a deletion by another name.
- **Workaround (program):** before every move the program checks `exists(target)` and picks a free name instead
  (`photo.jpg` becomes `photo (2).jpg`, then `(3)`), comparing without case. It checks again immediately before the
  `rename`. The check and the use are two steps, and `docs/spec/16-sandbox.md` says so (threat model N5): another
  process could create the name in between. Nothing in NovaLang can close that window.
- **Suggested for M13:** `rename(old, new)` should fail if `new` exists unless the caller says otherwise, and a
  create-only mode that is atomic.
- **Probe:** `tests/test_safety.py` `test_G028_rename_silently_replaces_an_existing_file` (gap probe, both engines);
  `tests/test_sort.py` `Collisions` shows the workaround keeping both files.

## G-029 No way to ask which capabilities were granted - FRICTION
- **Tried:** the program needs to know whether it may move files (to print "would move" or "moved"). There is no
  `capabilities()`. A name that was not granted is "undefined name", so the program evaluates a name that only
  `files.write` defines: `try { rename; return true } catch e { return false }`.
- **Workaround (program):** `may_write()`. It works the same on the VM, the tree-walker and the self-hosted engine.
- **Note:** this is what the spec's "a program cannot tell a denied capability from a name that does not exist" looks
  like from the inside. It is consistent, but it means the dry run is not a flag at all: **leaving out the write grant
  is the dry run**, and the program only reports it. That turned out to be a strength (see "What worked").

## G-030 No `isdir` or `stat`; a folder is "a path `listdir` accepts" - FRICTION (M13)
- **Tried:** to skip sub-folders the program needs to know what a name is. `exists` is true for both. The only test
  is `listdir(path)` inside `try`.
- **Workaround (program):** `is_folder()`. A file fails with `FileError: ... is a file, not a directory`, a link that
  leads outside the grant fails with `... is outside the folders this program may use`: both "not a folder", told
  apart only by the message text, which the program does not parse.
- **Closed (NovaLang 2.4):** `is_folder()` is now `std:files.is_dir` inside `try`: true for a folder or a link to one,
  false for a file. The read grant is still judged first, so a path outside the folder throws and is "do not touch".
- **Probe:** `tests/test_safety.py` `test_G030_listdir_cannot_tell_a_file_from_a_refused_path` (gap probe; it still
  passes, because `listdir` itself is unchanged - the answer is the library, not `listdir`).

## G-031 No `splitext`/`basename`: how hard is an extension without regex? - minor (M13)
- **Tried:** `split(name, ".")`, then the last piece. It was **not hard**: `split_name()` is eight lines and needs no
  regex (which `restricted` withholds anyway). `"a.tar.gz"` is `gz`, which is in `Archives`; `"a.b.c.Jpeg"` is `Jpeg`,
  lower-cased with `lower`; `"mystery"` and `"trailing."` have no extension and go to `review/`. A name that starts
  with a dot is hidden and skipped before the question comes up.
- **What is missing:** the name of a path (`dirname` exists, `basename` does not) and `splitext`. A compound
  extension (`.tar.gz` as one unit) is not distinguished; here it does not matter because both parts are archives.
- **Closed (NovaLang 2.4):** `split_name()` is `std:text.splitext` with the dot dropped. `splitext("a.")` is
  `["a", "."]`, which the program reads as "no extension" as before, so a taken `a.` is still numbered `a. (2)`.
- **Probe:** `tests/test_sort.py` (`EXPECTED` in `tests/common.py` covers upper-case, dotted, spaced, accented,
  no-extension and trailing-dot names).

## G-032 No `lstat`/`islink`: a link cannot be told from a file - BLOCKER for links (M13)
- **Tried:** a symbolic link to a file inside the folder (`inner.txt -> real.txt`) is an ordinary-looking name.
  `rename` moved the link itself into `Documents/`, where its relative target no longer exists: **a broken link**.
  A link that leads *outside* the folder is a different case and the sandbox handles it: every function refuses it
  (`FileError: ... is outside the folders this program may use`), so the program probes with `exists` and skips it.
- **Workaround (host):** `host.py` is the one place that can tell. Before launching it looks for top-level links that
  stay inside the folder; it warns in a dry run and **refuses to start a real run** until they are removed. It
  reads the folder but never changes it. This is the only thing the launcher does other than grant and start.
- **Closed (NovaLang 2.4):** `sort.nova` lists the folder's links with `std:files.is_link` before it moves anything. A real
  run `throw`s (the program has no `exit` or stderr without the `process` grant, so the launcher reports "the program
  stopped" and exits 1, where it used to exit 2); a dry run prints the warning in the plan. A link that leads out still
  throws on `is_link` and is skipped. `host.py` no longer reads the folder at all.
- **Probe:** `tests/test_sort.py` `InsideLinks`; `Apply.test_no_file_is_lost_duplicated_or_changed` for the outside link.

## G-033 The target folder can only arrive through the working directory - FRICTION
- **Tried:** the program needs to be told which folder to sort. `args()` and `cwd()` belong to the `process`
  capability, which also grants `exit`, `abspath` and `realpath` ("reveal the layout of the machine"). The brief was
  `files.read` and `files.write` only.
- **Workaround (host):** `host.py` starts the program inside the folder (`os.chdir`) and the program works on
  `"."`. Relative paths resolve against the engine's working directory without any capability. No value or function is
  handed to the program.
- **Note:** there is no argument-passing capability smaller than `process`.

## G-034 The CLI reads the flag after `--bootstrap` as the program; the self-hosted engine cannot be embedded - FRICTION
- **Tried:** `novalang.py --bootstrap --profile restricted --allow-read . sort.nova` fails with
  `FileNotFoundError: .../--profile`: `--bootstrap` takes the next word as the program. The working order is
  `--profile restricted --allow-read . --bootstrap sort.nova`. Nothing in `--help` says so.
- **Also:** `Nova()` (the embedding API) takes `engine="vm"` or `"tree"` only. The self-hosted interpreter has no
  embedding, which is why `host.py` has `--engine vm|tree` and the tests drive the third engine through the command
  line with the same grants. (Already G-020 in Nova_Stats.)
- **Workaround (tests):** `tests/common.py` `run_bootstrap`.

## G-035 No way to learn whether the file system ignores case - minor
- **Tried:** on a Mac `a.JPG` and `a.jpg` cannot sit side by side, on Linux they can. The program has no way to ask.
- **Workaround (program):** it assumes the stricter rule everywhere: taken names are compared in lower case, so on a
  case-sensitive file system it numbers a file it did not need to (never the other way round).
- **Probe:** `tests/test_sort.py` `Collisions.test_a_name_that_differs_only_in_case_is_taken_too`.

---

## What worked (no entry needed)
- **A read-only grant is a real dry run.** With only `files.read`, `rename`, `mkdir`, `remove` and `write` are not
  defined, so the program can print a plan and cannot act on it. A flag could be wrong; a missing capability cannot.
  `tests/test_safety.py` `test_a_dry_run_cannot_move_anything_even_if_it_tried`.
- **How the sandbox handles moving files:** `rename` between two folders inside the grant just works, and both paths
  are checked. `..`, an absolute path elsewhere, a sibling folder, and a link that leads out are all refused with the
  same `FileError`, on the VM and the self-hosted engine, **before** the file system is touched.
  `tests/test_safety.py` `Sandbox`.
- **The same answer on every engine.** The plan and the resulting folder are identical on the VM, the tree-walker and
  the self-hosted interpreter (`tests/test_sort.py`).
- **`listdir` is sorted**, so the plan is deterministic and the tests can compare whole outputs.
- **Sandbox errors are catchable** (`try/catch`), which is what makes the probes in G-029 and G-030 possible.
- **No clock, no randomness, no environment** were needed, and none were granted: a taken name is numbered instead of
  stamped.
- **The launcher is 61 lines and gives the program nothing.** It grants and starts; every file operation is the sandbox's.
