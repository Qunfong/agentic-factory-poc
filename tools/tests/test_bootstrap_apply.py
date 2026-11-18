"""tools/bootstrap.sh and .ps1 with --apply against a fake `gh` (brief 011, Q32). Nothing reaches GitHub:
the fake is first on PATH, GH_TOKEN and GITHUB_TOKEN are unset, GH_HOST is unroutable and GH_CONFIG_DIR
is empty, and each shell must resolve `gh` to the fake before bootstrap runs."""
import json, os, pathlib, secrets, shutil, stat, subprocess, sys, tempfile, unittest

TESTS = pathlib.Path(__file__).resolve().parent
TOOLS = TESTS.parent
OWNER, REPO = "Qunfong", "agentic-factory-poc"
R = f"{OWNER}/{REPO}"
BASH = shutil.which("bash")
PS = shutil.which("pwsh") or shutil.which("powershell")
FLAGS = {"sh": ["--org", OWNER, "--repo", REPO, "--po-logins", OWNER, "--release-owner", OWNER,
                "--factory-bot-login", "factory-bot[bot]", "--azure-openai-endpoint", "https://x.openai.azure.com",
                "--apply"],
         "ps1": ["-Org", OWNER, "-Repo", REPO, "-PoLogins", OWNER, "-ReleaseOwner", OWNER,
                 "-FactoryBotLogin", "factory-bot[bot]", "-AzureOpenaiEndpoint", "https://x.openai.azure.com",
                 "-Apply"]}
LABELS = ["feature", "gate:intent-approved", "spec", "work-item", "queued", "blocked", "agent", "escalated",
          "tier:green", "tier:amber", "tier:red", "round:1", "round:2", "factory:builder-failed",
          "needs-human-review", "infra-failure"]
RULESET_LOOKUP = {"sh": ["--paginate", "--jq"], "ps1": ["--paginate", "--slurp"]}
CORE, REVIEW = "factory-default-branch", "factory-default-branch-review"
IDS = {REVIEW: "101", CORE: "102"}
# What GitHub's read-back gives when both rulesets hold what bootstrap sent (ADR-0013).
GOOD = {REVIEW: "never merge=squash", CORE: "never check=required@15368 linear queue=SQUASH"}


def scenario(readback):
    return [
        [["api", f"users/{OWNER}", "--jq", ".type"], "User\n"],
        [["api", f"users/{OWNER}", "--jq", ".id"], "4242\n"],
        [["api", f"users/{OWNER}"], "{}"],
        [["auth", "status"], ""],
        [["api", f"repos/{R}", "--jq", ".visibility"], "public\n"],
        [["api", f"repos/{R}"], "{}"],
        [["api", f"repos/{R}/rulesets", "--paginate", "--jq"], ""],
        [["api", f"repos/{R}/rulesets", "--paginate", "--slurp"], "[[]]"],
        [["api", f"repos/{R}/rulesets"], "[]"],
        [["api", f"repos/{OWNER}/meter-acceptance"], "{}"],
        *[[["api", "-X", "POST", f"repos/{R}/rulesets"], IDS[name] + "\n", {"name": name}] for name in IDS],
        *[[["api", f"repos/{R}/rulesets/{IDS[name]}", "--jq"], readback[name] + "\n"] for name in IDS],
        [["api", "-X", "PUT"], "{}"],
        [["api", "-X", "PATCH"], "{}"],
        [["label", "create"], ""],
        [["variable", "set"], ""],
    ]


def expected_calls(shell):
    """Every gh call --apply makes, in order, as argv without the --input path."""
    lookup = ["api", f"repos/{R}/rulesets", *RULESET_LOOKUP[shell]]
    calls = [["api", f"users/{OWNER}", "--jq", ".type"], ["auth", "status"], ["api", f"repos/{R}"],
             ["api", f"users/{OWNER}"], ["api", f"repos/{R}/rulesets"], ["api", f"repos/{OWNER}/meter-acceptance"]]
    calls += [["label", "create", name] for name in LABELS]
    calls += [["variable", "set", v] for v in ("GATE_ROLES", "WIP_LIMIT", "ACCEPTANCE_REPO", "AZURE_OPENAI_ENDPOINT",
                                              "FACTORY_BOT_LOGIN")]
    calls += [["api", "-X", "PUT", f"repos/{R}/environments/staging"], ["api", f"users/{OWNER}", "--jq", ".id"],
              ["api", "-X", "PUT", f"repos/{R}/environments/production"],
              ["api", f"repos/{R}", "--jq", ".visibility"],
              ["api", "-X", "PUT", f"repos/{R}/actions/permissions/fork-pr-contributor-approval"],
              ["api", "-X", "PUT", f"repos/{R}/private-vulnerability-reporting"], ["api", "-X", "PATCH", f"repos/{R}"]]
    for name in (REVIEW, CORE):
        calls += [lookup, ["api", "-X", "POST", f"repos/{R}/rulesets"], ["api", f"repos/{R}/rulesets/{IDS[name]}", "--jq"]]
    return calls


def shape(entry):
    """The call's argv cut to what expected_calls names: verb, path and the flags that pick an answer."""
    a = entry["argv"]
    if a[:2] in (["label", "create"], ["variable", "set"]):
        return a[:3]
    if "--input" in a:
        return a[:a.index("--input")]
    if a[:2] == ["api", f"repos/{R}/rulesets"] and "--paginate" in a:
        return a[:2] + RULESET_LOOKUP["sh" if "--jq" in a else "ps1"]
    if a[1].startswith(f"repos/{R}/rulesets/") and "--jq" in a:
        return a[:a.index("--jq") + 1]
    return a


