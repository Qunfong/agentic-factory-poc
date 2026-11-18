# ADR-0008: Go public from a fresh one-commit snapshot, behind an authorize gate

- **Status:** Accepted (@Qunfong: ANSWERS Q2, Q5, Q7+Q9; 2026-11-12: the flip is delegated to Claude Code under conditions)
- **Date:** 2026-11-11
- **Decision makers:** @Qunfong
- **Confidence:** not stated

## Decision

**The repo goes public, so that rulesets work on GitHub Free. It does so as a new repo with a single root commit, not by rewriting history.** The current repo becomes the private `agentic-factory-poc-archive`.
- Before the flip, a pre-publish scan (pinned gitleaks plus a client-name deny-list kept outside the repo) must pass.
- Every agent workflow starts with an `authorize` job: the actor and the triggering actor must have maintain or admin, or be the factory bot.
- Dispatch accepts only items whose ready label came from such an actor (Q27).
- Fork PRs need approval before they run, Discussions are off, and private vulnerability reporting is on.

## Candidates

### A. GitHub Pro
- Server-side gates on a private repo. Rejected by @Qunfong (Q2).

### B. Rewrite the history and force-push
- Removes the client name and the private email from history, but rewrites every SHA. Rejected (Q7+Q9).

### C. Fresh snapshot repo (chosen)

## Consequences

- The default branch is `master`.
- Actions logs become public, which drives ADR-0010 (tester transcript) and ADR-0007 (AC-only logs).
- The flip is allowed only after the scan passes, briefs 012 and 013 are merged, and bootstrap `--apply` is ready to run.

## Re-evaluation Triggers

- A client repo ever runs on this factory: re-assess everything that ends up in public logs.
