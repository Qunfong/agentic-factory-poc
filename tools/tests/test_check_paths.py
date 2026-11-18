import os, pathlib, subprocess, sys, tempfile, unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from check_paths import Change, Policy, compile_glob, unsafe, violations  # noqa: E402

BUILDER = ("--allow", "app/src/main/**")
TESTER = ("--allow", "app/src/test/**", "--new-files-only")


def git(*args, stdin=None):
    return subprocess.run(["git", *args], input=stdin, capture_output=True, text=True, encoding="utf-8",
                          check=True).stdout.strip()


class GlobTest(unittest.TestCase):
    def assertMatches(self, pattern, yes=(), no=()):
        g = compile_glob(pattern)
        for path in yes:
            self.assertTrue(g.matches(path), f"{pattern} should match {path}")
        for path in no:
            self.assertFalse(g.matches(path), f"{pattern} should not match {path}")

    def test_double_star_crosses_slashes_single_star_does_not(self):
        self.assertMatches("docs/**", yes=["docs/a.md", "docs/a/b/c.md"], no=["docs", "docsx/a.md", "x/docs/a.md"])
        self.assertMatches("docs/*", yes=["docs/a.md"], no=["docs/a/b.md"])
        self.assertMatches("**/*.md", yes=["README.md", "a/b/c.md"], no=["a/b.mdx", "a.md/b"])
        self.assertMatches("app/**/billing/**", yes=["app/billing/X.java", "app/x/y/billing/z/X.java"],
                           no=["app/billing", "app/xbilling/X.java"])

    def test_matching_is_case_sensitive(self):
        self.assertMatches("factory/**", yes=["factory/x"], no=["Factory/x", "FACTORY/x"])
        self.assertMatches("docs/adr/proposed-*.md", yes=["docs/adr/proposed-cache.md"],
                           no=["docs/adr/Proposed-cache.md", "docs/adr/proposed-a/b.md", "docs/adr/accepted-x.md"])

    def test_question_mark_is_one_char_and_other_chars_are_literal(self):
        self.assertMatches("F?/a+b.md", yes=["F7/a+b.md"], no=["F/a+b.md", "F77/a+b.md", "F7/aab.md", "F//a+b.md"])

    def test_bad_patterns_are_rejected(self):
        for pattern in ("../x", "a/../b", "/abs/**", "C:/x", "a\\b", "a//b", "./a", "a**/b", "a/**b", ""):
            with self.assertRaises(ValueError, msg=pattern):
                compile_glob(pattern)

    def test_unsafe_paths_are_named(self):
        for path in ("app/src/main/../../factory/x", "/etc/passwd", "app\\src\\main\\X.java", "a//b", "c:/x"):
            self.assertTrue(unsafe(path), path)
        self.assertEqual(unsafe("app/src/main/X.java"), "")


class ViolationsTest(unittest.TestCase):
    """The policy alone, for changes git never reports but the guard must still refuse."""
    policy = Policy((compile_glob("app/src/main/**"),))

    def test_traversal_out_of_an_allowed_path_fails(self):
        bad = violations([Change("A", ("app/src/main/../../factory/x",))], self.policy)
        self.assertIn("'..' path segment", "\n".join(bad))

    def test_both_sides_of_a_rename_are_checked(self):
        self.assertTrue(violations([Change("R100", ("app/src/main/A.java", "factory/A.java"))], self.policy))
        bad = violations([Change("R100", ("factory/A.java", "app/src/main/A.java"))], self.policy)
        self.assertIn("factory/A.java: outside allowed paths", "\n".join(bad))

    def test_only_added_and_modified_files_pass(self):
        self.assertEqual(violations([Change("A", ("app/src/main/B.java",)), Change("M", ("app/src/main/A.java",))],
                                    self.policy), [])
        for status in ("D", "T", "U", "X", "C75", "unstaged", "untracked"):
            self.assertTrue(violations([Change(status, ("app/src/main/A.java",))], self.policy), status)


