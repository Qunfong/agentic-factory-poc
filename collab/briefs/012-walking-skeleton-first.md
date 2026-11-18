# Brief 012: one green end-to-end run before anything else

## Goal
The factory has 11 stacked branches and ~11k lines of hardening, and **not one live run**: no factory run, the 40-verify CI-only steps never ran, codex-on-Azure and the litellm review path never ran in Actions. Qun reports the build pipeline doesn't work. Priority now: prove the pipeline works end to end, then continue.

## Decisions
1. **Hardening freeze.** No new controls, policy rules or hardening questions until this brief is done. Existing controls stay as they are; never weaken one to get green (standing rule). Ask questions only for real blockers.
2. **Work on the tip.** Branch `brief-012` from the tip of `brief-011` (it contains 004–011). Open one **draft** PR against `master` so CI runs on the combined code. The per-brief PRs stay open for Qun.
3. **Run in the current private repo.** Qun is the only collaborator, so the public-log concerns (Q28/Q37) do not block test runs here. Do not wait for the snapshot or the flip.
4. **Builder unblock without weakening.** The builder fails closed because ponytail is `reviewed: pending` (Q44). For this brief, remove ponytail from `factory/charters/builder.yaml` `always:` (fewer third-party skills, no control loosened). Re-add it after Qun reviews the pin. Do **not** use `--allow-pending`.
5. **Fix forward, smallest change.** Each failure: diagnose the root cause, fix on `brief-012`, one commit per cause. Do not add new hardening in passing.

## What to build / do
1. Diagnose first: list the last failed run of each workflow (`gh run list`, `gh run view --log-failed`), and record in STATUS per workflow: last run, result, first real error line (no secrets, no scenario content).
2. Get **40-verify fully green** on the draft PR, all jobs incl. `required`: shellcheck download, gitleaks container, Semgrep container + rules digest, hash-pinned installs, egress block + probes, acceptance against the example repo.
3. Prove the egress control once: a throwaway commit that removes the iptables rule must make the probe fail. Revert it; record the run URL.
4. **One factory run end to end** on a trivial test issue (e.g. "add a health detail field", one AC): spec → spec PR → breakdown → dispatch → tester (codex on Azure) → publish → builder → publish → 40-verify → 50-review → PR with green `required` and a review comment. If a workflow can only be dispatched from the default branch, say so in STATUS and ask Qun (merging is his call).
5. Record each fix and run URL in STATUS under a new "Brief 012 runs" section.

## Acceptance criteria
- Run URL of a fully green 40-verify on the draft PR.
- Run URL of the failing egress probe (negative proof) and of the green revert.
- Run URLs of one complete factory run ending in a PR with green `required` and review output from both families (or `needs-human-review` where Q22 requires it).
- A short list in STATUS: what was broken, root cause, fix commit.
- No control removed or loosened; policy check still 0 violations.

## Open points
- **Next after this brief: brief 015 (evaluate Open Code Review as the reviewer).** Qun asked not to lose it; it comes before any new hardening. Backlog order in `docs/design/factory-flow.md`.
- Whether to merge the stack as per-brief PRs or as one combined PR after this works: Qun's call (listed in ANSWERS "Waiting for Qun").

## Addendum (Cowork, 2026-11-12): known causes, before any log is read
Found by reading the repo; confirm with the run logs.
1. **Every factory run uses `master`'s workflows**, and `master` is still the initial import (`155dc19`). Labels, `workflow_dispatch`, cron and `workflow_run` all run the default branch's YAML. That YAML needs `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENAI_TESTER_MODEL`, `PSTACK_MARKETPLACE`, `ACCEPTANCE_REPO`, `ACCEPTANCE_REPO_TOKEN`, `GATE_ROLES`; none exist. So no factory run can work until the fixed workflows are on `master`. A draft PR only exercises 40-verify.
2. **Bootstrap never ran**, so `GATE_ROLES`, `WIP_LIMIT`, `ACCEPTANCE_REPO` and the labels are missing.
3. **No acceptance repo and no `ACCEPTANCE_REPO_TOKEN`.** Brief 007 makes verify fail closed on that (correct), so `required` can never be green today.

What this changes:
- Step 2 (40-verify green) needs the acceptance repo first: Claude Code creates the private repo `Qunfong/meter-acceptance` from `acceptance-repo-example/` and sets `ACCEPTANCE_REPO`; Qun creates the token (top of ANSWERS).
- Run bootstrap now **without the ruleset part** (variables, labels, repo settings only) if it supports that; if not, set those variables and labels by hand with `gh` and record them in STATUS. Rulesets still wait for the flip.
- Step 4 (factory run) needs the workflows on `master`. That means merging the per-brief PRs (Qun's decision: per brief). So: get 40-verify green on the 012 draft PR, fold the fixes back into their brief branches, then Qun merges 004 → … → 011 in order, then run the factory end to end on `master`.
- Do not stop the cron of `25 dispatch` on `master` by weakening anything; it fails harmlessly. If it spams failed runs, disabling that workflow (`gh workflow disable`) until the merge is fine and reversible; note it in STATUS.
4. **50-review fails on every PR whose 40-verify passes** (Qun, 2026-11-12). Cause, read from `master`: `workflow_run` always runs the default branch's YAML and tools. `master`'s `tools/review.py` exits with "models.yaml: pin a real model for gemini/frontier" because `master`'s `factory/models.yaml` still holds `<pin: …>` placeholders, and it also expects `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`. The fix (brief 003: pinned `gemini-3.6-flash`/`azure/gpt-5`, authorize job, new secrets) lives on the branches. **It cannot be fixed or proven on a draft PR; 45-fix-round has the same problem.** Both are proven only after the merge, in the first factory run. Do not patch `master` directly.
   - Meanwhile the failures are noise: on `master` the review is advisory and no merge depends on it. Disabling 50 and 45 until the merge is Qun's call (see ANSWERS "Waiting for Qun").
