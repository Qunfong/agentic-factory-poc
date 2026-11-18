# Brief 010: Skill fixes after brief 001

Written by Cowork (2026-11-11), answering Q39–Q43 and Q45. Apply on branch `brief-001` (or `brief-010` stacked on it); it amends brief 001 decision 4.

## Goal
Every skill a factory agent loads can actually fire in CI, has no dangling references, and "always" means the body is in context.

## Decisions
1. **Drop vendored `architect` and `blast-radius` from all charters** (Q39). Both are `disable-model-invocation: true` and point to unvendored files (`how`, `why`, `arena`, `unslop`, harness doc). They cost tokens and never run. Replace them with two own skills (text below). Delete `factory/skills/vendor/architect/` and `factory/skills/vendor/blast-radius/` and their lock entries. Keep `create-verification-skill` vendored for interactive use only (brief 001 decision 5); no charter lists it.
2. **"Always" = inlined into the prompt for every role** (Q43). `tools/build_prompt.py` inlines always-on bodies for Claude roles too, as it already does for the Codex tester. `.claude/skills/` holds only on-trigger skills. Reason: deterministic context, and the A/B eval then measures what we think it measures.
3. **`verify-meter` leaves the CI charters** (Q42, option b). The builder's tools are `Bash(mvn:*)` only; widening them is not worth it, because 40-verify already starts the real app and runs the hidden scenarios from a trusted job. verify-meter stays in the repo for interactive use only; eval setup C does not include it (ANSWERS Q46).
4. **Tester without ponytail is intended** (Q45). Ponytail is about minimal production change; the tester writes new tests only.

## New per-role table (replaces brief 001 decision 4)

| Role | Always (inlined) | On trigger (`.claude/skills/`) |
| --- | --- | --- |
| builder | ponytail, meter-conventions | impact-check |
| tester | test-behaviour, meter-test-conventions | — |
| spec-writer | spec-shape | — |
| review / verifier | none | — |

## Text changes (Cowork's files; apply verbatim, then recompute hashes in charters and `skills.lock.yaml`)

### `factory/prompts/builder.md`, line 2 (Q40)
Replace the `poteto-mode` line with:
> Work in ponytail mode (full): the smallest complete change. Prove it works with `mvn -B -f app/pom.xml verify`, fix root causes rather than symptoms, and stay inside the work item's paths. If your change touches a public signature, a JSON field, configuration or code shared across capability packages, use the impact-check skill before you report done.

### `factory/prompts/spec-writer.md` (Q23, Q39)
- Line 3: `Input: the feature issue below (PRD and acceptance criteria numbered AC-1, AC-2, ...).`
- Step 1: `Read AGENTS.md, docs/adr/index.md and the code the feature touches. Follow the spec-shape rules below before writing.`
- Add after step 2: `AC IDs in spec.md and work-items.json are AC-F<issue>-<n>, keeping the issue's number n (AC-3 in issue 12 becomes AC-F12-3). Never renumber, merge or split an AC; if one is unclear, list it under Open questions.`
- In the work-items example, `"ac_ids": ["AC-F<issue>-1"]`.

### `factory/skills/meter-conventions/SKILL.md` (Q41)
`- No \`System.out\` / \`printStackTrace\` (ArchUnit, \`ArchitectureTest\`).`

### `.github/ISSUE_TEMPLATE/feature.yml` (Q23, Claude Code edits this one)
Description: `One per line, numbered from 1, e.g. "AC-1: a negative reading is rejected with 400". The spec writer turns AC-1 into AC-F<issue>-1; hidden scenarios are tagged with that full ID.`

### New `factory/skills/spec-shape/SKILL.md`
```markdown
---
name: spec-shape
description: Use when writing spec.md, plan.md and work-items.json for a feature of the meter service. Settles data shapes and interfaces before any code exists.
---

# Spec shape

1. Ground. Name the capability packages the feature touches and read their controller, service and model. Read the ADRs for those packages. If nothing exists yet, say "greenfield".
2. Sketch the shape in spec.md as Java signatures, not prose: request/response `record`s, service method signatures, repository methods, error cases as `ProblemDetail` type + status. Bodies are `// not implemented`.
3. Check the sketch against these rules and fix it before writing anything else:
   - money and energy are `BigDecimal`, time is `Instant` (UTC);
   - validation happens at the boundary;
   - retried writes are idempotent; say what the idempotency key is;
   - no new top-level technical packages.
4. One AC maps to exactly one work item. A work item is a vertical slice (HTTP to storage) that can merge alone; list its `paths` as narrowly as you can, because the guard enforces them.
5. Write an ADR proposal only for a real choice between alternatives that a later change would have to undo. Not for following an existing ADR.
6. Red flags; stop and list under Open questions: an AC that needs a business rule the issue does not give; a shape that needs `app/pom.xml` or a migration (that is a protected change); two ACs that contradict.
```

### New `factory/skills/impact-check/SKILL.md`
```markdown
---
name: impact-check
description: Use before reporting done when your change alters a public method signature, a request/response record, a JSON field, a configuration key, or code used by more than one capability package.
---

# Impact check

Find what your change can break outside the diff, and prove the one fact it is safe because of.

1. List what changed beyond the lines: public signatures, serialized JSON (field names, nullability, number format), HTTP status codes, configuration keys, behaviour on retry.
2. Find the users. Search for callers of each changed symbol and for the JSON field names in tests and docs. A search that finds nothing is an answer; write it down.
3. Name the one fact the change is safe because of (for example "no caller relies on the old field name"). Point at the `file:line` that shows it.
4. Prove it by running code: `mvn -B -f app/pom.xml verify` with an existing test that exercises that path. You may not add or edit tests; if no test covers it, write "unproven" and say which test is missing.
5. In the run summary, under "Impact": the fact, its proof or "unproven", and each remaining risk with its `file:line`.
```

## What to build
1. Apply the text changes above; update charters, `skills.lock.yaml` (own skills by content hash), `load_skills.py` and `build_prompt.py` for decision 2.
2. Remove the vendored skills from decision 1 and their lock entries.
3. `skill_eval.py`: setup B = always-on inlined; setup C = B plus exactly the role's on-trigger skills from its charter, in `.claude/skills/`, with the CI tool set. No verify-meter (amended by ANSWERS Q46).

## Acceptance criteria
- `load_skills.py --check` passes; a builder run's `.claude/skills/` contains exactly `impact-check`; the spec-writer's and tester's are empty.
- The built builder prompt contains the ponytail and meter-conventions bodies; the built spec-writer prompt contains spec-shape.
- `grep -rn "poteto\|pstack" factory/prompts factory/charters` is empty.
- No loaded skill references a file that is not in its own folder.
- STATUS records the new always-on token counts per role.
