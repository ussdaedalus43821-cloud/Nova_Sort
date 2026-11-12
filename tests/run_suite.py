"""The whole suite, timed. Run from anywhere: python3 tests/run_suite.py"""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEPS = [
    ("behaviour: dry run, apply, collisions, links, on VM, tree-walker and self-hosted", ["tests.test_sort"]),
    ("safety: never deletes, the sandbox, and the gap probes", ["tests.test_safety"]),
]
failed = False
for title, modules in STEPS:
    started = time.time()
    done = subprocess.run([sys.executable, "-m", "unittest"] + modules, cwd=ROOT, capture_output=True, text=True)
    ran = [l for l in done.stderr.splitlines() if l.startswith("Ran ")]
    print("%-80s %5.1fs  exit %d  %s" % (title, time.time() - started, done.returncode, ran[0] if ran else ""))
    if done.returncode:
        failed = True
        print(done.stderr)
print("RED" if failed else "GREEN")
sys.exit(1 if failed else 0)