class GuardTest(unittest.TestCase):
    """The guard CLI against a real repository, the way publish runs it."""

    def setUp(self):
        self.old_cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        git("init", "-q")
        git("config", "core.autocrlf", "false")
        git("config", "core.ignorecase", "false")
        git("config", "user.name", "t")
        git("config", "user.email", "t@example.com")
        for f in ("app/src/main/A.java", "app/src/test/ATest.java", "factory/x.yaml", "tools/check_paths.py"):
            self.write(f, "base\n")
        git("add", "-A")
        git("commit", "-q", "-m", "base")
        self.base = git("rev-parse", "HEAD")

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.tmp.cleanup()

    def write(self, path, text):
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    def stage(self, path, content, mode="100644"):
        """Put a path in the index directly, as a case-sensitive filesystem or a crafted patch would."""
        blob = git("hash-object", "-w", "--stdin", stdin=content)
        git("update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}")

    def stage_symlink(self, path, target):
        self.stage(path, target, mode="120000")

    def guard(self, *policy, expect_head=True):
        args = ["--base", self.base, *(["--expect-head", self.base] if expect_head else []), *policy]
        r = subprocess.run([sys.executable, str(TOOLS / "check_paths.py"), *args],
                           capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout

    def assertBlocked(self, policy, reason, **kw):
        code, out = self.guard(*policy, **kw)
        self.assertEqual(code, 1, out)
        self.assertIn(reason, out)

    def test_allowed_staged_change_passes(self):
        self.write("app/src/main/A.java", "new\n")
        self.write("app/src/main/B.java", "b\n")
        git("add", "-A")
        self.assertEqual(self.guard(*BUILDER), (0, "Path guard ok (2 files)\n"))

    def test_committed_forbidden_edit_fails(self):
        self.write("factory/x.yaml", "evil\n")
        git("commit", "-qam", "agent commit")
        self.assertBlocked(BUILDER, "factory/x.yaml: outside allowed paths", expect_head=False)
        self.assertBlocked(BUILDER, f"HEAD moved from {self.base}")

    def test_rename_from_allowed_to_forbidden_fails(self):
        git("mv", "app/src/main/A.java", "factory/A.java")
        self.assertBlocked(BUILDER, "factory/A.java: outside allowed paths")
        self.assertBlocked(BUILDER, "app/src/main/A.java: status D is not publishable")

    def test_partly_staged_change_to_an_existing_test_fails(self):
        self.write("app/src/test/ATest.java", "weak\n")
        git("add", "-A")
        self.write("app/src/test/ATest.java", "weaker\n")
        self.assertBlocked(TESTER, "status unstaged is not publishable")
        self.assertBlocked(TESTER, "existing file changed")

    def test_type_change_fails(self):
        self.stage_symlink("app/src/main/A.java", "../../../factory/x.yaml")
        self.assertBlocked(BUILDER, "status T is not publishable")

    def test_deletion_fails(self):
        git("rm", "-q", "app/src/main/A.java")
        self.assertBlocked(BUILDER, "app/src/main/A.java: status D is not publishable")

    def test_unstaged_deletion_fails(self):
        os.remove("app/src/main/A.java")
        self.assertBlocked(BUILDER, "status unstaged is not publishable")

    def test_edit_to_the_guard_itself_fails(self):
        self.write("tools/check_paths.py", "import sys; sys.exit(0)\n")
        git("add", "-A")
        self.assertBlocked(BUILDER, "tools/check_paths.py: outside allowed paths")

    def test_case_variant_paths_fail(self):
        self.stage("Factory/x", "x\n")
        self.assertBlocked(BUILDER, "Factory/x: outside allowed paths")

    def test_case_variant_of_an_existing_file_fails(self):
        self.stage("app/src/test/atest.java", "shadow\n")
        self.assertBlocked(TESTER, "case variant of existing app/src/test/ATest.java")

    def test_added_symlink_fails(self):
        self.stage_symlink("app/src/main/L.java", "../../../factory/x.yaml")
        self.assertBlocked(BUILDER, "app/src/main/L.java: symlink is not publishable")

    def test_untracked_and_ignored_files_fail(self):
        self.write(".git/info/exclude", "*.tmp\n")
        self.write("app/src/main/C.java", "c\n")
        self.write("app/src/main/hidden.tmp", "h\n")
        self.assertBlocked(BUILDER, "app/src/main/C.java: status untracked")
        self.assertBlocked(BUILDER, "app/src/main/hidden.tmp: status untracked")

    def test_force_added_ignored_file_is_checked(self):
        self.write(".git/info/exclude", "*.tmp\n")
        self.write("factory/evil.tmp", "e\n")
        git("add", "-f", "factory/evil.tmp")
        self.assertBlocked(BUILDER, "factory/evil.tmp: outside allowed paths")

    def test_filesystem_symlink_fails(self):
        try:
            os.symlink("../../../factory/x.yaml", "app/src/main/L.java")
        except OSError as e:
            self.skipTest(f"cannot create symlinks here: {e}")
        git("add", "-A")
        self.assertBlocked(BUILDER, "app/src/main/L.java: symlink is not publishable")

    def test_non_ascii_paths_are_reported_unquoted(self):
        self.write("factory/caf\u00e9.md", "x\n")
        git("add", "-A")
        self.assertBlocked(BUILDER, "factory/caf\u00e9.md: outside allowed paths")

    def test_unknown_base_fails_closed(self):
        self.base = "0" * 40
        self.assertBlocked(BUILDER, "Path guard failed")


if __name__ == "__main__":
    unittest.main()
