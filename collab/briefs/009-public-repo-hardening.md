# Brief 009: Public-repo hardening (before Qun flips visibility)

Drafted by Claude Code (2026-11-11), from ANSWERS Q2. It is a separate brief from 008 because it changes workflows and history checks, not bootstrap alone.

## Goal
Once the repo is public, an outsider can't:
- spend model budget
- reach a secret
- read hidden acceptance content
- learn client names

Qun flips visibility only after this brief is merged and the full-history gitleaks scan (item 4) passes.

## Observed (2026-11-11)
- Actions are enabled on the private repo and already run:
  - `40 verify` on PRs #1 and #2
  - `45 fix round` and `50 review` through `workflow_run`
  - `25 dispatch` on its cron schedule
- None of these runs did harm. `45 fix round` exited with "not an agent branch".
- Every commit so far is authored as `QunWang <qunfong@live.nl>`. That email becomes public with the history (open point 1).

## What to build
1. **Fork PRs.**
   - bootstrap `--apply` sets "Require approval for all outside collaborators" for fork PR workflows (`PUT repos/{o}/{r}/actions/permissions/fork-pr-contributor-approval`, `approval_policy: all_external_contributors`).
   - No `pull_request_target` anywhere, enforced by `tools/check_workflow_policy.py`.
   - `workflow_run` consumers (45, 50) act only when the head repo is this repo (brief 006).
2. **Who can start an agent.**
   - Agent workflows start only from a label, `workflow_dispatch`, or a push or PR by factory-bot or a maintainer.
   - Each such job's first step is an `authorize` step. It passes when the actor is the App's bot login, or when `gh api repos/{repo}/collaborators/{actor}/permission` returns `maintain` or `admin`. Otherwise it fails the job before any model call.
   - Issues and comments from anyone else are ignored.
   - `check_workflow_policy.py` asserts that every job using claude-code-action or codex-action `needs:` an authorize job.
3. **Public logs.**
   - Verify prints AC IDs and pass/fail only, never scenario names, bodies or stack traces from `acceptance/`. Surefire output for acceptance goes to a file that is not uploaded.
   - Agent transcripts don't go to stdout. claude-code-action runs with its log or verbose output off, if the action supports that (verify against its `action.yml`).
   - Run records and transcripts are artifacts with `retention-days: 7`.
4. **History and names.**
   - Run gitleaks over the full history of every branch (`gitleaks git --log-opts="--all"`), and grep for a deny-list of client names that Qun supplies locally.
   - Make both a CI step in 40-verify (PR diff) and a one-off script `tools/prepublish_check.sh`/`.ps1` that Qun runs before the flip. The deny-list lives outside the repo (local file path argument or repo secret), so it doesn't name the clients itself.
5. **`SECURITY.md`.** A private vulnerability-reporting route (GitHub private advisories). bootstrap leaves Discussions off.

## Acceptance criteria
- `tools/check_workflow_policy.py` fails on:
  - a fixture with `pull_request_target`
  - an agent job without an authorize dependency
  - an artifact without `retention-days`
- It passes on the real workflows.
- The authorize step rejects a `read` collaborator and an outsider, and accepts `maintain`, `admin` and the bot login. A unit test covers its decision table.
- `tools/prepublish_check` exits 0 on the current history and 1 on a fixture branch with a fake key or a deny-listed name.
- A verify log from a run with a failing scenario contains the AC ID and FAIL, and no scenario text.

## Open points
0. **Decided (ANSWERS Q7+Q9).** There will be no history rewrite. After 004–007 and 009 merge into `master`, this repo is archived and a fresh private repo is created from a single snapshot commit authored with Qun's noreply email. The pre-publish scan runs there before Qun flips visibility. Points 1 and 3 below are therefore settled by the snapshot.
1. The commit email `qunfong@live.nl` is in all history. Keep it, or rewrite the author to the GitHub noreply address before the flip? A rewrite changes every SHA and needs force-pushes to `master`, `phase-0` and `collab-setup`. That's Qun's call (QUESTIONS Q7).
2. Gitleaks runs from the Docker image `zricethezav/gitleaks:v8.24.0@sha256:2bcceac45179b3a91bff11a824d0fb952585b429e54fc928728b1d4d5c3e5176` (Qun's choice, Q8). In CI, pin the same version.
3. **First scan (2026-11-11), 15 commits across all refs.**
   - Gitleaks found no leaks.
   - The client-name check failed. A client name appears in `collab/ANSWERS.md:24` (since `f3cc944`) and in an earlier version of this brief. Both are pushed to the private remote and are in the history of every collab and brief branch. Removing them needs a history rewrite before the flip (QUESTIONS Q9).
