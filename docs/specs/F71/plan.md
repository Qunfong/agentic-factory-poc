# F71 plan: escalate fix rounds at once when only undeclared pre-existing tests fail

Spec: [spec.md](spec.md). Work items: [work-items.json](work-items.json). Design: [D68](../../design/D68/design.md), recommendation C (classifier). Followed ADR proposal: [proposed-tester-updates-declared-tests](../../adr/proposed-tester-updates-declared-tests.md), point 4. New ADR proposal: [proposed-fix-round-classifier-input](../../adr/proposed-fix-round-classifier-input.md).

## Modules that change

- `tools/classify_failures.py` (new, trusted): it parses the `build-test` job log, applies the rule, and writes the decision and the comment.
- `tools/tests/test_classify_failures.py` (new): it runs in `40-verify` `static` (`python3 -m unittest discover -s tools/tests`).
- `.github/workflows/45-fix-round.yml`: a new `classify` job between `gate` and `next-round`. `next-round` branches on its output.

Unchanged: `40-verify.yml`, `30-build.yml`, `tools/publish.py`, charters, `factory/**`, `app/**`.

One work item: the three ACs are the two branches of one decision plus its comment, all in the same tool and the same workflow step. Splitting them would only create a serial chain with merge conflicts.

**Red tier, protected change** (spec Open question 1). Every path is red tier, and `.github/` is denied to the builder. WI-1 is built in an interactive factory session and reviewed by the security owner. It is not dispatched to `30 build`.

## Ordered steps (WI-1)

1. Fixtures first (`tools/tests/fixtures/`, none taken from real secrets). Add sanitised `build-test` log excerpts for the following cases: a test compile error in an existing test; a `Failed to load ApplicationContext` error; an assertion failure; a main compile error; a failure in a newly added test; a nested-class failure; an unknown `<<< ERROR!`; a forged line with `../`, an absolute path outside the checkout, or a non-`.java` path; a log over the size cap.
2. `parse_log`: per-line regexes for maven-compiler `[ERROR] <prefix>/app/src/(main|test)/java/....java:[l,c]` and for surefire 3.x `<<< FAILURE!` / `<<< ERROR!` headers with `-- in <fqcn>` or `<fqcn>.<method>`. Look ahead a bounded number of lines for the context-load markers. Return `None` on anything red that is not attributed. Strip GitHub's timestamp prefix from each log line.
3. `classify`: the pure rule from the spec (steps 0 to 3). Unit tests cover each AC branch and each `reason`.
4. Tree checks with `git cat-file -e <sha>:<path>` and `git merge-base`. These are subprocess calls with argument lists, never shell strings.
5. `escalation_comment`: a fixed template. A test asserts that no fixture log line, or any substring of 20 or more characters from one, appears in the output (AC-F71-2).
6. `45-fix-round.yml` `classify` job. It reuses the `next-round` guards and `needs: [authorize, gate]`, with `permissions: actions: read, contents: read, issues: read`. It checks out `github.workflow_sha` with `fetch-depth: 0` and `persist-credentials: false`, then runs `git fetch --no-tags origin <head_sha>` (objects only, no checkout). It reads `build-test`, `static` and `scope` from the same jobs API call that `gate` uses, downloads the job log, reads `Paths:` from the issue, and runs the tool. The decision goes in a job output, and `comment.md` goes in an artifact with `retention-days` of 7 or less.
7. `next-round`: `needs` gains `classify`, and `if:` gains `always()` together with today's guards, so that a failed `classify` still dispatches. When `needs.classify.outputs.decision == 'escalate'`, it adds `escalated`, downloads `comment.md`, and posts it unless an issue comment already contains the marker. Otherwise it runs today's step unchanged.
8. `python3 tools/check_workflow_policy.py`, `python3 -m unittest discover -s tools/tests`, actionlint. Then `mvn -B -f app/pom.xml verify`, which is unaffected but required for "done".
9. Prove it on a real red PR: re-run `45 fix round` on a `40 verify` run like PR #56 or #62, and record the run in `docs/design/factory-flow.md`.

## Risks

- **Log format drift.** A surefire or maven-compiler upgrade, or a change in GitHub's log prefix, makes logs `unparsed`. That degrades to today's behaviour, not to a wrong escalation. The fixtures pin the formats this was built against.
- **`next-round` with `always()`.** It must keep every current guard (same-repo head, `wi-` branch, `required_failed == 'true'`). `check_workflow_policy.py`'s `workflow_run_jobs_require_a_same_repo_head` and `build_dispatchers_are_authorized` must still pass. The policy check may need a rule that `classify` runs only trusted tools (ADR-0006). That is a further `tools/` change in the same work item only if the existing rules do not already cover it.
- **Merge-base assumption.** If someone ever merges `main` into a `wi-` branch, the merge-base moves forward. A test that this work item added could then look pre-existing only if it was also on `main`, which it cannot be before the squash merge. Low risk, documented in the tool's docstring.
- **Open questions 2 to 4 in the spec** change the rule. Each answer is a one-line change in `classify` plus a test, so they do not block the structure, but they must be answered before the plan gate.
- **Hidden acceptance.** There is no app behaviour to scenario-test. `acceptance` for this PR has these AC IDs in scope with no scenarios unless QA writes workflow-level ones. That is informational only (ADR-0007, `required` comment).
