# F72: Tester output is checked before any builder starts

Source: feature issue #72, decomposed from design idea #68 ([D68](../../design/D68/design.md), failure class 2, options 2a + 2b, no auto-retry).

## Problem

Nothing checks the tester's output before the builder runs. In PR #65 (F60 WI-1) the tester handed over a test file with a misused annotation and no `@Test` method. The defect showed up only later as a red `build-test`. A builder fix round cannot repair it, because the builder never touches `app/src/test/**` (ADR-0020). Two builder rounds were spent and the work item then escalated without a diagnosis.

## Grounding

This is a **factory change, not a meter-service change**. No Java package is touched (greenfield for `app/`). The modules involved:

- `tools/tester_loop.py` (ADR-0010): `run()` returns success the first time the model answers without tool calls. `write_file` creates new files under `app/src/test/**` only. `run_mvn` takes a fixed argument allow-list (`TEST_COMPILE_ARGS`), and its child process has the model key removed. Limits are `MAX_TURNS = 60` and the charter's `max_active_minutes` as a wall-clock deadline. Past either limit it raises `InfraFailure`, and `main()` exits 1 with `result=infra-failure`.
- `.github/workflows/30-build.yml`: the job chain is `tester` → `publish-tests` (calls `publish.yml` with `role: tester` and `FACTORY_APP_PRIVATE_KEY`) → `builder`. The `builder` job's `if:` already refuses to start when `run_tester == 'true'` and `publish-tests` did not succeed. `builder-failed` is the existing pattern for labelling a work item: a separate job with `issues: write`, `gh label create --force`, then `gh issue edit --add-label`.
- `.github/workflows/publish.yml`: one `publish` job. It mints the App token first, then checks out `base_sha`, takes the trusted tools from `github.workflow_sha` (ADR-0006), applies the patch and runs `tools/publish.py`. `publish.py`'s tester guard is `--allow app/src/test/** --new-files-only`. `STUB_MARKER = "// factory-test-stub"` already exists there.
- `tools/check_workflow_policy.py`: `maven_cache_only_in_verify_and_release` forbids `cache: maven` outside 40/60. `tools_after_agent_code_come_from_workflow_sha` requires every job in `publish.yml` to read tools only through `git show "$WORKFLOW_SHA:tools/..."`. `40-verify.yml` is the precedent for running agent-written code with no secrets.
- `tools/bootstrap.sh` / `bootstrap.ps1` create `factory:builder-failed`. They do not create `factory:tester-failed` yet.
- ADRs read: 0004, 0005, 0006, 0007, 0010, 0011, 0020, and [proposed-tester-updates-declared-tests](../../adr/proposed-tester-updates-declared-tests.md) (D68 class 1; independent of this feature). New design choice proposed for the plan gate: [proposed-tester-output-gate](../../adr/proposed-tester-output-gate.md).
- **Every path is red tier** (`tools/**`, `.github/**`; risk-map red floor). `.github/**` is a protected path (AGENTS.md "Ask first") and in `publish.py`'s `DENIED_PREFIXES`. See Open question 1.

## Data shape

The money/energy/`Instant` rules do not apply because no domain data is involved. The shape is a Python module shared by the loop and the trusted gate. Bodies are not implemented.

```python
# tools/check_tester_output.py  (new; trusted when taken from github.workflow_sha)
STUB_MARKER = "// factory-test-stub"
TEST_FILE_GLOB = "app/src/test/**/*Test.java"
# An annotation token outside comments: @Test, @ParameterizedTest, or their fully qualified
# forms @org.junit.jupiter.api.Test / @org.junit.jupiter.params.ParameterizedTest.
TEST_ANNOTATION_RE: "re.Pattern"

@dataclass(frozen=True)
class Finding:
    path: str            # repo-relative, forward slashes
    kind: str            # "no-test-method" | "test-compile-failed"
    detail: str          # fixed template text; never raw file content

def has_test_method(source: str) -> bool: ...            # not implemented; strips // and /* */ comments first
def is_stub(source: str) -> bool: ...                    # first line, stripped, == STUB_MARKER
def methodless_test_files(repo_root: Path, paths: Iterable[str], exempt_stubs: bool) -> list[Finding]: ...
def added_test_files(base_sha: str) -> list[str]: ...    # `git diff --cached --name-status --no-renames <base>` status A, matching TEST_FILE_GLOB
def main(argv=None) -> int: ...                          # CLI for the gate: --base SHA [--test-compile]; 0 ok, 1 rejected, 2 usage/infra
```

