# Nova_Sort

> **The second proof of concept for [NovaLang](https://github.com/ussdaedalus43821-cloud/Nova_Lang), after [Nova_Stats](https://github.com/ussdaedalus43821-cloud/Nova_Stats).**
> It tests the **M11 security sandbox** as much as the language: a file organizer that runs in the `restricted`
> profile with `files.read` and `files.write` for one folder and nothing else, and that must never delete a file.

It scans one folder (such as `~/Downloads`), reads each file's extension, creates category folders and moves the
files into them. Anything it does not recognise goes to `review/`.

## Run

```bash
python3 host.py ~/Downloads             # a DRY RUN: prints the plan, moves nothing
python3 host.py ~/Downloads --apply     # moves the files
python3 host.py ~/Downloads --engine tree   # the tree-walking engine instead of the bytecode VM
```

The default is a dry run. A real run needs `--apply`. Run it twice and the second run does nothing.

Example plan:

```
Nova_Sort: DRY RUN. Nothing is moved, and with only files.read granted nothing could be.
  skip    .DS_Store  (hidden)
  create  Documents/
  would   report.pdf  ->  Documents/report.pdf
  would   a.jpg  ->  Images/a (2).jpg  (name was taken)
  skip    Projects  (folder)

Summary: would move 2 files (Documents 1, Images 1), skipped 2, failed 0
To move them, run again with --apply.
```

## What it does and does not touch

- **Moves** (`rename`) files that sit directly in the folder into `Images`, `Documents`, `Archives`, `Audio`, `Video`,
  `Installers` or `Code`; unknown or extensionless files go to `review/`. The table is at the top of
  [`sort.nova`](sort.nova).
- **Never overwrites.** If the name is taken the file becomes `name (2).ext`, then `(3)`; names are compared without case.
- **Leaves alone:** hidden files, folders (nothing recurses), unfinished downloads (`.crdownload`, `.part`, `.download`,
  `.tmp`), and symbolic links that lead outside the folder.
- **Refuses a real run** while a link that points to somewhere inside the folder is there, because moving it would
  break it ([`docs/GAPS.md`](docs/GAPS.md) G-032).
- **Never deletes.** See below.

## How the sandbox is used

`host.py` gives the program **nothing**: no function, no value, no file access of its own. It starts NovaLang with
`Nova(profile="restricted", read=[folder])`, adds `write=[folder]` only for `--apply`, and starts the program inside
the folder. Every file operation (`listdir`, `exists`, `mkdir`, `rename`) is the sandbox's own, with the sandbox's own
path checks (`..`, other folders and links that lead out are refused).

- **Dry run = no write grant.** Without `files.write`, `rename` and `mkdir` are not even defined, so the program can
  print a plan and cannot carry it out. It is not a flag.
- **"Never delete" is kept by the application, not by the sandbox.** `files.write` also defines `remove`, `delete`,
  `write` and `copy`, and `rename` silently replaces an existing file ([G-027 and G-028](docs/GAPS.md)). So
  `sort.nova` uses only `rename`, `mkdir`, `exists` and `listdir`, checks for a free name before every move, and
  `tests/test_safety.py` fails if the source ever names anything that removes or overwrites. These are the two gaps to
  close in M13.

## Layout

| Path | Role |
| --- | --- |
| `sort.nova` | the program: scan, classify, plan, move |
| `host.py` | the launcher: grants the sandbox, starts the program, checks for links |
| `docs/GAPS.md` | every gap found (G-027 to G-035) and what worked |
| `tests/` | 26 tests: behaviour, safety, the sandbox, and gap probes, on all three engines |
| `novalang/` | the interpreter, copied unmodified (see `novalang/VENDORED.md`) |

## Test

```bash
python3 tests/run_suite.py
```

The behaviour tests build a messy folder in a temporary directory and check, on the VM, the tree-walker and the
self-hosted interpreter, that the plan and the result are identical, that no file is lost, duplicated or changed,
that nothing outside the folder changes, and that a second run does nothing.

## Limits

One folder, one level; no undo (the printed plan is the record); no stamping or logging (the program has no clock
and no write); it assumes a case-insensitive file system and numbers a name it did not need to on a case-sensitive
one (G-035). A dry run on a folder is a plan for that moment: another process can change the folder before `--apply`.
