# Brief 017: the feature issue is the place to follow a feature

Qun's request (2026-11-12, after issue #16): "this should all be stored in the same issue". Decided with Cowork: keep the separate objects (spec PR, work-item issues, `wi-<n>` PRs), but make the feature issue the place where all of them come together. Starts **after the first factory run on #16 is fully green**. It is backlog item 1, together with brief 015.

## Why
On #16 the factory created spec PR #21, work item #22 and branch `wi-22`. Nothing on #16 points to them, so Qun has to search Actions and the PR list to see where a feature stands.

## Decisions
1. **Objects stay separate.** The spec PR is the plan gate. A work item is its own issue because a feature can split into several, each with its own branch, labels, WIP slot and fix rounds.
2. **Work items are sub-issues of the feature issue** (GitHub sub-issues API), so #16 shows them with a progress bar.
3. **Every PR links back.** The spec PR and each `wi-<n>` PR body start with `Part of #<feature>`, and `wi-<n>` PRs also say `Closes #<work item>`.
4. **One status comment on the feature issue**, found by a hidden marker and edited in place, never posted twice. Content: spec PR and state; per work item, its issue, PR and stage (build / verify / review / merged / builder-failed / needs-human-review), with links to runs. **Only AC IDs and pass/fail. No scenario text, no model output** (public repo, ADR-0007/0008).
5. **The feature issue closes** when its last work item's PR is merged, with a final status line.
6. **Who writes:** only trusted jobs that already hold the App token or `issues: write` (`publish.yml`, 20-breakdown, 50-review, and the merge step). Never an agent job (ADR-0004). The feature number comes from `docs/specs/F<n>/` or the work item's recorded parent, never from model text.

## What to build
- `tools/feature_status.py` (+ tests): builds the comment from GitHub state (sub-issues, PRs, labels, latest runs) and upserts it by marker. It is idempotent: running it twice gives the same comment.
- 20-breakdown: add each created work item as a sub-issue of the feature, then call the status update.
- `publish.yml`: write `Part of #<feature>` / `Closes #<wi>` into PR bodies, then call the status update.
- 50-review and the merge step: call the status update; on the last merged work item, close the feature issue.
- A policy rule: no agent job calls `feature_status.py` or has `issues: write`.

## Acceptance criteria
- On a new test feature, the feature issue shows: sub-issues, one status comment that changes through spec → build → verify → review → merged, and closes itself at the end.
- Re-running any workflow does not create a second comment.
- Unit tests: marker upsert, a feature with two work items, a builder-failed item, and a comment that contains no text from the acceptance repo.
- Policy check 0 violations.
