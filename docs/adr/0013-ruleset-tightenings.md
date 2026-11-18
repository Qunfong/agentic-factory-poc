# ADR-0013: The `required` check must come from GitHub Actions, and merges are squash-only

- **Status:** Accepted (@Qunfong in the Cowork session, 2026-11-12); to be built after PRs #1–#14 are merged
- **Date:** 2026-11-12
- **Decision makers:** @Qunfong
- **Confidence:** not stated

## Decision

**Two additions to the rulesets of ADR-0002:**
1. In `factory-default-branch`, the required status check `required` is pinned to the GitHub Actions app (`integration_id` 15368).
2. Merges are squash-only and history is linear. The `pull_request` rule of `factory-default-branch-review` sets `allowed_merge_methods: ["squash"]`, and `factory-default-branch` adds `required_linear_history`.

Bootstrap's `--apply` read-back fails unless the rulesets show both.

## Context

A required check matched by name alone is satisfied by any commit status called `required`, whoever sets it. `master`'s first 50-review job had `statuses: write`. With one maintainer and run records keyed to commits, a history of one commit per PR is easier to audit and to revert.

## Candidates

### A. Also require signed commits
- Rejected: the factory-bot and Actions commit without Qun's key. Lots of friction, little gain.

### B. Push rulesets that restrict paths
- Not available on the plan. The `publish` path guard (ADR-0005) covers agents.

## Consequences

- A status from any other app or token no longer satisfies `required`.
- What it doesn't cover: a PR that adds its own workflow with a job named `required` still runs as GitHub Actions. That is covered by the path guard (agents can't touch `.github/`), the red tier, and code-owner review of human PRs.
- A merge commit is no longer possible; squash messages carry the PR title.

## Re-evaluation Triggers

- A merge queue becomes available (organisation repo): set its `merge_method` to `SQUASH`.
- Releases start using tags: add a tag ruleset for `v*` (no deletion, no update).
