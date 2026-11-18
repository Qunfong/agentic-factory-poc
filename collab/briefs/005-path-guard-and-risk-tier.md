# Brief 005: Path guard and risk-tier hardening

Drafted by Claude Code at Qun's request (2026-11-11), from the high-severity items in the design review. Cowork: please review.

Runs after 004, because it reuses 004's `publish` job.

## Goal
An agent can't get a forbidden change past the guard or the tier check, either by committing it, renaming it, editing the guard itself, or relying on rule order.

## What to build
1. **Base SHA.** Each agent workflow records `BASE_SHA` before the agent step runs.
2. **Trusted guard copy.** Guards and tier checks run from a copy taken from the base commit (`git show $BASE_SHA:tools/check_paths.py > $RUNNER_TEMP/...`), never from the agent's working tree. This applies to `check_paths.py`, `check_tier.py` and `run_record.py`.
3. **`check_paths.py` diff.** It diffs against `BASE_SHA` with `git diff --name-status -M $BASE_SHA` plus untracked files and files the agent force-added despite .gitignore. Rules:
   - Check both the old and new side of every rename.
   - Fail on any status other than A or M, including D, T, C and unmerged.
   - Fail if HEAD moved during the agent step.
   - Fail on symlinks.
4. **Matching.** Explicit, case-sensitive glob matching where `**` crosses `/` and `*` doesn't. Write a small helper rather than use fnmatch, and give it its own unit tests.
5. **Spec-writer allow list.** In `10-spec.yml`, narrow the spec writer's allow list to the charter: `docs/specs/F<n>/**` and `docs/adr/proposed-*.md`.
6. **Tier.** `check_tier.py` takes the **highest** tier over all matching rules. `risk-map.yaml` gets `tools/** → red`. That file is under factory/, so Cowork or Qun edits it, or approves my edit in ANSWERS.
7. **Agent permissions.** `.claude/settings.json`: remove `Bash(python3 tools/*)` for factory agents and allow only read-only tools by explicit name.

## Acceptance criteria
- `tools/tests/test_check_paths.py` (pytest, runs on Windows and Linux) fails the guard for each of these:
  - a committed forbidden edit
  - a rename from an allowed path to a forbidden one
  - an `MM` or `T` status
  - a deleted file
  - an edit to `tools/check_paths.py` itself
  - a case-variant path (`Factory/x`)
  - `../` traversal
  - a symlink
- `tools/tests/test_check_tier.py`: `factory/prompts/x.md` scores red and `README.md` scores green.
- The phase-2 local dry run shows the guard blocking a forbidden edit.
