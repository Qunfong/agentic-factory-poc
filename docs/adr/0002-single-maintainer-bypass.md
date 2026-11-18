# ADR 0002: POC: single maintainer, bypass via PR only; revert when a second reviewer exists

- Status: Accepted (Qun, ANSWERS Q6, 2026-11-11)
- Modules: `.github/`, `tools/bootstrap.sh`, `tools/bootstrap.ps1`

## Context

The repo is owned by a personal account with one maintainer, Qunfong. The default-branch ruleset requires an approving review from a code owner, and GitHub never counts a PR author's own approval. The `production` environment has one required reviewer with "prevent self-review" on. With one human, both controls block every change Qunfong makes himself, and every production deploy he starts.

Agent PRs are not affected. factory-bot opens them, so Qunfong is never their author and can approve them normally.

## Decision

Two weakenings, each behind its own bootstrap flag. Both are off by default, accepted only for a personal-account owner, and print a WARNING that names this ADR.

1. `--admin-bypass-via-pr` (`-AdminBypassViaPr`). A bypass skips every rule in its ruleset, so bootstrap writes two rulesets on `~DEFAULT_BRANCH` and puts the bypass only on the one that holds the review rule:

   | Ruleset | Rules | `bypass_actors` |
   | --- | --- | --- |
   | `factory-default-branch` | deletion, non-fast-forward, required status check `required` (strict), merge queue unless `--no-merge-queue` | always empty |
   | `factory-default-branch-review` | pull request: 1 approval, code-owner review, dismiss stale reviews, last-push approval | empty, or with the flag exactly one entry |

   ```json
   {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}
   ```

   Repository admins may merge a PR without an approving review. The bypass covers only the review rule: the required check, the deletion and force-push protection, and the merge queue still block everyone, admins included. `pull_request` mode means the bypass applies only on pull requests, so direct pushes to `master` stay blocked. GitHub's REST docs list `pull_request` as a `bypass_mode` but do not document that `actor_id` 5 is the admin role. On apply, bootstrap reads both rulesets back as the admin running it. It fails unless `factory-default-branch` reports `current_user_can_bypass` `never`, and `factory-default-branch-review` reports `pull_requests_only` with the flag or `never` without it.

   This is narrower than the first version of this ADR, which put the bypass on a single ruleset holding every rule. That let an admin merge a PR whose `required` check was red. Splitting the review rule out keeps Q6's "as narrow as possible".

2. `--allow-self-review` (`-AllowSelfReview`). The `production` environment keeps Qunfong as its sole required reviewer, with `prevent_self_review: false`.

What stays in force:

- factory-bot (the App) is never a bypass actor. Every agent PR still needs Qunfong's normal approval.
- Without the flags, both rulesets have empty `bypass_actors` and `prevent_self_review` is `true`.
- No deletion, no force push, the required check and the merge queue apply to everyone, with or without the flag. Code-owner review applies to everyone who is not bypassing.

## Consequences

- A bypassed merge skips only the review. The PR still needs a green `required` check, so a red PR cannot merge. GitHub shows the bypass on the PR.
- Every bypassed merge and every self-approved production deploy gets a line under "Bypass log" in `collab/STATUS.md`: the PR or run, and the reason.

## Revert trigger

Revert as soon as a second person can review: a second maintainer, or a reviewer with write access who can approve PRs and production deploys. Rerun bootstrap `--apply` without the two flags. The PUT of `factory-default-branch-review` replaces its `bypass_actors` with an empty list, the environment PUT sets `prevent_self_review` back to `true`, and the read-back then expects `never` on both rulesets. Mark this ADR superseded at the same time.
