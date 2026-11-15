"""The launcher for Nova_Sort. It gives the program nothing: no function, no value, no file access of
its own. It starts NovaLang's `restricted` profile and grants `files.read`, and with --apply
`files.write`, for ONE folder. Everything else, including every file operation, is the sandbox's own.

The program is started inside the folder it sorts and works on ".", so it needs no argument and no
`process` capability (which would also give it `exit`, `cwd` and `realpath`).

Usage: python3 host.py FOLDER [--apply] [--engine vm|tree]
       default: a dry run (read grant only). --apply adds the write grant.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "novalang"))
from novalang import Nova, NovaLangError


def main(arguments):
    apply = "--apply" in arguments
    engine = "vm"
    if "--engine" in arguments:
        engine = arguments[arguments.index("--engine") + 1]
    positional = [a for i, a in enumerate(arguments)
                  if not a.startswith("--") and (i == 0 or arguments[i - 1] != "--engine")]
    if len(positional) != 1 or engine not in ("vm", "tree"):
        print(__doc__.strip().splitlines()[-3], file=sys.stderr)
        return 2
    folder = os.path.realpath(os.path.expanduser(positional[0]))
    if not os.path.isdir(folder):
        print("Nova_Sort: %s is not a folder" % positional[0], file=sys.stderr)
        return 2
    program = os.path.join(HERE, "sort.nova")
    os.chdir(folder)
    grants = {"read": [folder]}
    if apply:
        grants["write"] = [folder]
    nova = Nova(engine=engine, profile="restricted", **grants)
    try:
        nova.load_file(program)
    except KeyboardInterrupt:
        print("\nStopping Nova_Sort...", file=sys.stderr)
        return 130
    except NovaLangError as error:
        print("Nova_Sort: the program stopped: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
