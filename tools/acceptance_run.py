"""Run the hidden acceptance scenarios in scope and print one verdict per AC ID (brief 007, brief 009 item 3).

  wait-healthy --url U --timeout S   exit 0 once U answers 2xx, 1 when S seconds pass first
  run --pom P --scope "AC-F1-1 ..." --app-url U --log L

`run` compiles the scenarios once, then runs surefire once per AC with -Dgroups=<AC>, so a report
belongs to the tag that selected it. All Maven and scenario output goes to L, which is never printed
or uploaded: the public log carries only `AC-F1-3: pass|FAIL` lines and counts. It exits 1 unless
every AC in scope has at least one scenario and all of them passed.
"""
import argparse, dataclasses, enum, pathlib, shutil, subprocess, sys, time, urllib.request
import xml.etree.ElementTree as ET


class Verdict(enum.Enum):
    PASS = "pass"
    FAILED = "failed"
    NO_SCENARIO = "no scenario"
    RUN_ERROR = "run error"


@dataclasses.dataclass(frozen=True)
class Case:
    ok: bool


def wait_healthy(url, timeout_s, interval_s=2.0, probe=None):
    probe = probe or (lambda: urllib.request.urlopen(url, timeout=5).status < 300)
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            if probe():
                return True
        except OSError:
            pass
        if time.monotonic() + interval_s > deadline:
            return False
        time.sleep(interval_s)


def read_cases(reports_dir):
    """Every testcase in the surefire XML under reports_dir. Skipped counts as not passed."""
    cases = []
    for f in sorted(pathlib.Path(reports_dir).glob("TEST-*.xml")):
        for tc in ET.parse(f).getroot().iter("testcase"):
            cases.append(Case(ok=all(tc.find(t) is None for t in ("failure", "error", "skipped"))))
    return cases


def verdict(exit_code, cases):
    if not cases:
        return Verdict.NO_SCENARIO
    if not all(c.ok for c in cases):
        return Verdict.FAILED
    return Verdict.PASS if exit_code == 0 else Verdict.RUN_ERROR


def run_scope(scope, runner):
    """{AC: Verdict} for each AC in scope, in order."""
    if not runner.compile():
        return {ac: Verdict.RUN_ERROR for ac in scope}
    return {ac: runner.run(ac) for ac in scope}


def report(verdicts):
    lines = [f"{ac}: {'pass' if v is Verdict.PASS else 'FAIL'}" for ac, v in verdicts.items()]
    count = {v: sum(1 for x in verdicts.values() if x is v) for v in Verdict}
    failed = len(verdicts) - count[Verdict.PASS]
    lines.append(f"acceptance: {len(verdicts)} in scope, {count[Verdict.PASS]} pass, {failed} FAIL "
                 f"({count[Verdict.NO_SCENARIO]} without a scenario, {count[Verdict.RUN_ERROR]} run errors)")
    return lines, failed == 0 and bool(verdicts)


class Maven:
    def __init__(self, pom, app_url, log):
        self.exe = shutil.which("mvn")
        if self.exe is None:
            raise SystemExit("acceptance: mvn not found")
        self.pom, self.app_url, self.log = pathlib.Path(pom), app_url, log
        self.reports = self.pom.parent / "target" / "surefire-reports"

    def _mvn(self, *args):
        with open(self.log, "a", encoding="utf-8") as out:
            return subprocess.run([self.exe, "-B", "-f", str(self.pom), *args, f"-Dapp.url={self.app_url}"],
                                  stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL).returncode

    def compile(self):
        return self._mvn("test-compile") == 0

    def run(self, ac):
        shutil.rmtree(self.reports, ignore_errors=True)
        code = self._mvn("surefire:test", f"-Dgroups={ac}")
        try:
            return verdict(code, read_cases(self.reports))
        except ET.ParseError:
            return Verdict.RUN_ERROR


def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("wait-healthy")
    h.add_argument("--url", required=True)
    h.add_argument("--timeout", type=float, default=90)
    r = sub.add_parser("run")
    r.add_argument("--pom", required=True)
    r.add_argument("--scope", required=True)
    r.add_argument("--app-url", required=True)
    r.add_argument("--log", required=True)
    a = p.parse_args(argv)
    if a.cmd == "wait-healthy":
        if wait_healthy(a.url, a.timeout):
            print(f"app healthy at {a.url}")
            return 0
        print(f"::error::app did not become healthy at {a.url} within {a.timeout:g}s")
        return 1
    scope = a.scope.split()
    if not scope:
        print("::error::acceptance: empty scope passed to run")
        return 1
    lines, ok = report(run_scope(scope, Maven(a.pom, a.app_url, a.log)))
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
