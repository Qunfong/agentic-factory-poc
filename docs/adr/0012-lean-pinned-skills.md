# ADR-0012: Each agent loads only its charter's skills, pinned by hash; own skills before vendored ones

- **Status:** Proposed (briefs 001, 010, 014; ANSWERS Q39, Q43, Q44, Q48); 014 decided by @Qunfong (2026-11-12)
- **Date:** 2026-11-12
- **Decision makers:** Cowork; brief 014 by @Qunfong
- **Confidence:** not stated

## Decision

**Skills are listed per role in `factory/charters/*.yaml` and pinned by directory sha256 in `factory/skills.lock.yaml`. No workflow installs a plugin.**
- "Always" skills are inlined into the prompt. `.claude/skills/` holds only on-trigger skills.
- Third-party sources are refused until they are `reviewed: yes`.
- `load_skills.py --check` fails when a skill references a skill by name that the same role doesn't load.
- Ponytail is **not** vendored. Its relevant rules became our own `minimal-change` skill (brief 014).

## Context

Large plugin bundles cost tokens on every run, and they put unreviewed third-party text into agent prompts. Ponytail also conflicted with the charter: it asks the builder to write tests.

## Consequences

- Runs fail closed while any skill they load is unreviewed. Since brief 014 the builder loads only own skills (`minimal-change`, on trigger `impact-check`), so it is no longer blocked by a pending third-party pin. Builder always-on estimate (chars/4): 1097 → 825 (STATUS, 2026-11-12).
- The builder prompt names `minimal-change`; `ponytail` is a retired name in the `--check` reference check (Q57).
- `create-verification-skill` (pstack) is for interactive use only and is never loaded in CI.

## Re-evaluation Triggers

- The skill eval (brief 001, setup B vs C) shows that an on-trigger skill adds no value: drop it.
