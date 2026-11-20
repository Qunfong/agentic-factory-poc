# ADR-0005: Path guard from the base commit, and a risk tier with a red floor

- **Status:** Proposed (brief 005, 011; ANSWERS Q17, Q18; implemented, not merged)
- **Date:** 2026-11-11
- **Decision makers:** Cowork; to be accepted by @Qunfong
- **Confidence:** not stated

## Decision

**`publish` diffs the agent's patch against an explicit base and accepts only added or modified files inside the role's charter globs.** Links, `..` and case tricks are rejected. Deletions and renames always need a protected-change request. Each PR gets a risk tier, the maximum over the rules in `factory/risk-map.yaml` that match its files. A **red floor** applies to `tools/`, `.github/`, `factory/`, `.claude/`, `AGENTS.md` and `CLAUDE.md`, because those steer the factory itself.

## Context

A guard that trusts the agent's own git state can be fooled. `**/*.md` scored `AGENTS.md` green, yet that file steers every agent (Q17).

## Consequences

- The guard stays simple and provable. Refactoring work items that delete files are slower (Q18). This is accepted for the POC.
- The tier drives the review: green and amber get one AI review; red gets two families and a human (ADR-0003).
- **One narrow, trusted exception, not a guard change** (2026-11-19, own incident on F7 WI-1): the tester may write a compile-time stub under `app/src/test/**` at the exact path the builder's real class will later occupy; Maven puts test-classes ahead of classes on the classpath, so a stub left behind silently shadows the real implementation (a 404 at runtime, not a build failure). `tools/publish.py`'s `remove_shadowed_stubs()` deletes exactly that file, as a trusted mechanical step *after* the builder's own guarded patch is validated - never by widening what the guard accepts from the agent, and never touching a file without the exact `// factory-test-stub` first line. `check_paths.py` itself is unchanged.

## Re-evaluation Triggers

- Deletions or renames block real work items often.
