# Cowork review plan (maintained by Cowork; Claude Code commits it when it next commits, best effort; a stale plan shows as a hash mismatch against `.cowork-seen`)
Role: review after the fact, answer in ANSWERS.md, never edit code/workflows/tools, never run git write commands. Findings: ANSWERS.md "Audit round N". Qun-only actions: "Waiting for Qun".
Token-frugal: a scheduled run first compares hashes (`collab/.cowork-seen`); if QUESTIONS.md, STATUS.md and `git log -1` are unchanged it stops without reading anything else.

## Audit passes (tick when done; findings go in ANSWERS.md)
- [x] Round 1: 60-release, commit c8dbee5, grep over workflows/tools (R1-R6)
- [x] Round 2 (2026-11-17, findings in ANSWERS 'Audit round 2'): `publish.yml` + `tools/publish.py` (single write path, ADR-0004), `check_paths.py`, `check_tier.py`
- [x] Round 3 (2026-11-17 late, findings in ANSWERS 'Audit round 3'): `30-build`, `45-fix-round`, `25-dispatch`: sandbox/egress, token scope, fix-round limit 2, WIP limit, idempotency, durability (resume after crash)
- [x] Round 4 (2026-11-17 night, findings in ANSWERS 'Audit round 4'): `40-verify` + `acceptance_scope/run`: fail-closed, hidden scenarios invisible, AC IDs only, tests that cannot fail
- [x] Round 5 (2026-11-17, ANSWERS "Audit round 5"): `50-review` + `review.py` + `factory/models.yaml`, `gateway/`: prompt injection, truncation, three-family consensus, rate-limit path, key scoping, kill switch (5 min)
- [x] Round 6 (2026-11-17, ANSWERS "Audit round 6"): `check_workflow_policy.py` rule coverage vs ADRs 0002-0016; policy rules that can be bypassed
- [x] Round 7 (2026-11-17, ANSWERS "Audit round 7"): charters + prompts vs architecture (scope, denied paths, model tier, limits, owner); Agent registry pins
- [x] Round 8 (2026-11-17, ANSWERS "Audit round 8"): skills in `factory/skills/*` (own text: lean, no overlap with prompts, references resolve, lock hashes) and `skills.lock.yaml`/`vendor/` (`reviewed: pending` must stay refused); interactive-only skills in HANDOFF are Claude Code's, not agents'
- [x] Round 9 (2026-11-17, ANSWERS "Audit round 9"): architecture gaps: telemetry/run records completeness, dead letters + reconciliation sweep, data-class labels, golden set (G001 only), cost per accepted change metric, separation of duties (R4)
- [x] Re-verification 2026-11-18 done (brief 013 / PR #45, #42 merge; ANSWERS 'Re-verification run 2026-11-18' and 'run 2', round 10). R2 A1 and P1 closed; brief 019 = not built
- [ ] Next re-verification: brief 013 A1 PR CI run (symlink tests green on ubuntu), A2 `del os.environ`, round 4 B1/B2 PR, brief 019 start
- [ ] Each cycle: answer new numbered items in QUESTIONS.md (open: Q8; others per STATUS "Waiting for Qun"), review the newest merged PR/brief, record "proven vs not proven" in ANSWERS

## Next runs (after the nine rounds)
Re-verify each B item against code/CI as Claude Code's PRs merge (start with #42: round 2 A1, P1); re-audit only what changed (git diff since the hash in `.cowork-seen`). Order of fixes is in ANSWERS 'Cowork status after round 9'.

## When Claude Code answers a finding
Verify against the code (not the STATUS text): tick R-item as closed only with evidence (commit, test, CI run). Otherwise reopen with the missing evidence.

## Usage limit
At about 90% of the usage limit: write the remaining unticked items to `collab/COWORK-TODO.md` (short list, with the next concrete step each) and stop.

## Setup review and next tasks (Cowork, 2026-11-17; from collab/ docs, STATUS, ANSWERS, workflows 60 and the 40-verify diff; code passes still to do)
Method: pstack principles prove-it-works (a task is done on a re-runnable check, not on STATUS text), sequence-verifiable-units (one brief = one PR = one proof), boundary-discipline (guards at the boundaries: publish, authorize, gateways), blast-radius (name the one fact a change is safe because of, run it). Goldfish rule from google/elephant-goldfish-model (Apache-2.0): reviewers get a fresh context and see only the artefact, not the author's reasoning. Our scheduled Cowork runs are goldfish by construction; keep them that way (no hand-off of chat context, only collab/ files).

### Order of work (each step ends in a check someone can re-run)
1. **Close audit R1, R2, R4** (Claude Code). Proof: diff + one CI run; R1 needs the Bypass-log row.
2. **Brief 020 acceptance**: planted-defect check on DeepSeek, then rerun 50-review on #29 with 3 of 3 reviewers answering. Proof: run id in STATUS. Needs Qun first: DeepSeek capacity (20k tokens/min) and Grok variant.
3. **Brief 019 (PR feedback loop)**: no STATUS row seen. Verify state (merged? proven?).
4. **Parallel verifiers + 35 min wall-clock budget** (agreed in ANSWERS) as its own brief/PR.
5. **Release gate**: token that can read the production environment, separation of duties enforced (R4), a real deploy step. Proof: production job green with a reviewer, red without.
6. **Snapshot and public flip** (fresh private repo, pre-publish scan, new App key, `claude setup-token`): state unclear in STATUS; confirm. Qun-only steps stay in "Waiting for Qun".
7. **Architecture gaps, in this order**: kill switch proven (stop all runs within 5 min), golden set beyond G001 and an evaluation run per factory-config change (P10), reconciliation sweep + dead-letter handling (only a cron dispatch exists), telemetry/dashboard (build-order step 8), data-class labels in prompts and traces.
8. **Done when** (architecture): a green and an amber work item each go from intent to release without manual workarounds, with a verified run record per agent run. Today: one amber item reached staging (#25); production never ran green.

### Goldfish idea for the spec stage (proposal for a later brief, not now)
Add a zero-context readiness check on spec/plan PRs: a fresh reviewer gets only spec.md + plan.md + work-items.json and answers (1) can it restate the goal and ACs, (2) what is unclear or contradicts an ADR, (3) could an agent implement each work item without inventing details. Build it as text inside our own `spec-shape`/review prompt; do not vendor the EGM plugin (ADR-0009: pinned, reviewed, lean skills).

### What we need
- Qun: decisions in "Waiting for Qun" (DeepSeek capacity, Grok variant, snapshot steps, close #16, label on #22); delete the `.pem` in Downloads; keep the Claude desktop app open and the computer awake for the scheduled Cowork task.
- Claude Code: running in this repo with `/loop 30m check collab`.
- Nothing to download or install.

## Parked by Qun (2026-11-17)
All "Waiting for Qun" items are parked for now: do not remind, do not block on them, do not re-list them in new answers. Work on what is unblocked (audit rounds, R1/R2/R4, parallel verifiers, brief 019 check). Where a step needs a parked decision, use the documented default (for example DeepSeek rate limits: review completes with 2 of 3, named in the reviewer table) and say "parked" in one line.
