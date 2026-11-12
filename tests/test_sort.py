"""Behaviour of Nova_Sort on a messy folder, on every engine. Run: python3 -m unittest tests.test_sort -v"""
import os, unittest

from tests.common import (EXPECTED, STAYS, cleanup, contents, make_fixture, run_bootstrap, run_host,
                          snapshot, text)

ENGINES = ("vm", "tree", "bootstrap")


def run(engine, target, apply):
    return run_bootstrap(target, apply) if engine == "bootstrap" else run_host(target, apply, engine)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.world, self.target, self.outside = make_fixture()
        self.addCleanup(cleanup, self.world)


class DryRun(Fixture):
    def test_the_default_changes_nothing_on_every_engine(self):
        for engine in ENGINES:
            with self.subTest(engine=engine):
                before, outside_before = snapshot(self.target), snapshot(self.outside)
                done = run(engine, self.target, apply=False)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn("DRY RUN", done.stdout)
                self.assertIn("To move them, run again with --apply.", done.stdout)
                self.assertEqual(snapshot(self.target), before)
                self.assertEqual(snapshot(self.outside), outside_before)

    def test_the_plan_names_every_move(self):
        done = run_host(self.target)
        for name, destination in EXPECTED.items():
            self.assertIn("%s  ->  %s" % (name, destination), done.stdout)
        self.assertIn("would move %d files" % len(EXPECTED), done.stdout)

    def test_the_plan_is_the_same_on_every_engine(self):
        outputs = {engine: run(engine, self.target, False).stdout for engine in ENGINES}
        self.assertEqual(outputs["vm"], outputs["tree"])
        self.assertEqual(outputs["vm"], outputs["bootstrap"])


class Apply(Fixture):
    def test_every_file_lands_where_the_plan_said(self):
        done = run_host(self.target, apply=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        for name, destination in EXPECTED.items():
            self.assertFalse(os.path.exists(os.path.join(self.target, name)), name + " should have moved")
            self.assertTrue(os.path.isfile(os.path.join(self.target, destination)), destination)
        for name in STAYS:
            self.assertTrue(os.path.lexists(os.path.join(self.target, name)), name + " should have stayed")
        self.assertIn("moved %d files" % len(EXPECTED), done.stdout)

    def test_no_file_is_lost_duplicated_or_changed(self):
        before = contents(self.target)
        outside_before = snapshot(self.outside)
        done = run_host(self.target, apply=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(contents(self.target), before)
        self.assertEqual(snapshot(self.outside), outside_before)
        self.assertEqual(os.readlink(os.path.join(self.target, "link.txt")), os.path.join("..", "outside", "secret.txt"))

    def test_the_result_is_the_same_on_every_engine(self):
        results = {}
        for engine in ENGINES:
            world, target, _ = make_fixture()
            self.addCleanup(cleanup, world)
            done = run(engine, target, apply=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            results[engine] = (snapshot(target), done.stdout)
        self.assertEqual(results["vm"], results["tree"])
        self.assertEqual(results["vm"], results["bootstrap"])

    def test_a_second_run_does_nothing(self):
        run_host(self.target, apply=True)
        after_first = snapshot(self.target)
        done = run_host(self.target, apply=True)
        self.assertEqual(snapshot(self.target), after_first)
        self.assertIn("moved 0 files", done.stdout)

    def test_unfinished_downloads_hidden_files_folders_and_links_stay(self):
        done = run_host(self.target, apply=True)
        for text in ("(hidden)", "(unfinished download)", "(folder)", "(outside this folder, probably a link)"):
            self.assertIn(text, done.stdout)


class Collisions(unittest.TestCase):
    def sort(self, existing, new):
        world, target, _ = make_fixture()
        self.addCleanup(cleanup, world)
        for rel, text in existing:
            os.makedirs(os.path.dirname(os.path.join(target, rel)), exist_ok=True)
            with open(os.path.join(target, rel), "w") as f:
                f.write(text)
        for name, text in new:
            with open(os.path.join(target, name), "w") as f:
                f.write(text)
        before = contents(target)
        done = run_host(target, apply=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(contents(target), before, "a file was lost, duplicated or changed")
        return target, done

    def test_a_taken_name_gets_a_number_and_the_old_file_is_untouched(self):
        target, done = self.sort([("Images/photo.png", "old")], [("photo.png", "new")])
        self.assertEqual(text(os.path.join(target, "Images", "photo.png")), "old")
        self.assertEqual(text(os.path.join(target, "Images", "photo (2).png")), "new")
        self.assertIn("(name was taken)", done.stdout)

    def test_a_name_that_differs_only_in_case_is_taken_too(self):
        target, _ = self.sort([("Images/PHOTO.PNG", "old")], [("photo.png", "new")])
        self.assertEqual(text(os.path.join(target, "Images", "PHOTO.PNG")), "old")
        self.assertTrue(os.path.isfile(os.path.join(target, "Images", "photo (2).png")))

    def test_numbers_keep_counting(self):
        target, _ = self.sort([("Images/p.png", "1"), ("Images/p (2).png", "2")], [("p.png", "3")])
        self.assertEqual(text(os.path.join(target, "Images", "p (3).png")), "3")

    def test_a_file_where_a_category_folder_belongs_is_left_alone(self):
        # "review" has no extension, so it is itself bound for review/, and it blocks review/.
        world, target, _ = make_fixture(extra=[("review", "I am a file, not a folder")])
        self.addCleanup(cleanup, world)
        before = contents(target)
        done = run_host(target, apply=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(contents(target), before, "a file was lost, duplicated or changed")
        self.assertEqual(text(os.path.join(target, "review")), "I am a file, not a folder")
        self.assertIn("(a file named review is in the way)", done.stdout)
        for name in ("mystery", "trailing.", "weird.xyz"):
            self.assertTrue(os.path.isfile(os.path.join(target, name)), name + " should have stayed")
        self.assertTrue(os.path.isfile(os.path.join(target, "Images", "a.jpg")), "the other files still move")


class InsideLinks(unittest.TestCase):
    def setUp(self):
        self.world, self.target, _ = make_fixture()
        self.addCleanup(cleanup, self.world)
        os.symlink("report.pdf", os.path.join(self.target, "shortcut.pdf"))   # a relative link to a file in the folder

    def test_a_real_run_refuses_to_start_and_changes_nothing(self):
        before = snapshot(self.target)
        done = run_host(self.target, apply=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("shortcut.pdf", done.stderr)
        self.assertIn("nothing was moved", done.stderr)
        self.assertEqual(snapshot(self.target), before)

    def test_a_dry_run_warns_and_still_shows_the_plan(self):
        done = run_host(self.target)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("shortcut.pdf", done.stderr)
        self.assertIn("DRY RUN", done.stdout)


class Names(unittest.TestCase):
    def test_an_empty_folder_is_a_quiet_no_op(self):
        world, target, _ = make_fixture()
        self.addCleanup(cleanup, world)
        empty = os.path.join(world, "empty")
        os.makedirs(empty)
        done = run_host(empty, apply=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("moved 0 files", done.stdout)

    def test_the_host_refuses_a_path_that_is_not_a_folder(self):
        world, target, _ = make_fixture()
        self.addCleanup(cleanup, world)
        done = run_host(os.path.join(target, "mystery"))
        self.assertEqual(done.returncode, 2)
        self.assertIn("not a folder", done.stderr)


if __name__ == "__main__":
    unittest.main()
