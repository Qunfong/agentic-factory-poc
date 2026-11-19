import os, pathlib, sys, tempfile, unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import tester_loop  # noqa: E402


class ValidateMvnArgsTest(unittest.TestCase):
    def test_test_compile_is_allowed(self):
        self.assertIsNone(tester_loop.validate_mvn_args(["-B", "-q", "-f", "app/pom.xml", "test-compile"]))

    def test_running_one_named_test_is_allowed(self):
        self.assertIsNone(tester_loop.validate_mvn_args(
            ["-B", "-q", "-f", "app/pom.xml", "test", "-Dtest=FooTest"]))
        self.assertIsNone(tester_loop.validate_mvn_args(
            ["-B", "-q", "-f", "app/pom.xml", "test", "-Dtest=FooTest#ac1_rejects_negative"]))

    def test_a_disallowed_mvn_argument_is_rejected(self):
        for args in (
            ["-B", "-q", "-f", "app/pom.xml", "install"],
            ["-B", "-q", "-f", "app/pom.xml", "test-compile", "-Dmaven.test.skip=true"],
            ["-B", "-q", "-f", "app/pom.xml", "test", "-Dtest=Foo;rm -rf /"],
            ["-B", "-q", "-f", "app/pom.xml", "test", "-Dtest=../Foo"],
            [],
        ):
            self.assertIsNotNone(tester_loop.validate_mvn_args(args), args)


class ValidateWritePathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "app/src/test/java").mkdir(parents=True)
        (self.root / "app/src/test/java/Existing.java").write_text("x")
        (self.root / "app/src/main").mkdir(parents=True)

    def test_a_new_file_under_app_src_test_is_allowed(self):
        self.assertIsNone(tester_loop.validate_write_path(self.root, "app/src/test/java/NewTest.java"))

    def test_a_path_escape_is_rejected(self):
        for path in ("../../etc/passwd", "app/src/test/../../../etc/passwd", "/etc/passwd", "a\\b"):
            self.assertIsNotNone(tester_loop.validate_write_path(self.root, path), path)

    def test_a_write_outside_app_src_test_is_rejected(self):
        for path in ("app/src/main/Evil.java", "app/pom.xml", ".github/workflows/evil.yml"):
            self.assertIsNotNone(tester_loop.validate_write_path(self.root, path), path)

    def test_overwriting_an_existing_file_is_rejected(self):
        self.assertIsNotNone(tester_loop.validate_write_path(self.root, "app/src/test/java/Existing.java"))


class ResolveContainedTest(unittest.TestCase):
    """Cowork A1: read_file/list_files must not follow a symlink, direct or via an ancestor,
    out of the repo (e.g. to /proc/self/environ, leaking the model key into the transcript)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "app/src/test/java").mkdir(parents=True)
        (self.root / "app/src/test/java/Existing.java").write_text("x")
        self.outside = pathlib.Path(self.tempfile_outside())

    def tempfile_outside(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        secret = pathlib.Path(d.name) / "secret.txt"
        secret.write_text("AZURE_OPENAI_API_KEY=super-secret")
        return secret

    def test_a_plain_file_resolves_inside_the_repo(self):
        real = tester_loop.resolve_contained(self.root, "app/src/test/java/Existing.java")
        self.assertEqual(real, (self.root / "app/src/test/java/Existing.java").resolve())

    def test_a_direct_symlink_is_refused(self):
        link = self.root / "app/src/test/java/Leak.java"
        try:
            link.symlink_to(self.outside)
        except OSError as e:
            self.skipTest(f"cannot create symlinks here: {e}")
        with self.assertRaises(tester_loop.ToolError):
            tester_loop.resolve_contained(self.root, "app/src/test/java/Leak.java")

    def test_a_symlinked_ancestor_directory_is_refused(self):
        link_dir = self.root / "app/src/test/java/escape"
        try:
            link_dir.symlink_to(self.outside.parent, target_is_directory=True)
        except OSError as e:
            self.skipTest(f"cannot create symlinks here: {e}")
        with self.assertRaises(tester_loop.ToolError):
            tester_loop.resolve_contained(self.root, "app/src/test/java/escape/secret.txt")

    def test_read_file_refuses_a_symlink(self):
        link = self.root / "app/src/test/java/Leak.java"
        try:
            link.symlink_to(self.outside)
        except OSError as e:
            self.skipTest(f"cannot create symlinks here: {e}")
        with self.assertRaises(tester_loop.ToolError):
            tester_loop.read_file(self.root, "app/src/test/java/Leak.java")

    def test_list_files_silently_omits_a_symlinked_entry(self):
        link = self.root / "app/src/test/java/Leak.java"
        try:
            link.symlink_to(self.outside)
        except OSError as e:
            self.skipTest(f"cannot create symlinks here: {e}")
        found = tester_loop.list_files(self.root, "app/src/test")
        self.assertIn("app/src/test/java/Existing.java".replace("/", os.sep).replace(os.sep, "/"), found)
        self.assertNotIn("app/src/test/java/Leak.java", found)


class LoadKeyFileTest(unittest.TestCase):
    def test_reads_the_key_into_os_environ_and_deletes_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            key_path = pathlib.Path(d) / "key"
            key_path.write_text("super-secret\n")
            self.addCleanup(os.environ.pop, "AZURE_OPENAI_API_KEY", None)
            tester_loop.load_key_file(str(key_path), "AZURE_OPENAI_API_KEY")
            self.assertEqual(os.environ["AZURE_OPENAI_API_KEY"], "super-secret")
            self.assertFalse(key_path.exists())


class RunMvnEnvTest(unittest.TestCase):
    def test_the_model_api_key_is_removed_from_run_mvns_environment(self):
        captured = {}

        def fake_run(cmd, cwd, env, capture_output, text, timeout):
            captured["env"] = env
            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

        os.environ["AZURE_OPENAI_API_KEY"] = "super-secret"
        self.addCleanup(lambda: os.environ.pop("AZURE_OPENAI_API_KEY", None))
        real_run = tester_loop.subprocess.run
        tester_loop.subprocess.run = fake_run
        try:
            tester_loop.run_mvn(pathlib.Path("."), ["-B", "-q", "-f", "app/pom.xml", "test-compile"])
        finally:
            tester_loop.subprocess.run = real_run
        self.assertNotIn("AZURE_OPENAI_API_KEY", captured["env"])

    def test_a_disallowed_argument_never_reaches_subprocess(self):
        calls = []
        real_run = tester_loop.subprocess.run
        tester_loop.subprocess.run = lambda *a, **k: calls.append((a, k))
        try:
            with self.assertRaises(tester_loop.ToolError):
                tester_loop.run_mvn(pathlib.Path("."), ["-B", "-q", "-f", "app/pom.xml", "install"])
        finally:
            tester_loop.subprocess.run = real_run
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
