# ADR-0011: Model secrets live in a `master`-only environment

- **Status:** Accepted (@Qunfong, ANSWERS Q50, 2026-11-12); applied on the snapshot repo
- **Date:** 2026-11-12
- **Decision makers:** @Qunfong
- **Confidence:** not stated

## Decision

**`CLAUDE_CODE_OAUTH_TOKEN`, `GEMINI_API_KEY` and `AZURE_OPENAI_API_KEY` move to the environment `factory-models`.** Its deployment-branch policy allows only `master`, and it has no required reviewers. Agent jobs declare `environment: factory-models`. A policy rule enforces it: every job that references a model secret declares that environment.

## Context

A collaborator with write access could push a branch that carries its own `on: push` workflow and read repo-level secrets (Q50).

## Candidates

### A. Environment with a `master`-only branch policy (chosen)
### B. Keep zero write collaborators, with nothing enforced

## Consequences

- No extra clicks per run.
- A workflow on any other branch gets no model keys.
- Bootstrap creates the environment.

## Re-evaluation Triggers

- Model calls move behind a gateway with a key per run (README "POC shortcuts").