class BootstrapApplyAgainstFakeGh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shells = {}
        if BASH:
            cls.shells["sh"] = lambda: [BASH, (TOOLS / "bootstrap.sh").as_posix(), *FLAGS["sh"]]
        if PS:
            cls.shells["ps1"] = lambda: [PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                         str(TOOLS / "bootstrap.ps1"), *FLAGS["ps1"]]
        if not cls.shells:
            raise unittest.SkipTest("neither bash nor PowerShell is installed")
        cls.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(cls.tmp.name)
        cls.stub = root / "bin"
        cls.stub.mkdir()
        (root / "gh-config").mkdir()
        py, fake = pathlib.Path(sys.executable), TESTS / "fake_gh.py"
        (cls.stub / "gh").write_text(f'#!/bin/sh\nexec "{py.as_posix()}" -I "{fake.as_posix()}" "$@"\n', newline="\n")
        (cls.stub / "gh").chmod((cls.stub / "gh").stat().st_mode | stat.S_IEXEC)
        (cls.stub / "gh.cmd").write_text(f'@"{py}" -I "{fake}" %*\r\n', newline="")
        env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")}
        cls.env = {**env, "PATH": str(cls.stub) + os.pathsep + env["PATH"], "GH_HOST": "gh-stub.invalid",
                   "GH_CONFIG_DIR": str(root / "gh-config"), "GH_PROMPT_DISABLED": "1",
                   "FAKE_GH_LOG": str(root / "calls.jsonl"), "FAKE_GH_NONCE": secrets.token_hex(8), "FAKE_GH_SCENARIO": str(root / "scenario.json")}
        cls.log = pathlib.Path(cls.env["FAKE_GH_LOG"])
        cls.scenario = pathlib.Path(cls.env["FAKE_GH_SCENARIO"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def gh_is_the_fake(self, shell):
        """Ask `gh` itself, resolved exactly as the shell resolves it, whether it is the fake."""
        probe = "gh __fake_gh_identity"
        cmd = [BASH, "-c", probe] if shell == "sh" else [PS, "-NoProfile", "-Command", probe]
        r = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=60)
        return r.returncode == 0 and r.stdout.strip() == self.env["FAKE_GH_NONCE"]

    def apply(self, shell, readback=GOOD):
        if not self.gh_is_the_fake(shell):
            self.fail(f"{shell} does not resolve gh to the fake; refusing to run --apply")
        self.log.unlink(missing_ok=True)
        self.scenario.write_text(json.dumps(scenario(readback)), encoding="utf-8")
        p = subprocess.run(self.shells[shell](), capture_output=True, text=True, env=self.env, timeout=300)
        calls = [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []
        return p.returncode, p.stdout.replace("\r", ""), p.stderr, calls

    def test_apply_makes_exactly_the_expected_calls_with_the_same_payloads(self):
        payloads, filters = {}, {}
        for shell in self.shells:
            with self.subTest(shell=shell):
                rc, out, err, calls = self.apply(shell)
                self.assertEqual(rc, 0, err + out[-2000:])
                self.assertEqual([shape(c) for c in calls], expected_calls(shell))
                first_write = next(i for i, c in enumerate(calls) if c["argv"][:2] == ["label", "create"])
                self.assertIn(["api", f"repos/{R}/rulesets"], [c["argv"] for c in calls[:first_write]],
                              "the plan check runs before any write")
                payloads[shell] = [(shape(c), c["payload"]) for c in calls if "payload" in c]
                self.assertEqual([p["name"] for s, p in payloads[shell] if s[-1] == f"repos/{R}/rulesets"], [REVIEW, CORE])
                filters[shell] = {c["argv"][c["argv"].index("--jq") + 1] for c in calls
                                  if c["argv"][1].startswith(f"repos/{R}/rulesets/") and "--jq" in c["argv"]}
                self.assertEqual(len(filters[shell]), 1, "one read-back filter for both rulesets")
        if len(payloads) == 2:
            self.assertEqual(payloads["sh"], payloads["ps1"])
            self.assertEqual(filters["sh"], filters["ps1"], "PowerShell passes the read-back filter to gh intact")

    def test_a_read_back_that_differs_from_adr_0013_stops_apply(self):
        cases = [
            ("a bypass on the review ruleset", REVIEW, "always merge=squash", 1),
            ("merge commits allowed", REVIEW, "never merge=merge,squash,rebase", 1),
            ("required from any actor", CORE, "never check=required@null linear queue=SQUASH", 2),
            ("no linear history", CORE, "never check=required@15368 queue=SQUASH", 2),
            ("a merge-commit queue", CORE, "never check=required@15368 linear queue=MERGE", 2),
        ]
        for shell in self.shells:
            for what, name, got, posts in cases:
                with self.subTest(shell=shell, case=what):
                    rc, out, err, calls = self.apply(shell, readback={**GOOD, name: got})
                    self.assertEqual(rc, 1, out[-2000:])
                    self.assertIn(f"ruleset '{name}' reads back as '{got}', expected '{GOOD[name]}'", err)
                    self.assertEqual(sum(c["argv"][:4] == ["api", "-X", "POST", f"repos/{R}/rulesets"] for c in calls),
                                     posts, "apply stops at the first ruleset whose read-back is wrong")


if __name__ == "__main__":
    unittest.main()
