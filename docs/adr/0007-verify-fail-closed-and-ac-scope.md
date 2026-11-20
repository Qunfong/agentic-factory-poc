# ADR-0007: Verify fails closed, runs hidden acceptance tests by AC ID, and blocks egress

- **Status:** Proposed (brief 007, 011; ANSWERS Q4, Q23–Q26, Q52; implemented, not merged)
- **Date:** 2026-11-11
- **Decision makers:** Cowork; AC convention to be confirmed by the PO/QA (@Qunfong)
- **Confidence:** not stated

## Decision

**`required` passes only when every job passes, and every missing input is a failure.** That covers a missing acceptance repo or token, an unhealthy app, an AC without a scenario, and a run error.
- Hidden scenarios live in a private acceptance repo and are tagged `@Tag("AC-F<issue>-<n>")`. The PO writes `AC-1, AC-2…` in the issue, and the spec writer rewrites them 1:1, never renumbering them.
- Verify runs the ACs of the PR's own work item **plus** all ACs that are already merged (regression).
- Logs print only `AC-…: pass|FAIL`.
- The app under test runs as `nobody`, with outbound network blocked. A probe against `https://api.github.com` proves it: the runner can reach it and `nobody` can't. If the runner can't reach it either, the check fails as "inconclusive".

## Context

Agents must not see or overfit the acceptance scenarios. The repo goes public, so scenario content must never reach a log.

## Consequences

- `required` can't go green until the acceptance repo `meter-acceptance` and `ACCEPTANCE_REPO_TOKEN` exist (brief 012 addendum).
- A reverted work item's ACs stay in scope until a spec PR retires them (Q25). This fails safe.
- **`acceptance` no longer blocks merge (Qun, 2026-11-20, first iteration).** Writing a hidden scenario for every AC before any PR can merge was too much overhead this early - the factory was producing real work items faster than scenarios could be authored for them (F7 WI-1 was the first case: `acceptance` failed only because no scenario existed yet, correctly, but that's now the normal case, not the exception). `40-verify.yml`'s `required` job still `needs: acceptance` and still reports `needs.acceptance.result`, so it keeps running and verify still waits for it - but the job no longer fails `required` on that result. The merge gate for now is the human-approved PR review branch protection already requires (`factory-default-branch-review`), not this check. This is explicitly a first-iteration call, not a retraction of ADR-0007's reasoning (agents must not see or overfit the acceptance scenarios) - that part is unchanged, scenarios just aren't mandatory yet.

## Re-evaluation Triggers

- An app needs outbound network: give it an explicit allow-list through a protected change.
- Scenario authoring catches up with feature throughput, or a lighter-weight way to write them appears - make `acceptance` block merge again.
