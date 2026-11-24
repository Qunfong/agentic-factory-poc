# ADR-0019: Work-item PRs merge themselves once `required` passes; spec and design PRs do not

- **Status:** Proposed (Claude Code, 2026-11-24, from Qun's explicit answer "ook de merge zelf
  automatisch"). Needs one manual ruleset change by Qun before it actually merges anything - see
  below.
- **Date:** 2026-11-24
- **Decision makers:** @Qunfong
- **Confidence:** medium - the mechanism is implemented and policy-checked, but unexercised; the
  ruleset bypass actor it depends on has not been added yet

## Decision

55-merge.yml, triggered the same way as 50-review (`workflow_run` off `40 verify`, re-reading
`required`'s own job conclusion, never the raw run conclusion - the same bug class as the
50-review fix, PR #25), auto-merges a PR once: `required` is `success`, and the PR carries the
`agent` label (a builder/work-item PR, never a spec or design PR). If the branch is `BEHIND`
master it calls the branch-update API instead of merging - the exact failure mode hit live on PR
#27, where a human had to notice and fix it by hand. The merge itself runs through a new `merge`
job in `publish.yml`, the one place `check_workflow_policy.py` lets a workflow push or write a PR
(`push_and_pr_only_in_publish`); 55-merge.yml only ever calls it, never `gh pr merge` directly.

**Scope, on purpose:** only work-item (`agent`-labelled) PRs auto-merge. The spec PR stays the
*plan gate* and the design PR (ADR-0018) stays the *idea sign-off* - both are judgment calls a
required check cannot make, unlike a work item, which `required` (build, static, scope) already
verifies mechanically. If this scope is wrong, say so; it was this session's own interpretation of
"ook de merge zelf automatisch" in the middle of an unattended run, not a separate confirmation.

## The one step this cannot do for itself

`factory-default-branch-review`'s only bypass actor today is the `Admin` repository role - a
human. The factory-bot App is a different actor than the PR's own author (so the self-review rule
is not what blocks it), but nothing grants *it* permission to merge without a formal approval
either. Adding that bypass requires editing branch-protection rules directly, which Claude Code's
own safety classifier refuses to do on its own initiative ("Undermining Oversight") - correctly:
loosening who may bypass required review is exactly the kind of change that should be a visible,
reviewable decision, not something an agent does quietly mid-run. Qun runs this once, by hand:

```
gh api repos/Qunfong/agentic-factory-poc/rulesets/27561999 -X PUT \
  -F name="factory-default-branch-review" -F target="branch" -F enforcement="active" \
  -f 'conditions[ref_name][include][]=~DEFAULT_BRANCH' \
  -f 'bypass_actors[][actor_id]=5' -f 'bypass_actors[][actor_type]=RepositoryRole' -f 'bypass_actors[][bypass_mode]=pull_request' \
  -f 'bypass_actors[][actor_id]=5709140' -f 'bypass_actors[][actor_type]=Integration' -f 'bypass_actors[][bypass_mode]=pull_request' \
  -f 'rules[][type]=pull_request' \
  -F 'rules[][parameters][required_approving_review_count]=1' \
  -F 'rules[][parameters][require_code_owner_review]=true' \
  -F 'rules[][parameters][require_last_push_approval]=true' \
  -F 'rules[][parameters][dismiss_stale_reviews_on_push]=true' \
  -F 'rules[][parameters][required_review_thread_resolution]=false' \
  -F 'rules[][parameters][allowed_merge_methods][]=squash'
```

`5709140` is `FACTORY_APP_ID` (the factory-bot App); `5` is the existing `Admin` bypass, kept as-is.
Until this runs, 55-merge.yml's own merge step will fail with the same "review required" block Qun
saw on PR #27 - visibly, in the Actions log, never silently.

## Alternatives considered

- **Drop `required_approving_review_count` to 0 instead of adding a bypass actor.** Rejected: that
  would also let a *person* merge without any review, which is a bigger change than "the bot may
  merge a mechanically-verified work item" and was not asked for.
- **Use Qun's personal token/credentials for the merge call.** Rejected without being asked:
  spends a human's identity on an unattended path: the factory-bot App, which already authors
  these PRs (publish.yml), is the right actor to also close them.

## Consequences

Until the ruleset change above is applied, nothing behaves differently - 55-merge.yml will exist
but every merge attempt fails at the same point PR #27 did, loudly. After it is applied, a
work-item PR that passes `required` needs no human click. `collab/STATUS.md` keeps logging the
auto-merge events the same way it already logs admin-bypass merges, so the audit trail does not
go quiet.

## Revisit when

The first work-item PR actually auto-merges after the ruleset change - confirm it did not need a
second push to un-stick a BEHIND branch, and that squash + delete-branch behaves the same via the
App token as it did via Qun's own admin-bypass clicks.
