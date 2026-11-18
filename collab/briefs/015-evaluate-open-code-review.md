# Brief 015: evaluate Open Code Review as the review engine (spike, later)

Starts only **after the first green end-to-end factory run** (brief 012), when 50-review has run for real. It is an evaluation, not an adoption. Source: Qun shared github.com/alibaba/open-code-review (Apache-2.0) on 2026-11-12.

## Why
Our `tools/review.py` sends one diff (cut at 120k characters) in one prompt per reviewer. That has the weaknesses OCR's README names for prompt-only reviewers: incomplete coverage on large diffs, line numbers that drift, and quality that varies with small prompt changes. OCR adds deterministic steps around an agent: it decides which files get reviewed, bundles related files into isolated sub-agents, matches rules per file, and runs separate modules that check and correct each comment's location and content. It speaks OpenAI-compatible and Anthropic protocols, including `openai-responses`.

Vendor claims, **not verified by us**: higher precision and F1 than Claude Code on the same model, about 1/9 of the tokens, lower recall. The benchmark is their own (AACR-Bench).

## Decisions (fixed for the spike)
1. OCR may only replace the **reviewer** step. Cross-family verification, the dedupe-only merge model, `needs-human-review` on red, and `infra-failure` on provider errors all stay in `review.py` (ADR-0003). OCR's findings become input to that pipeline; OCR does not post to the PR itself.
2. Models stay as they are: Gemini `gemini-3.6-flash` as reviewer (through Gemini's OpenAI-compatible endpoint, or LiteLLM in front) and Azure `gpt-5` as verifier. No new provider.
3. Run the CLI binary from a GitHub release, pinned by sha256, with telemetry off. Do not use the npm package or the marketplace action (supply chain, ADR-0009). Run it with the agent's tools read-only, and confirm from the source that it has no shell or write tool.
4. Treat the PR content as untrusted, as now: OCR reads it with a model key in the environment. Run it in a job with no other secrets.

## What to do
- Collect 10–20 real PRs from this repo, including at least one diff over 120k characters, one red-tier PR and one with a known seeded defect.
- Run both reviewers with the same models: today's `review.py` (A) and OCR as reviewer + our verifier (B). Record per PR: findings, true/false positives (Qun or Cowork labels them), seeded defects found, location correct yes/no, tokens, wall time.
- Write the result to `docs/review/<date>-ocr-evaluation.md`, with numbers only from these runs.

## Acceptance criteria
- A table A vs B per PR and in total. No number in it that was not measured here.
- A recommendation: adopt B for the reviewer step, borrow specific ideas only, or drop it. If B is adopted, Cowork writes the ADR and Qun decides.

## Not in scope
- The `delegate` mode (it reviews with the coding agent's own model; that breaks the cross-family rule).
- OCR's GitHub Action posting comments directly.
