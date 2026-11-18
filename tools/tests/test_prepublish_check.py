"""tools/prepublish_check.sh and .ps1 against fixture repos. The deny-list cases run with a stub
`docker` that reports no leaks; the gitleaks cases need Docker and the pinned image already pulled."""
import os, pathlib, shutil, stat, subprocess, tempfile, unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
IMAGE = "zricethezav/gitleaks:v8.24.0@sha256:2bcceac45179b3a91bff11a824d0fb952585b429e54fc928728b1d4d5c3e5176"
NAME = "Zorblaxcorp"
# Built at run time so the secret scan of this repo doesn't flag the fixture.
FAKE_AWS_KEY = "AKIA" + "QX7RZ4WK2JM5NP3T"


def posix(path):
    return pathlib.Path(path).as_posix()


def runners():
    found = []
    # The full path: on Windows a bare "bash" resolves to System32's WSL launcher before PATH.
    bash = shutil.which("bash")
    if bash:
        found.append(("sh", lambda deny, repo: [bash, (TOOLS / "prepublish_check.sh").as_posix(),
                                                "--deny-list", posix(deny), "--repo", posix(repo)]))
    ps = shutil.which("pwsh") or shutil.which("powershell")
    if ps:
        found.append(("ps1", lambda deny, repo: [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                                 str(TOOLS / "prepublish_check.ps1"), "-DenyList", deny, "-Repo", repo]))
    return found


def docker_ready():
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class PrepublishCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.name", "Fixture")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        git(self.repo, "config", "commit.gpgsign", "false")
        self.commit("README.md", "hello\n", "initial")
        self.deny = self.tmp / "outside" / "deny.txt"
        self.deny.parent.mkdir()
        self.deny.write_text(f"# client names\n\n{NAME.lower()}\r\n", encoding="utf-8")
        stub = self.tmp / "stub"
        stub.mkdir()
        (stub / "docker").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
        (stub / "docker").chmod(stat.S_IRWXU)
        (stub / "docker.cmd").write_text("@exit /b 0\r\n", encoding="utf-8")
        self.stub_env = {**os.environ, "PATH": str(stub) + os.pathsep + os.environ["PATH"]}

    def commit(self, path, text, message, branch=None):
        if branch:
            git(self.repo, "checkout", "-q", "-b", branch)
        (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / path).write_text(text, encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", message)
        if branch:
            git(self.repo, "checkout", "-q", "main")

    def scan(self, env=None, deny=None):
        out = {}
        for name, cmd in runners():
            r = subprocess.run(cmd(str(deny or self.deny), str(self.repo)), capture_output=True, text=True,
                               env=env or self.stub_env, timeout=300)
            out[name] = (r.returncode, r.stdout + r.stderr)
        self.assertTrue(out, "neither bash nor PowerShell found")
        return out

    def assert_all(self, results, code, *expected):
        for shell, (rc, text) in results.items():
            with self.subTest(shell=shell):
                self.assertEqual(rc, code, text)
                self.assertNotIn(NAME.casefold(), text.casefold())
                self.assertNotIn(FAKE_AWS_KEY, text)
                for e in expected:
                    self.assertIn(e, text)

    def test_clean_history_passes(self):
        self.assert_all(self.scan(), 0, "PASS", "deny-list: 1 name(s), 1 commit(s): 0 content")

    def test_name_in_a_file_on_another_branch_fails_without_printing_it(self):
        self.commit("notes.md", f"Contract with {NAME} BV\n", "add notes", branch="side")
        self.assert_all(self.scan(), 1, "FAIL", "content: ", " notes.md", "1 content")

    def test_name_in_a_file_path_is_counted_and_withheld(self):
        self.commit(f"docs/{NAME}-plan.md", "nothing here\n", "add plan", branch="side")
        self.assert_all(self.scan(), 1, "FAIL", "1 file path(s)", "1 path")

    def test_name_in_a_commit_message_fails(self):
        self.commit("a.txt", "a\n", f"Kick-off for {NAME.upper()}", branch="side")
        self.assert_all(self.scan(), 1, "FAIL", "message or author: ", "1 message or author")

    def test_name_in_a_ref_or_annotated_tag_fails(self):
        git(self.repo, "branch", f"client/{NAME}")
        git(self.repo, "tag", "-a", "v1", "-m", f"release for {NAME}")
        self.assert_all(self.scan(), 1, "FAIL", "1 ref name", "1 tag hit")

    def test_deny_list_inside_the_repo_is_refused(self):
        inside = self.repo / "sub" / "deny.txt"
        inside.parent.mkdir()
        inside.write_text(NAME + "\n", encoding="utf-8")
        self.assert_all(self.scan(deny=inside), 2, "must live outside the repository")

    def test_empty_deny_list_is_refused(self):
        self.deny.write_text("# nothing\n\n", encoding="utf-8")
        self.assert_all(self.scan(), 2, "holds no names")

    @unittest.skipUnless(docker_ready(), "Docker or the pinned gitleaks image is not available")
    def test_real_gitleaks_passes_a_clean_history(self):
        self.assert_all(self.scan(env=dict(os.environ)), 0, "gitleaks: 0 finding(s)", "PASS")

    @unittest.skipUnless(docker_ready(), "Docker or the pinned gitleaks image is not available")
    def test_real_gitleaks_finds_a_key_on_another_branch(self):
        self.commit("config.ini", f"aws_access_key_id = {FAKE_AWS_KEY}\n", "add config", branch="side")
        self.assert_all(self.scan(env=dict(os.environ)), 1, "gitleaks: 1 finding(s)", "config.ini aws-access-token", "FAIL")


    @unittest.skipUnless(docker_ready(), "Docker or the pinned gitleaks image is not available")
    def test_real_gitleaks_withholds_a_leak_path_that_holds_a_name(self):
        self.commit(f"{NAME}.ini", f"aws_access_key_id = {FAKE_AWS_KEY}\n", "add config", branch="side")
        self.assert_all(self.scan(env=dict(os.environ)), 1, "gitleaks: 1 finding(s)", "<path withheld>", "FAIL")

if __name__ == "__main__":
    unittest.main()
