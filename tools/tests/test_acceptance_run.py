import contextlib, html, http.server, io, pathlib, sys, tempfile, threading, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import acceptance_run as r  # noqa: E402

V = r.Verdict
SECRET = "negative_reading_is_rejected expected: <400> but was: <201>"


def surefire_xml(*cases):
    body = "".join(f'<testcase name="{n}" classname="com.example.ScenarioTest">{inner}</testcase>' for n, inner in cases)
    return f'<?xml version="1.0"?><testsuite name="x" tests="{len(cases)}">{body}</testsuite>'


class FakeRunner:
    def __init__(self, compiles=True, verdicts=None):
        self.compiles, self.verdicts, self.ran = compiles, verdicts or {}, []

    def compile(self):
        return self.compiles

    def run(self, ac):
        self.ran.append(ac)
        return self.verdicts.get(ac, V.NO_SCENARIO)


class HealthTest(unittest.TestCase):
    def test_app_that_never_answers_fails_within_the_bound(self):
        self.assertFalse(r.wait_healthy("x", timeout_s=0.05, interval_s=0.01, probe=lambda: False))

    def test_connection_errors_are_retried_until_healthy(self):
        answers = iter([OSError("refused"), OSError("refused"), True])

        def probe():
            a = next(answers)
            if isinstance(a, Exception):
                raise a
            return a

        self.assertTrue(r.wait_healthy("x", timeout_s=1, interval_s=0.01, probe=probe))

    def test_cli_exits_1_when_nothing_listens(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = r.main(["wait-healthy", "--url", "http://127.0.0.1:9/actuator/health", "--timeout", "0.1"])
        self.assertEqual(code, 1)
        self.assertIn("did not become healthy", out.getvalue())

    def test_cli_exits_0_against_a_live_server(self):
        server = http.server.HTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
        server.RequestHandlerClass.log_message = lambda *a: None
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code = r.main(["wait-healthy", "--url", f"http://127.0.0.1:{server.server_port}/", "--timeout", "5"])
        finally:
            server.shutdown()
        self.assertEqual(code, 0)


class ReportsTest(unittest.TestCase):
    def cases(self, xml):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "TEST-com.example.ScenarioTest.xml").write_text(xml, encoding="utf-8")
            return r.read_cases(d)

    def test_failure_error_and_skipped_are_not_passes(self):
        cases = self.cases(surefire_xml(("a", ""), ("b", f'<failure message="{html.escape(SECRET)}"/>'),
                                        ("c", "<error/>"), ("d", "<skipped/>")))
        self.assertEqual([c.ok for c in cases], [True, False, False, False])

    def test_missing_reports_dir_has_no_cases(self):
        self.assertEqual(r.read_cases("does-not-exist"), [])

    def test_verdict_table(self):
        ok, bad = r.Case(True), r.Case(False)
        self.assertEqual(r.verdict(0, []), V.NO_SCENARIO)
        self.assertEqual(r.verdict(1, []), V.NO_SCENARIO)
        self.assertEqual(r.verdict(0, [ok]), V.PASS)
        self.assertEqual(r.verdict(1, [ok, bad]), V.FAILED)
        self.assertEqual(r.verdict(1, [ok]), V.RUN_ERROR)


class RunScopeTest(unittest.TestCase):
    def test_each_ac_in_scope_runs_once_in_order(self):
        runner = FakeRunner(verdicts={"AC-F1-1": V.PASS, "AC-F1-2": V.PASS, "AC-F1-3": V.PASS})
        verdicts = r.run_scope(["AC-F1-1", "AC-F1-2", "AC-F1-3"], runner)
        self.assertEqual(runner.ran, ["AC-F1-1", "AC-F1-2", "AC-F1-3"])
        lines, ok = r.report(verdicts)
        self.assertTrue(ok)
        self.assertEqual(lines[-1], "acceptance: 3 in scope, 3 pass, 0 FAIL (0 without a scenario, 0 run errors)")

    def test_ac_without_a_scenario_fails(self):
        lines, ok = r.report(r.run_scope(["AC-F1-1", "AC-F1-9"], FakeRunner(verdicts={"AC-F1-1": V.PASS})))
        self.assertFalse(ok)
        self.assertEqual(lines[:2], ["AC-F1-1: pass", "AC-F1-9: FAIL"])
        self.assertIn("1 without a scenario", lines[-1])

    def test_compile_failure_fails_every_ac_without_running_any(self):
        runner = FakeRunner(compiles=False)
        lines, ok = r.report(r.run_scope(["AC-F1-1"], runner))
        self.assertEqual((ok, runner.ran, lines[0]), (False, [], "AC-F1-1: FAIL"))

    def test_empty_scope_is_not_a_pass(self):
        self.assertFalse(r.report({})[1])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(r.main(["run", "--pom", "p", "--scope", " ", "--app-url", "u", "--log", "l"]), 1)

    def test_report_lines_are_ac_ids_and_verdicts_only(self):
        lines, _ = r.report({"AC-F1-1": V.FAILED, "AC-F1-2": V.RUN_ERROR, "AC-F1-3": V.PASS})
        for line in lines[:-1]:
            self.assertRegex(line, r"^AC-F[0-9]+-[0-9]+: (pass|FAIL)$")


if __name__ == "__main__":
    unittest.main()
