"""tools/bootstrap.sh and .ps1 dry runs (brief 008). Both run offline with --owner-type and a `gh`
stub on PATH that records any call, so a dry run that reaches GitHub fails the test."""
import json, os, pathlib, re, shutil, stat, subprocess, tempfile, unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
ADR = "docs/adr/0002-single-maintainer-bypass.md"
REPO = "Qunfong/agentic-factory-poc"
ADMIN_VIA_PR = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}]
CORE, REVIEW = "factory-default-branch", "factory-default-branch-review"
ACTIONS_ONLY = [{"context": "required", "integration_id": 15368}]  # GET /apps/github-actions -> id 15368


def shells():
    found = {}
    bash = shutil.which("bash")  # full path: a bare "bash" can resolve to System32's WSL launcher
    if bash:
        found["sh"] = lambda flags: [bash, (TOOLS / "bootstrap.sh").as_posix(), *flags]
    ps = shutil.which("pwsh") or shutil.which("powershell")
    if ps:
        to_ps = {"--org": "-Org", "--repo": "-Repo", "--po-logins": "-PoLogins", "--release-owner": "-ReleaseOwner",
                 "--owner-type": "-OwnerType", "--no-merge-queue": "-NoMergeQueue",
                 "--admin-bypass-via-pr": "-AdminBypassViaPr", "--allow-self-review": "-AllowSelfReview",
                 "--azure-openai-endpoint": "-AzureOpenaiEndpoint"}
        found["ps1"] = lambda flags: [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                      str(TOOLS / "bootstrap.ps1"), *[to_ps.get(f, f) for f in flags]]
    return found


def payloads(out):
    """Every ('METHOD path', JSON payload) write, in the order printed."""
    found, last = [], None
    for line in out.splitlines():
        m = re.match(r"\+ gh api -X (\w+) (\S+) --input", line)
        if m:
            last = f"{m.group(1)} {m.group(2)}"
        elif line.startswith("  payload: ") and last:
            found.append((last, json.loads(line[len("  payload: "):])))
            last = None
    return found


def rulesets(out):
    """Ruleset payloads by name; each name is written exactly once."""
    writes = [body for key, body in payloads(out) if key == f"POST repos/{REPO}/rulesets"]
    names = [body["name"] for body in writes]
    assert sorted(names) == [CORE, REVIEW], names
    return {body["name"]: body for body in writes}


def rule_types(ruleset):
    return [r["type"] for r in ruleset["rules"]]


def rule(ruleset, kind):
    return next(r for r in ruleset["rules"] if r["type"] == kind)


class BootstrapDryRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shells = shells()
        if not cls.shells:
            raise unittest.SkipTest("neither bash nor PowerShell is installed")
        cls.tmp = tempfile.TemporaryDirectory()
        stub = pathlib.Path(cls.tmp.name)
        cls.calls = stub / "gh-calls.log"
        (stub / "gh").write_text(f'#!/bin/sh\necho "$@" >> "{cls.calls.as_posix()}"\nexit 1\n', newline="\n")
        (stub / "gh").chmod((stub / "gh").stat().st_mode | stat.S_IEXEC)
        (stub / "gh.cmd").write_text(f'@echo %* >> "{cls.calls}"\r\n@exit /b 1\r\n')
        cls.env = {**os.environ, "PATH": str(stub) + os.pathsep + os.environ["PATH"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_all(self, *flags, release_owner="Qunfong"):
        base = ["--org", "Qunfong", "--repo", "agentic-factory-poc", "--po-logins", "Qunfong",
                "--release-owner", release_owner]
        results = {}
        for name, cmd in self.shells.items():
            p = subprocess.run(cmd([*base, *flags]), capture_output=True, text=True, env=self.env, timeout=120)
            results[name] = (p.returncode, p.stdout.replace("\r", ""), p.stderr)
        return results

    def setUp(self):
        self.calls.unlink(missing_ok=True)

    def tearDown(self):
        self.assertFalse(self.calls.exists(), "a dry run with --owner-type called gh")

    def test_personal_account_with_both_flags(self):
        for name, (rc, out, err) in self.run_all("--owner-type", "user", "--no-merge-queue",
                                                 "--admin-bypass-via-pr", "--allow-self-review").items():
            with self.subTest(shell=name):
                self.assertEqual(rc, 0, err)
                preflight = out.split("== Preflight ==")[1].split("==")[0]
                self.assertNotIn("teams", preflight)
                p = dict(payloads(out))
                rs = rulesets(out)
                self.assertEqual(rs[CORE]["bypass_actors"], [])
                self.assertEqual(rule_types(rs[CORE]),
                                 ["deletion", "non_fast_forward", "required_status_checks", "required_linear_history"])
                self.assertEqual(rs[REVIEW]["bypass_actors"], ADMIN_VIA_PR)
                self.assertEqual(rule_types(rs[REVIEW]), ["pull_request"])
                for body in rs.values():
                    self.assertEqual(body["enforcement"], "active")
                    self.assertEqual(body["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
                self.assertIs(p[f"PUT repos/{REPO}/environments/production"]["prevent_self_review"], False)
                self.assertEqual(out.count(f"revert trigger in {ADR}"), 2)
                self.assertIn("gh label create factory:builder-failed", out)
                self.assertIn("gh secret set CLAUDE_CODE_OAUTH_TOKEN", out)
                self.assertNotIn("ANTHROPIC_API_KEY --repo", out)

    def test_personal_account_without_the_flags_keeps_full_protection(self):
        for name, (rc, out, err) in self.run_all("--owner-type", "user", "--no-merge-queue").items():
            with self.subTest(shell=name):
                self.assertEqual(rc, 0, err)
                p = dict(payloads(out))
                rs = rulesets(out)
                self.assertEqual(rs[CORE]["bypass_actors"], [])
                self.assertEqual(rs[REVIEW]["bypass_actors"], [])
                self.assertEqual(rule_types(rs[REVIEW]), ["pull_request"])
                self.assertIs(p[f"PUT repos/{REPO}/environments/production"]["prevent_self_review"], True)
                self.assertNotIn("revert trigger", out)

    def test_the_merge_queue_stays_in_the_unbypassable_ruleset(self):
        for name, (rc, out, err) in self.run_all("--owner-type", "user", "--admin-bypass-via-pr").items():
            with self.subTest(shell=name):
                self.assertEqual(rc, 0, err)
                rs = rulesets(out)
                self.assertEqual(rule_types(rs[CORE]), ["deletion", "non_fast_forward", "required_status_checks",
                                                        "required_linear_history", "merge_queue"])
                self.assertEqual(rs[CORE]["bypass_actors"], [])
                self.assertEqual(rule(rs[CORE], "merge_queue")["parameters"]["merge_method"], "SQUASH")

    def test_the_required_check_comes_from_actions_and_merges_are_squash_only(self):
        for flags in (("--owner-type", "user"), ("--owner-type", "user", "--no-merge-queue", "--admin-bypass-via-pr"),
                      ("--owner-type", "org")):
            for name, (rc, out, err) in self.run_all(*flags).items():
                with self.subTest(shell=name, flags=flags):
                    self.assertEqual(rc, 0, err)
                    rs = rulesets(out)
                    checks = rule(rs[CORE], "required_status_checks")["parameters"]
                    self.assertEqual(checks["required_status_checks"], ACTIONS_ONLY)
                    self.assertIs(checks["strict_required_status_checks_policy"], True)
                    self.assertEqual(rule(rs[CORE], "required_linear_history"), {"type": "required_linear_history"})
                    self.assertEqual(rule(rs[REVIEW], "pull_request")["parameters"]["allowed_merge_methods"], ["squash"])

    def test_both_shells_print_the_same_payloads(self):
        for flags in (("--owner-type", "user", "--no-merge-queue", "--admin-bypass-via-pr", "--allow-self-review"),
                      ("--owner-type", "user")):
            results = self.run_all(*flags)
            if len(results) < 2:
                self.skipTest("needs both bash and PowerShell")
            with self.subTest(flags=flags):
                self.assertEqual(payloads(results["sh"][1]), payloads(results["ps1"][1]))
                raw = {s: [l for l in out.splitlines() if l.startswith("  payload: ")] for s, (_, out, _) in results.items()}
                self.assertEqual(raw["sh"], raw["ps1"], "payloads are byte-identical")

    def test_labels_variables_and_secrets_match_brief_011(self):
        endpoint = "https://ai-services-x.openai.azure.com"
        results = self.run_all("--owner-type", "user", "--azure-openai-endpoint", endpoint + "/")
        setup = {}
        for name, (rc, out, err) in results.items():
            with self.subTest(shell=name):
                self.assertEqual(rc, 0, err)
                for label, desc in (("needs-human-review", "a person must review"), ("infra-failure", "never a pass"),
                                    ("factory:builder-failed", "branch holds tests only")):
                    line = next(l for l in out.splitlines() if l.startswith(f"+ gh label create {label} "))
                    self.assertIn(desc, line)
                self.assertIn(f"+ gh variable set AZURE_OPENAI_ENDPOINT --repo {REPO} --body {endpoint}\n", out)
                for retired in ("OPENAI_TESTER_MODEL", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GITLEAKS_LICENSE"):
                    self.assertNotIn(retired, out.replace("AZURE_OPENAI_API_KEY", ""))
                self.assertNotIn("Optional: gh secret set", out)
                setup[name] = [l for l in out.splitlines() if l.startswith(("+ gh label create", "+ gh variable set"))]
        if len(setup) == 2:
            self.assertEqual(setup["sh"], setup["ps1"])

    def test_a_malformed_endpoint_is_refused(self):
        for name, (rc, _, err) in self.run_all("--owner-type", "user", "--azure-openai-endpoint", "http://x.example").items():
            with self.subTest(shell=name):
                self.assertEqual(rc, 2)
                self.assertIn("openai.azure.com", err)

    def test_organisation_refuses_the_weakenings(self):
        for flag in ("--admin-bypass-via-pr", "--allow-self-review"):
            for name, (rc, out, err) in self.run_all("--owner-type", "org", flag).items():
                with self.subTest(shell=name, flag=flag):
                    self.assertEqual(rc, 2)
                    self.assertIn("personal account only", err)
                    self.assertNotIn("payload", out)

    def test_personal_account_refuses_a_team_release_owner(self):
        for name, (rc, _, err) in self.run_all("--owner-type", "user", release_owner="team:rel").items():
            with self.subTest(shell=name):
                self.assertEqual(rc, 2)
                self.assertIn("personal account, use a login", err)


if __name__ == "__main__":
    unittest.main()
