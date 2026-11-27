# F72 plan: Tester output is checked before any builder starts

Spec: [spec.md](spec.md). ADR proposal: [proposed-tester-output-gate](../../adr/proposed-tester-output-gate.md).
All paths are red tier. Read spec Open question 1 before dispatching anything.

## Modules that change

| Module | Change | Work item |
| --- | --- | --- |
| `tools/check_tester_output.py` (new) | method check, added-file listing, gate CLI | WI-1 |
| `tools/tester_loop.py` | completion check before success, `tests-incomplete` result | WI-1 |
| `tools/tests/test_check_tester_output.py`, `tools/tests/test_tester_completion.py` (new) | unit tests | WI-1 |
| `.github/workflows/publish.yml` | secret-less `tester-gate` job; `publish` needs it | WI-2 |
| `.github/workflows/30-build.yml` | `tester-failed` labelling job | WI-2 |
| `tools/check_workflow_policy.py` + `tools/tests/test_check_workflow_policy_tester_gate.py` (new) | rule: the gate job holds no secrets/App token | WI-2 |
| `tools/bootstrap.sh`, `tools/bootstrap.ps1` | create `factory:tester-failed` | WI-2 |

No `app/**`, no `app/pom.xml`, no `factory/**`, no migration.

## Ordered steps

1. **WI-1, checker module.** Write `has_test_method`, `is_stub`, `methodless_test_files` and `added_test_files` test-first.
   - Cases: `@Test` method; `@ParameterizedTest`; the fully qualified forms; `@Test` only inside a `//` or `/* */` comment (no method); a nested class with a test; the stub marker on line 1 (exempt only when `exempt_stubs`); the marker on line 2 (not exempt); a non-`*Test.java` file (ignored).
2. **WI-1, loop.** Track the paths `write_file` wrote, and inject a `completion_check` into `run()` so tests can stub out mvn.
   - Tests: the model stops with a methodless file, gets one `user` message and continues, then succeeds after fixing it. `test-compile` exit 1 leads to a rejection. A limit hit with pending findings gives `tests-incomplete` and exit 1. Stdout never contains file content or mvn output (extend the quiet-output assertions).
   - Confirm that `run_mvn` called by the check still uses the scrubbed env.
3. **WI-1, verify.** `python -m pytest tools/tests` and `mvn -B -f app/pom.xml verify` (unchanged app).
4. **WI-2, policy rule first.** Add the `check_workflow_policy.py` rule and its test, then confirm the rule fails on today's `publish.yml` only where intended. It must not fail: there is no gate job yet, so the rule passes vacuously.
5. **WI-2, gate job** in `publish.yml`.
   - Order: trusted tools from `WORKFLOW_SHA`, checkout `base_sha` (`persist-credentials: false`), setup-java without cache, download `patch-tester`, apply, run the checker with `--test-compile`.
   - Add `needs: tester-gate` and the `if:` to `publish`.
   - Run `tools/check_workflow_policy.py`, actionlint and the policy tests.
6. **WI-2, label job** in `30-build.yml` and the label in both bootstrap scripts, plus the bootstrap tests that list labels (`test_bootstrap.py`, `test_bootstrap_apply.py`). These are existing tests under `tools/tests`, not `app/src/test`, but they are red tier, so the change is reviewed as such.
7. **WI-2, live proof.** Dispatch `30 build` on a throwaway work item whose tester output is forced bad: once a methodless test file, once a file that does not compile. Each time expect a red `publish-tests`, no push to `wi-<n>`, the label `factory:tester-failed`, and a skipped `builder`. Then run one good work item and expect an unchanged green path.

## Risks

- **Running agent code.** `test-compile` compiles agent-written sources. Annotation processors come from the base `pom.xml` (the tester guard admits only `app/src/test/**`), but javac still processes attacker-chosen input. Mitigation: the job holds no secrets, has a read-only, non-persisted `GITHUB_TOKEN`, and the policy rule pins that.
- **The reusable workflow's secret scope.** `FACTORY_APP_PRIVATE_KEY` is passed into `publish.yml`. Any job there *could* reference it. The new policy rule is what keeps the gate job from doing so.
- **False rejections.** A heuristic annotation match can misjudge unusual sources, for example `@Test` inside a string literal, which counts as present. The rule errs toward accepting. The gate is about empty or misannotated files, not a full Java parser.
- **Loop cost.** Each completion check runs `test-compile` (about 30-60 s). That counts toward the wall-clock limit, so a loop near its limit may end `tests-incomplete` where today it would have ended (wrongly) as success.
- **Pipeline fit.** The factory builder cannot publish `.github/**` (spec Open question 1). If WI-2 is dispatched as-is, `publish-code` fails with "work item path ... is never allowed for the builder".
- **Ordering with D68's other features.** "Tester may update declared existing tests" changes the tester guard in `publish.py`. This feature does not touch `publish.py`, so the two can merge in either order. Only `added_test_files` (status `A`) must stay "new files only" and not count modified files.
