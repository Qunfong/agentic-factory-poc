# ADR-0015: Three reviewer families with 2-of-3 consensus, isolated per provider

- **Status:** Accepted (@Qunfong, 2026-11-12: "add and implement"; built as #31 `5513515` and #33 `4fa4505`). Supersedes the review rows of [ADR-0003](0003-cross-family-model-routing.md). The Gemini rows (reviewer, merge model) are **Superseded** by [ADR-0016](0016-deepseek-replaces-gemini.md); the consensus, verification and failure rules still apply.
- **Date:** 2026-11-13
- **Decision makers:** @Qunfong
- **Confidence:** not stated

## Decision

Every tier that gets AI review (amber and red) is reviewed independently by three families that are not the author's: Gemini `gemini-3.6-flash`, Azure `gpt-5` and Azure `grok-4.7` (xAI). A finding reported by at least 2 of 3 is **strong**. A single-source finding is checked by another answering family: confirmed findings are kept, rejected ones are listed with the reason in a collapsed section. Consensus is advisory: it never blocks or approves a merge.

A failing provider affects only its own reviewer. The review is complete with at least 2 answering reviewers; with fewer it gets `needs-human-review` and `infra-failure`, never a pass. Every error names the model. If the merge model is down, findings are grouped mechanically (same file, lines within 3, same category). Each family has its own call timeout in `factory/models.yaml` (`timeout_s`, default 180 s; merged as #34 `4d6018f`, not yet proven on a real review).

| Role | Model |
| --- | --- |
| reviewers, amber and red | `gemini/gemini-3.6-flash`, `azure/gpt-5`, `openai/grok-4.7` (Azure v1 endpoint) |
| verifier of a single-source finding | any answering family other than the finding's source |
| merge/dedupe | Gemini flash, may only group; mechanical grouping when it is unavailable |
| red tier | always `needs-human-review` (unchanged from ADR-0003) |

## Context

ADR-0003 gave amber one flash reviewer and red two. One reviewer is noisy, and a third non-author family was missing. Qun deployed `grok-4.7` on the existing Azure resource, so a third family came without a new provider (brief 018). Then 50-review #213/#216/#217 failed as a whole on one rate limit with no model named, because one exception aborted the run and the merge model was the same provider (ANSWERS, 2026-11-13). A Grok review of PR #29's 28 KB diff took 239 s, past the default 180 s timeout (`fix-reviewer-timeouts`).

## Consequences

- Grok and `gpt-5` share the Azure resource and its key: one Azure outage takes out two reviewers, and the review then is incomplete (`needs-human-review`), not passed.
- `gpt-5` is still both tester and a reviewer (ADR-0003 consequence, unchanged).
- The PR comment shows a reviewer table, per-finding agreement and every rejected finding; the run record holds the same data, without diff text.
- Agreement can be a shared blind spot, and LLM verdicts vary between reruns. That is why consensus only orders findings.
- The 50-review job limit rises to 45 min; a job that hits it posts nothing and fails.

## Re-evaluation Triggers

- Brief 020 (Qun, 2026-11-13) replaces Gemini with DeepSeek on the same Azure resource and makes `gpt-5` the merge model: done in [ADR-0016](0016-deepseek-replaces-gemini.md).

- Brief 015's evaluation (today vs. three-family consensus vs. Open Code Review) shows another setup finds more real issues at similar noise.
- A provider other than Azure becomes available for one of the two Azure families.
- Gemini billing is enabled (Q22): consider a pro model and revisit mandatory human review on red.
