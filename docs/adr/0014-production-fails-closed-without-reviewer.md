# ADR-0014: Production deploys fail closed when the environment has no required reviewer

- **Status:** Accepted (@Qunfong, 2026-11-12; built as #17, `fe056d3`)
- **Date:** 2026-11-12
- **Decision makers:** @Qunfong
- **Confidence:** not stated

## Decision

The `production` job of `60-release` first reads the `production` environment through the API. It deploys only when the environment has a `required_reviewers` protection rule. If the rule is missing, or the environment cannot be read, the job fails.

## Context

The first `60 release` run (43277109349) deployed to `production` without any reviewer. GitHub auto-creates a missing environment without protection, and a private repo on the Free plan cannot add required reviewers. The release gate of ADR-0002 therefore did not exist, and nothing reported it. Deploy steps are placeholders today, so the only effect was an image push to ghcr.

## Candidates

### A. Accept until the flip and log each unguarded production run in the Bypass log
- Rejected: it relies on someone noticing, and the next `app/**` merge would deploy again.

### B. Fail closed unless a required reviewer exists (chosen)
- Adds a check only; weakens nothing.

### C. Disable the production job until the snapshot repo
- Rejected: it would have to be re-enabled by hand, and a missing gate would again pass silently later.

## Consequences

- On the current private Free repo every release goes red at `production`. That is expected; build and staging still have to be green.
- The first factory run (issue #16) stops at staging, which matches its scope.
- On the snapshot repo bootstrap sets the reviewer, and the check then passes. Bootstrap's read-back should check the same rule.

## Re-evaluation Triggers

- Real deploy steps replace the placeholders: keep the check, and add a check that staging has the protection it needs.
- The repo moves to an organisation with deployment protection rules or custom gates: express the same rule there and drop the API check only if the platform enforces it.
