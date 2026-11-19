# ADR-0010: The tester runs as a LiteLLM tool loop that writes no transcript to logs

- **Status:** Accepted, built and proven (@Qunfong, ANSWERS Q28/Q37, 2026-11-12; brief 013 merged 2026-11-18, PR #45). `30-build.yml`'s tester step runs `tools/tester_loop.py`; no `codex-action`, no transcript in the log. AC3 proven live on [run 44493440107](https://github.com/Qunfong/agentic-factory-poc/actions/runs/44493440107) (2026-11-19): a canary string the prompt asked the model to repeat appears 3 times in the run-record transcript artifact and 0 times in the public job log; the tester wrote a real, correct test for AC-F16-1 (8 turns, 7 tool calls, 2 `mvn` runs, committed to `wi-2`). The first attempt ([run 44342754745](https://github.com/Qunfong/agentic-factory-poc/actions/runs/44342754745), 2026-11-18) hit an infra bug (see Consequences), itself proof the quiet design holds under a real failure too, not only the happy path.
- **Date:** 2026-11-12
- **Decision makers:** @Qunfong
- **Confidence:** not stated

## Decision

**codex-action is replaced for the tester by `tools/tester_loop.py`.** It is a minimal LiteLLM loop on Azure `gpt-5` with four tools: read, list, write under `app/src/test/**`, and allow-listed `mvn`. Only step names, counts and exit codes reach the log. The transcript goes to a run-record artifact kept for at most 7 days. `mvn` runs with the model key removed from its environment.

## Context

codex-action prints the tester's transcript, and Actions logs are public once the repo flips (ADR-0008). This conflicts with ANSWERS Q2 point 3.

## Candidates

### A. Accept the transcript in the logs, with two policy conditions
- Cowork's recommendation. Not chosen.

### B. Run `codex exec` ourselves, with output to a file
- Loses the action's key proxy and its drop of sudo. Not chosen.

### C. LiteLLM tool loop (chosen)
- No transcript in logs. It is a real build, and the loop holds the key itself, hence the scrubbed `mvn` environment.

## Consequences

- The publish guard (ADR-0005) still checks the tester's output; the loop's own path checks are an extra layer, not a replacement.
- **`read_file`/`list_files` refuse a symlink, direct or through a symlinked ancestor** (Cowork audit, A1, 2026-11-18): the tester checks out a tree it does not control, and an unchecked symlink (e.g. to `/proc/self/environ`) would let the model read this process's own environment, model key included, into the transcript it produces. Fixed in `tools/tester_loop.py`'s `resolve_contained()`, mirroring `check_paths.py`'s `filesystem_link_violations()`.
- **The model key no longer lives in this process's own `os.environ` once it's been read** (Cowork audit, A2, 2026-11-18; cheap fix Cowork suggested, applied). `tools/tester_loop.py`'s `main()` pops `AZURE_OPENAI_API_KEY` from `os.environ` right after `completion_args()` captures it into `model_args`, so a sibling process (e.g. one `run_mvn` spawns, same Linux user) can no longer find it via this process's `/proc/<pid>/environ` either - not just absent from the child's own env, as before. `30-build.yml` still has no egress block for the tester job (round 3, "sandbox/egress for 30-build/45-fix-round/25-dispatch", still open per `collab/COWORK-PLAN.md`); that stays a defence-in-depth item, not a precondition for this fix.

- **`litellm.completion()` always imports its MCP handler when `tools` is non-empty, which crashed every call** (first live run, 2026-11-18, run 44342754745): `ModuleNotFoundError: No module named 'mcp'`, since the tester loop uses plain OpenAI-style function tools, not MCP, and `mcp` isn't in `tools/requirements-review.txt`. The log showed only `tester: infra-failure: ModuleNotFoundError` - no stack trace, no model text, confirming the quiet design holds on a real failure, not just the happy path. Fixed by passing `_skip_mcp_handler=True` (a documented-in-source private kwarg litellm's `main.py` checks before the MCP import) instead of adding the `mcp` package and its transitive dependencies for a feature never used.

## Re-evaluation Triggers

- codex-action gains an option to keep its transcript out of the log.
- litellm removes or renames `_skip_mcp_handler` in a future version - re-check this fix on any litellm version bump.