```python
# tools/tester_loop.py  (changed)
class CompletionCheck:                                   # not implemented
    def __call__(self, repo_root: Path, written: set[str]) -> list[Finding]: ...
    # 1. methodless_test_files(repo_root, written, exempt_stubs=<Open question 2>)
    # 2. run_mvn(repo_root, list(TEST_COMPILE_ARGS)); exit_code != 0 -> Finding("app/pom.xml", "test-compile-failed", ...)

def run(system_prompt, model_args, repo_root, deadline, max_turns=MAX_TURNS,
        completion_check=CompletionCheck()) -> tuple[str, list, dict]: ...
# counts gains "completion_rejections"; raises TestsIncomplete at a limit while findings are pending
class TestsIncomplete(Exception): ...                    # not an InfraFailure: the model ran, its output did not pass
```

Error cases. The factory has no HTTP surface here, so no `ProblemDetail`. A "status" is a process or job result:

| Case | Where | Result |
| --- | --- | --- |
| Model stops, completion check has findings, limits not reached | `tester_loop.run` | not an exit; a `user` message with the reason is appended, loop continues |
| Limits reached while the last check had findings | `tester_loop.main` | stdout `tester: result=tests-incomplete`, exit 1 |
| Limits reached with no pending findings (today's behaviour) | `tester_loop.main` | `tester: result=infra-failure`, exit 1 (unchanged) |
| New `*Test.java` without test method (non-stub) in the patch | gate job in `publish.yml` | `::error::tester gate rejected: <path>: no test method`, job fails |
| `mvn -B -q -f app/pom.xml test-compile` non-zero on base + patch | gate job in `publish.yml` | `::error::tester gate rejected: test-compile failed (exit <n>)`, job fails |
| Any `publish-tests` failure | `30-build.yml` new job `tester-failed` | label `factory:tester-failed` on the work item; `builder` does not start |

Idempotency: there are no retried writes except the label. `gh label create --force` and `--add-label` are idempotent, so the key is the label name on the issue number. A rerun of the gate on the same `base_sha` and the same patch artifact gives the same verdict.

## Interfaces

- `publish.yml` gains a job `tester-gate`:
  - `if: inputs.merge_pr == '' && inputs.role == 'tester'`, `permissions: {contents: read}`.
  - It does not reference `secrets.*` (no `FACTORY_APP_PRIVATE_KEY`, no model key), does not mint an App token, and checks out with `persist-credentials: false`.
  - It sets up Java 21 **without** `cache: maven`.
  - It takes `check_tester_output.py` from `git show "$WORKFLOW_SHA:tools/..."`, downloads `patch-tester`, checks out `base_sha`, `git apply --index`, then runs `check_tester_output.py --base "$BASE_SHA" --test-compile`.
  - `publish` gets `needs: tester-gate` and `if: inputs.merge_pr == '' && (inputs.role != 'tester' || needs.tester-gate.result == 'success')`, so it also runs when the gate is skipped for other roles.
- `30-build.yml` gains a job `tester-failed`: `needs: [prepare, tester, publish-tests]`, `if: always() && needs.prepare.result == 'success' && needs.tester.result == 'success' && needs.publish-tests.result == 'failure'`, `permissions: {issues: write}`. It works like `builder-failed`: label colour B60205, description "Tester output rejected before the builder".
- `builder`'s existing `if:` is unchanged. It already blocks the builder in this case.
- `tools/bootstrap.sh` and `bootstrap.ps1` add `factory:tester-failed|B60205|Tester output rejected before the builder`.
- `tools/check_workflow_policy.py` gains a rule: in `publish.yml`, the job that runs `mvn` references no `secrets.*` and no `create-github-app-token`.

## Behaviour per AC

### AC-F72-1: the tester loop does not end with success while its output is broken
- When the model answers without tool calls, `run()` runs the completion check before it returns.
  - Check 1: every file the loop itself wrote via `write_file` whose path matches `TEST_FILE_GLOB` must contain a `@Test` or `@ParameterizedTest` method.
  - Check 2: `test-compile` (the allow-listed `TEST_COMPILE_ARGS`, key-scrubbed env) must exit 0.
- If the check has findings, the loop appends one `{"role": "user", "content": ...}` message and goes on to the next turn.
  - The message is built from a fixed template. It names each offending path and kind, and for `test-compile` the exit code and the last 4000 characters of mvn output (the same tail `run_mvn` already returns to the model).
  - The message goes into the transcript file only. Stdout gets only the new count `completion_rejections=<n>`.
- The existing `MAX_TURNS` and wall-clock deadline still bound the loop. A completion check counts toward neither limit beyond the turn it ends.
- If a limit is hit while findings are pending, the result is `tests-incomplete` and the exit code is 1. The loop never reports `result=success` with pending findings.
- If the check has no findings, the loop returns success exactly as today.

### AC-F72-2: publish-tests rejects a new test file without a test method
- The `tester-gate` job lists the files the patch adds (git status `A`) that match `app/src/test/**/*Test.java`.
- A file whose first line, stripped, is exactly `// factory-test-stub` is exempt.
- Any other added file with no `@Test` / `@ParameterizedTest` token outside comments is a finding. The job prints one `::error::` line per file (path and kind, no file content) and fails.
- Then `publish` does not run (nothing is pushed), `publish-tests` fails, `tester-failed` labels the work item `factory:tester-failed`, and `builder`'s existing condition keeps it from starting.

### AC-F72-3: publish-tests rejects a tester patch that does not test-compile
- In the same `tester-gate` job, after the method check passes, the gate runs `mvn -B -q -f app/pom.xml test-compile` on `base_sha` plus the applied patch.
- The job holds no model key and no App key, and has a read-only `GITHUB_TOKEN` that is not persisted to `.git`.
- A non-zero exit fails the job with `::error::tester gate rejected: test-compile failed (exit <n>)`. The mvn output stays in the job log, the same as `40-verify`'s `build-test`.
- The consequences are the same as AC-F72-2: no push, the label `factory:tester-failed`, and no builder start.
- The tester guard only admits `app/src/test/**`, so `app/pom.xml` and its plugins come from the base commit.

## Out of scope

- Re-dispatching the tester after a rejection (`tester.yaml` `max_fix_rounds`). D68 Open question 2 leaves this to a human; the gate fails closed with a label.
- Letting the tester modify existing tests, and the fix-round classifier (D68 failure class 1, the other two features of #68).
- Judging test quality beyond "has a test method and compiles" (assertion strength, AC tag coverage).
- Removing the label automatically on a later successful run (`builder-failed` is not removed either).

## Open questions

1. **Can this feature go through the factory at all, or is it implemented by a human / interactive session?**
   - Every path is red tier.
   - WI-2 needs `.github/workflows/*.yml`, which AGENTS.md lists as "ask first" and `publish.py`'s `builder_allowed_paths` rejects outright (`DENIED_PREFIXES`). Publishing that work item would fail.
   - The tester can only write `app/src/test/**`, so it cannot write the Python tests under `tools/tests/`.
   - Hidden acceptance is JUnit by its acceptance-criterion `@Tag`, which has nothing to run against tools or workflows.
   - The work items below are shaped as if a person, or a Claude Code session working on the factory (HANDOFF.md), builds them. Please confirm before the plan gate.
2. **Does the in-loop check (AC-F72-1) exempt `// factory-test-stub` files the way AC-F72-2 does?** AC-F72-1 names no exemption. Without one, the loop is stricter than the gate, which is safe but could reject a legitimate stub named `*Test.java`. The spec leaves `exempt_stubs` open instead of guessing.
3. **Should a path-guard rejection of the tester patch also get `factory:tester-failed`?** The spec labels on *any* `publish-tests` failure, because a failed reusable-workflow call does not reliably say which inner job failed. The narrower option needs an output from `publish.yml` that tells the gate and the guard apart.
4. **Which annotations count as a "test method"?** The ACs name `@Test` and `@ParameterizedTest` only. Under this spec a file with only `@RepeatedTest`, `@TestFactory` or `@TestTemplate` methods is rejected. Is that intended?
5. **Without `cache: maven`** (policy rule), every gate run resolves Maven dependencies from scratch, which takes about 1-2 minutes per work item. Is that acceptable, or should `MAVEN_CACHE_FILES` admit `publish.yml`'s gate job (a `factory/**`/policy change)?
