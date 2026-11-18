# Brief 001: Lean skills per role

## Goal
Each agent gets only the skills its charter lists, loaded per run. No globally installed skill packs. We measure whether each skill earns its place.

## Why
Bloat comes from whole plugins (all descriptions loaded, overlapping instructions), from router skills like `poteto-mode` whose playbooks duplicate the factory's own orchestration, and from text that restates what a linter or test can enforce. Target: 2 always-on skills plus 1–2 on-demand skills per agent.

## Decisions (already made, do not reopen without a question)
1. Remove the `plugins` / `plugin_marketplaces` inputs (pstack) from all factory workflows. pstack stays available to humans in interactive Claude Code sessions only.
2. Skill sources live in the repo:
   - own skills: `factory/skills/<name>/SKILL.md` (Cowork writes the text; drafts are already there)
   - third-party skills: `factory/skills/vendor/<name>/` via `tools/vendor_skills.sh`, pinned in `factory/skills.lock.yaml`
3. Selected third-party skills to vendor (each pinned to a reviewed commit): from pstack `architect`, `blast-radius`, `create-verification-skill`; from ponytail `ponytail`. Nothing else.
4. Per-role set (charters must list exactly these, by name plus content hash):

   | Role | Always | On trigger |
   | --- | --- | --- |
   | builder | ponytail, meter-conventions | verify-meter, blast-radius |
   | tester | test-behaviour, meter-test-conventions | verify-meter |
   | spec-writer | architect | — |
   | review / verifier | none (prompt + `tools/review.py`) | — |

5. `verify-meter` is generated once, interactively, by a human or Claude Code with pstack `create-verification-skill`, then committed to `factory/skills/verify-meter/`. Cowork reviews the text.

## What to build
1. `tools/load_skills.py <role>`: read the role's charter, empty `.claude/skills/` in the run workspace, copy only the listed skills there, verify each content hash, and fail on any unknown or unpinned skill. For the Codex tester, make the same skills available in the way Codex loads them, or inline them into the prompt via `tools/build_prompt.py`. Pick the simplest option that works and note it in STATUS.
2. Update the charters' `skills:` blocks to the table above. Update `skills.lock.yaml`: remove the pstack plugin entry and add the vendored skills.
3. Call `load_skills.py` in `10-spec.yml` and `30-build.yml` before each agent step.
4. `tools/skill_eval.py`: run golden tasks from `factory/golden/<id>/` locally and headless in three setups (A: no skills, B: always-on set, C: always-on plus on-demand). Per run, record pass/fail (`mvn verify` plus the task's acceptance test), tokens, turns, wall time and diff size (lines). Write a CSV to `factory/golden/results/`. Start with the one sample task in `factory/golden/G001/`. Cowork will add more.
5. Add a lint rule instead of a skill wherever an instruction is mechanically checkable (for example: no `System.out`, no field injection with `@Autowired`). Start with Checkstyle or ArchUnit, whichever is simpler; keep it to the rules listed in `meter-conventions` under "enforced by tooling".

## Acceptance criteria
- No workflow installs a plugin; `grep -r "plugins:" .github/workflows` is empty.
- A builder run's `.claude/skills/` contains exactly ponytail, meter-conventions, verify-meter and blast-radius; a test proves `load_skills.py` rejects a skill missing from the lock or with a wrong hash.
- `python tools/skill_eval.py --task G001 --setups A,B` runs locally on Windows and writes a CSV.
- STATUS.md records the token count of the always-on skill descriptions per role.

## Open points (answer in QUESTIONS.md if you hit them)
- Whether Claude Code in CI picks up `.claude/skills/` from the workspace without the plugin mechanism. Verify, do not assume.
- Exact Codex mechanism for skills.
