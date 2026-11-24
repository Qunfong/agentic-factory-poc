import contextlib, io, pathlib, sys, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_secrets_env as pre  # noqa: E402

SECRET = "sk-should-never-be-printed"
ALL = {n: SECRET for n in pre.CREDENTIALS}


def run(argv, env):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = pre.main(argv, env)
    return code, out.getvalue()


class PreflightTest(unittest.TestCase):
    def test_table_shows_yes_no_and_never_a_value(self):
        code, out = run([], ALL)
        self.assertEqual(code, 0)
        self.assertNotIn(SECRET, out)
        for name in pre.CREDENTIALS:
            self.assertRegex(out, rf"{name}\s+yes")

    def test_a_named_role_without_its_credentials_fails_clearly(self):
        env = dict(ALL, AZURE_OPENAI_ENDPOINT="")
        code, out = run(["--role", "tester"], env)
        self.assertEqual(code, 1)
        self.assertIn("::error::role tester can't run: missing AZURE_OPENAI_ENDPOINT", out)
        self.assertNotIn(SECRET, out)

    def test_review_runs_without_the_v1_endpoint_but_says_a_human_takes_over(self):
        env = dict(ALL, AZURE_AI_V1_ENDPOINT="")
        code, out = run(["--role", "review"], env)
        self.assertEqual(code, 0)
        self.assertIn("without AZURE_AI_V1_ENDPOINT: the Grok and DeepSeek reviewers are off", out)
        self.assertIn("needs-human-review", out)

    def test_review_needs_only_the_azure_key_and_endpoints(self):
        self.assertEqual(pre.CREDENTIALS, ("CLAUDE_CODE_OAUTH_TOKEN", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
                                           "AZURE_AI_V1_ENDPOINT"))
        code, out = run(["--role", "review"], ALL)
        self.assertEqual(code, 0)
        self.assertNotIn("without", out)

    def test_presence_flags_from_a_workflow_count_as_set(self):
        rows = dict((r, ok) for r, ok, _ in pre.readiness({"CLAUDE_CODE_OAUTH_TOKEN": "set"}))
        self.assertEqual(rows, {"spec-writer": True, "design-writer": True, "builder": True,
                                 "tester": False, "review": False})

    def test_without_role_the_table_never_fails(self):
        self.assertEqual(run([], {})[0], 0)


if __name__ == "__main__":
    unittest.main()
