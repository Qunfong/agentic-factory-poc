# Brief 020: DeepSeek on Azure replaces Gemini as a reviewer family

Qun's decision (2026-11-13): replace Gemini with DeepSeek. Reasons, from the runs so far: the free Gemini key keeps hitting its daily quota (50-review #213/#216/#217 and the first three-family run on #29), and only flash models are usable on it (Q22). DeepSeek runs on the same Azure AI Services resource as gpt-5 and Grok: one key, one bill, no free-tier quota. Do it now; it is the fix for the incomplete reviews. ADR-0016 (Cowork) supersedes the Gemini parts of ADR-0003 and ADR-0015 once it is built.

## Decisions
1. **Reviewer families:** OpenAI (`azure/gpt-5`), xAI (`grok-4.7`) and DeepSeek. None is the author's family (Claude), so the 2-of-3 rule of ADR-0015 is unchanged.
2. **Which DeepSeek model.** Qun deployed `DeepSeek-V4.1-Flash-1017` (2026-11-13); use it. Original guidance, kept for later changes: List what `ai-services-qun` can deploy (`az cognitiveservices account list-models`, filter DeepSeek) and pick the newest **stable** DeepSeek chat model, not a preview. Prefer a non-reasoning (V-series) model over an R-series reasoning model: Grok already reasons slowly (239 s per call), and a fast, different style of reviewer adds more than a second slow one. If only a reasoning model is available, take it and set its `timeout_s` from one measured call. Deploy GlobalStandard, upgrade option `NoAutoUpgrade`, and record name, version and capacity in STATUS. Qun approved the pay-per-token cost of this one deployment.
3. **Endpoint and key:** the same Azure AI v1 endpoint (`AZURE_AI_V1_ENDPOINT`) and key (`AZURE_OPENAI_API_KEY`) as Grok. No new secret.
4. **Merge/dedupe model:** `azure/gpt-5` instead of Gemini, with the existing limits: it may only group, partition check, and mechanical grouping as the fallback when it is unavailable.
5. **Gemini removed** from `models.yaml`, the review job's env and the presence check. Remove the `GEMINI_API_KEY` secret only after the first green three-family run without Gemini; log it in STATUS. README and bootstrap drop the optional Gemini key.
6. **Red tier keeps `needs-human-review` for now.** It was added to compensate for the flash reviewer (Q22). Whether to drop it with three stronger families is Qun's decision after brief 015's measurements, not part of this brief.
7. **Data:** the model is hosted by Microsoft in the Azure region of the resource. Requests go to Azure, not to DeepSeek's own API. Never call `api.deepseek.com`.

## What to build
- `factory/models.yaml`: a `deepseek` family (`openai/<deployment>` via the v1 endpoint, own `timeout_s`); amber and red reviewers `[openai, xai, deepseek]`; `merge_model: openai`.
- 50-review: drop the Gemini env and the presence check; keep everything else.
- Tests: the family table without Gemini; DeepSeek 429 or timeout → that reviewer is `infra-failure`, and the review still completes with 2.
- One live smoke call, then a rerun of 50-review on spec PR #29: this is brief 018's acceptance, with all 3 reviewers answering.

## Acceptance criteria
- 50-review on #29 is complete with 3 of 3 reviewers. The reviewer table shows the exact DeepSeek model and its latency.
- No `gemini` left in workflows, models or tools (grep), except history in ADRs and STATUS.
- Policy check 0 violations; no control loosened.
