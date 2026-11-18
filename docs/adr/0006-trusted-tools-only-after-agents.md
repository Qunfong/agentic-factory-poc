# ADR-0006: After an agent has run, only trusted copies of factory tools execute

- **Status:** Proposed (brief 009, 011; ANSWERS Q19, Q20, Q49, Q56; implemented, not merged)
- **Date:** 2026-11-11
- **Decision makers:** Cowork; to be accepted by @Qunfong
- **Confidence:** not stated

## Decision

**Jobs that run after an agent take `tools/` from `github.workflow_sha`, never from the agent's tree.** A policy rule (`tools/check_workflow_policy.py`, run in 40-verify) rejects any other reference to `tools/` in those jobs. Inside an agent job, after the agent step, every `tools` reference is rejected, including the trusted `git show` form, because the agent can write `.git/refs/replace/`. Run records are written in their own jobs.

## Context

`Bash(mvn:*)` means the agent can run arbitrary code. Any script in its tree, or any git object it can influence, is therefore attacker-controlled.

## Consequences

- No current workflow is affected: tools already run in separate, later jobs.
- New workflows must follow the pattern, or the policy check fails `required`.

## Re-evaluation Triggers

- Factory config moves to a separate repo that agents cannot write (README "POC shortcuts").
