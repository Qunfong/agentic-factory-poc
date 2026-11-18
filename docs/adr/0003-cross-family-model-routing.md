# ADR-0003: Cross-family model routing, with fail-closed reviews

- **Status:** Proposed (Cowork, ANSWERS Q1, Q22, Q35; implemented in brief 003 and 011, merged `a63864a`). The review rows (reviewer, verifier, red reviewers, merge) are **Superseded** by [ADR-0015](0015-three-family-review-consensus.md); the spec writer, builder and tester rows still apply.
- **Date:** 2026-11-11
- **Decision makers:** Cowork (design session); to be accepted by @Qunfong
- **Confidence:** not stated

## Decision

**Every check is done by a different model family from the one whose work it checks.** Claude writes specs and code, Azure OpenAI `gpt-5` writes tests and verifies, and Gemini `gemini-3.6-flash` reviews. A review that can't run ends as `infra-failure` or `needs-human-review`, never as a pass.

| Role | Model | Path |
| --- | --- | --- |
| spec writer, builder | Claude | claude-code-action, `CLAUDE_CODE_OAUTH_TOKEN` |
| tester | Azure `gpt-5` (pinned, `NoAutoUpgrade`) | codex-action today; LiteLLM loop after ADR-0010 |
| reviewer, amber | Gemini `gemini-3.6-flash` | LiteLLM |
| verifier, amber | Azure `gpt-5` | LiteLLM |
| reviewers, red | Gemini flash + Azure `gpt-5`, each verifying the other's single-source findings; **always** `needs-human-review` | LiteLLM |
| merge/dedupe | Gemini flash, may only group duplicates (a partition check enforces it) | LiteLLM |

## Context

The subscription token works only inside claude-code-action, so Claude can't do raw API reviews. Only one Azure deployment exists (`gpt-5`). On the free AI Studio key, no stable Gemini pro model is usable (STATUS, 2026-11-11: `gemini-2.5-pro` 404, `gemini-3.1-pro-preview` 429).

## Candidates

### A. Gemini pro as reviewer (the original Q1 mapping)
- Not available without billing, and the only pro model is a preview. Rejected for now (Qun: no billing, Q22).

### B. Flash reviewer, plus mandatory human review on red (chosen)
- Weaker reviewer, compensated by an added control on the riskiest PRs.

### C. Every red PR to a human, with no AI review
- Considered in Q22 (option c). Kept as an addition to B, not used on its own.

## Consequences

- `gpt-5` is both the tester and a verifier. This is accepted for the POC and listed in the README risk table.
- 429, 503 and timeouts are retried with backoff, then reported as `infra-failure`.
- Models are pinned by exact name: no aliases (`gemini-3.5-flash`) and no `-preview` models.

## Re-evaluation Triggers

- A stable Gemini pro model is listed for this key, or billing is enabled: drop the mandatory human review on red.
- A second Azure deployment or model family becomes available: split the tester from the verifier.
