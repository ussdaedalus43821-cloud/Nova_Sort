"""The "never delete a file" rule, and what the sandbox does and does not enforce.

The first class is the rule itself, kept at the application level because the sandbox cannot keep it
(G-027). The second class is the sandbox: what it denies, and, as probes that fail the day NovaLang is
fixed, the two things it does not (G-027, G-028).
Run: python3 -m unittest tests.test_safety -v"""
import os, re, unittest

from tests.common import SORT, HOST, cleanup, make_fixture, run_probe, snapshot, text

# Everything `files.write` defines that removes, replaces or changes a file's contents. `rename` and
# `mkdir` are the only two write-side names the program may use.
FORBIDDEN = ("remove", "delete", "write", "copy", "append", "python", "regex", "replace_all", "exit")


def code_only(source):
    """The program with its comments and string literals blanked out, so a word in a comment or in a
    message does not count, and a name used as code does."""
    out, i, n = [], 0, len(source)
    while i < n:
        c = source[i]
        if c == "#":
            while i < n and source[i] != "\n":
                i += 1
        elif c == '"':
            i += 1
            while i < n and source[i] != '"':
                i += 2 if source[i] == "\\" else 1
            i += 1
            out.append('""')
        else:
            out.append(c)
            i += 1
    return "".join(out)


class NeverDeletes(unittest.TestCase):
    def test_the_program_never_names_anything_that_removes_or_overwrites(self):
        code = code_only(text(SORT))
        self.assertIn("rename", code)            # the scanner can see code at all
        for word in FORBIDDEN:
            self.assertIsNone(re.search(r"\b%s\b" % word, code), "sort.nova uses %r" % word)

    def test_the_scanner_catches_what_it_is_for(self):
        self.assertIsNotNone(re.search(r"\bremove\b", code_only('remove("x")')))
        self.assertIsNotNone(re.search(r"\bdelete\b", code_only("delete notes.txt")))
        self.assertIsNone(re.search(r"\bremove\b", code_only('# remove it\nprint("remove")')))

    def test_the_launcher_does_nothing_to_files_itself(self):
        code = code_only(text(HOST))
        for word in ("remove", "unlink", "rmdir", "rmtree", "rename", "replace", "shutil", "open", "write",
                     "expose", "expose_global", "python"):
            self.assertIsNone(re.search(r"\b%s\b" % word, code), "host.py uses %r" % word)

    def test_a_dry_run_cannot_move_anything_even_if_it_tried(self):
        world, target, _ = make_fixture()
        self.addCleanup(cleanup, world)
        before = snapshot(target)
        done = run_probe('try { rename("mystery", "review/mystery") } catch e { print("denied: " + str(e)) }\n'
                         'try { mkdir("review") } catch e { print("denied: " + str(e)) }\n'
                         'try { remove("mystery") } catch e { print("denied: " + str(e)) }\n', target)
        self.assertEqual(done.stdout.count("undefined name"), 3, done.stdout + done.stderr)
        self.assertEqual(snapshot(target), before)


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.world, self.target, self.outside = make_fixture()
        self.addCleanup(cleanup, self.world)

    def probe(self, source, **kwargs):
        done = run_probe(source, self.target, **kwargs)
        return done.stdout + done.stderr

    def test_a_path_outside_the_folder_is_refused_for_reading_and_writing(self):
        for engine in (False, True):
            out = self.probe('try { listdir("../outside") } catch e { print(str(e)) }\n'
                             'try { rename("mystery", "../outside/mystery") } catch e { print(str(e)) }\n'
                             'try { exists("../outside/secret.txt") } catch e { print(str(e)) }\n',
                             write=True, bootstrap=engine)
            self.assertEqual(out.count("is outside the folders this program may use"), 3, out)
        self.assertFalse(os.path.exists(os.path.join(self.outside, "mystery")))

    def test_a_link_that_leads_out_is_refused_even_though_it_sits_inside(self):
        out = self.probe('try { rename("link.txt", "Documents.txt") } catch e { print(str(e)) }\n', write=True)
        self.assertIn("is outside the folders this program may use", out)
        self.assertEqual(snapshot(self.outside)["secret.txt"][0], "file")
        self.assertEqual(snapshot(self.target)["link.txt"][0], "link")

    def test_no_clock_args_or_env_without_their_capabilities(self):
        out = self.probe('for n in ["args", "env", "cwd", "exit", "now", "time", "sleep", "input", "regex"] {\n'
                         '    try { n } catch e { print("x") }\n}\n'
                         'try { args } catch e { print(str(e)) }\ntry { env } catch e { print(str(e)) }\n'
                         'try { now } catch e { print(str(e)) }\n', write=True)
        for name in ("args", "env", "now"):
            self.assertIn("undefined name '%s'" % name, out)


class SandboxGaps(unittest.TestCase):
    """These pass while the gaps exist and fail when NovaLang closes them: then update docs/GAPS.md."""

    def setUp(self):
        self.world, self.target, self.outside = make_fixture()
        self.addCleanup(cleanup, self.world)

    def test_G027_a_write_grant_defines_remove_and_delete(self):
        for bootstrap in (False, True):
            path = os.path.join(self.target, "doomed.txt")
            with open(path, "w") as f:
                f.write("x")
            done = run_probe('remove("doomed.txt")\nprint("remove ran")\n', self.target, write=True, bootstrap=bootstrap)
            self.assertIn("remove ran", done.stdout, done.stderr)
            self.assertFalse(os.path.exists(path), "files.write should (today) include remove")
        with open(os.path.join(self.target, "doomed2.txt"), "w") as f:
            f.write("x")
        done = run_probe('delete("doomed2.txt")\nprint("delete ran")\n', self.target, write=True)
        self.assertIn("delete ran", done.stdout, done.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.target, "doomed2.txt")))

    def test_G028_rename_silently_replaces_an_existing_file(self):
        for bootstrap in (False, True):
            with open(os.path.join(self.target, "one.txt"), "w") as f:
                f.write("one")
            with open(os.path.join(self.target, "two.txt"), "w") as f:
                f.write("two")
            done = run_probe('rename("one.txt", "two.txt")\nprint("renamed")\n', self.target, write=True, bootstrap=bootstrap)
            self.assertIn("renamed", done.stdout, done.stderr)
            self.assertEqual(text(os.path.join(self.target, "two.txt")), "one", "the old two.txt is gone, with no error")
            self.assertFalse(os.path.exists(os.path.join(self.target, "one.txt")))
            os.remove(os.path.join(self.target, "two.txt"))

    def test_G030_listdir_cannot_tell_a_file_from_a_refused_path(self):
        done = run_probe('for p in ["mystery", "link.txt", "Projects"] {\n'
                         '    try { listdir(p); print(p + ": folder") } catch e { print(p + ": " + str(e)) }\n}\n', self.target)
        lines = dict(l.split(": ", 1) for l in done.stdout.strip().splitlines())
        self.assertEqual(lines["Projects"], "folder")
        self.assertIn("is a file, not a directory", lines["mystery"])
        self.assertIn("is outside the folders", lines["link.txt"])     # a different message, but only by text


if __name__ == "__main__":
    unittest.main()
