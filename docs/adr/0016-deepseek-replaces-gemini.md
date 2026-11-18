# ADR-0016: DeepSeek on Azure replaces Gemini as a reviewer family; gpt-5 groups findings

- **Status:** Accepted (@Qunfong, 2026-11-13: "replace Gemini with DeepSeek"; brief 020). Built on `brief-020` (`bf6adaf`), not merged or proven yet. Supersedes the Gemini rows of [ADR-0015](0015-three-family-review-consensus.md) (reviewers, merge model).
- **Date:** 2026-11-13
- **Decision makers:** @Qunfong
- **Confidence:** not stated

## Decision

Amber and red are reviewed by Azure `gpt-5` (OpenAI), Azure `grok-4.7` (xAI) and Azure `DeepSeek-V4.1-Flash-1017` (DeepSeek). All three run on the same Azure AI Services resource with one key (`AZURE_OPENAI_API_KEY`); Grok and DeepSeek use the v1 endpoint (`AZURE_AI_V1_ENDPOINT`). Requests go to Azure only, never to `api.deepseek.com`. `gpt-5` becomes the merge model, with the same limits as before: it may only group, a partition check enforces it, and mechanical grouping is the fallback. Everything else in ADR-0015 is unchanged: 2 of 3 = strong, single-source findings verified by another family, at least 2 answering reviewers or `infra-failure`, red always `needs-human-review`.

| Role | Model |
| --- | --- |
| reviewers, amber and red | `azure/gpt-5`, `openai/grok-4.7`, `openai/DeepSeek-V4.1-Flash-1017` (Azure v1 endpoint) |
| verifier of a single-source finding | any answering family other than the finding's source |
| merge/dedupe | `azure/gpt-5`, may only group; mechanical grouping when it is unavailable |
| red tier | always `needs-human-review` until Qun decides otherwise after brief 015 |

DeepSeek deployment (from `factory/models.yaml` on `brief-020`): version `2026-10-17`, GlobalStandard, capacity 20 (20 requests and 20k tokens per minute), `NoAutoUpgrade`, call timeout 180 s.

## Context

The free Gemini key hit its daily quota repeatedly: 50-review #213/#216/#217 failed, and the first three-family run on spec PR #29 (43366402472) got 1 of 3 answers (STATUS, brief 018). Only flash models were usable on that key (Q22). Qun chose DeepSeek and deployed it himself on the resource that already hosts `gpt-5` and Grok. One measured call on #29's diff took 2.2 s (8042 tokens in, 7 out, no findings).

## Consequences

- No free-tier quota in the review path; one bill, one key.
- **All three reviewers share one Azure resource and key.** A resource outage or a revoked key takes out all three: the review ends as `infra-failure` with `needs-human-review`, never a pass. Family diversity remains (three model vendors), provider diversity is gone.
- **DeepSeek is a Preview model in the Azure catalog** (Qun's choice). This is an exception to ADR-0003's "no preview models", recorded in `models.yaml`. Preview models can change or be withdrawn; `NoAutoUpgrade` limits the first, not the second.
- **20k tokens per minute** is less than the largest diff `review.py` sends (120k characters ≈ 30k tokens). Large diffs will rate-limit DeepSeek; it then counts as `infra-failure` for that reviewer and the review completes with 2, visibly.
- One fast "no findings" answer does not yet show that DeepSeek reviews well; brief 015's evaluation and a planted-defect check (ANSWERS) measure that.
- The policy check now treats every secret except `GITHUB_TOKEN`, `ACCEPTANCE_REPO_TOKEN` and `FACTORY_APP_PRIVATE_KEY` as a model key (`741f195`), so `GEMINI_API_KEY` stays behind the authorize gate until it is deleted after the first green run without Gemini.

## Re-evaluation Triggers

- DeepSeek reports nothing on a diff with a known defect, or brief 015 shows it adds no confirmed findings.
- The DeepSeek model leaves Preview, is withdrawn, or a GA DeepSeek model appears on the resource.
- DeepSeek rate-limits on normal PRs (raise capacity, Qun's decision).
- A second provider becomes available, to restore provider diversity.
