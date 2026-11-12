"""Shared helpers: build a messy folder, run Nova_Sort on it, and take a snapshot of what is on disk."""
import hashlib, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = os.path.join(ROOT, "host.py")
NOVA = os.path.join(ROOT, "novalang", "novalang.py")
SORT = os.path.join(ROOT, "sort.nova")

# (name, content): what the fixture folder holds before a run. Contents are all different, so a
# lost, overwritten or duplicated file shows up as a missing or repeated content.
FILES = [
    ("IMG_0001.JPG", "image one"),
    ("a.jpg", "image a"),
    ("report.pdf", "report"),
    ("notes.TXT", "notes"),
    ("backup.tar.gz", "archive"),
    ("song.mp3", "song"),
    ("clip.MOV", "clip"),
    ("setup.dmg", "installer"),
    ("tool.py", "code"),
    ("résumé.PDF", "resume"),
    ("my file (1).png", "spaced"),
    ("a.b.c.Jpeg", "dots"),
    ("mystery", "no extension"),
    ("trailing.", "trailing dot"),
    ("weird.xyz", "unknown"),
    (".DS_Store", "hidden"),
    (".bashrc", "hidden too"),
    ("movie.crdownload", "unfinished"),
    ("ISO.PART", "unfinished upper"),
]
EXPECTED = {
    "IMG_0001.JPG": "Images/IMG_0001.JPG", "a.jpg": "Images/a.jpg", "my file (1).png": "Images/my file (1).png",
    "a.b.c.Jpeg": "Images/a.b.c.Jpeg", "report.pdf": "Documents/report.pdf", "notes.TXT": "Documents/notes.TXT",
    "résumé.PDF": "Documents/résumé.PDF", "backup.tar.gz": "Archives/backup.tar.gz", "song.mp3": "Audio/song.mp3",
    "clip.MOV": "Video/clip.MOV", "setup.dmg": "Installers/setup.dmg", "tool.py": "Code/tool.py",
    "mystery": "review/mystery", "trailing.": "review/trailing.", "weird.xyz": "review/weird.xyz",
}
STAYS = [".DS_Store", ".bashrc", "movie.crdownload", "ISO.PART", "Projects", "link.txt"]


def make_fixture(extra=()):
    """A temporary world: world/target (the folder to sort) and world/outside (must never change)."""
    world = tempfile.mkdtemp(prefix="nova_sort_test_")
    target = os.path.join(world, "target")
    outside = os.path.join(world, "outside")
    os.makedirs(os.path.join(target, "Projects"))
    os.makedirs(outside)
    with open(os.path.join(outside, "secret.txt"), "w") as f:
        f.write("outside secret")
    with open(os.path.join(target, "Projects", "keep.txt"), "w") as f:
        f.write("inside a folder")
    for name, content in list(FILES) + list(extra):
        with open(os.path.join(target, name), "w", encoding="utf-8") as f:
            f.write(content)
    os.symlink(os.path.join("..", "outside", "secret.txt"), os.path.join(target, "link.txt"))
    return world, target, outside


def snapshot(folder):
    """{relative path: ("file", sha256) | ("dir",) | ("link", target)} for everything under folder."""
    seen = {}
    for here, dirs, files in os.walk(folder):
        for name in dirs + files:
            path = os.path.join(here, name)
            rel = os.path.relpath(path, folder)
            if os.path.islink(path):
                seen[rel] = ("link", os.readlink(path))
            elif os.path.isdir(path):
                seen[rel] = ("dir",)
            else:
                with open(path, "rb") as f:
                    seen[rel] = ("file", hashlib.sha256(f.read()).hexdigest())
    return seen


def contents(folder):
    """Sorted contents of every regular file under folder: what must survive any run."""
    out = []
    for here, _dirs, files in os.walk(folder):
        for name in files:
            path = os.path.join(here, name)
            if not os.path.islink(path):
                with open(path, "rb") as f:
                    out.append(f.read())
    return sorted(out)


def run_host(folder, apply=False, engine="vm"):
    args = [sys.executable, HOST, folder, "--engine", engine] + (["--apply"] if apply else [])
    return subprocess.run(args, capture_output=True, text=True, timeout=120)


def run_bootstrap(folder, apply=False):
    """The self-hosted interpreter has no embedding API, so it is driven through the command line with
    the same grants (`--allow-read .`, and `--allow-write .` only for --apply)."""
    args = [sys.executable, NOVA, "--profile", "restricted", "--allow-read", "."]
    if apply:
        args += ["--allow-write", "."]
    return subprocess.run(args + ["--bootstrap", SORT], capture_output=True, text=True, timeout=300, cwd=folder)


def run_probe(source, folder, read=True, write=False, bootstrap=False):
    """Run a few lines of NovaLang under the restricted profile with the given grants, inside folder."""
    path = os.path.join(os.path.dirname(folder), "probe.nova")
    with open(path, "w") as f:
        f.write(source)
    args = [sys.executable, NOVA, "--profile", "restricted"]
    if read:
        args += ["--allow-read", "."]
    if write:
        args += ["--allow-write", "."]
    return subprocess.run(args + (["--bootstrap"] if bootstrap else []) + [path],
                          capture_output=True, text=True, timeout=300, cwd=folder)


def text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def cleanup(world):
    shutil.rmtree(world, ignore_errors=True)
