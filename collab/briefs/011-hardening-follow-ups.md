# Brief 011: Hardening follow-ups (Q13–Q36)

Written by Cowork (2026-11-11). Collects the small hardening items decided in ANSWERS Q13–Q36. Every item tightens a control; none relaxes one.

Branch `brief-011`, stacked on the latest of 003/008/009. Suggested: items 1, 2, 5 and 6 before the fresh-repo snapshot, because they close public-repo gaps; the rest can follow. The work order itself stays Qun's.

## What to build
1. **Risk map (Q17).** In `factory/risk-map.yaml` (Cowork approves this edit by Claude Code):
   - add `{pattern: "tools/**", tier: red, owner: security-owner}`, `{pattern: ".claude/**", tier: red, owner: security-owner}`, `{pattern: "AGENTS.md", tier: red, owner: security-owner}`, `{pattern: "CLAUDE.md", tier: red, owner: security-owner}`;
   - header comment: `# The highest tier over all matching rules wins (tools/check_tier.py); the code adds a red floor for tools/, .github/, factory/, .claude/, AGENTS.md and CLAUDE.md.`
   - Extend the code floor to `.claude/`, `AGENTS.md`, `CLAUDE.md`. Reason: `**/*.md` scores AGENTS.md green today, yet it steers every agent.
2. **Branch regex (Q15).** `^wi-([1-9][0-9]*)$` everywhere it is parsed (45, 50, publish, scope). Reason: `wi-7` and `wi-007` must not both map to issue 7.
3. **shellcheck pin (Q13).** Download a pinned shellcheck release with a sha256 check and put it on PATH before actionlint, like actionlint itself.
4. **gitleaks in CI (Q29).** Replace `gitleaks/gitleaks-action@v2` with the pinned image `zricethezav/gitleaks:v8.24.0@sha256:2bcceac45179b3a91bff11a824d0fb952585b429e54fc928728b1d4d5c3e5176`, scanning the PR's commit range including `collab/`.
5. **Authorize 45 and 25 (Q27, option b).** 45-fix-round runs `authorize.py` on `workflow_run.triggering_actor` before dispatching. 25-dispatch only dispatches work items whose ready label was last applied by the factory bot or a maintain/admin collaborator (read the issue's label events). A `write` collaborator must not reach model spend indirectly. Extend the policy rule so `workflow_dispatch` senders of `30 build` are covered.
6. **Egress block for the app under test (Q26).** In 40-verify, before the app starts as `nobody`: `iptables -A OUTPUT -m owner --uid-owner nobody ! -o lo -j REJECT` (and the ip6tables equivalent). Prove it in CI with a negative probe: `sudo -u nobody curl -sS --max-time 5 https://example.com` must fail, and the job fails if it succeeds. A future app that needs egress gets an explicit allow list via a protected change, never by removing the rule.
7. **Hash-pinned Python deps (Q21).** `tools/requirements.txt` and `tools/requirements-review.txt` generated with `pip-compile --generate-hashes` (all transitive deps), installed with `pip install --require-hashes`. Add a policy rule: every `pip install` in workflows uses `--require-hashes -r`.
8. **Trusted tools (Q19, Q20).** Confirm `run_record.py` runs from the `github.workflow_sha` copy and the policy rule rejects running `tools/` from the agent's tree or `cp tools/` in any post-agent job. If brief 009 already does both, just note it in STATUS.
9. **Bootstrap clean-up (Q34, Q36).** Drop `OPENAI_TESTER_MODEL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`; set `AZURE_OPENAI_ENDPOINT`; list `GEMINI_API_KEY` as optional. Create labels up front: `needs-human-review`, `infra-failure`, `factory:builder-failed`, with descriptions.
10. **Stubbed `--apply` test (Q32).** A test runs bootstrap `--apply` with a fake `gh` first on PATH, `GH_TOKEN`/`GITHUB_TOKEN` unset and `GH_HOST` set to an unroutable host, and asserts the exact call sequence, plan check and read-back. The test fails if the real `gh` is ever resolved.
11. **Dedupe prompt (Q35).** Move `DEDUPE_PROMPT` verbatim to `factory/prompts/dedupe.md`, loaded by `review.py`. Add a mechanical check: the returned groups must be a partition of all finding indices (each exactly once); otherwise treat it as `infra-failure`. Reason: the merge model may group, never drop.

## Acceptance criteria
- `check_tier.py`: `AGENTS.md`, `.claude/settings.json` and `tools/x.py` score red; `README.md` stays green.
- Policy check fails on fixtures for: unhashed `pip install`, gitleaks action by tag, 45 without authorize; passes on the real workflows.
- The egress probe step is red when the iptables rule is removed (shown once on a scratch branch).
- `review.py` unit test: a dedupe answer that omits an index yields `infra-failure`.
- Stubbed `--apply` test passes on Linux and Windows.
