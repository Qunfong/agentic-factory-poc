# Brief 014: own `minimal-change` skill replaces vendored ponytail

Qun's decision (2026-11-12): do not vendor ponytail as a whole; keep only what is relevant to the CI builder, as our own skill. Small; may be done inside brief 012 (it replaces the temporary removal of ponytail there).

## Why
Ponytail is written for interactive sessions: levels, slash commands, "active until the user says stop", replies to a human, and "leave one small test", which the builder may not do (Q11). Those parts cost tokens and conflict with the charter. The useful core is the "smallest complete change" discipline.

## What to build
1. New skill `factory/skills/minimal-change/` with the `SKILL.md` below, verbatim, plus `NOTICE` holding the ponytail MIT licence text (copy `factory/skills/vendor/ponytail/LICENSE`), because the text is adapted from it.
2. `factory/charters/builder.yaml`: `always:` gets `minimal-change` (hash from `load_skills.py`), not ponytail.
3. Remove `factory/skills/vendor/ponytail/`, the `ponytail` source and skill from `factory/skills.lock.yaml`, and ponytail from `vendor_skills.sh`.
4. Q48 name check: add `ponytail` to the retired names, so no skill can reference it.
5. Report the builder's always-on token estimate in STATUS (it was 1098 with ponytail).

## Acceptance criteria
- `load_skills.py --check` 0 problems; policy 0 violations; tests green.
- No `ponytail` left in charters, lock or prompts (grep), except the NOTICE attribution.
- The `pstack` source stays `reviewed: pending`; it is interactive-only (`create-verification-skill`) and never loaded in CI, so it does not block anything.

## SKILL.md (verbatim)

```markdown
---
name: minimal-change
description: The smallest complete change that makes the work item's tests pass. Always on for the builder.
---

# Minimal change

Solve the whole work item with the least new code. Be lazy about the solution, never about completeness.

## Before you edit
Read the work item, the spec, the tester's tests and the code they touch. List every place the change must reach: callers, wiring, config, mappers, error paths. That list is the scope. Features nobody asked for are not.

## Pick the first option that fully works
1. Already in this codebase (helper, service, pattern)? Use it the way the surrounding code does.
2. Java standard library or a Spring feature the project already uses? Use it.
3. A dependency already in `app/pom.xml`? Use it. A new dependency is a protected change: request it, never work around it.
4. Otherwise: the minimum code that works and that a reader understands at a glance.

## Rules
- Finish every part the tests and acceptance criteria need. A shorter diff that misses a caller or an edge case is not smaller, it is broken.
- No abstraction, interface, option, config property or "for later" code the work item does not need. Keep the existing layers, packages and conventions.
- Bug fix: find every caller of the code you touch, then fix the root cause once, in the shared code.
- Code you move keeps its validation and error handling.
- Between options of equal size, take the one that is correct on edge cases (null, empty, boundaries, concurrency the code already has).
- Comment only the why the code cannot show, in one line. A known shortcut gets `// shortcut: <limit>, <when to upgrade>`.
- Never cut: input validation at trust boundaries, error handling that prevents data loss, security checks, anything the work item or spec asks for.

## Tests
The tester owns all tests. You do not add, change or delete test files. If you believe a check is missing, name it in your summary.

## Summary
End with at most two lines: what you deliberately left out or did not verify, and any risk a reviewer must know.
```
