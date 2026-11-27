# Proposed: The trusted tester-output gate is a secret-less job inside publish.yml, ahead of the App-token job

Status: Proposed (F72, spec writer). Modules: `.github/workflows/publish.yml`, `30-build.yml`, `tools/check_tester_output.py`.

## Context

D68 (failure class 2) needs a trusted check on the tester's patch before any builder starts. The check has two parts: every new `*Test.java` has a test method, and the tree test-compiles. The in-loop check in `tools/tester_loop.py` runs in the agent's own job, so it is not trusted on its own (ADR-0006). The trusted check runs `mvn test-compile` on agent-written sources, so it must run without model or App secrets (ADR-0011, the `40-verify` precedent). Today the only trusted step between `tester` and `builder` is the `publish` job in `publish.yml`, and that job mints the factory-bot App token in its first steps.

## Decision

Add a job `tester-gate` to `publish.yml`:
- It runs only for `role: tester`.
- It has `permissions: {contents: read}`, references no `secrets.*`, mints no App token, checks out with `persist-credentials: false`, and uses no Maven cache.
- It takes `check_tester_output.py` from `github.workflow_sha`, applies the patch artifact to `base_sha`, and runs the method check and then `test-compile`.

The `publish` job `needs` it and runs for the tester only when it succeeded. A new `tester-failed` job in `30-build.yml` labels the work item `factory:tester-failed` when `publish-tests` fails, the same way `builder-failed` works. A policy-check rule pins that the gate job holds no secret and no App token. The check logic lives in one module that both the loop and the gate import, so the two never disagree on what a "test method" is.

## Alternatives

- **Run the checks inside the existing `publish` job.** Rejected: that job holds the App private key and token, and `test-compile` would run agent code next to them.
- **A separate job in `30-build.yml` between `tester` and `publish-tests`.** This works and is as secret-free. But the gate then lives outside the one path every tester patch is published through (ADR-0004). A future caller of `publish.yml` with `role: tester` would skip it. It also does not match the AC wording that `publish-tests` rejects.
- **Check inside `publish.py` only (no compile).** It needs no new job, but it cannot meet the test-compile requirement, which is the half that caught PR #65.
- **Rely on `40-verify` (`build-test`).** This is today's behaviour. The defect is found only after the builder ran, and a builder fix round cannot repair it.

## Consequences

- Every round-0 work item spends one more runner job of about 1-2 minutes (Maven resolution without a cache) before the builder starts.
- `publish.yml` now has a job that runs agent-written code. The new policy rule, not convention, keeps the secret-less property. Removing or weakening that rule is a security-owner change.
- A rejected tester patch leaves no `wi-<n>` branch, so a rerun of `30 build` round 0 runs the tester again (`run_tester` is true while the branch does not exist). That is a retry by a human, not an automatic one (D68 Open question 2 stays open).
- Revisit when the gate needs its result to be machine-readable, for example to tell guard and gate rejections apart, or to auto-redispatch the tester. That needs a `publish.yml` output for the gate verdict.
