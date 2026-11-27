# F71: Fix rounds escalate immediately when only undeclared pre-existing tests fail

Source: feature issue #71, decomposed from design idea #68 ([docs/design/D68/design.md](../../design/D68/design.md), recommendation C, the classifier half).

## Problem

`.github/workflows/45-fix-round.yml` dispatches a `30 build` builder round whenever the `required` job of a `40 verify` run on `wi-<n>` failed, up to 2 rounds, then adds `escalated` with the fixed comment "Fix-round limit reached; a person takes over." The builder can never write under `app/src/test/**` (ADR-0020, `tools/publish.py` `builder_allowed_paths`, builder charter). So when the only red is a pre-existing test the work item does not own (PR #56, PR #62: `ReadingControllerTest` no longer loads its context after `ReadingController` gained a dependency), both rounds are wasted, often with "produced no changes", and the escalation says nothing about the cause.

## Grounding

**This is not a meter-service feature.** It does not touch `app/**`. Every changed path is factory code: `.github/workflows/45-fix-round.yml` and a new trusted tool under `tools/`. Both are red tier (`factory/risk-map.yaml`, red floor in `tools/check_tier.py`). `.github/` is also in `publish.py` `DENIED_PREFIXES`, so the factory builder cannot build this work item. See Open question 1.

What exists:

- `45-fix-round.yml`: `authorize` (from `workflow_sha`, `tools/authorize.py`), then `gate` (`actions: read`; reads the `required` job's conclusion from the run's jobs API), then `next-round` (`actions: write`, `issues: write`; counts `round:*` labels, then either adds `round:<n+1>` and runs `gh workflow run "30 build"`, or adds `escalated` and comments).
- `40-verify.yml` `build-test`: `mvn -B -f app/pom.xml verify` on the PR head. It saves no surefire reports and no log artifact. Its output is only the GitHub job log. `required` fails if `build-test`, `static` or `scope` did not succeed.
- Work item `Paths:` line: written into the issue body by `tools/create_work_items.py`, read back with `sed -n 's/^Paths: //p'` (`publish.yml`, `30-build.yml`).
- Work item base commit: round 0 of `30-build.yml` `prepare` starts from `GITHUB_SHA` (the `main` tip at dispatch) when `wi-<n>` does not exist yet. Every later commit sits on top of it. Work-item PRs squash-merge and nothing merges `main` back into a `wi-` branch, so the base commit is `git merge-base <main> <head_sha>`.
- ADR-0006: after agent code has run, only tools from the workflow's own commit execute. ADR-0007: the classifier reads only `build-test`, never `acceptance`. ADR proposal [proposed-tester-updates-declared-tests](../../adr/proposed-tester-updates-declared-tests.md) (D68), point 4, is the decision this feature builds. It is followed here, not re-proposed.
- New design choice, proposed for the plan gate: [proposed-fix-round-classifier-input](../../adr/proposed-fix-round-classifier-input.md), where the classifier reads build output from.

Spec-shape rules that do not apply here: no money, energy or `Instant` fields, no HTTP boundary, no Java package. The shape is sketched as Python signatures because the code is a Python tool in `tools/`. No `app/pom.xml` change, no migration.

## Data shape

```python
# tools/classify_failures.py  (new, trusted: runs from the workflow's own commit, ADR-0006)

Kind = Literal["compile error", "context load failure", "assertion failure"]   # closed vocabulary

@dataclass(frozen=True)
class Failure:
    path: str   # repo-relative, matches ^app/src/(main|test)/java/[A-Za-z0-9_/]+\.java$ ; never log text
    kind: Kind

@dataclass(frozen=True)
class Decision:
    action: Literal["escalate", "dispatch"]
    failures: tuple[Failure, ...]   # sorted by path, then kind; deduplicated; empty unless action == "escalate"
    reason: Literal["undeclared-pre-existing-only", "owned-or-main", "unparsed", "no-test-failure", "other-job-failed"]
```

How a log line becomes a `Failure`. The log is untrusted data, because agent-written code produced it.

| Source in the `build-test` log | `path` | `kind` |
| --- | --- | --- |
| maven-compiler `[ERROR] <abs>/app/src/<main or test>/java/<rel>.java:[l,c] ...` | `app/src/<main or test>/java/<rel>.java`, with the checkout prefix stripped | `compile error` |
| surefire `<<< ERROR!` for a class or method whose following trace contains `Failed to load ApplicationContext` or `ApplicationContext failure threshold` | the class's file (below) | `context load failure` |
| surefire `<<< FAILURE!` for a method (an `AssertionError` or a subclass) | the class's file | `assertion failure` |

- Class to file: a fully qualified name `a.b.C` (or `a.b.C$D`, `a.b.C.D` for nested classes) maps to `app/src/test/java/a/b/C.java`. It is kept only if that path exists in the tree of `head_sha`. Otherwise the result is `unparsed`.
- A path is kept only if it matches the regex above and exists in `head_sha`'s tree (`git cat-file -e`). Nothing else from the log ever leaves the tool.
- A surefire `<<< ERROR!` that is not a context load failure has no kind in the issue's vocabulary. See Open question 3. Until it is answered, it makes the result `unparsed`.

## Interfaces

```python
def parse_log(log: str, repo_root_prefixes: tuple[str, ...]) -> list[Failure] | None:
    """Failures found in a build-test job log; None when the log shows a red build that this
    parser cannot fully attribute (unknown error shape, a path that is not kept, size cap hit)."""
    # not implemented

def classify(failures: list[Failure] | None, base_tree: set[str], head_tree: set[str],
             declared_paths: list[str], other_jobs_green: bool) -> Decision:
    """Pure function; the whole rule of this feature lives here."""
    # not implemented

def escalation_comment(decision: Decision, verify_run_id: int) -> str:
    """Fixed template: marker line, one bullet per failure as "`<path>`: <kind>", run link built from the id."""
    # not implemented

def main(argv) -> int:
    """--log FILE --base-sha SHA --head-sha SHA --paths "<Paths: line value>" --other-jobs-green true|false --run-id N --out DIR
    Writes DIR/decision (escalate|dispatch) and DIR/comment.md. Exit 0 on any decision; exit 1 only on
    bad arguments or git errors, and the workflow then falls back to dispatch (see AC-F71-3)."""
    # not implemented
```

`classify` rule, evaluated in order:

0. `other_jobs_green` is false (`static` or `scope` did not succeed in the same verify run) gives `dispatch` / `other-job-failed` (Open question 2).
1. `failures is None` gives `dispatch` / `unparsed`. An empty list gives `dispatch` / `no-test-failure`, for example when `build-test` failed before any compile or test step.
2. Any failure whose `path` starts with `app/src/main/`, or is not in `base_tree` (this work item added it), or is in `declared_paths`, gives `dispatch` / `owned-or-main`.
3. Otherwise every failure is in a test file that exists in `base_tree` and is not declared. That gives `escalate` / `undeclared-pre-existing-only`.

Workflow (`45-fix-round.yml`). The jobs `authorize` and `gate` and their conditions stay unchanged. The new job steps:

```yaml
classify:            # needs: [authorize, gate]; if: required_failed == 'true' (same guards as next-round)
  permissions: {actions: read, contents: read, issues: read}
  # checkout github.workflow_sha with fetch-depth: 0 (tool + main history); fetch head_sha objects only, never check it out or run it
  # base_sha = git merge-base origin/main "$HEAD_SHA"; job id of "build-test" from the run's jobs API;
  # conclusions of "static" and "scope" from the same jobs API call (--other-jobs-green);
  # gh api .../actions/jobs/<id>/logs > log; Paths: from the issue body; python3 tools/classify_failures.py ...
  # outputs: decision (escalate|dispatch); comment uploaded as an artifact (retention <= 7 days)
next-round:          # needs: [authorize, gate, classify]
  # decision == escalate  -> add label "escalated"; post comment.md unless a comment with its marker exists; no round label, no 30 build
  # otherwise (dispatch, or classify did not succeed) -> today's step, unchanged: round:<n+1> and 30 build, limit 2
```

Error cases:

| Case | Outcome |
| --- | --- |
| `build-test` log unavailable, too large (cap 20 MB), or unparseable | `dispatch`, as today. The classifier only skips rounds when it is certain. |
| `classify` job fails (git, API) | `next-round` dispatches as today. It does not fail open into "escalate" and does not drop the round. |
| `wi-<n>` head not found in history, or merge-base empty | `classify` exits 1, which leads to dispatch as today |
| Issue body has no `Paths:` line | `declared_paths = []` |

Idempotency: a re-run of `45 fix round` for the same `40 verify` run must not post a second comment. The idempotency key is the verify run id. The comment's first line is `<!-- factory:fix-round-classifier run=<run_id> -->`, and `next-round` skips posting when an issue comment already contains that line. Adding `escalated` again is a no-op.

## Behaviour per AC

### AC-F71-1: Only undeclared pre-existing test failures: no build round, `escalated`

Given `required` failed on `wi-<n>`, and every failing test class and every compile error parsed from `build-test` is in a file that is under `app/src/test/`, exists at the work item's base commit, and is not in the issue's `Paths:` line. Then `45 fix round` adds the label `escalated` to issue `<n>`, adds no `round:*` label, and runs no `30 build`. This holds on round 0 and on round 1, whatever the current round count is.

### AC-F71-2: The escalation comment names files and kinds, and quotes no log text

The comment on issue `<n>` lists each distinct failing file once per kind, as `` `<path>`: <kind> ``. `<kind>` is one of `compile error`, `context load failure`, `assertion failure`. Every path passed the tree-existence check, and every kind comes from the fixed vocabulary, so no byte of the job log reaches the comment. The tool builds the list from `classify_failures.py` run from `workflow_sha`, never from a tool or file on the agent branch. Beyond the list, the comment holds only fixed text: that no builder round was started because the builder may not edit these tests, how to proceed (declare the test in a follow-up work item's `Paths:` or fix it by hand), the idempotency marker, and a link to the verify run built from its numeric id.

### AC-F71-3: Any failure the builder owns: next round as today

When at least one parsed failure is in `app/src/main/**` or in a file that is not in the base tree (added by this work item), the decision is `dispatch`. `next-round` then runs today's step unchanged: it adds `round:<n+1>` and dispatches `30 build`, and when the next round would be 3 it escalates with today's "Fix-round limit reached" comment. The same path is taken when the classifier cannot decide (`unparsed`, `no-test-failure`, or the `classify` job failed) and when a failing pre-existing test is declared in `Paths:`.

## Out of scope

- Letting the tester modify declared existing tests, the method-count check, and the tester output gate. Those are the other features from D68.
- A test-repair role (D68 alternative B).
- Any change to the builder's guard, to `40-verify.yml`, to `30-build.yml`'s round limit, or to `acceptance`.
- Removing `escalated` again, and any human-triggered fix round.

## Open questions

1. **Protected change: who builds this?** Every path is red tier, and `.github/workflows/45-fix-round.yml` is in `publish.py`'s `DENIED_PREFIXES`. A builder run for this work item would be rejected by the guard ("work item path ... is never allowed for the builder"). Proposal: after the plan gate, the work item is implemented in an interactive factory session as a human-reviewed PR. 20-breakdown should not dispatch it to `30 build`. A person must confirm this route.
2. **Does a failure outside `build-test` block escalation?** AC-F71-1 speaks only of test classes and compile errors. If `static` (Semgrep on `app/src/main`, policy check) or `scope` also failed in the same run, the builder might fix those. The spec takes the cautious route: escalate only when `build-test` is the only failed input of `required`, otherwise `dispatch`. The issue does not state this rule. Please confirm.
3. **A test error that is not a context load failure** (for example an NPE or a `@MockBean` missing at runtime) has no kind in AC-F71-2's list. Options: (a) add a fourth kind `test error`; (b) report it as `assertion failure`; (c) treat it as `unparsed`, which means dispatch as today. The spec uses (c) until this is answered. That makes AC-F71-1 apply less often, but never wrongly.
4. **Forged log lines.** Agent-written main code can print a line that looks like a compiler error for some other existing test file. The worst outcome is an early escalation to a person, never a skipped check or a merged change. The spec accepts this, and no AC covers it. Please confirm.
