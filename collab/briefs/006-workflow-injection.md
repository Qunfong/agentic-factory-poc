# Brief 006: Workflow script injection

Drafted by Claude Code at Qun's request (2026-11-11), from the high-severity items in the design review. Cowork: please review.

Small. It can go in parallel with 005 because it touches different lines.

## Goal
No text from an event someone else controls (issue title or body, branch name, PR title, comment) is pasted directly into a `run:` script. A fork can't start a fix round.

## What to build
1. **Sweep every `${{ github.event.* }}` and `${{ github.head_ref }}` used inside `run:`.** Move each into `env:` and quote it in the script. Known cases:
   - `10-spec.yml:71`: the issue title.
   - `45-fix-round.yml:19`: `workflow_run.head_branch`.
2. **Fix-round guard.** `45-fix-round.yml` requires `github.event.workflow_run.head_repository.full_name == github.repository`. It parses the issue number from the branch with a strict `^wi-([0-9]+)$` and fails on anything else.
3. **Gate check.** `10-spec.yml` checks the gate role with `grep -Fxq`.
4. **CI lint.** Add `actionlint`, pinned, as a step in 40-verify so this can't creep back in.

## Acceptance criteria
- `actionlint` passes on all workflows.
- `grep -nE 'run:.*\$\{\{ *github\.(event|head_ref)' .github/workflows/*.yml` and a multi-line equivalent find nothing.
