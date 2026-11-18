# Brief 002: Context hygiene (start after 001 is merged)

Source of the ideas: github.com/ranxianglei/billion-context, reviewed by Cowork. Do not install it. It is a local proxy for month-long sessions. Our runs are short-lived, so we take only these ideas.

## Goal
Lower cost per run and keep the context the agents receive small, ordered and traceable.

## What to build
1. **Stable prompt prefix (prompt-cache friendly).** `tools/build_prompt.py` emits a fixed order: charter → skills → AGENTS.md → spec → work item → round feedback. The stable parts come first and the variable parts last. No timestamps or run IDs in the prefix.
2. **Record cache usage.** `tools/run_record.py` stores the input, cached-input and output tokens per agent step, taken from the CLI or API usage output. `skill_eval.py` adds the cache hit rate to its CSV.
3. **Handoff summary.** Each agent step writes `run/<role>-summary.md`: decisions, files touched, open questions, at most 300 words. The next agent gets the summaries, not the previous transcript. Fix rounds (45) get the reviewer findings plus the builder summary.
4. **Searchable run history (later, only if needed).** If the summaries grow beyond a few per work item, add `tools/search_runs.py <keyword>` over `run/*-summary.md`, exposed to the agent as an allowed command. No embeddings and no vector DB.

## Acceptance criteria
- Two consecutive builder runs on the same work item share a byte-identical prompt prefix up to the work-item section. A test proves this.
- The run record for every agent step has the fields `tokens_in`, `tokens_cached` and `tokens_out`.
- `30-build` passes `tester-summary.md` to the builder. The builder prompt contains no raw tester transcript.

## Out of scope
Proxies, certificate interception, auto-updating tools, and turning off the agents' built-in compaction.
