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

## Re-evaluation Triggers

- An app needs outbound network: give it an explicit allow-list through a protected change.
