# Brief 013: tester without transcript in logs (LiteLLM-driven)

Starts **after brief 012 is green**. Qun's decision on Q28/Q37 (2026-11-12): option (c).

## Goal
The tester's transcript must never appear in Actions logs, because those are public once the repo flips (ANSWERS Q2 point 3). Replace codex-action for the tester by a small LiteLLM-driven tool loop on Azure `gpt-5` that writes nothing from the model to stdout/stderr.

## Decisions
1. Model: Azure `gpt-5` via LiteLLM (pinned, hash-installed, same as 50-review). Family stays OpenAI, so the Q1/Q22 mapping is unchanged.
2. Minimal tool set, matching `factory/charters/tester.yaml`: `read_file`, `list_files`, `write_file` (only new files under `app/src/test/**`), `run_mvn` (fixed argument allow-list, e.g. `-q test-compile`, `-q test -Dtest=...`). No shell, no network tool, no git.
3. Path rules are enforced in the tool code (reject `..`, links, anything outside the allowed globs) **and** again by the existing publish guard. The tool loop is not trusted to replace the guard.
4. Logs: only step names, tool names, counts, exit codes and the final result line. Model text, tool arguments and file contents go to a run-record artifact (retention ≤ 7 days, existing rule), never to the log.
5. Same limits as the charter (max turns, max minutes). 429/503/timeout after backoff → `infra-failure`, never a pass.
6. The tester job keeps the brief 009 rules: authorize first, no acceptance-repo checkout, no secrets in env except the one model key the loop needs. That last part is a change from codex-action's key proxy, so the job must not run any untrusted code before the loop: `run_mvn` runs in a child process with the key **removed** from its environment.
7. Skills: the tester's always-on skill bodies are inlined into the system prompt, as now (brief 010).

## What to build
- `tools/tester_loop.py` (+ tests): tool loop, path checks, env scrub for `run_mvn`, quiet logging.
- Replace codex-action in the tester job; keep prepare → agent → publish.
- Policy rule: the tester job does not use codex-action, and no step in an agent job prints model output (extend the "quiet transcripts" rule).

## Acceptance criteria
- Unit tests: path escapes, a write outside `app/src/test/**`, a disallowed mvn argument, and a key leak into the `run_mvn` env are all rejected.
- One live run on the 012 test issue: tests land on `wi-<n>`, the job log has no model text (grep the downloaded log for a canary string the prompt asks the model to repeat).
- Policy check 0 violations; no control loosened.
