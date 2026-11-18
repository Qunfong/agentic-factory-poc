# Brief 018: three reviewer families, 2-of-3 consensus

Qun's direction (2026-11-12): review with three models and keep only the feedback the models agree on most. Qun added a Grok deployment on the existing Azure resource. **Qun (2026-11-12): add and implement now**, right after the #16 run (PR #25 merged). Brief 015 measures it later. This changes ADR-0003, so Cowork writes ADR-0015 when it is built.

## Why
- Today amber gets one reviewer (Gemini flash) and red gets two. One reviewer is noisy, and the Q22 interim relies on a flash model.
- A third family that is not the author's (Claude) was missing. Grok (xAI) on Azure fills it, so the three reviewers are Gemini, OpenAI and xAI, and none of them is the builder's family.
- Outside practice: K-LLM review uses 4-of-6 = strong; Mozilla.ai Star Chamber uses a configurable threshold of 2; the Entelligence benchmark keeps comments found by at least 2 of 3 models. Caveats: agreement can be a shared blind spot, and LLM judges flip 7–17% of verdicts on identical reruns. So consensus decides how prominent a finding is, never the merge.

## Decisions
1. **Reviewers, every tier that gets AI review:** `gemini/gemini-3.6-flash`, Azure `gpt-5` and Azure `grok-4.7`. They run independently, with the same prompt and the same diff, and none sees another's output.
2. **Same finding** = same file, line ranges within 3 lines of each other, same category (the existing rule in `review.py`). The merge model may only group findings, never drop them (Q22, Q35).
3. **Strong** = reported by ≥ 2 of 3 families. Shown first, as "Agreed by N models".
4. **Single-source** findings are not dropped silently. A model of a different family checks each one, as the verifier does today. Confirmed → kept, marked "1 model + verified". Rejected → listed in a collapsed "Low confidence" section with the reason.
5. **Red tier** still always gets `needs-human-review`. Any reviewer that fails after backoff → `infra-failure` for that reviewer. If fewer than 2 reviewers answered, the review counts as incomplete and the PR gets `needs-human-review`. Never a pass.
6. **Advisory only**, as now: consensus never blocks or approves a merge.
7. **Grok setup:** deployment `grok-4.7` on `ai-services-qun`, OpenAI-compatible v1 endpoint (`https://ai-services-qun.services.ai.azure.com/openai/v1`). Set the deployment's upgrade option to `NoAutoUpgrade` and record model and version in STATUS. Grok uses the resource key in `AZURE_OPENAI_API_KEY` (Qun regenerates it, see ANSWERS), and the new variable `AZURE_AI_V1_ENDPOINT` = `https://ai-services-qun.services.ai.azure.com/openai/v1`. No separate secret. **Never** take a key from chat or from a file in the repo.

## Visibility (Qun, 2026-11-12: "how do I see what the reviewers did?")
Today the PR comment shows only family names, counts, and the kept findings. Rejected findings appear only as a number, and the run record (7-day artifact) has no per-finding data. Add to the same PR comment:
- **A reviewer table**, one row per reviewer: exact model ID (e.g. `gemini/gemini-3.6-flash`, `azure/gpt-5`, `azure/grok-4.7`), result (ok / infra-failure / no key), findings raised, tokens in/out, seconds. Plus one row for each verifier call.
- **A section per finding** with agreement (`2/3: gemini, grok`), the verifier's verdict and a one-line reason.
- **A collapsed "Rejected / low confidence" section** (`<details>`) listing every finding not kept, with who raised it and why it was rejected. Nothing is only a count.
- **The run record** holds the same per-reviewer and per-finding data (no diff text, no secrets). The comment links the run.
- All of it is about the PR's own diff, which is public anyway. Never include acceptance-repo content.

## Provider outages (Qun, 2026-11-13: "why does it fail if Gemini is down, we still have two models")
Seen: 50-review #213/#216/#217 failed with `infra-failure: RateLimitError after 4 attempts`, and the log didn't say which provider (almost certainly the free Gemini key's daily quota). Today one failing call aborts the whole review, because (a) amber has only one reviewer, Gemini, and (b) `review.py` raises `InfraFailure` out of the whole run, and (c) the merge/dedupe model is also Gemini. Rules:
1. **Name the failing model in every error**, e.g. `infra-failure: RateLimitError from gemini/gemini-3.6-flash after 4 attempts`. The run record holds the same.
2. **Isolate failures per call.** A reviewer that fails after backoff is marked `infra-failure` in the reviewer table; the others continue. The review counts as complete with ≥ 2 answering reviewers; with < 2 it is incomplete → `needs-human-review` + `infra-failure` label, never a pass (decision 5).
3. **No single provider in the merge step.** If the merge model is unavailable, group mechanically (same file, lines within 3, same category) and say so in the comment. The merge model only ever groups, so mechanical grouping is a safe fallback.
4. **Verifier = any available family** other than the finding's source(s). If none is available, the finding stays as "unverified", visible, never dropped.
5. Test: Gemini 429 on every call → the review still completes with gpt-5 + Grok, the comment shows Gemini as infra-failure, and the mechanical grouping note is present.

## What to build
- `factory/models.yaml`: an `xai` family (`azure/grok-4.7` or the v1 endpoint via LiteLLM's OpenAI-compatible provider), and reviewers `[gemini, openai, xai]` for amber and red.
- `review.py`: run three reviewers, group findings, compute agreement, verify single-source findings with another family, and render sections Strong / Verified / Low confidence. Add the agreement counts to the run record.
- Tests: 3/3, 2/3, 1/3 confirmed, 1/3 rejected, one reviewer down, two reviewers down.
- A one-word live smoke call to Grok (key from env, never printed) before the first CI run.

## Acceptance criteria
- On a real PR the comment shows the three sections and per-finding agreement. The run record lists each reviewer's model and outcome.
- Brief 015's evaluation includes this setup (A: today, B: 3-family consensus, C: Open Code Review as one of the reviewers, if it is adopted).
- Policy check 0 violations; no control loosened.
