import os, pathlib, subprocess, sys, tempfile, time, unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import publish  # noqa: E402


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.old_cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        git("init", "-q")
        git("config", "core.autocrlf", "false")
        git("config", "user.name", "t")
        git("config", "user.email", "t@example.com")
        for f in ("docs/index.md", "app/src/main/A.java", "app/src/test/ATest.java", "factory/x.yaml"):
            self.write(f, "base\n")
        git("add", "-A")
        git("commit", "-q", "-m", "base")
        self.base = git("rev-parse", "HEAD")
        self.patch = pathlib.Path(self.tmp.name, "..", f"{pathlib.Path(self.tmp.name).name}.patch").resolve()

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.patch.unlink(missing_ok=True)
        self.tmp.cleanup()

    def write(self, path, text):
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, newline="\n")

    def agent_patch(self, edit):
        """Do what an agent job does: change the tree, export a binary diff, leave the tree clean."""
        edit()
        git("add", "-A")
        self.patch.write_bytes(subprocess.run(["git", "diff", "--cached", "--binary", self.base],
                                              capture_output=True, check=True).stdout)
        git("reset", "-q", "--hard", self.base)
        git("clean", "-qfdx")

    def run_publish(self, role, base=None, issue="7", issue_paths=None):
        return publish.publish(role, issue, "1", base or self.base, str(self.patch), str(TOOLS), "gpt-x", "42",
                               issue_paths)

    def test_spec_writer_change_becomes_one_bot_commit_on_spec_branch(self):
        self.agent_patch(lambda: self.write("docs/specs/F7/spec.md", "spec\n"))
        self.assertEqual(self.run_publish("spec-writer")[1], "spec/F7")
        self.assertEqual(git("log", "-1", "--format=%an|%s"), "factory-bot|spec: F7")
        self.assertIn("Factory-Run: 42", git("log", "-1", "--format=%B"))

    def test_spec_writer_pr_body_links_proposed_adrs(self):
        self.agent_patch(lambda: (self.write("docs/specs/F7/spec.md", "spec\n"),
                                  self.write("docs/adr/proposed-x.md", "adr\n")))
        role, _ = self.run_publish("spec-writer")
        out = pathlib.Path(self.tmp.name).parent / "pr-out"
        publish.write_pr(role, str(TOOLS), out, "7", "F7 title", self.base)
        body = (out / "body.md").read_text(encoding="utf-8")
        self.assertIn("[proposed-x.md](docs/adr/proposed-x.md)", body)

    def test_pr_body_has_no_adr_section_when_none_were_added(self):
        self.agent_patch(lambda: self.write("docs/specs/F7/spec.md", "spec\n"))
        role, _ = self.run_publish("spec-writer")
        out = pathlib.Path(self.tmp.name).parent / "pr-out2"
        publish.write_pr(role, str(TOOLS), out, "7", "F7 title", self.base)
        self.assertNotIn("Proposed ADRs", (out / "body.md").read_text(encoding="utf-8"))

    def test_design_writer_change_becomes_one_bot_commit_on_design_branch(self):
        self.agent_patch(lambda: self.write("docs/design/D7/design.md", "design\n"))
        self.assertEqual(self.run_publish("design-writer")[1], "design/D7")
        self.assertEqual(git("log", "-1", "--format=%an|%s"), "factory-bot|design: D7")

    def test_design_writer_outside_docs_design_is_rejected(self):
        self.agent_patch(lambda: self.write("docs/specs/F7/spec.md", "evil\n"))
        with self.assertRaisesRegex(publish.Rejected, "path guard"):
            self.run_publish("design-writer")

    def test_spec_writer_outside_docs_is_rejected(self):
        self.agent_patch(lambda: self.write("app/src/main/A.java", "evil\n"))
        with self.assertRaisesRegex(publish.Rejected, "path guard"):
            self.run_publish("spec-writer")

    def test_builder_with_issue_paths_may_write_a_declared_non_code_path(self):
        self.agent_patch(lambda: self.write("README.md", "docs\n"))
        role, branch = self.run_publish("builder", issue_paths=["README.md"])
        self.assertEqual((role, branch), (publish.ROLES["builder"], "wi-7"))

    def test_builder_with_issue_paths_is_narrowed_to_them_not_the_old_default(self):
        self.agent_patch(lambda: self.write("app/src/main/A.java", "x\n"))
        with self.assertRaisesRegex(publish.Rejected, "path guard"):
            self.run_publish("builder", issue_paths=["README.md"])

    def test_builder_issue_paths_drops_test_files_tester_owns_those(self):
        self.agent_patch(lambda: self.write("app/src/main/A.java", "x\n"))
        role, _ = self.run_publish("builder", issue_paths=["app/src/main/A.java", "app/src/test/ATest.java"])
        self.assertEqual(role, publish.ROLES["builder"])

    def test_builder_issue_paths_may_never_include_a_denied_path(self):
        self.agent_patch(lambda: self.write("README.md", "docs\n"))
        with self.assertRaisesRegex(publish.Rejected, "never allowed"):
            self.run_publish("builder", issue_paths=["README.md", ".github/workflows/evil.yml"])

    def test_builder_with_no_issue_paths_keeps_the_old_default_guard(self):
        self.agent_patch(lambda: self.write("README.md", "docs\n"))
        with self.assertRaisesRegex(publish.Rejected, "path guard"):
            self.run_publish("builder", issue_paths=None)

    def test_builder_allowed_paths_helper(self):
        self.assertIsNone(publish.builder_allowed_paths([]))
        self.assertIsNone(publish.builder_allowed_paths(["app/src/test/ATest.java"]))
        self.assertEqual(publish.builder_allowed_paths(["README.md", "app/src/test/ATest.java"]), ["README.md"])
        with self.assertRaisesRegex(publish.Rejected, "never allowed"):
            publish.builder_allowed_paths(["AGENTS.md"])

    def test_spec_writer_may_write_only_its_charter_paths(self):
        self.agent_patch(lambda: (self.write("docs/specs/F7/plan.md", "p\n"),
                                  self.write("docs/adr/proposed-cache.md", "a\n")))
        self.assertEqual(self.run_publish("spec-writer")[1], "spec/F7")
        for path in ("docs/specs/F8/spec.md", "docs/adr/accepted-cache.md", "docs/adr/proposed-x/y.md",
                     "docs/notes.md", "docs/specs/F7.md"):
            git("reset", "-q", "--hard", self.base)
            self.agent_patch(lambda: self.write(path, "x\n"))
            with self.assertRaisesRegex(publish.Rejected, "path guard", msg=path):
                self.run_publish("spec-writer")

    def test_a_patch_that_rewrites_the_guard_is_still_guarded(self):
        def disable_guard():
            self.write("tools/check_paths.py", "import sys; sys.exit(0)\n")
            self.write("app/src/main/A.java", "new\n")
        self.agent_patch(disable_guard)
        with self.assertRaisesRegex(publish.Rejected, "path guard"):
            self.run_publish("builder")

    def test_builder_may_not_delete_files(self):
        self.agent_patch(lambda: os.remove("app/src/main/A.java"))
        with self.assertRaisesRegex(publish.Rejected, "path guard"):
            self.run_publish("builder")

    def test_tester_may_add_but_not_change_tests(self):
        self.agent_patch(lambda: self.write("app/src/test/NewTest.java", "t\n"))
        self.assertEqual(self.run_publish("tester")[1], "wi-7")
        self.assertIn("Assisted-by: litellm:gpt-x", git("log", "-1", "--format=%B"))
        git("reset", "-q", "--hard", self.base)
        self.agent_patch(lambda: self.write("app/src/test/ATest.java", "weakened\n"))
        with self.assertRaisesRegex(publish.Rejected, "path guard"):
            self.run_publish("tester")

    def test_builder_may_not_touch_tests(self):
        self.agent_patch(lambda: self.write("app/src/test/ATest.java", "weakened\n"))
        with self.assertRaisesRegex(publish.Rejected, "path guard"):
            self.run_publish("builder")

    def test_builder_rename_out_of_main_is_rejected(self):
        self.agent_patch(lambda: git("mv", "app/src/main/A.java", "factory/A.java"))
        with self.assertRaisesRegex(publish.Rejected, "path guard"):
            self.run_publish("builder")

    def test_a_role_without_changes_is_rejected(self):
        self.agent_patch(lambda: None)
        for role in ("tester", "builder"):
            with self.assertRaisesRegex(publish.Rejected, "no changes"):
                self.run_publish(role)

    def test_tester_may_not_swap_a_test_for_a_symlink(self):
        # A real symlink on disk, not just an index entry: agent_patch's own `git add -A` (after
        # edit()) reconciles the index against the working tree, so a symlink staged only via
        # `update-index --cacheinfo` with an unchanged regular file underneath gets silently
        # reverted on a symlink-capable filesystem (Audit round 2, A2 - this was a test bug, not
        # a guard bug: check_paths.py catches a real type-change fine, see GuardTest.test_type_change_fails
        # and test_filesystem_symlink_fails in test_check_paths.py).
        def swap():
            self.write("app/src/test/Empty.java", "")
            os.remove("app/src/test/ATest.java")
            try:
                os.symlink("Empty.java", "app/src/test/ATest.java")
            except OSError as e:
                self.skipTest(f"cannot create symlinks here: {e}")
        self.agent_patch(swap)
        with self.assertRaisesRegex(publish.Rejected, "path guard"):
            self.run_publish("tester")

    def test_rerun_rebuilds_the_same_commit(self):
        self.agent_patch(lambda: self.write("app/src/main/B.java", "b\n"))
        self.run_publish("builder")
        first = git("rev-parse", "HEAD")
        git("reset", "-q", "--hard", self.base)
        time.sleep(1.1)
        self.run_publish("builder")
        self.assertEqual(git("rev-parse", "HEAD"), first)

    def test_patch_that_does_not_apply_to_base_is_rejected(self):
        self.agent_patch(lambda: self.write("app/src/main/A.java", "new\n"))
        self.write("app/src/main/A.java", "moved on\n")
        git("commit", "-qam", "someone else")
        with self.assertRaisesRegex(publish.Rejected, "does not apply"):
            self.run_publish("builder", base=git("rev-parse", "HEAD"))

    def test_base_sha_must_be_the_checked_out_commit(self):
        self.agent_patch(lambda: self.write("app/src/main/A.java", "new\n"))
        with self.assertRaisesRegex(publish.Rejected, "base sha"):
            self.run_publish("builder", base="0" * 40)

    def test_builder_publish_deletes_a_shadowed_test_stub(self):
        # Own incident, F7 WI-1: Maven puts test-classes ahead of classes, so a tester's
        # compile-time stub left behind silently shadows the real implementation (404s, not a
        # build failure) once the builder adds the real class at the same path.
        self.write("app/src/test/com/Stub.java", "// factory-test-stub\npublic class Stub {}\n")
        git("add", "-A")
        git("commit", "-qam", "tester stub")
        self.base = git("rev-parse", "HEAD")
        self.agent_patch(lambda: self.write("app/src/main/com/Stub.java", "public class Stub {}\n"))
        self.run_publish("builder")
        files = git("ls-tree", "-r", "--name-only", "HEAD")
        self.assertNotIn("app/src/test/com/Stub.java", files)
        self.assertIn("app/src/main/com/Stub.java", files)

    def test_builder_publish_never_deletes_a_real_test_with_the_same_name(self):
        self.write("app/src/test/com/Stub.java", "public class Stub { /* a real test, no marker */ }\n")
        git("add", "-A")
        git("commit", "-qam", "real test, same name as a future main class")
        self.base = git("rev-parse", "HEAD")
        self.agent_patch(lambda: self.write("app/src/main/com/Stub.java", "public class Stub {}\n"))
        self.run_publish("builder")
        self.assertIn("app/src/test/com/Stub.java", git("ls-tree", "-r", "--name-only", "HEAD"))

    def test_builder_publish_leaves_an_unmatched_stub_alone(self):
        # The stub exists, but this patch doesn't add the main file it stands in for.
        self.write("app/src/test/com/Stub.java", "// factory-test-stub\npublic class Stub {}\n")
        git("add", "-A")
        git("commit", "-qam", "tester stub, unrelated to this patch")
        self.base = git("rev-parse", "HEAD")
        self.agent_patch(lambda: self.write("app/src/main/B2.java", "b2\n"))
        self.run_publish("builder")
        self.assertIn("app/src/test/com/Stub.java", git("ls-tree", "-r", "--name-only", "HEAD"))

    def test_inputs_are_parsed_at_the_boundary(self):
        self.agent_patch(lambda: None)
        with self.assertRaisesRegex(publish.Rejected, "unknown role"):
            self.run_publish("reviewer")
        with self.assertRaisesRegex(publish.Rejected, "decimal"):
            self.run_publish("builder", issue="7;rm -rf /")
        for issue in ("007", "0"):
            with self.assertRaisesRegex(publish.Rejected, "leading zeros"):
                self.run_publish("builder", issue=issue)


if __name__ == "__main__":
    unittest.main()
