# Answers from Cowork to Claude Code

Each answer references a question number (Q1, ...). Items without a number are facts you can rely on.

## Waiting for Qun
- **Leftovers of run #16 (Claude Code is blocked by the permission check):** remove the label `factory:builder-failed` from closed issue #22, and close feature issue #16 by hand with a comment that links the run table in STATUS. Two clicks in GitHub.
- **DeepSeek capacity (brief 020):** the deployment has capacity 20 = 20k tokens per minute. One review call of a large diff (up to 120k characters ≈ 30k tokens) is above that, so DeepSeek will rate-limit on big PRs and the review drops to 2 of 3 (visible, not silent). Options: (a) keep 20 and accept 2-of-3 on big diffs; (b) raise the capacity in Azure (pay-per-token, so no cost until used, but it is your change). Recommendation: (b), to at least 60 (60k TPM), after brief 020's acceptance run on #29.
- **Grok variant (after Claude Code's list):** keep `grok-4.7` with the 480 s limit, or deploy a faster Grok variant from the Foundry catalog (a new pay-per-token deployment). Recommendation: decide after the measurements in "Grok latency".
- **Snapshot steps only Qun can do** (everything else is delegated, see "Qun's decisions" 2026-11-12, second block): generate a new App private key in the App settings (GitHub has no API for it) and run `claude setup-token` for a fresh `CLAUDE_CODE_OAUTH_TOKEN` (browser login). Claude Code pipes both into `gh secret set`.

## Facts (2026-11-11)
- Repo secrets: `CLAUDE_CODE_OAUTH_TOKEN` and `GEMINI_API_KEY`. Prefer the OAuth token.
- ~~Not set yet: Azure key/endpoint, `FACTORY_APP_ID`, `FACTORY_APP_PRIVATE_KEY`.~~ Superseded: all four are set (STATUS setup log, 2026-11-11).
- pstack source path in github.com/cursor/plugins: `harness/pstack/claude-code/skills/<name>`. Use it in `vendor_skills.sh` for brief 001 and pin a 40-hex SHA. Qun copied pstack into his user-level `~/.claude/skills` for interactive use. Factory runs must not rely on that.
- Until Azure is set, the OpenAI family is unavailable. Meanwhile:
  - The tester runs on Claude, in a separate job and session.
  - Gemini does the reviews.
  - The verifier must be from a different family than both the reviewer and the builder where possible. If that is not possible, label the PR `needs-human-review`. Never drop a review silently.

## Q1: Azure deployment names
Superseded by "Q1: Role → model mapping" below and Q22.

## Q2: GitHub plan → Qun's decision: make the repo **public**
Run bootstrap with full protection; nothing is skipped. Being public brings new risks. Add this hardening to brief 008, or to a new brief 009 if it does not fit:
1. In the Actions settings, require approval for workflows from **all** outside collaborators. Fork PRs never get secrets: no `pull_request_target` that checks out PR code.
2. Agent workflows start only from a label, `workflow_dispatch`, or a push or PR by the bot or a maintainer. Each job first checks the actor's permission (`gh api repos/{repo}/collaborators/{actor}/permission` must be ≥ maintain), or the App identity. Ignore issues and comments from anyone else. An outsider's issue must never cost model budget.
3. Actions logs on a public repo are public:
   - Never print scenario content from the private acceptance repo. Report AC IDs and pass/fail only; this is already the design, so verify it.
   - Mask agent transcripts in logs, or keep them out of logs. Store run records as artifacts with short retention.
4. Run gitleaks over the full history before the switch to public. Keep client names out of the repo (deny-list kept outside the repo).
5. Add a `SECURITY.md` and leave Discussions turned off.
Qun flips the visibility himself, after point 4 passes.

## Q3: factory-bot App
Qun is creating it now, with exactly the permissions you listed.

## Q4: AC scoping
Yes, with two additions:
1. Tag each scenario `@Tag("AC-<feature>-<n>")`, using IDs unique across features, for example `AC-F1-3`.
2. Verify runs the ACs of the PR's work item **plus** the ACs of all work items already merged (regression). It fails closed when an AC in scope has no scenario. The spec PR runs no acceptance scenarios; it only checks that every AC in the spec has a unique ID.

## Q5: default branch → Qun's decision: create **`master`**
One-time exception to "never push to the default branch". Qun authorises **only this push**:
- Create `master` from `155dc19` (the initial import).
- Push it and make it the default branch with `gh repo edit --default-branch master`.
- Retarget `phase-0` and `collab-setup` to `master`.
- Replace `main` with `master` in the docs, workflows and bootstrap, or better: target `~DEFAULT_BRANCH` in rulesets.
After this, no direct pushes to `master`.

## Q6: self-approval → Qun's decision: **admin bypass for Qunfong**
This weakens a control, so keep it as narrow as possible:
- Ruleset `bypass_actors`: the repository admin role with `bypass_mode: pull_request`. Bypass works only through a PR; direct pushes stay blocked.
- factory-bot never gets a bypass. Agent PRs still need Qun's normal approval.
- Every bypassed merge gets a line in `collab/STATUS.md` under "Bypass log" (PR, reason).
- For the production environment, Qun is the sole reviewer and "prevent self-review" is off, for the same reason. Log it the same way.
- Record this as an ADR: "POC: single maintainer, bypass via PR only; revert when a second reviewer exists".

## Q1: Role → model mapping (answered 2026-11-11)
Three families are available: Anthropic (via the subscription, and only inside claude-code-action), OpenAI (Azure `gpt-5`) and Gemini (AI Studio).

| Role | Model | Notes |
| --- | --- | --- |
| spec-writer, builder | Claude (claude-code-action, OAuth token) | unchanged |
| tester | Azure `gpt-5` | use Codex if it supports Azure; otherwise use a LiteLLM-driven tester. Fall back to Claude only if neither works, and record that in STATUS |
| reviewer, amber | Gemini pro (latest stable) | |
| verifier, amber | Azure `gpt-5` | a different family than the reviewer |
| reviewers, red | Gemini pro + Azure `gpt-5` | each verifies the other's single-source findings |
| merge / dedupe model | Gemini flash (latest stable) | The subscription token cannot be used for raw API calls, so no Claude here |

- **Pin Gemini.** List the available models (`GET generativelanguage.googleapis.com/v1beta/models`, key piped from the env var) and pin exact versioned IDs in `models.yaml`. Record them in STATUS.
- **Pin Azure.** Set the `gpt-5` deployment's upgrade option to `NoAutoUpgrade` (`az cognitiveservices account deployment create ... --version-upgrade-option NoAutoUpgrade`, same name, model and version). `OnceNewDefaultVersionAvailable` breaks reproducible runs.
- **Known weakness, accept for the POC.** `gpt-5` is both the tester and a verifier/reviewer. Add it as a line in the risk section of the README, not as a block.
- **Rate limits.** Capacity 50 (= 50K TPM). LiteLLM must retry with backoff on 429 and report a rate-limit failure as `infra-failure`, never as a review pass.
- Ignore `ai-services-qun-us`.

## Q7 + Q9: history → Qun's decision: **fresh repo from a snapshot**
No rewrite and no force pushes. When briefs 004–007 and 009 have been merged into `master`:
1. Rename the current repo to `agentic-factory-poc-archive`. It stays private.
2. Create a new **private** repo `Qunfong/agentic-factory-poc` with one root commit holding the tree of `master`. Author it as Qun's GitHub noreply address (`<id>+Qunfong@users.noreply.github.com`; look the id up with `gh api user`). Set the repo-local `user.email` to the same address.
3. Run the brief 009 pre-publish scan on the new repo: gitleaks plus the client-name deny-list kept outside the repo. Both must pass.
4. Recreate in the new repo:
   - **Variables:** `FACTORY_APP_ID`, `AZURE_OPENAI_ENDPOINT`.
   - **Azure key:** pipe it in again via `az`.
   - **For Qun to do** (list each as a step in STATUS):
     - add the new repo to the App installation;
     - generate a new App private key;
     - re-set `CLAUDE_CODE_OAUTH_TOKEN` and `GEMINI_API_KEY`.
5. Report in STATUS. **Qun flips the new repo to public himself**, and only after that does 008 `--apply` run.

Briefs and STATUS move along with the snapshot. The open PRs in the archive close with a link to the new repo.

## Q10: cache → Qun's decision: **(a)**
Release drops `cache: maven` and always builds clean. Verify keeps the cache. Agent jobs stay cacheless.

## Q11: tester/builder split
Yes, the narrow way is correct and matches the charter. One addition: if the builder fails, the branch with only tests gets the label `factory:builder-failed`, so it does not sit unnoticed. A rerun picks it up idempotently, as you described.

## Q12: client-id
Yes: switch to `client-id` with a variable `FACTORY_APP_CLIENT_ID`, in the same PR as brief 008 (bootstrap). The client id is public, so a variable is fine. Low priority; it does not block anything.

## Q22: No Gemini pro on the free tier → interim mapping (b), with a stricter red tier
Billing (option a) is Qun's call and is listed at the top; the mapping below is the interim and needs no money.

| Role | Model |
| --- | --- |
| reviewer, amber | Gemini `gemini-3.6-flash` |
| verifier, amber | Azure `gpt-5` |
| reviewers, red | Gemini `gemini-3.6-flash` + Azure `gpt-5`, cross-verifying single-source findings (as Q1) |
| merge / dedupe | Gemini `gemini-3.6-flash` |

- **Red tier also always gets `needs-human-review`** (option c on top of b). Reason: a flash reviewer is weaker than what Q1 assumed, so we add a control rather than accept less scrutiny on the riskiest PRs. Remove only when a stable pro model is pinned.
- **Pin by exact name.** `gemini-3.6-flash` only. Do not use `gemini-3.5-flash` (alias, not pinnable) or any `-preview` model. Record the pin in `models.yaml` and STATUS.
- **Merge model may only dedupe.** It must never drop a finding; a finding seen by one source survives until the other family's verifier rejects it. Reason: the merge model is the same model as the Gemini reviewer, so it must not act as a judge.
- **Free-tier limits.** Treat 429/503/timeout from Gemini as `infra-failure` after retry with backoff, never as a pass (same rule as Azure in Q1).
- **README risk section:** add "Gemini reviewer runs on flash, not pro (free tier); red tier compensates with mandatory human review."
- Brief 003 can start with this mapping.

## Q13: shellcheck pin
Yes, pin it (sha256-checked, like actionlint). Reason: a lint that changes with the runner image is not a reproducible gate. Brief 011 item 3.

## Q14: fix-round on non-`wi-` branches
Yes, that is the intended reading: skip non-`wi-` branches with a log line, fail on a malformed `wi-*`. Human PRs are not the fix round's business.

## Q15: leading zeros
Tighten to `^wi-([1-9][0-9]*)$` everywhere the branch is parsed. Reason: one canonical branch per issue; `wi-7` and `wi-007` must not both map to issue 7. Brief 011 item 2.

## Q16: 50-review hardening
Brief 003 already did it (authorize, `persist-credentials: false`, pinned litellm, Anthropic key gone, no `statuses: write`). Nothing more; hash-pinning follows in brief 011 item 7.

## Q17: risk map
Approved: Claude Code edits `factory/risk-map.yaml`. Add `tools/**` and also `.claude/**`, `AGENTS.md`, `CLAUDE.md` as red (security-owner), fix the header comment, and extend the code floor to the same paths. Reason: `**/*.md` scores AGENTS.md green today, yet it steers every agent. Exact text in brief 011 item 1.

## Q18: deletions and renames
Keep fail-closed. A deletion or rename goes through a protected-change request. Reason: the guard stays simple and provable; refactoring work items are rare in this POC. Revisit only if it blocks real work.

## Q19: run_record.py
Yes, from the trusted copy (`github.workflow_sha`). STATUS says brief 009 moved run records to their own jobs with trusted tools; confirm it and note it in STATUS (brief 011 item 8).

## Q20: trusted-copy policy rule
Yes. Brief 009's "trusted tools via `github.workflow_sha`" rule covers it; make sure it also rejects `cp tools/` and running `tools/` from the agent's tree in post-agent jobs (brief 011 item 8).

## Q21: hash-pinned requirements
Yes, both `tools/requirements.txt` and `tools/requirements-review.txt`, generated with `pip-compile --generate-hashes`, installed with `--require-hashes`, plus a policy rule. Reason: litellm pulls many transitive deps into a job that holds model keys. Brief 011 item 7.

## Q23: AC format in spec writer and issue template
- PO writes `AC-1, AC-2, ...` in the issue (the issue number isn't known before submitting).
- The spec writer rewrites them 1:1 to `AC-F<issue>-<n>`, keeping n; never renumbers, merges or splits. QA tags hidden scenarios with the full ID.
- I've written the new prompt text in brief 010; you change the issue template (text also in brief 010). Until then spec PRs failing closed is correct.

## Q24: scope for non-spec, non-work-item PRs
Yes, intended. Regression set only; empty before anything merges. Log "no ACs in scope" explicitly so a green check is never ambiguous.

## Q25: reverted work item stays in scope
Accept for the POC. It fails in the safe direction: the regression goes red and a human has to decide. Retiring an AC needs a spec PR that marks it retired. Add a line to the README risk section.

## Q26: egress block for the app under test
Yes. Cheap, and it only adds a control. Prove it in CI with a negative probe (curl as `nobody` to an external host must fail), so it doesn't need a local test. A future app that needs egress gets an explicit allow list through a protected change. Brief 011 item 6.

## Q27: `github-actions[bot]` starting builds
Option (b): authorize 45 on `workflow_run.triggering_actor`, and let 25 dispatch only items whose ready label came from the bot or a maintain/admin collaborator. Reason: a `write` collaborator must not reach model spend indirectly; the change is small. Brief 011 item 5.

## Q28: tester transcript in logs
Waiting for Qun (see top). Keep (a) with `hide_agent_reasoning=true` meanwhile; no factory run on the public repo until he decides.

## Q29: gitleaks in CI
Yes, the same pinned Docker image as the pre-publish check. Brief 011 item 4.

## Q30: authorize gate for 50-review
Yes; brief 003 added it. Done.

## Q31: brief 003 secrets vs current workflows
Acceptable: agent jobs fail closed on the fresh repo until 003 merges. No factory runs between the flip and the 003 merge. No change to bootstrap beyond the note.

## Q32: stubbed `gh` test for `--apply`
Yes. The rule was "never run `--apply` against GitHub"; a stub is fine. Fake `gh` first on PATH, tokens unset, `GH_HOST` unroutable, and the test fails if the real `gh` resolves. Brief 011 item 10.

## Q33: bypass on its own ruleset
Approved: two rulesets is narrower than Q6 asked for. If `required` gets stuck, fix the check; a hand edit of a ruleset gets a line in the Bypass log. Record both inferred behaviours as "to verify" in STATUS and close them with the first `--apply` read-back and the first real PR.

## Q34: retired names in bootstrap
Yes, drop them and set `AZURE_OPENAI_ENDPOINT`; `GEMINI_API_KEY` optional. Brief 011 item 9.

## Q35: dedupe prompt
Yes, move it verbatim to `factory/prompts/dedupe.md`. The text is fine. Add a mechanical check that the groups are a partition of all indices, else `infra-failure`. Reason: the merge model may group, never drop (Q22). Brief 011 item 11.

## Q36: review labels
Yes, bootstrap creates `needs-human-review`, `infra-failure` and `factory:builder-failed` up front, with descriptions. Brief 011 item 9.

## Q37: tester transcript after the move to Azure
Waiting for Qun (see top), together with Q28.

## Q38: local `claude` login
Waiting for Qun (see top).

## Q39: architect and blast-radius are manual-only
Replace them. Both are `disable-model-invocation: true` and point to unvendored files, so they cost tokens and never run. New own skills `spec-shape` (spec writer) and `impact-check` (builder, on trigger); text in brief 010.

## Q40: `poteto-mode` line in builder.md
Replacement line in brief 010.

## Q41: meter-conventions tool name
Yes: "(ArchUnit, `ArchitectureTest`)". Text in brief 010.

## Q42: verify-meter can't run in CI
Option (b): drop verify-meter from the builder's and tester's CI charters. Reason: 40-verify already starts the real app and runs the hidden scenarios from a trusted job; widening the builder's tools would buy nothing. verify-meter stays for interactive use and eval setup C. Brief 010.

## Q43: "always" vs "on trigger" for Claude roles
Inline always-on bodies into the prompt for every role, as for the Codex tester; `.claude/skills/` holds only on-trigger skills. Reason: "always" must mean in context, deterministically, and the eval then measures the real setup. Brief 010.

## Q44: `reviewed: pending` sources
Yes, refuse them (fail closed). Allow `--allow-pending` only for local `skill_eval.py`, and add a policy rule that no workflow passes it. Qun's review of the pins is listed at the top.

## Q45: tester without ponytail
Intended. Ponytail is about minimal production change; the tester only writes new tests.

## Q46: eval setup C and verify-meter
- Keep CI tools. Drop verify-meter from setup C: setup C = B + exactly the role's on-trigger skills from its charter. This amends brief 010 step 3.
- Reason: the eval must measure the CI configuration. A skill that can only report "curl not allowed" adds tokens and noise and says nothing about its value.
- If verify-meter's value is ever worth measuring, add a separate, clearly labelled local-only setup D (curl, java). Not now; it does not feed any CI decision.

## Q48: name-level reference check
- Yes, but narrow and deterministic, no free-text parsing: in `load_skills.py --check`, collect the known skill names (everything in `skills.lock.yaml` plus vendored and interactive-only skills such as `create-verification-skill`, `verify-meter`, and the retired `architect`, `blast-radius`, `how`, `why`, `arena`, `unslop`). Fail when a loaded skill's body mentions one of those names in backticks and that skill is not loaded for the same role.
- Reason: dangling name references were exactly the brief 010 bug (Q39). A fixed name list catches the realistic cases at near-zero cost; anything subtler is caught by Qun's pin review (Q44).
- Add one test with a fixture that references `how` and one that references a loaded skill (must pass).

## Q47: stale skill names in README and HANDOFF
Acknowledged; no further action. The Q48 name check now guards loaded skills; README/HANDOFF stay a manual check.

## Q49: tighten the tree-tools rule
Yes, tighten it. Tightening a control needs no extra approval.
- Match `tools` as a path operand of any copy/move/sync/exec command (`cp`, `mv`, `rsync`, `install`, `tar`, `python`, `bash`, `sh`, `.`/`source`), with or without `./` prefix, trailing `/`, `/.` or quotes.
- Prefer a positive rule over a longer deny regex: in post-agent jobs, every `tools/` reference must be rooted at the trusted checkout path (`github.workflow_sha` copy). Anything else fails.
- Add test cases: `cp -r tools "$X"`, `cp -r ./tools/ x`, `cp -a "tools/." x`, `rsync -a tools x`, `python tools/publish.py`, `bash ./tools/x.sh`; and one trusted-path case that must pass.

## Q50: write collaborators and model secrets
Waiting for Qun (see top).

## Q51: pin Semgrep
Yes, same treatment as Q13/Q21. Reason: an unpinned scanner is not a reproducible gate, and pipx pulls a large dependency tree.
- Pin `semgrep==<version>` with hashes via `pin_requirements.py` (its own requirements file, installed with `--require-hashes`), or a digest-pinned Docker image run with `--network none`. Your choice; the image is simpler if the rules are local.
- Also pin the rules: `--config p/java` fetches the registry ruleset at run time. Vendor the ruleset into the repo (e.g. `factory/semgrep/java.yml`, with source and date in a header), run with `--metrics off` and the local config only.
- Extend the policy rule: no `pipx run` / `pip install` without a version and hash in any workflow.

## Q52: egress probe positive control
Use a GitHub-owned host the job already depends on: `https://api.github.com` for both the positive and the negative probe. Reason: the probe should add no new external dependency, and using the same host for both makes the comparison exact. If the positive control fails, the step fails with "probe inconclusive" (fail closed, distinct message), never a pass.

## Q53: minimum age for pinned packages
Yes, 14 days. Reason: most malicious or broken releases are yanked within days; correctness over freshness.
- `pin_requirements.py` resolves with an upload-time cutoff of now − 14 days (e.g. `uv pip compile --exclude-newer`, or filter PyPI upload times) and fails if a required pin is younger.
- Exceptions only through a committed file `tools/young-pins.txt` (`pkg==version  # reason, date`), for security fixes. A new exception counts as a protected change (red path, Qun reviews).
- Re-run the pinning now; record changed versions in STATUS.

## Q54: brief 010 step 3 stale
Fixed in `collab/briefs/010-skill-fixes-after-001.md`: step 3 and decision 3 now match Q46 (setup C = B + the charter's on-trigger skills, CI tools, no verify-meter). Commit it with your next brief-010 commit.

## Q55: Semgrep rules licence → **(a) pinned fetch**
- Keep it. Reason: no licence risk, integrity is pinned, and a digest change fails closed. That is the right direction.
- Make the failure unambiguous: a digest mismatch fails `static` with "semgrep ruleset digest changed: bump required", distinct from findings and never a pass.
- Bumping the digest is a protected change (the pin lives under a red path); the PR states old/new digest and the date of the fetch.
- Never store the fetched rules as an Actions artifact or cache on the public repo; that is distribution too.
- If the digest flaps without real upstream changes (non-deterministic response), report it as a question; then (c) own rules under `factory/semgrep/` become the fallback. Not (b): stale rules are a weaker gate; not (d).

## Q56: agent-job rule stricter than Q49
Accepted. Tightening needs no approval, and the replace-ref reason is sound. Keep it, and add one test: a `git show "$WORKFLOW_SHA:tools/x"` after the agent step inside an agent job must be rejected.

## Q54: brief 010 step 3 stale
Fixed in the brief text (setup C = B plus exactly the charter's on-trigger skills, per Q46).

## Q55: Semgrep rules licence
(a), keep the pinned fetch with sha256 check. Reason: no licence risk, current rules, and a red `static` job on an upstream change is fail-closed, which is correct; bump the digest in a reviewed PR. Do not vendor.

## Q56: stricter tools rule inside agent jobs
Accepted. Reason: replace refs make `git show` untrustworthy once the agent has run; tools already run in separate later jobs.

## Priority: brief 012
Before any further work, do brief 012 (walking skeleton: green 40-verify and one full factory run). Hardening freeze until it is done.

## Qun's decisions (2026-11-12, live in the Cowork session)
- **Merge:** per-brief PRs, in the work order, after brief 012 is green. Not one combined PR. Fixes found in 012 go back into the brief branch they belong to (or a small follow-up PR per brief), so each PR is green on its own.
- **Q50:** option (a). Model secrets move to environment `factory-models`, deployment branch policy `master` only, no required reviewers. Claude Code adds it to bootstrap and adds the policy rule "every job that references a model secret has `environment: factory-models`". Applied on the new snapshot repo.
- **Q28/Q37:** option (c), LiteLLM-driven tester. See `collab/briefs/013-litellm-tester.md`; starts after 012. Until then codex-action is fine in the private repo; no factory run on the public repo before 013 is merged.
- **Q44:** Cowork summarised, Qun decides (top). Proposed builder.md line once approved: "Ponytail's 'leave a small test' does not apply to you: the tester owns all tests. If a check is missing, name it in your summary."

## Qun's decisions (2026-11-12, second block, live in the Cowork session)
- **Ponytail:** not vendored. Keep only the relevant rules as our own skill `minimal-change`: brief 014. This replaces the Q44 review for ponytail. The pstack pin (`create-verification-skill`) is interactive-only and needs no review for CI.
- **Snapshot steps delegated to Claude Code:** add the new repo to the App installation (`gh api -X PUT /user/installations/<id>/repositories/<repo_id>`), re-set `GEMINI_API_KEY` and `AZURE_OPENAI_API_KEY` from Qun's local env vars by piping (never printed), create environment `factory-models` (Q50) through bootstrap. Only the App key and the Claude token need Qun (top).
- **Flip to public:** delegated to Claude Code, **only when all of these hold**, each recorded in STATUS with evidence: the brief 009 pre-publish scan (gitleaks + client-name deny-list) passes on the new repo; briefs 012 and 013 are merged; bootstrap `--apply` read-back is ready to run right after. If any check fails, do not flip; write a question.

## Q38: done
Qun ran `/login` locally (2026-11-12). Claude Code may run the skill eval, but **after** briefs 012 and 014, so it measures the builder with `minimal-change` instead of ponytail.

## Docs (2026-11-12, Qun's request)
Cowork now keeps the design docs and factory ADRs current on every scheduled run.
- New: `docs/design/factory-flow.md` (flow diagram, stages with Built/Merged/Proven, routing, secrets, path to first green run) and ADRs 0003–0012 in `docs/adr/`, plus a new `docs/adr/index.md`.
- Claude Code: commit these with your next commit on `brief-012`. For `docs/adr/index.md`, take Cowork's working-tree version verbatim (it includes 0002).
- When you record a run URL or a merge in STATUS, Cowork moves the stage to Merged/Proven in the flow doc. Please keep run URLs in STATUS, one per proven stage.
- README.md stays yours; its "Flow" section can link to `docs/design/factory-flow.md` and `docs/adr/index.md`.

## Q57: builder.md wording after ponytail
- Keep your line as is: "Follow the minimal-change skill: the smallest complete change." It names an always-on skill the builder loads, so the Q48 check covers it.
- Drop the planned Q44 line ("Ponytail's 'leave a small test' ..."). It is obsolete: the `## Tests` section of `minimal-change` already says the tester owns all tests.

## Brief 012 after phase 1 (Cowork, 2026-11-12)
Phase 1 is accepted: 40-verify green on PR #14 (run 43194602253), brief 014 done. Not yet met from brief 012's criteria: acceptance against the example repo, the egress negative proof, and the factory run.
- **Acceptance and egress proof move into step 4.** On a non-work-item PR the scope is empty by design (Q24), so acceptance can't run there. Prove them on the first work-item PR (`wi-<n>`) of the factory run: its AC is in scope, so acceptance, the `nobody` egress block and both probes run. Then push one throwaway commit on a scratch copy of that branch that removes the iptables rule; the probe must fail. Record both run URLs. Do not make acceptance run on empty scope to get an earlier proof; that would be new hardening during the freeze.
- **Before Qun merges:** record in STATUS, per per-brief PR, the latest 40-verify run URL and for each red job: cause, and the brief/commit that fixes it. This is the evidence for the merge decision at the top.
- **Fold-back:** `cabab48` (Q55 message) belongs to brief 011; fold it back with the other 012 fixes.
- **Next, in order:** acceptance repo + Qun's token → bootstrap without rulesets (vars, labels) → Qun merges → factory run on `master` (step 4) → skill eval (Q38) → brief 013.

## 50-review / 45-fix-round failures until the merge
Qun's decision (2026-11-12): option (a), leave them. Nothing is disabled. The red runs come from `master`'s old version (placeholder `models.yaml`), stop before any model call, and block nothing. Treat them as expected noise until 003/011 are merged; the first factory run after the merge proves both.

## Per-brief PRs green on their own (Qun's decision, 2026-11-12: option a)
Every per-brief PR must be green on its own before Qun merges it. How, so it stays small and doesn't duplicate code:
1. **Environment before code.** First create `meter-acceptance`, set `ACCEPTANCE_REPO`, and let Qun create `ACCEPTANCE_REPO_TOKEN`. Then re-run 40-verify on every open PR. Fix nothing in code that configuration fixes.
2. **Fix once, at the earliest branch, and let it flow up.** Commit each remaining fix on the **earliest** brief branch whose PR needs it (e.g. the pinned gitleaks image step on `brief-004`). Then merge that branch up the existing chain (004 → 006 → 005 → 007 → 009 → 008 → 003 → 001 → 010 → 011 → 012), as you already do. When it conflicts with the later version of the same code, take the later version. The fix exists once, not copied into each branch.
3. **Smallest change that makes the job honestly green.** Never skip, soften or `continue-on-error` a check to make an early PR green. If a job can only pass with code from a later brief, move just that piece down; if it is too big, write a question.
4. **Evidence.** STATUS gets a table: PR, brief, latest 40-verify run URL, green yes/no, the fix commit if any. Qun merges in work order only PRs marked green there.
5. No Bypass-log entries are needed for this, because nothing is merged red.

## Acceptance repo token: done (Qun, 2026-11-12)
Qun reports `meter-acceptance` and the read-only `ACCEPTANCE_REPO_TOKEN` are in place. Claude Code: confirm with `gh secret list` / `gh variable list` (names only, never values) that `ACCEPTANCE_REPO_TOKEN` and `ACCEPTANCE_REPO` exist, record it in STATUS, then re-run 40-verify on every open per-brief PR (step 1 of "Per-brief PRs green on their own") and fill the per-PR table.

## Merge evidence draft (Cowork, 2026-11-12, from the `brief-012` stash)
Read from Claude Code's uncommitted STATUS draft; no new questions (Q1–Q57 all answered).
- The per-PR table is good evidence: #7–#12 green, #1–#6 red only on S1 (secret scan permission) and A1/A2 (acceptance checkout). Fill RUN13/RUN14 and commit it.
- Do not merge anything red until Qun settles (a) vs (b) at the top. Under (a): first Qun fixes the token (A2), then re-run #1–#6; then move only `c50126a`'s permission line to `phase-0` and merge up the chain.
- If after the token fix an old acceptance job (PRs #1–#4, before brief 007's scope) runs ACs it should not, write a question; do not skip or soften the job.
- `ACCEPTANCE_REPO_TOKEN` "done" above is superseded by A2: set, but no read access yet.

## S1 moved to phase-0 (Cowork, 2026-11-12, 12:54)
Seen: `ea7b957` on `phase-0`, merged up the whole chain at 12:22. This is step 2 of "Per-brief PRs green on their own"; good.
- Before committing the STATUS stash: change its line "Merge decision (Qun): option (b) ..." to (a), unless Qun confirms (b) at the top. Drop the "Mergeable under (b)" column; use "green yes/no" and "fix commit" (S1 → `ea7b957`).
- Re-run 40-verify on #1–#4 and record the run URLs; S1 should be gone. A2 stays red until Qun fixes the token (top); do not work around it.
- Also commit Cowork's untracked `docs/design/` and `docs/adr/0003`–`0012` plus `docs/adr/index.md` with your next commit (see "Docs" above); they are still untracked.

## Review coverage: no silent truncation (Cowork, 2026-11-12)
Found while reading Open Code Review (brief 015): `tools/review.py` cuts the PR diff at 120 000 characters and reviews only the first part, **without saying so**. That breaks "never drop a review silently" (ADR-0003). This is a correctness fix to an existing control, not new hardening, so it is allowed under the 012 freeze.
- Minimal fix, on `brief-003` (earliest branch with the current review.py), flowing up the chain: if the diff is longer than the limit, still review the first part, but add `needs-human-review` and put a line in the comment: "Diff too large (N chars); only the first 120000 were reviewed." Record `truncated: true` in the run record.
- One unit test: an oversized diff gets the label and the line.
- Better coverage (per-file bundles) waits for the brief 015 evaluation.

## Brief 015: Open Code Review (evaluation, later)
Qun shared alibaba/open-code-review. It is not adopted. It is a candidate to replace only the reviewer step, evaluated against our `review.py` with the same models, after the first green factory run. See `collab/briefs/015-evaluate-open-code-review.md`. No action now.

## Q58: AC-F1-4 on PRs #1–#6 → Qun's decision: **(b)** (in chat, 2026-11-12)
Recorded here; Qun decided, not Cowork.
- AC-F1-4 is parked in `meter-acceptance` (`6bfcb84`, `@Disabled` with a reason) until PR #7 (brief 007) merges. Remove the `@Disabled` right after that merge, before the factory run, and record the commit in STATUS. It is on "Waiting for Qun" so it is not forgotten.
- Reason it is acceptable: test data the scenario owner controls, no check skipped or softened, reversible. The old pre-007 job reports the skipped test as `pass`; that job disappears with #7, so accept it, do not fix it.
- Evidence gap to close before Qun merges #10–#14: the per-PR table lists heads from before the truncation fix (`33e5bc0`, merged up to 012). Add each current head and its green 40-verify run URL to the table (re-run if no run exists). No other change.
- The first `wi-<n>` PR of the factory run must show AC-F1-4 **running** under the 007 scope (pass after the build, or FAIL before it). If it still shows as skipped, the un-park was missed: stop and write a question.

## Current-head evidence #10–#14 (Cowork, 2026-11-12, after `275b840`)
Seen: green 40-verify runs for the current heads of #10–#14 in STATUS. This closes the Q58 evidence gap. Two small leftovers, no code change:
- #4's head is now `a6b6822` (Cowork's ANSWERS) and #14's head is `275b840` (STATUS + factory-flow). STATUS says "see below" / "its run is below", but no run URL follows. Add the 40-verify run URL for both heads to the table (re-run if none exists), so every PR Qun merges has evidence for its exact head.
- Keep collab-only commits off the PR branches until the merges are done, as you already decided; Cowork's working-tree files (`docs/design/learnings.md`, the factory-flow changelog, this section) can wait for the first commit after the merges.

## Learnings (2026-11-12, Qun's request)
New: `docs/design/learnings.md`, lessons so far, kept current by the scheduled Cowork run. Claude Code: commit it with Cowork's other docs. When something surprises you or costs a detour, say so in STATUS in one line ("Learning: ..."); Cowork moves it into learnings.md.

## Checklist before the first factory test run (Cowork, 2026-11-12)
Everything that must be true before Qun opens the test issue. Claude Code: tick each item in STATUS with evidence (names only for secrets/vars).
1. **Merged:** PRs #1–#14 in work order (Qun). #4 and #14 first get a current-head 40-verify run URL.
2. **Repo setup without rulesets (Claude Code, bootstrap or `gh`):** labels (all of README "Labels", incl. `feature`, `gate:intent-approved`, `spec`, `work-item`, `queued`, tiers, rounds, `factory:builder-failed`, `needs-human-review`, `infra-failure`); variables `GATE_ROLES` = `{"gate:intent-approved": ["Qunfong"]}`, `WIP_LIMIT` = `1` for the test, `FACTORY_BOT_LOGIN` = `agentic-factory-bot-qunfong[bot]`; environments `staging` and `production`. STATUS's diagnosis says no labels exist and nothing records these variables yet.
3. **Secrets present (names):** `CLAUDE_CODE_OAUTH_TOKEN`, `AZURE_OPENAI_API_KEY`, `GEMINI_API_KEY`, `FACTORY_APP_PRIVATE_KEY`, `ACCEPTANCE_REPO_TOKEN`; variables `AZURE_OPENAI_ENDPOINT`, `FACTORY_APP_CLIENT_ID`, `ACCEPTANCE_REPO`. If the Claude token has expired, Qun runs `claude setup-token`.
4. **Test feature = "delete the readings of a meter"**: the one feature with a hidden scenario already written (today tagged `AC-F1-4`, parked). Qun opens it with the feature template, one acceptance criterion `AC-1` matching that scenario.
5. **Re-tag the scenario before the work-item PR is verified (Qun as QA):** the spec writer turns `AC-1` into `AC-F<issue number>-1`. In `meter-acceptance`, change the delete scenario's tag from `AC-F1-4` to that ID and remove its `@Disabled`. Without this, verify fails closed ("AC in scope without a scenario"), which is correct but stops the test. This replaces "remove the `@Disabled` after #7".
6. **Gates Qun performs during the run:** set `gate:intent-approved` on the issue; merge the spec PR (plan gate); approve and merge the work-item PR (merge gate). Production deploy is out of scope for this first test.
Expect fixes: codex-on-Azure, the LiteLLM review path, publish with the App token and the egress probe with ACs in scope have never run in Actions.

## After the merges (Cowork, 2026-11-12 evening)
Seen in STATUS: #1–#14 merged in work order (`a63864a`), no red merge, no Bypass-log entry; AC-F1-4 un-parked (`e60a297`); first `60 release` run 43277109349 green. The merge item is removed from "Waiting for Qun". Checklist status:
1. Merged: ✓.
2. Labels and variables (`GATE_ROLES`, `WIP_LIMIT` = `1`, `FACTORY_BOT_LOGIN`): still open, nothing in STATUS sets them. Do it now with bootstrap (no rulesets) or `gh`, and list the names in STATUS. Environments: exist (auto-created), but without protection (see "Waiting for Qun").
3. Secrets/vars: tick with names in STATUS; check the Claude token still works before the issue is opened.
4. Unchanged.
5. Un-park is done. What remains: after the spec PR names `AC-F<issue>-1`, re-tag the delete scenario from `AC-F1-4` to that ID. Until then AC-F1-4 is in no merged work item's scope, so it does not run; that is expected.
6. Unchanged; production stays out of scope.
- Do not merge the test work-item PR before Qun answers the production-gate item.

## Rulesets: two tightenings (Qun's decision, 2026-11-12)
Qun approved in chat. Both are tightenings; ADR-0013. **Timing:** not now. Do it as one small follow-up PR (`brief-016-rulesets`, off `master`) **after** PRs #1–#14 are merged and before the flip, so the green PRs don't move again. It only takes effect at bootstrap `--apply` on the public repo.
1. **`required` must come from GitHub Actions.** In `factory-default-branch`, the `required_status_checks` entry becomes `{"context": "required", "integration_id": 15368}`. Reason: otherwise any actor that can write a commit status named `required` satisfies the gate.
2. **Squash only, linear history.** The `pull_request` rule in `factory-default-branch-review` gets `"allowed_merge_methods": ["squash"]`. `factory-default-branch` gets `{"type": "required_linear_history"}`. If a merge queue is ever enabled, its `merge_method` becomes `SQUASH`.
- Same change in `bootstrap.ps1`. Extend the `--apply` read-back to fail unless both rulesets show these values, and add the payload to the dry-run tests.
- Update README "Branch protection" in the same PR.

## First factory test run: issue #16 (Qun, 2026-11-12)
Qun opened the test feature as issue #16 ("Delete the readings of a meter", one AC). Expected IDs: `AC-F16-1`. Claude Code: watch the runs of 10-spec onward and record them in STATUS (run URL per stage, first error line if red). Do not change gates to make it pass. ~~Qun still has to answer the production-gate item (top) before the work-item PR merges.~~ Done: Qun chose (b), merged as #17 (`fe056d3`), see below.

## Issue template is invalid: root cause (Cowork, 2026-11-12)
Qun saw the blank issue form, and issue #16 has no labels. Cause in `.github/ISSUE_TEMPLATE/feature.yml` on `master` (from the initial import):
`attributes: {label: Design link (tokens, reference images, mockups)}`. The label is unquoted inside a YAML flow mapping, so the commas split it. It parses as `label: "Design link (tokens"` plus two extra keys, `reference images` and `mockups)`. GitHub rejects issue forms with unknown attribute keys and silently falls back to the blank form, so the `feature` label is never applied either.
- **Fix (Claude Code, small PR now; a correctness fix, allowed under the freeze):** quote it: `attributes: {label: "Design link (tokens, reference images, mockups)"}`.
- **Guard against a repeat:** in 40-verify's static job (or the policy check), load every `.github/ISSUE_TEMPLATE/*.yml` and fail when an element's `attributes` has keys outside GitHub's issue-form schema (`label`, `description`, `placeholder`, `value`, `options`, `render`, `multiple`, `default`). One unit test with this exact broken line.
- **#16 meanwhile:** Qun adds the `feature` label by hand first, then `gate:intent-approved`. 10-spec requires `feature` to already be on the issue when the gate label arrives. The spec writer reads the whole body as text, so `AC-1: …` in the body is enough.

## Production gate → Qun's decision: **(b)**, done (#17, `fe056d3`, 2026-11-12)
- `60-release`'s `production` job now starts with a fail-closed step: it reads the environment and refuses to deploy unless a `required_reviewers` rule exists. Recorded as ADR-0014.
- Expected effect: every release on this private Free repo goes red at `production` until the snapshot repo has a reviewer. That red is correct; do not mark it `infra-failure` and do not work around it. Build and staging must still be green; record the production failure line in STATUS once.
- For #16 the release stops at staging, matching the checklist scope. The work-item PR may merge once its gates pass.
- Small follow-up for the snapshot (no hurry): bootstrap's `--apply` read-back should check the same rule on `production`, so the gate and its setup agree.

## Seen on branches, not yet in STATUS (Cowork, 2026-11-12, after `cda1191`)
- `fix-issue-form` (`442be18`, `cda1191`, off `origin/master`): label quoted; the issue-form schema check sits in `tools/check_workflow_policy.py` with `tools/tests/test_issue_forms.py`. That placement is fine (the answer allowed the policy check). Matches the root-cause answer; no change requested.
- `brief-016-rulesets` (`6a1f2f6`, `94aa99e`): ADR-0013 built in both bootstrap twins, read-back and README. Matches the answer.
- Claude Code: open a PR for each, add a STATUS row with the 40-verify run URL, and merge `fix-issue-form` first (it is on the path of issue #16; 016 only matters at `--apply`). Then record #16's stage runs as asked above.
- ✓ Done (STATUS `0edbb11`): #19 and #20 are open with green 40-verify; #16's stage runs are recorded.

## Run #16 so far (Cowork, 2026-11-12, after `0edbb11`)
- 10-spec ([43280109890](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43280109890), attempt 5), 40-verify on spec PR #21 ([43285356428](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43285356428)) and 50-review on #21 ([43285523343](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43285523343)) count as proven for the spec path. The two reds before (stored token not logged in; App not installed on the repo) were configuration, fixed by Qun, no gate touched. Good.
- 50-review on #21 proves authorize and the Gemini reviewer only. The Azure verifier ran with nothing to verify, so it is **not** proven yet. Record it as proven only on a PR where the reviewer raises at least one finding (most likely the `wi-<n>` PR). If the `wi-<n>` review also raises 0, say so in STATUS; do not plant a finding to force it.
- Merge order (Qun merges; see "Waiting for Qun"): #20 first, then #21 (plan gate). #18 and #19 do not block #16 and can follow in any order.
- After #21 merges: re-tag the scenario `AC-F1-4` → `AC-F16-1` in `meter-acceptance` **before** the `wi-<n>` PR is verified; otherwise 40-verify fails closed on a missing scenario (that red would be correct, not a bug). Then record 20-breakdown, 25-dispatch, 30-build, 40-verify (with `AC-F16-1` in scope and the egress block), 50-review and 60-release (staging green, production red per ADR-0014) the same way.
- Keep `WIP_LIMIT=1` until #16 is through 50-review on its `wi-<n>` PR.

## Run #16 after the plan gate (Cowork, 2026-11-12, after `884e7f2`)
Seen on `origin/master` and `origin/wi-22`, not yet in STATUS:
- Qun merged #20 (`4e58d57`), #18 (`4ce3ed8`), #21 (`f84b7a5`, plan gate) and #19 (`0bd81a8`). Merge-commit method is fine for now; squash-only applies only after `--apply` on the snapshot repo (ADR-0013). The merge item is removed from "Waiting for Qun".
- 20-breakdown and 25-dispatch produced work item #22; 30-build's tester pushed `884e7f2` (`ReadingDeleteTest`, trailer `Assisted-by: codex:azure/gpt-5`, `Factory-Run: 43289283565`) to `wi-22`. That is the first sign of the tester on Azure in a real run.
- Claude Code: add STATUS rows (run URL, result, first error line if red) for 20-breakdown, 25-dispatch and 30-build (tester, publish-tests, builder, publish-code), then for 40-verify, 50-review and 60-release on the `wi-22` PR, as listed in "Run #16 so far". Cowork marks a stage proven only from those rows.
- The `wi-22` PR's 40-verify needs the re-tag to `AC-F16-1` first (see "Waiting for Qun"). The tester's `@DisplayName("AC-F16-1: …")` unit tests do not replace the hidden scenario; scope still requires the tagged scenario in `meter-acceptance`.
- Unchanged: `WIP_LIMIT=1` until #16 is through 50-review on the `wi-22` PR; the Azure verifier counts as proven only on a review with at least one finding.

## Feature issue as hub (Qun, 2026-11-12)
Qun wants a feature followed from its own issue. New brief `collab/briefs/017-feature-issue-as-hub.md`: sub-issues, `Part of #<feature>` links, one status comment kept up to date, and the issue closes itself. **Start after the run on #16 is fully green**; it is backlog item 1 (before brief 015). Brief number 016 is skipped because branch `brief-016-rulesets` already used it.
- Backlog order (Cowork, scheduled run 2026-11-12): the standing instruction keeps brief 015 as backlog item 1 until it is done, so 015 stays 1 and 017 is 2 in `docs/design/factory-flow.md`. Both start only after #16 is fully green. If Qun wants 017 first, he says so and the order flips.

## Run #16 build stages (Cowork, 2026-11-12, after `ac86360`)
Seen in STATUS. Marked proven in `docs/design/factory-flow.md`: 20-breakdown ([43289016415](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43289016415)); 30-build's tester (Azure gpt-5 via codex), publish-tests and builder ([43289283565](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43289283565)). Re-tag `AC-F16-1` done (`d9b97f9`), removed from "Waiting for Qun".
- **publish-code red (`origin/main`):** PR #23 is the right fix (two tool lines plus a test that bans `main` refs). No gate changed. After #23 merges: remove `factory:builder-failed` from #22, re-dispatch 30-build as Qunfong, record the run. The rerun must be idempotent (Q11): tests already on `wi-22` are not duplicated. If the tester pushes a second test commit, report it in STATUS as a finding.
- **codex-action refused `github-actions[bot]`:** decided: (a) for now every 30-build that runs codex is dispatched by a maintainer (Qunfong). Do **not** widen codex-action's allowed users/bots: that loosens a check, and only Qun can decide it. Brief 013 removes codex-action and with it this block. Consequence: the flow is not unattended until 013; 20-breakdown/25-dispatch still dispatch, the first build attempt goes red at `tester`, and that red is expected. Record it once, not per item.
- **25-dispatch did not run** on #16: 20-breakdown dispatched within `WIP_LIMIT` itself, as built. 25-dispatch stays unproven until an item waits in `queued`; no extra run is needed for the walking skeleton.
- Next rows wanted in STATUS: 30-build rerun (publish-code), the `wi-22` PR, its 40-verify (acceptance with `AC-F16-1` in scope, egress block and probes), 50-review (Azure verifier only counts with ≥ 1 finding), 60-release (staging green, production red per ADR-0014).

## Three reviewer families with Grok (Qun, 2026-11-12)
Qun deployed `grok-4.7` (xAI) on `ai-services-qun` and wants reviews by three models, keeping the most agreed feedback. New brief `collab/briefs/018-three-family-review-consensus.md`: Gemini + gpt-5 + Grok, strong = 2 of 3, single-source findings checked by another family and never dropped silently. **Start after the first fully green run**, together with brief 015. Do not use the key Qun pasted in chat; wait until he has regenerated it (top).

## Brief 018: start now (Qun, 2026-11-12)
Qun: "add and implement". Start brief 018 now, on a branch `brief-018` off `master`. Grok uses the regenerated resource key in `AZURE_OPENAI_API_KEY` and the variable `AZURE_AI_V1_ENDPOINT`, which Qun sets with the commands Cowork gave him. Before CI: set the `grok-4.7` deployment to `NoAutoUpgrade`, record model and version in STATUS, and make one smoke call with the key from env. Only after Qun has regenerated the key; check that the secret's `updated_at` is later than now.

## Review visibility (Qun, 2026-11-12)
Qun can't see what the reviewers did beyond a count. Added to brief 018, section "Visibility": a reviewer table with exact model, result, findings, tokens and seconds; agreement and verifier verdict per finding; a collapsed list of rejected findings with reasons; the same data in the run record. Build it as part of 018.

## Review fails on one provider (Qun, 2026-11-13)
50-review #213/#216/#217: `RateLimitError after 4 attempts` with no model named; almost certainly the free Gemini daily quota. Qun: why does the whole review fail when other models exist? Because amber has one reviewer, `review.py` aborts on the first `InfraFailure`, and the merge model is Gemini too. Added to brief 018, section "Provider outages": name the model in every error, isolate failures per reviewer (≥ 2 answering = complete), mechanical grouping when the merge model is down, a verifier from any available other family. Part of 018, which is being built now.

## Spec PR #29 (F28): Qun's answers at the plan gate (2026-11-13)
Qun accepted Cowork's proposals. Claude Code: commit them now to `spec/F28` as one commit, author Qun's noreply address, message `spec: F28 plan-gate decisions`. Only under `docs/specs/F28/`. Add a section "Decisions at the plan gate" to `spec.md` with these lines, remove them from "Open questions", and update `plan.md` WI-3 (no longer blocked). Do not change any AC ID. Let 40-verify and 50-review rerun, then tell Qun it is ready to merge.
1. Bill for a month with insufficient data: **422**, `ProblemDetail` with `code = "insufficient-data"`.
2. Consumption response: a bare JSON array of `{"month","kwh","reason"}`, `reason: null` when `kwh` is present.
3. A retry of an identical reading returns 409; clients treat it as already stored.
4. Duplicate is checked first: 409 before 422.
5. Equal counter values are allowed (strict decrease only).
6. The tariff stays as constants in `billing.Tariff`; configuration is a separate feature.
7. `kwh` in the bill is a JSON number.
8. WI-3 is red tier; Qun reviews it as domain owner.
Also accepted at this gate: `GET /readings` in `takenAt` order, and the two proposed ADRs (ProblemDetail `code`, `ReadingStore`).
From the next feature on this happens through brief 019 (the factory acts on PR comments) instead of a manual commit.

## Brief 019: no cap on human-requested revisions (Qun, 2026-11-13)
Changed in brief 019, decision 5. A maintainer explicitly asks for every revision, so there is no fixed maximum. Guards instead: one revision at a time per PR (queued), no push when nothing changed (with a reply per thread), and token/cost use per revision shown in the feature status comment. The automatic fix rounds (45) keep their cap of 2.

## Run #16 through release (Cowork, 2026-11-13, after `4fa4505`)
- **Brief 012 step 4 is done.** The walking skeleton ran end to end on `master`: 30-build 43292923660, 40-verify 43293223375 (`AC-F16-1: pass`, egress block and probes), 50-review 43293464763 attempt 2 (Azure verifier proven), merge `f85274d`, 60-release 43294559180 (staging green, production red as ADR-0014 requires), negative egress proof 43294913361. The hardening freeze from brief 012 ends here; the backlog in `docs/design/factory-flow.md` applies, brief 015 first.
- **Production check "cannot read the production environment":** correct fail-closed behaviour, keep it. Follow-up for the snapshot repo only: give the check the least permission that lets it read the environment's protection rules, and prove it there twice (no reviewer rule → red; with the rule → it waits for the reviewer). Do not catch the read error as "no rule" or as a pass. If the fix needs a new App permission, that is a click for Qun; ask in QUESTIONS when you get there.
- **Leftovers:** remove `factory:builder-failed` from closed #22 (stale since #23). Close feature issue #16 by hand with a comment that links the run table in STATUS; brief 017 automates this later.
- **25-dispatch** stays unproven; accepted. It is proven the first time an item waits in `queued`.

## Brief 018 merged; record it in STATUS (Cowork, 2026-11-13)
- #31 (`5513515`) and #33 (`4fa4505`) are on `master`, but STATUS has no row for brief 018 yet. Add one with the Grok deployment's model and version (`NoAutoUpgrade`), the smoke call result and the first 50-review run URL on a real PR with the three-family comment (reviewer table, agreement, rejected list). That run is brief 018's acceptance criterion and the "Proven" cell of 50-review.
- `fix-reviewer-timeouts` (per-family `timeout_s`, Grok 480 s, one retry of a timeout, job limit 45 min): agreed. A longer timeout loosens no control, a timeout still ends as `infra-failure` for that reviewer, and a job that hits its limit posts nothing and fails. Open it as a PR; ADR-0015 records the per-family timeout.
- ADR-0015 (three-family review consensus) is written and supersedes ADR-0003's review rows.

## Grok latency (Cowork, 2026-11-13)
Grok runs on Azure AI Services (Foundry), deployment `grok-4.7`. One review call took 239 s for 489 output tokens, which points at long hidden reasoning, not at the network. Foundry offers Grok as separate reasoning and non-reasoning models rather than a `reasoning_effort` setting; for Grok 4 Fast and 4.1 Fast they are separate deployments.
- Claude Code: list the Grok models this resource can deploy (`az cognitiveservices account list-models -n ai-services-qun -g Qun-zijn-Speeltuin`, filter on xAI). Report in STATUS: names, versions, reasoning or non-reasoning, and whether `grok-4.7` accepts a `reasoning_effort` parameter (one test call; report the error if not). No new deployment without Qun's yes (cost).
- First prove #34 (480 s limit) with a rerun of 50-review on #29 after the Gemini quota resets.
- Then measure latency per candidate on #29's diff, and include it in the brief 015 evaluation. Pick the fastest Grok variant whose findings hold up, not the fastest overall.

## Gemini → DeepSeek (Qun, 2026-11-13)
Qun: replace Gemini with DeepSeek. New brief `collab/briefs/020-deepseek-replaces-gemini.md`. **Start now**, before brief 015. It fixes the incomplete reviews caused by the free Gemini quota. Reviewers become gpt-5 + Grok + DeepSeek, all on `ai-services-qun` with one key; the merge model becomes gpt-5. Qun approved the cost of one DeepSeek deployment (newest stable chat model, `NoAutoUpgrade`). Red tier keeps `needs-human-review` until Qun decides otherwise.

## Brief 020: DeepSeek deployment name (Qun, 2026-11-13)
Qun deployed DeepSeek himself: deployment **`DeepSeek-V4.1-Flash-1017`** on Azure AI Services. Claude Code:
- Confirm it is on `ai-services-qun` (`az cognitiveservices account deployment list -n ai-services-qun -g Qun-zijn-Speeltuin`). If yes, use `AZURE_OPENAI_API_KEY` + `AZURE_AI_V1_ENDPOINT` as for Grok. If it is on another resource, use `AZURE_DEEPSEEK_API_KEY` + `AZURE_DEEPSEEK_ENDPOINT`, which Qun sets with Cowork's commands.
- Record model name, version, SKU, capacity and upgrade option in STATUS. Set `NoAutoUpgrade` if it isn't already. Check that it is a GA model, not a preview; if it is a preview, say so in STATUS and keep it (Qun chose it), and note it in ADR-0016.
- `models.yaml`: `deepseek: {model: openai/DeepSeek-V4.1-Flash-1017, ...}`. Measure one call on #29's diff and set `timeout_s` with margin.
- Confirmed by Qun (deployment list on `ai-services-qun`): deployment `DeepSeek-V4.1-Flash-1017`, model `DeepSeek-V4.1-Flash-1017`, version `2026-10-17`. It is on the same resource, so use `AZURE_OPENAI_API_KEY` + `AZURE_AI_V1_ENDPOINT`; no new secret or variable. Still set `NoAutoUpgrade` and record SKU and capacity.

## Brief 020 built on `brief-020` (Cowork, 2026-11-13, after `bf6adaf`)
- Seen `741f195` and `bf6adaf` on `brief-020`; no STATUS row or PR yet. Open the PR, and add a STATUS row with the DeepSeek deployment (version `2026-10-17`, GlobalStandard, capacity 20, `NoAutoUpgrade`, **Preview** in the catalog), the smoke call and then the 50-review rerun on #29 with 3 of 3 answering. That run is the acceptance of both brief 018 and brief 020, and the "Proven" cell of 50-review.
- `741f195` (every secret outside `GITHUB_TOKEN`, `ACCEPTANCE_REPO_TOKEN`, `FACTORY_APP_PRIVATE_KEY` is a model key): agreed. Deny by default tightens the gate and keeps `GEMINI_API_KEY` behind `authorize` until it is deleted. Delete `GEMINI_API_KEY` after the first green run without Gemini, as brief 020 says, and log it in STATUS.
- DeepSeek Preview: keep it (Qun's choice). ADR-0016 records it as the one exception to "no preview models".
- **DeepSeek's 2.2 s, 7 output tokens, no findings on a 28 KB diff is an answer, not yet evidence that it reviews.** Before the #29 rerun, make one planted-defect check: give the DeepSeek call (same prompt as `review.py`) a small diff with one obvious bug (for example an off-by-one or a swapped comparison in a copy of `app/src/main`), locally or on a scratch PR that is closed afterwards, nothing merged. Record in STATUS whether it reports the bug, with tokens and seconds. If it finds nothing: report it and do not change routing; Qun decides.
- Rate limits: capacity 20 means 20k tokens per minute; large diffs will hit 429 (Waiting for Qun). Until he decides, that is the designed path: `infra-failure` for that reviewer, named in the reviewer table, review complete with 2. Respect `Retry-After` in the retry.
- ADR-0016 is written; ADR-0015's Gemini rows are superseded.

## Parallel verifiers (STATUS brief 018, "Open")
Agreed, after brief 020's acceptance run, on its own branch and PR:
- Run verifier calls concurrently, at most 2 at a time per family (DeepSeek's per-minute limit), with one wall-clock budget for the whole review that ends well before the 45-min job limit (35 min), so the comment is always posted.
- A finding whose verification did not finish in time is listed as "Unverified (time budget)" and the PR gets `needs-human-review`. Never drop it, never count it as confirmed or rejected.
- Test: a slow verifier hits the budget → comment posted, finding listed as unverified, label set.
- No ADR change needed: ADR-0015's rules already cover it (single-source findings are verified or stay visible).

## Audit round 1 (Cowork, 2026-11-17, partial: 60-release, c8dbee5, grep over workflows and tools)
Reviewed after the fact, at master `c8dbee5`. Severity: B = fix before the snapshot/flip, A = advice, N = nit. Claude Code: take B first, answer each in QUESTIONS.md, do not weaken a control to close one.
- **R1 (B)** `c8dbee5` "Update 40-verify.yml" is a commit on `master` that changes `SEMGREP_RULES_SHA256` in a red-tier path (`.github/**`). Show how it got in (PR or admin bypass). If bypass: add a row to the Bypass log in STATUS (it is empty). Also state what changed in the Semgrep ruleset behind the new digest; a re-pin without a rules diff is a blind accept.
- **R2 (B)** `60-release.yml` sets `permissions: packages: write` for the whole workflow, so `staging` and `production` inherit it. Set `contents: read` at top and `packages: write` on `build` only (P3).
- **R3 (A)** Actions are not SHA-pinned (at least `actions/checkout@v4`, `setup-java@v4`, `upload/download-artifact@v4`, `anthropics/claude-code-action@v1`, `openai/codex-action@v1`), while ADR-0009 pins other supply chain items. The two agent actions run with model keys: pin those to a commit SHA first. Check ADR-0009 for an exemption and cite it or close the gap.
- **R4 (B)** Separation of duties "release owner did not approve the merge of the same change" (architecture, States/gates) exists only as a comment in `60-release.yml` and in bootstrap. No check enforces it, and a private Free repo cannot add environment reviewers. State where it is enforced, or add a release-gate check that reads the merge approver and the production approver and fails if equal. Production's environment check also cannot read protection rules with `github.token` (known, STATUS 60 release); fix with a token that can.
- **R5 (A)** `tools/check_run_records.py` only flags commits that have `Assisted-by:` without `Factory-Run:`. An agent commit with neither trailer passes, so traceability depends on the agent adding a trailer. Identify agent commits by the factory bot author or committer instead. With `fetch-depth: 50`, a `since..HEAD` range whose base is outside the shallow history errors out; on a zero `before` it checks only HEAD's 50 commits. Fail closed is fine, but say so in the message and test the zero-SHA case.
- **R6 (N)** `60-release.yml` deploy steps are `echo` placeholders. Mark the production run "not proven" in STATUS until a real deploy step exists.

### Next audit passes (not yet done)
`30-build`, `40-verify`, `50-review`, `publish.yml` and `tools/publish.py`, `tools/review.py` (prompt-injection, truncation), `check_workflow_policy.py` rule coverage, `factory/models.yaml` and charters vs the architecture's Agent registry requirements, tests that cannot fail.

### Waiting for Qun
- `~/Downloads/agentic-factory-bot-qunfong.2026-11-12.private-key.pem` is the factory-bot private key on disk. STATUS says it never touched disk. Delete it, and regenerate the key if the folder is synced or shared (then update secret `FACTORY_APP_PRIVATE_KEY`).

## Feature #28 / spec PR #29: not yet reviewed by 3 families (Cowork, 2026-11-17, from GitHub, not STATUS)
- Fact: the only 50-review comment on #29 (2026-11-13 04:48, head `5857eae5`) says "Review incomplete: 1 of 3 reviewers answered". Gemini: 429, Grok: timeout after 778 s, only `azure/gpt-5` answered. #29 still carries `needs-human-review` and `infra-failure` from that run. No 50-review ran on `spec/F28` since; the later runs (13 Nov 09:01, 14 Nov, 17 Nov) are on `master` or collab PRs. Brief 018 per-family timeouts (#34) and brief 020 (DeepSeek, #38) merged after it, so #29 has never been reviewed with the current setup.
- Qun's expectation: all 3 families (gpt-5, Grok, DeepSeek) answer on #29. This is the acceptance run of brief 018 and brief 020 (see "Brief 020 built on `brief-020`").
- Claude Code, in this order, one proof per step: (1) the planted-defect check on DeepSeek (already agreed; STATUS row with tokens/seconds and whether it found the bug); (2) re-run 40-verify on `spec/F28` head so 50-review starts from current `master`; (3) record in STATUS the 50-review run id, the reviewer table (3 of 3 `ok`, or which family failed and why), and whether the `needs-human-review` and `infra-failure` labels were removed by the new comment; (4) if a family still fails: report the error line and keep the "not a pass" outcome, do not change routing or lower the 2-of-3 rule.
- Review is on PRs only: the feature issue #28 itself is not reviewed by models, the spec PR is. If Qun wants issue-level review, that is a new brief.
- Cost note: one run calls three paid models on a 28 KB diff; acceptable for this one acceptance run.

## Cowork run 2026-11-17 (evening): answers, R-status, PR #39 review
Goldfish run from files, GitHub and the code at master `16053c1`. "Parked" items from COWORK-PLAN are not re-listed.

### R-items: verified against the code
- **R2: closed.** Evidence: master `60-release.yml` has exactly two `permissions` keys: top-level `contents: read` (line 8) and `build` with `contents: read` + `packages: write` (line 13); `staging` and `production` have none. Commit `ce2fb43`, merged in #39. Caveat: its regression test `tools/tests/test_release_workflow_permissions.py` passes locally (I ran it) but no workflow runs `tools/tests` (Audit round 2, A1). The fix is proven; the guard against regression is not.
- **R1: stays open.** Bypass-log row exists (verified in STATUS). Ruleset diff impossible (Q59). `master` still has no branch protection, so the bypass can recur.
- **R4: stays open**, now an accepted gap by Q60 (below). **R3, R5, R6: open**, untouched (R3 widened in Audit round 2, A4).

### Q59 (Semgrep rotation): (c), with a stated limit
Take (c): in `static`, after the digest check passes, write `sha256` + sorted rule-ID list to a small committed manifest (e.g. `factory/semgrep-p-java.ids`), no rule bodies. A rotation then shows added/removed IDs; changed rule *content* under the same ID is still invisible, so say that in the Bypass-log row of the next re-pin. I cannot give a legal reading of the Semgrep Rules License; IDs and a hash are facts, not rule text, which is why (c) over (b). Whether even that is acceptable is Qun's call (parked: build (c), which is the smaller footprint, and do not upload artifacts). Because `tools/**` and `factory/**` are red, Claude Code builds it as its own PR.

### Q60 (separation of duties): (a) + (b), plus an ADR
Agreed: do not build check (c); a control that cannot be falsified looks like a real one. Do (a) and (b): record `merged_by` per release in the run record (inert data), and keep R4 open with the trigger "second collaborator or environment reviewers become configurable". ADR-0017 (docs/adr, proposed) states the gap and the trigger. The comment in `60-release.yml` describes the intended state; add "not enforceable on a private Free repo, see ADR-0017" when Claude Code next touches it (red path, so its PR).

### Q61 (COWORK-PLAN claims a commit step): (a)
Dropped the claim in COWORK-PLAN.md line 1; it now says "Claude Code commits it when it next commits (best effort)". Staleness is already detected: the scheduled run compares `collab/.cowork-seen` with `git log -1`; a stale plan shows up as a hash mismatch, no extra check needed. Cowork cannot run git write commands.

### Review of PR #39 (how it went)
Facts from GitHub: opened 13:13, AI review 13:17, checks (`build-test`, `static`, `scope`, `acceptance`, `required`) green 13:38-13:39, merged by Qun 13:42:53; 3 commits; no human review or comment; the 50-review comment was updated 13:43, after the merge.
- **Good:** 3 of 3 reviewers answered (gpt-5 4 findings, DeepSeek 1, Grok 0); Claude Code reacted to the earlier review of `46c3f24` (honest wording about open gaps, added the permissions test). Body says "Not merging"; Qun merged: fine, that is the gate.
- **P1 (B) wrong tier on a red change.** The review header says "tier: amber", but the PR touches `.github/workflows/60-release.yml` and `tools/tests/` which `check_tier` floors to red. `tools/review.py:431` reads the tier from a `tier:*` label and defaults to amber when absent; only builder PRs get that label (`publish.py` `tier_label`). Effect: every hand-made or collab PR touching red paths gets the amber review and no `needs-human-review`. Missing data fails open. Fix: compute the tier in 50-review with `check_tier.py` from the master copy (not the PR's), or default to red when the label is absent.
- **P2 (N)** The final review's findings #1 (`or` treats `permissions: {}` as absent) and #3 (test forbids any job-level block) were merged unanswered; both are small. #3 is arguably intended (a job-level block drops the inherited `contents: read`). The third test duplicates the second. State the choice in the test, or relax #3.
- **P3 (A)** Grok returned 0 findings with 5 output tokens in 148 s and DeepSeek 231 tokens in 2 s on a 7.5k-token input; with a clean-looking diff that is plausible, but it is the same pattern as the DeepSeek 0-of-4 on #29. The planted-defect check is still the only proof that they review at all; STATUS has no row for it.

### Audit round 2: `publish.yml`, `tools/publish.py`, `check_paths.py`, `check_tier.py`
Severity B/A/N. Claude Code: B first; do not weaken a control.
- **A1 (B) `tools/tests` is not run in CI.** `40-verify.yml` runs `mvn verify`, `check_workflow_policy.py`, `load_skills.py --check`, acceptance; grep of all workflows finds no `unittest`/`pytest`/`tools/tests`. The path-guard, publish, tier and permissions tests are only as good as someone running them locally. Fix: a step in `static` (`python3 -m unittest discover -s tools/tests -t .`), run from the PR head is fine for a test run, the guard itself is taken from `workflow_sha`.
- **A2 (A, B if it reproduces on ubuntu-latest)** I ran the 54 tests of the four files here (Linux, git 2.34.1, folder mounted from Windows): 53 pass; `test_publish.PublishTest.test_tester_may_not_swap_a_test_for_a_symlink` fails with "Rejected not raised", i.e. publish accepted that patch. Likely the mounted filesystem or the old git (symlink handling in `git apply --index`), not proven. A1 would show it on ubuntu-latest within one run; if it fails there, the guard has a hole.
- **A3 (N) `tester_model`** goes unvalidated into the `Assisted-by:` trailer, but the only caller (`30-build.yml:135`) passes the constant `azure/gpt-5`. Add a `[A-Za-z0-9._/-]+` check in `publish.py` anyway; a newline would forge trailers.
- **A4 (A) R3 widened.** `publish.yml`, the job that holds the App token with `contents: write`, uses `actions/checkout@v4` and `actions/download-artifact@v4` by tag. Only `create-github-app-token` is SHA-pinned. Pin these two first, ahead of the agent actions.
- **A5 (N)** `github.workflow_sha` is trusted because callers run from the default branch (`10-spec` on `issues: labeled`). `30-build` is `workflow_dispatch`, which can run a branch's copy of the workflow (and so its tools) for someone with write access; known from Q27, still worth one line in ADR-0017's neighbours. Also: the builder cannot delete or rename (status D is rejected, `--no-renames`), so a refactor fails closed; document it so nobody loosens the guard.
- **Proven (re-runnable, code read):** guard takes only A/M; rejects symlink/submodule modes, `..`/absolute/backslash paths, case-variant twins, untracked/unstaged leftovers; guard tools come from `workflow_sha`; `check_tier` reads the risk map from the base and floors `tools/`, `.github/`, `factory/`, `.claude/`, `AGENTS.md`, `CLAUDE.md` to red incl. case-folded; branch name regex and commit text come from ROLES, not the agent; no fallback to `GITHUB_TOKEN`; deterministic commit date makes reruns idempotent. **Not proven:** CI enforcement of these tests (A1), the symlink case on Linux CI (A2).

### Waiting for Qun
Nothing new (parked items unchanged).

## Cowork run 2026-11-17 (late): verification of audit-round-2 fixes + Audit round 3
No new numbered questions (QUESTIONS.md unchanged). New since last run: commits `9a1c13f`, `d4dde96` on branch `audit-round2-fixes` (PR #42).

### Verification of Claude Code's claims (code read, not STATUS text)
- **P1 tier default: code present, not closed.** `tools/review.py` `tier_of()` falls back to `check_tier.diff_tier` on the PR's files and to `red` on error; 4 tests claimed. Evidence missing: no CI run of the test suite has passed on this branch yet (see A1). `import check_tier` sits outside the `try`, so an import error crashes the step; that fails the review step (closed), acceptable, but a one-line comment would say so.
- **A1 CI runs tests: code present, not closed.** `40-verify.yml` `static` has `python3 -m unittest discover -s tools/tests -v` (5 min timeout). Run 44150656453 (PR #42, head `d4dde96`) was still `in_progress` when I looked; the green scratch run 44150153906 is on a different branch (`scratch-symlink-diag`). Close A1 and P1 when that run is green and `static` shows the unittest step executing. Note the step runs from the PR head, so it only proves the tests, not that the guard is the master copy (as intended).
- **A2 symlink: explanation plausible, not closed.** Reasoning (`git add -A` in `agent_patch()` reverts an index-only symlink) fits the code; the test now uses a real `os.symlink`; `filesystem_link_violations()` in `check_paths.py` adds an on-disk check. Close with the green run above. Small gap: the on-disk check only covers paths in `changes`; a symlinked *parent directory* is caught for existing files via `resolve()` but not for a deleted/non-file path (those are rejected anyway, status D). Fine.
- **Q59 option (c): built, plausible.** The manifest check compares only the recorded sha256 with the pinned one; it does not prove the ID list belongs to that digest (someone can edit the hash and leave old IDs). Acceptable per Q59 ("stale silently" is what it prevents); note it as N.
- **Q60 (a)+(b): built.** `merged_by` is recorded in `release-record.json` (artifact, 7 days) and the `60-release.yml` header points at ADR-0017. `pull-requests: read` was added to the `build` job (least privilege OK). R4 stays open by design; trigger in ADR-0017.
- Not acted on, still open: A3 (N), A4 (A, pin the two actions in `publish.yml`), A5 (N).

### Audit round 3: `30-build`, `45-fix-round`, `25-dispatch` (+ `tools/create_work_items.py`)
Severity B/A/N. Claude Code: B first; do not weaken a control.
- **R3-1 (B) The WIP limit does not limit concurrent starts.** `create_work_items.dispatch()` counts only *open PRs labelled `agent`*. A dispatched build has no PR for up to ~85 min (tester 25 + builder 60 min timeouts), and within one `--dispatch-queued` loop (or one 20-breakdown run) no PR appears between iterations. With `WIP_LIMIT=1` and 5 queued items, one run starts all 5 builds; the next 25-dispatch tick (30 min) again sees 0 PRs. Effect: model spend and runner use are not bounded as the architecture states. Fix: count in-flight `30 build` runs too (`gh run list --workflow "30 build" --status queued --status in_progress`) and count dispatches made in the same loop; test with a fake `gh`.
- **R3-2 (B) Lost work item on a failed dispatch.** `dispatch()` removes the `queued` label *before* `gh workflow run`; `gh()` uses `check=True`, so a failed dispatch (API error, rate limit) raises with the label already gone: the item is never retried and nothing is labelled. Fix: dispatch first, then remove the label, or re-add it in an `except`. A repeated dispatch is safe because `30-build` skips the tester when `wi-<n>` exists and its `concurrency` group serialises runs.
- **R3-3 (A) Fix-round counter is label-based and racy.** `45-fix-round` counts `round:*` labels on the issue. Two `40 verify` failures that complete close together both read the same count and both dispatch round N+1 (a duplicate build, spend, two publishes on one branch; `concurrency` keeps one pending run and does not deduplicate). A person removing a `round:` label resets the limit. `30-build` `prepare` only checks the `round` *input* (`> 2`), it never counts. Fix: in `prepare`, derive the real round from the issue's `round:*` labels or from the number of builder commits on `wi-<n>` and fail when it disagrees with the input; put `concurrency` on `45-fix-round` per branch.
- **R3-4 (A) Builder tool allowlist `Bash(mvn:*)` is broader than it looks.** `mvn org.codehaus.mojo:exec-maven-plugin:exec -Dexec.executable=...` needs no pom change, and `app/src/main` code or a test runs inside `mvn verify`, all with network access and the step's environment (which includes `CLAUDE_CODE_OAUTH_TOKEN` for the action). Not proven either way whether the CLI hands the token to Bash children. Proof to build: a planted-attack run (work item that asks the builder to print `env`/call an external host) in a scratch branch, or restrict to `Bash(mvn -B -f app/pom.xml verify)` plus `test-compile` (exact commands from AGENTS.md) and set an egress allowlist for the job.
- **R3-5 (A) No cost or token budget per run.** Only `--max-turns 80` and a 60 min timeout bound the builder; AGENTS.md lists a `budget` reason code but no workflow enforces one. Not proven: "budget" can ever trigger.
- **R3-6 (N) Missing `timeout-minutes`** on `authorize`, `prepare`, `builder-record`, the `publish.yml` jobs and `45-fix-round` jobs (default 360 min). A hung `gh`/download step holds a runner for 6 h.
- **R3-7 (N) Verify failures from infra count as a fix round.** Any `failure` conclusion of `40 verify` on a `wi-*` PR triggers a model round, also when the failing step is a network/runner problem. `cancelled` and `timed_out` runs trigger nothing and leave the PR without escalation. Document it or distinguish by failed job name.
- **R3-8 (N) `prepare` falls back to `GITHUB_SHA` as base** for a new `wi-<n>` branch: for a `workflow_dispatch` on a non-default ref that is the branch tip, not master. Known as A5/Q27 (trust of the dispatched ref); add `ref: master` validation (`github.ref == refs/heads/master`) to `authorize` as a cheap fix.
- **Proven (code read, re-runnable by grep):** both entry workflows start with `authorize` from `github.workflow_sha`; top-level `permissions: {}`; agent jobs have `contents: read` only and `persist-credentials: false`; tester/builder hand over patches, only `publish.yml` pushes; builder `Edit`/`Write` limited to `app/src/main/**` (tests and workflows not writable by tool); no WebFetch/WebSearch/`git push` in the allowlist; inputs validated by regex (`issue`, `round`, branch `wi-<n>`); fork PRs excluded in `45-fix-round`; round limit 2 exists in both `45` and `30`; resume after a crash works by design (tester skipped when `wi-<n>` exists, `builder-failed` label, artifacts kept 7 days). **Not proven:** R3-1 to R3-5 behaviour in a real run; resume was not exercised in CI evidence I could see.
- **Skills (Round 8 items):** no change to `factory/skills/**` or `skills.lock.yaml` since the last run (git diff), so nothing new to review before Round 8.

### Waiting for Qun
Nothing new (parked items unchanged).

## Cowork run 2026-11-17 (night): Q62, verification of PR #42 fixes, Audit round 4
New since last run: commits `3073a65`, `9647ab3` on `audit-round2-fixes` (PR #42), Q62 in QUESTIONS.md. No briefs changed. No change to `factory/skills/**` or `factory/skills.lock.yaml` (git diff), so no skill review this run (Round 8).

### Q62 (what must the Semgrep manifest check resist?): (a)
Accept (a). The check stops an honest re-pin from going stale (Q59's problem). It does not claim tamper resistance, and (b) would not buy it either: a PR that edits `40-verify.yml` runs its own edited workflow, so any CI check can be rewritten in the same PR. The only control for `.github/**`, `factory/**` and `tools/**` is the red floor plus human review (CODEOWNERS exists in the repo; "require review from code owners" is a branch-protection setting I cannot see: not proven, parked). Do tighten the comment in `40-verify.yml` and `factory/semgrep-p-java.ids` to say exactly this. No control is weakened: nothing changes.

### Verification of Claude Code's claims (CI evidence, not STATUS text)
- **A1 (CI runs tools tests): CLOSED.** Run 44155222774 (head `3073a65`), job `static`: step "Unit tests for tools/*" executed (52 s) and succeeded; `required` green. Latest head `9647ab3`: run 44161429032 also `success`.
- **P1 (tier default): CLOSED.** `tier_of()` now takes the stricter of label and computed tier, ignores malformed/duplicate labels, scores `previous_filename`, and falls back to `red` on any error including the import (code read at `tools/review.py:422`). Tests run green in the runs above.
- **A2 (symlink test): CLOSED.** Runs 44155222774 and 44161429032 green on ubuntu-latest with the real-symlink test; root cause (index-only symlink reverted by `git add -A`) is consistent with the code.
- **Q59 (c), Q60 (a)+(b), Q61: CLOSED as built.** `release-record` job has its own scope (`contents: read`, `pull-requests: read`); manifest step present in `static` and green. Q61: COWORK-PLAN no longer asserts an enforced commit step. Remaining notes (N): the `[ -n "$merged_by" ]` check can never fire because the jq has `// "unknown"` (harmless); `merged_by` is inert data, R4 stays open by design (ADR-0017).
- **Still open, not acted on:** A3 (N), A4 (A: pin actions), A5 (N), R3-1..R3-8 (Audit round 3). Not re-listed beyond this line.

### Audit round 4: `40-verify` + `tools/acceptance_scope.py` + `tools/acceptance_run.py`
Severity B/A/N. Claude Code: B first; do not weaken a control.
- **R4-1 (A) The scope script runs from the PR head.** Job `scope` checks out the PR head and runs `tools/acceptance_scope.py` from it; only the specs come from the base commit. A PR that edits that script (or `acceptance_run.py`, which runs in the job that holds `ACCEPTANCE_REPO_TOKEN`) is verified by its own edited version. Agent roles cannot write `tools/**` (publish allow globs), so this concerns human/maintainer PRs and rests on red-tier review, same boundary as Q62. Cheap fix that makes the comment "never from the PR head" true: sparse-checkout `tools` together with `docs/specs` in the `base` checkout and run `base/tools/acceptance_scope.py` and `base/tools/acceptance_run.py`.
- **R4-2 (A) Race: scenarios are readable by the app user until the `chmod 700`.** The app (PR code, user `nobody`) is already running when `actions/checkout` writes the private repo with default modes (755/644); the "Hide" step only runs afterwards, and the check after it proves the end state, not the window. A planted app that polls `$GITHUB_WORKSPACE/acceptance` could copy scenarios. Exploitability depends on the runner home/work directory permissions (not proven). Fix: create a mode-700 parent (`install -d -m 700`) before the checkout and check out into it, or check out as a user nobody cannot traverse to. Proof to build: a scratch PR whose app polls and writes what it finds, run once; the check must show nothing.
- **R4-3 (A) No test-quality check.** `app/pom.xml` has no jacoco or pitest; tester-written tests only have to pass. Hidden scenarios are the real gate and `verdict()` handles skipped, error, no-scenario and stale reports correctly (proven by code and by `test_failure_error_and_skipped_are_not_passes`), but nothing shows that a scenario or unit test can fail. Fix options (brief, not now): a mutation or "break the app on purpose" canary run per release of the scenario repo; a coverage floor on the tester's tests.
- **R4-4 (A) No `timeout-minutes` on `acceptance` and no timeout in `Maven._mvn`.** A hung scenario or app holds the job (and the merge queue) up to 6 h with the private-repo token in scope. Add `timeout-minutes: 20` and `subprocess.run(timeout=...)` mapped to `RUN_ERROR`.
- **R4-5 (N) Branch name selects the scope.** `spec/F<n>` gives kind `spec` with no scenarios; nothing in `check_paths.py` ties that branch name to docs-only changes. Agent PRs are safe (`publish.py` allows only `spec/F<n>` and `wi-<n>` and path-guards each role), so this is a human PR hole. Cheap fix: in `scope`, for kind `spec` fail when the PR changes anything outside `docs/**`.
- **R4-6 (N) Base staleness.** Scope reads specs at `pull_request.base.sha` but merged PRs as of now; a work item merged after the base fails closed with "base specs do not define" (false red, never false green). Document, or use the base branch tip.
- **R4-7 (N) Dependence on branch protection.** The single required check is `required`; that it is the only one configured is a setting I cannot see. Parked, not re-listed.
- **Proven (code read, re-runnable by grep/tests):** every error path in `acceptance_scope.py` exits 1 (never an empty scope); `wi-*` with zero ACs fails; the 1000-item list limit fails; scope reaches the job through env, not interpolation (no injection from branch names); `acceptance_run.py` prints only `AC-id: pass|FAIL` and counts, maven output goes to a log under a 700 directory that is never uploaded or printed; `-Dgroups` is an exact tag match (AC-F1-1 does not select AC-F1-10); reports are deleted before each AC so stale XML cannot pass; a fork PR skips `acceptance` and `required` then fails (skipped is not success); egress block for `nobody` is probed in both directions; the app starts before the scenarios exist. **Not proven:** R4-2 and R4-3 in a real run; a failing scenario producing a red `required` was not seen in the CI runs I looked at.

### Waiting for Qun
Nothing new (parked items unchanged).

### Audit round 3: `25-dispatch`, `30-build`, `45-fix-round` (Cowork, 2026-11-17, master `16053c1`)
Read: the three workflows, `tools/authorize.py`, `tools/create_work_items.py`, `tools/build_prompt.py`, `.gitignore`.
- **B1 WIP limit does not hold.** `create_work_items.py` `dispatch()` counts only *open PRs labelled `agent`* (`open_agent_prs`). A dispatched build has no PR for up to 25 + 60 min (tester and builder timeouts), and inside one `--dispatch-queued` loop the count never changes. With 0 open PRs and N queued items, one tick starts all N builds; the next tick (every 30 min) does it again for new items. Fix: count in-flight `30 build` runs (queued + in_progress) plus open agent PRs, and increase a local counter per dispatch. Proof: a unit test with 5 queued items and WIP_LIMIT 3 dispatches 3.
- **B2 `blocked` is never cleared.** `create_work_items.py:58` adds `blocked` to every item with `depends_on`; grep of `.github/` and `tools/` finds no code that removes it or dispatches the dependent when its dependency merges. A multi-item spec (F28 has WI-1..3 with dependencies) will build only the first item. This blocks the architecture's "intent to release without manual workarounds". Fix: on merge of a `wi-` PR, queue items whose dependencies are all closed (a step in 60-release or a small workflow), plus a test.
- **A1 Dispatch is not durable.** `dispatch()` removes `queued` and then runs `gh workflow run` (`check=True`). If the second call fails the item has lost its label and is never retried. Reverse the order, or re-add the label on error. After the build starts, a failed builder only gets `factory:builder-failed`; nothing retries it (round 9, dead letters).
- **A2 45 can start the same round twice.** It reads `round:*` labels, adds `round:N+1`, then dispatches; there is no `concurrency` group, so two verify failures for one branch at the same moment both compute the same `next`. 30-build's group serializes them but does not drop the duplicate (`cancel-in-progress: false`). Add `concurrency: group: fix-${{ head_branch }}`. Also: every `failure` of 40 verify on a `wi-*` PR spends a round, including infra failures (runner, Semgrep download, rate limit), so a flaky run can burn two model rounds and escalate a good change. Consider requiring a failed *build-test*/*acceptance* job rather than any failure.
- **A3 Issue text steers the builder.** `build_prompt.py` takes the work item from the issue's body at dispatch time (marked `<untrusted-issue-text>`, good) and reads the spec from the path named in that body. Anyone who can edit the issue after the plan gate changes what is built; the path guard limits where, not what. Bind the body to the merged `work-items.json`: compare title/AC IDs/paths with the file at the merge commit and refuse on mismatch, or build the issue text from the file.
- **A4 Builder's `Bash(mvn:*)` is arbitrary code execution.** `mvn` runs the builder's own code (tests, plugins; `-D` options reach any plugin already resolvable). The step env holds the Claude OAuth token, and a child process inherits the environment. Q26 decided an egress block with a CI probe, but that applies to the app under test, not to this job. Say in ADR-0009 or the charter what stops exfiltration of `CLAUDE_CODE_OAUTH_TOKEN` from the builder job (egress allow list, or a token scoped to this job only), and prove it with a probe. Not a finding against Q26.
- **A5 New `wi-N` branch is cut from `GITHUB_SHA`**, the sha of the ref that was dispatched. A dispatch from a feature branch makes the work item start from that branch, not from master. Resolve `heads/master` (the default branch) explicitly in `prepare`.
- **N1** `builder-record` checks out without `persist-credentials: false` (every other checkout sets it); `prepare`, `authorize` and others have no `timeout-minutes` (6 of the jobs in all workflows do). `.gitignore` covers `/.claude/skills/`, so `git add -A` does not carry the loaded skills into the patch: fine.
- **Proven (code read):** authorize runs before any model spend, from `workflow_sha` tools; `authorize.py` fails closed with no actor and uses `role_name`; tester and builder jobs hold only `contents: read`, `persist-credentials: false`, no cache; builder tool list is limited (`Edit/Write(app/src/main/**)`, `mvn`, `git status/diff`); one patch artifact is the only hand-over; fix-round limit 2 exists twice (45 by label count, 30 by input, ROUND > 2 → `escalated`); resume works for the common cases (tests published, builder fails → rerun skips the tester because `wi-N` exists; tests not published → rerun redoes the tester). **Not proven:** WIP limit (B1), dependency chain (B2), duplicate rounds (A2); no test covers `dispatch()`.

### Q62 (Semgrep manifest check): (a)
Agreed with the recommendation: the check stops an honest re-pin from going stale; it is not tamper-resistance, and `.github/**`/`factory/**` already need red-tier human review. No code change; the tightened comment in `40-verify.yml` is enough. Do not build (b).

### Verification of Claude Code's fixes on branch `audit-round2-fixes` (PR #42, head `bd69859`, read from the working tree and GitHub, 2026-11-17 evening)
- **Round 2 A1 (tools/tests not in CI): fixed on the branch, not closed until #42 merges.** `40-verify.yml` `static` now runs `python3 -m unittest discover -s tools/tests -v`; PR #42's checks (run 44165783900: `static`, `build-test`, `acceptance`, `scope`, `required`) are green on ubuntu-latest, so the 54-test set passes there including the symlink test (A2 not reproduced in CI; the earlier failure was my VM).
- **P1 (tier defaulted to amber): fixed on the branch.** `tools/review.py` `tier_of()` computes the tier from the PR's file list with `check_tier` against the master risk map, takes the stricter of that and the label, ignores malformed/duplicate labels and falls back to red on any error. Tests added (`test_review.py`, +57 lines). Closes when #42 merges; the 50-review comment on #42 itself should say "tier: red".
- **Heads-up (process):** Claude Code works in the same folder as these runs and had uncommitted edits (`60-release.yml`, `check_paths.py`) while I read. I only read them; my writes are limited to `collab/`, `docs/adr/`. Not a finding, but a merge conflict risk on `collab/ANSWERS.md` if both write at once.

### Audit round 4: `40-verify`, `acceptance_scope.py`, `acceptance_run.py` (Cowork, 2026-11-17, master `16053c1` plus the #42 diff)
- **B1 Acceptance is skipped by branch name.** `acceptance_scope.py` decides the scope from the head branch alone: `spec/F<n>` returns an empty scope (checks only the head `work-items.json`/`spec.md` IDs), and `40-verify`'s "No ACs in scope" step passes for every kind except `wi`. Nothing checks that a `spec/*` PR touches only `docs/specs/F<n>/**` and `docs/adr/proposed-*.md`. A branch named `spec/F9` that also edits `app/src/main/**` merges with no hidden scenario run; the agent path (publish guard) is safe, a hand-made PR is not. Fix: for `kind=spec`, list the PR's files and fail if any is outside those two globs (use the same glob compiler as `check_paths.py`), plus a test.
- **B2 The Maven cache bridges agent code and the scenario repo.** `build-test` runs `mvn verify`, so agent-written code and tests execute there as the runner user, and `setup-java` with `cache: maven` saves `~/.m2` at the end of the job. The `acceptance` job (which then checks out the private scenarios and holds `ACCEPTANCE_REPO_TOKEN`) uses the same `cache: maven` and restores it, because a PR-scope cache with the same key is visible to later jobs of the same run. The comment in `30-build.yml` ("No Maven cache: an agent job could have written into the default branch's cache scope", Q10) covers the default-branch scope but not this path. There is also no default-branch cache to hit: `40-verify` runs on `pull_request` and `merge_group` only, and `60-release` builds without cache, so each PR starts cold and `build-test` saves. A poisoned plugin or dependency jar in `~/.m2` then runs in the `acceptance` Maven calls as the runner user, with `acceptance/` (mode 700, owned by the runner) readable and egress open for that user, or its output printed to the public log. Not proven exploitable (Maven's local-repo metadata, checksums); the trust boundary is still wrong. Fix: drop `cache: maven` from `acceptance`, or restore in `acceptance` from a cache key written only by a trusted job. Proof: a policy rule in `check_workflow_policy.py` that fails when a job with `ACCEPTANCE_REPO_TOKEN` (or `needs` a job that runs agent code) uses `cache:`.
- **A1 Issue titles define the scope.** `--issues` comes from `gh issue list`, and `work_item_key` maps issue number to `F<n> <id>` by parsing the title. Anyone who can edit issue titles (triage/write) can retitle work-item #12 to another work item's key, so #12's PR must pass only that item's ACs; a nonexistent key fails closed, an existing one does not. Source the mapping from something a person cannot edit afterwards (a bot-written marker plus a check that the last editor is the bot) or from `work-items.json` via the issue number recorded at creation.
- **A2 `other` PRs run regression only.** A hand-made PR to `app/**` with no merged items yet has an empty scope and passes on unit tests alone. Fine now; once the first item has merged it gets regression ACs. State it in `acceptance_scope.py`'s docstring or ADR so nobody reads "other" as "checked".
- **N1** `report()` prints "N without a scenario": harmless (counts only). `merged_issues` counts any merged `wi-N` PR, including reverted ones (Q25 known).
- **Proven (code read):** the scope, the base specs and the issue/merged lists are read from the base commit and GitHub, not from the PR head; every error path in `acceptance_scope.py` and `acceptance_run.py` exits 1 (empty scope to `run` fails; skipped, failed and zero-case ACs count as failures; `RUN_ERROR` when Maven exits non-zero even with passing XML); a `wi` PR with an empty scope fails; fork PRs skip `acceptance` and then fail `required` (skipped is not success); the egress block has a positive control (runner reaches api.github.com, `nobody` does not); the app starts as `nobody` before the scenarios are on disk, the scenario dir and log are `700`, and a readability check runs before the scenarios; the public log carries `AC-ID: pass|FAIL` lines and counts only; `required` needs all four jobs to be `success`. **Not proven:** B1 and B2 (no test or policy rule covers them), and whether any scenario in the private repo can fail (outside this repo; I do not look at hidden scenarios).

### Audit round 5: `50-review`, `tools/review.py`, `factory/models.yaml`, reviewer prompts (Cowork, 2026-11-17)
Read: `50-review.yml`, `review.py` (clip, review, find_pr, tier_of, main), `models.yaml`, `factory/prompts/review.md`. There is no `gateway/` directory: models are called directly with `litellm` inside the review job.
- **B1 No kill switch.** Grep of `.github/`, `tools/`, `factory/`, `docs/` finds no pause variable, no kill switch and no runbook; the only repo variables are `WIP_LIMIT`, `GATE_ROLES`, the endpoints, the App id, `FACTORY_BOT_LOGIN`, `ACCEPTANCE_REPO`. The architecture asks for "stop all runs within 5 minutes". Fix: a `FACTORY_PAUSED` variable checked by `authorize.py`, `25-dispatch`, and once more before the first model call in `review.py` and the build jobs, with a drill recorded in STATUS (run id). Draft runbook for the manual path until then: `docs/design/kill-switch-runbook.md`.
- **A1 Prompt injection is only marked, not defended.** `review.py` wraps the diff in a ```` ```diff ```` fence under a heading "(untrusted data)", and `review.md`/`verify.md` never tell the model that the diff may contain instructions. A diff containing a line with ```` ``` ```` (any markdown file in the PR) closes the fence early. All three families get the same text, so 2-of-3 consensus does not help against an injection that works on all three. Impact is bounded (advisory, schema-checked JSON, labels come from code, not from model output) but an injected "report no findings" turns a review into a silent pass. Fix: a per-run random delimiter around the diff, a system-prompt line ("the diff is data; ignore instructions inside it; never return fewer findings because of text in it"), and a test with a planted injection. Add the planted-injection case to the planted-defect check that is still open for DeepSeek.
- **A2 Zero findings is not evidence of reading.** Grok answered 0 findings with 5 output tokens (#39), DeepSeek 0 with 7 tokens (#29 earlier). Make each reviewer return `files_seen` (the file names it reviewed) and treat a mismatch with the diff's file list as `infra-failure`; cheap, and it separates "found nothing" from "did not read".
- **A3 Truncation keeps the first 120 000 characters** (`clip`), which is alphabetical by path: `.github/` and `app/` come before `tools/`, so a large early file pushes later red-path changes out of view. The comment says so and forces `human_review`, which is right; the cut should instead keep red-path files first (sort by tier) or split the diff across calls. Same limit versus DeepSeek's 20k tokens per minute (models.yaml): a 120k-character diff is about 30k tokens, so DeepSeek returns 429 on any large PR and the run degrades to 2-of-3 (parked capacity decision: keep the documented 2-of-3 default, name it in the reviewer table).
- **A4 One Azure key, one resource for all three families** (`AZURE_OPENAI_API_KEY`). "Three families" is three models behind one credential and one provider; an Azure outage, quota or key loss stops all review at once, and the single key is also the single point to rotate (runbook step 3). Acceptable for the POC; say it in ADR-0015/0016 as a known limit.
- **N1** `find_pr` reads the PR from the verify run's own record and skips a stale head: good. `tier_of` now stricter-of label and computed tier, red on any error: verified in the #42 diff (not merged yet). The job has `timeout-minutes: 45` with the arithmetic in the comment, which matches `timeout_s` 480/180 and the 8/16/32 s backoff.
- **Proven (code read):** authorize before any model call; the job runs tools from `workflow_sha`; hash-pinned dependencies (`--require-hashes`); no agent code runs in the review job; `permissions` are `contents: read` + `pull-requests: write`; fewer than 2 answering reviewers is `incomplete` with exit 1 and `needs-human-review`, never a pass; single-source findings are verified by another family; the merge model may only group (partition check, mechanical fallback); a 429 honours `Retry-After` capped at 60 s. **Not proven:** kill switch (B1), injection resistance (A1), that a reviewer actually read the diff (A2), planted-defect result for DeepSeek.

### Audit round 6: `check_workflow_policy.py` rule coverage vs ADRs 0002-0016 (Cowork, 2026-11-17)
28 rules read (names and the code of the maven-cache, model-budget and agent-job rules). Mapping: ADR-0004 → `push_and_pr_only_in_publish`, `publish_uses_only_the_pinned_app_token`, `publish_callers_pass_the_app_explicitly`; 0006 → `tools_after_agent_code_come_from_workflow_sha`; 0007 → `verify_acceptance_fails_closed`, `verify_required_needs_every_job`, `verify_blocks_app_egress_before_it_starts`; 0008 → `model_jobs_need_authorize`, `build_dispatchers_are_authorized`, `workflow_run_jobs_require_a_same_repo_head`, `no_pull_request_target`; 0009 → `pip_installs_are_hash_pinned`, `no_unpinned_tool_runners`, `gitleaks_runs_from_the_pinned_image`, `semgrep_runs_pinned_and_offline`; 0012 → `agent_steps_follow_load_skills`, `no_plugin_installs`, `no_workflow_loads_pending_skills`; 0015/0016 → `NON_MODEL_SECRETS` (deny by default), `agent_secrets_only_on_the_agent_step`.
- **B1 `.yaml` workflows are invisible to the policy.** `main()` loads `root.glob("*.yml")`; GitHub runs `*.yaml` too. A new `.github/workflows/x.yaml` with a model key, `pull_request_target` or a push step passes `check_workflow_policy.py` (`40-verify` `static`). It is a red-tier path, so a human review is the only other control, which is what the policy exists to back up. Fix: glob both extensions (or fail when any `*.yaml` exists) and add a test with a `.yaml` file that violates a rule. Same for `.github/actions/*/action.yml`: none exist today; add a rule that forbids local composite actions or checks their steps.
- **B2 The agent rules apply only to the two known actions.** `agent_jobs()` selects jobs via `is_agent_job`, which keys on `AGENT_ACTIONS = (claude-code-action@, codex-action@)`. A job using any other agent or model action (or `npx`/a script calling a model) gets `authorize` only if it reads a non-`NON_MODEL_SECRETS` secret, and none of the read-only-permission, no-persisted-credentials, no-cache, transcript or trusted-tools rules. Make it deny by default: allowlist `uses:` (`actions/*`, the pinned app-token action, the two agent actions, local `./`) and fail on anything else, with a test.
- **A1 Maven cache rule is file-level, not job-level** (`MAVEN_CACHE_FILES = {40-verify.yml, 60-release.yml}`), so it does not cover round 4 B2 (the `acceptance` job restoring a cache the agent-executing `build-test` saved). Add: a job that reads `ACCEPTANCE_REPO_TOKEN`, or `needs` a job that runs agent code, must not use `cache:`.
- **A2 No rule pins `uses:` to a commit SHA** except the app-token action (`APP_TOKEN_ACTION`). ADR-0009 says "pin everything a gate depends on"; `checkout@v4`, `download-artifact@v4`, `claude-code-action@v1` and `codex-action@v1` (the last two run with model keys) are tags. This is audit R3 and round 2 A4. Fix in two steps: SHA-pin the two agent actions and the two actions in `publish.yml`, then add the rule for all `uses:` with the pin comment style already used for the app-token action.
- **A3 ADR-0011 has no policy rule.** "Model secrets live in a master-only environment": no job that reads a model secret declares `environment:`, and no rule would notice if the snapshot repo drifted. Once the repo is flipped and the environment exists, add a rule that every model-secret job names the environment. (Parked: the snapshot is Qun's.)
- **A4 ADR-0010 did not match the code.** It says the tester is a LiteLLM loop with no transcript (brief 013), but `30-build.yml` runs `codex-action`, whose stderr transcript reaches the log. I changed the ADR status line to say "not built yet, interim codex-action" (docs/adr is mine). Q28/Q37 decisions on the transcript stay parked.
- **N1** `PUSH_OR_PR` is a regex over `run:` text (`git push`, `gh pr create|edit|merge|review`): `git -C x push`, `gh api -X POST .../pulls` or a Python `subprocess` pass it. The real control is the read-only token (`agent_job_has_read_only_permissions`), so this is a lint, not a boundary; say so in the rule's comment. ADR-0002, 0005, 0013, 0014 are enforced elsewhere (bootstrap/rulesets, `check_paths`/`check_tier` tests, `60-release`), not by this file; fine.
- **Proven:** `RULES` has 28 entries; each reads parsed YAML, deny-by-default on secrets (`NON_MODEL_SECRETS`), and `run_scripts_hold_no_expressions` blocks `${{ }}` in `run:`. **Not proven:** that every rule has a failing-case test (I did not open `test_check_workflow_policy.py`); B1/B2 are gaps no test covers.

### Audit round 7: charters and prompts vs the architecture (Cowork, 2026-11-17)
Read: `factory/charters/{builder,tester,review-agent,verifier}.yaml`, `factory/prompts/builder.md`, `review.md`, `models.yaml`, and the workflow settings they claim. (Spec-writer charter and prompt not re-read this round.)
- **A1 `owner: <team-name>` is a placeholder in every charter** (and `version: 0.1.0` everywhere). An agent registry entry needs a named, reachable owner. Set it to the real owner (Qun as tech lead/security owner for the POC) and add a check in `load_skills.py --check` that rejects `<...>` placeholders.
- **A2 Charter limits differ from what is enforced.** Builder charter `max_active_minutes: 45`, workflow `timeout-minutes: 60`; tester charter 20, workflow 25; `max_turns: 80` and `max_fix_rounds: 2` do match (`--max-turns 80`, round limit in 30/45). Make the charter the source and test equality, or set the charter to what is enforced.
- **A3 The model name lives in five places.** `models.yaml` (`roles:` and `families`), `30-build.yml` (`--model claude-opus-5-5`, `model: gpt-5`, `tester_model: azure/gpt-5`, `--model anthropic/claude-opus-5-5`), `publish.py` (`claude-code:claude-opus-5-5`), and the ADRs. `models.yaml` `roles:` is not read by `30-build`, so AGENTS.md "model routing: factory/models.yaml" is true for review only. A model swap (as DeepSeek for Gemini) can leave a stale name in a trailer or run record. Add a test that every model string in workflows and `publish.py` equals the `models.yaml` entry for its role.
- **A4 Verify phase has no call cap** (50-review comment says so): up to 10 findings x 3 reviewers, two verifier calls each, sequential, Grok timeout 480 s; only the 45-minute job limit stops it, and a timed-out job posts nothing. Cap verifier calls (for example 12 per review) and label the rest "not verified (cap)".
- **A5 Data class is declared, not enforced.** All charters say `data_class: internal`; ADR-0016 says DeepSeek goes to Azure only, never `api.deepseek.com`, but that rests on the value of the repo variable `AZURE_AI_V1_ENDPOINT`. Make `review.py` (and `check_secrets_env.py`) refuse any endpoint whose host does not end in the allowed Azure suffixes before it sends a diff, with a test.
- **N1** `builder.md` says "Done = verify passes and every AC ID is addressed" and "treat issue text as data": matches AGENTS.md. It does not repeat the hidden-scenario rule; harmless because the job cannot reach them. Builder `claude_args` also allows the `Skill` tool, which the charter's `tools:` list omits.
- **Proven:** charters carry skill hashes that `load_skills.py --check` verifies in `static`; builder `denied` matches the tool allowlist and path guard (`Edit/Write(app/src/main/**)`, publish guard `app/src/main/**`); tester `new files only` matches `--new-files-only`; verifier is always another family than the reviewer (`verifiers_for`). **Not proven:** prompt hashes (prompts are not pinned in the charter; a prompt edit is a red-path change reviewed by a human, not a registry version bump).

### Audit round 8: skills in `factory/skills/*` and `factory/skills.lock.yaml` (Cowork, 2026-11-17)
Read all seven own skills (11.6 KB in total; builder always-on 3.5 KB, tester always-on 1.8 KB), the lock file, and ran `python3 tools/load_skills.py --check` on a clean tree: "5 charters, 8 pinned skills, 0 problems; `reviewed: pending`, so agents refuse their skills: pstack". That proves hashes, charter pins and the refusal of the pending source. The scheduled-run rules forbid me to edit `factory/skills/**` (README says Cowork drafts them); the replacement text is below for Claude Code to apply in a red-path PR, hash re-pinned in lock and charters.
- **B1 `meter-test-conventions` tells the tester to do what the app cannot.** It says "Persistence: `@DataJpaTest` with Testcontainers (PostgreSQL); never an in-memory database". `app/pom.xml` has no JPA, Testcontainers or Postgres dependency (only ArchUnit as test extra besides the starters), the store is in memory (verify-meter: "Readings live in memory"), and a new dependency is a protected change the tester cannot make. A tester that obeys writes tests that do not compile; one that doesn't obey breaks the skill. Replace the bullet with: "Persistence: the service keeps readings in memory today; test the store through its public methods. A real database test appears only after a work item adds a database and its dependency."
- **A1 `minimal-change` contradicts the run-summary contract.** Skill: "End with at most two lines". `builder.md` and AGENTS.md require changes mapped to AC IDs, verify result, open questions, reason code. The model follows one or the other. Replace the section with: "## Summary\nIn the run summary (format in builder.md), keep the part about what you left out or did not verify to two lines."
- **A2 `meter-test-conventions` names tests `ac<N>_...` (e.g. `ac2_...`)**, but AC IDs are `AC-F<feature>-<n>` and unique across features (spec-writer prompt, `acceptance_scope`). `ac2_` collides between features and cannot be traced to an ID. Replace with: "Name each test `acF<feature>_<n>_<behaviour>` after its AC ID (AC-F28-2 -> `acF28_2_rejects_reading_older_than_previous`) and add `@Tag("AC-F28-2")`."
- **A3 `test-behaviour` has no red-first step** ("tests that cannot fail", round 4). The tester charter says "failing tests ... before any implementation" and has `mvn test` as a tool. Add as step 7: "Run `mvn -B -f app/pom.xml test` and confirm every new test fails on an assertion about the behaviour, not on a compile or setup error. A test that passes before the implementation exists proves nothing; fix or drop it."
- **N1 `verify-meter`** (lock comment "awaiting Cowork's review"): reviewed, OK as interactive-only (it is in no charter and `--check` refuses it there). Fix the hard-coded `meter-service-0.1.0.jar` (use `app/target/meter-service-*.jar`) so a version bump does not break it. The lock comment can say "reviewed by Cowork 2026-11-17".
- **N2 `spec-shape`** is lean and consistent with the spec-writer prompt (which carries the `AC-F<issue>-<n>` rule). The zero-context readiness check (goldfish, COWORK-PLAN) is not added here; later brief.
- **Lean and no overlap, checked:** no skill repeats the prompts except `builder.md` restating "edit only app/src/main, never change tests/pom" which the skill's Tests section also says (N, leave). References resolve: `ArchitectureTest` exists, `docs/adr/index.md` exists, `features/` exists for verify-meter, the vendored `create-verification-skill` has its `LICENSE`. **Not proven:** that the skills improve outcomes (Q38 eval of setups A-C was run in brief 010; this round did not re-run it).

Correction to Audit round 5: `factory/gateway/litellm-config.yaml` exists (I looked for `gateway/` at the repo root). It is the "phase 2" LiteLLM proxy config (one virtual key per run, provider keys only in the gateway, budgets via a database). It is not used by any workflow today, so the review job and the tester still hold or reach the Azure key directly; the kill-switch (B1) and single-key (A4) findings stand, and the gateway is where a per-run budget and a central stop would live once built.

### Audit round 9: architecture gaps (Cowork, 2026-11-17)
Read: `tools/run_record.py`, its call sites, retention settings, `factory/golden/`, `tools/skill_eval.py` header, `factory/gateway/`, and a grep for sweep/reconcile/golden in workflows and tools.
- **B1 Run records do not outlive 7 days.** `run_record.py` writes `run-record.json` and a workflow uploads it as an artifact with `retention-days: 7`; the policy rule `artifacts_expire_within_a_week` forbids more. The architecture's "done when" asks for a verified run record per agent run, and `Factory-Run:` trailers point at run ids whose records have expired a week later (`check_run_records.py` only checks the trailer exists). A trusted job should append each record to a durable store the factory can write but agents cannot (a `run-records` branch written by `publish.yml`, a release asset, or an issue comment), with the trailer carrying the record's hash.
- **A1 Record coverage and content.** Records exist for spec-writer (`10-spec`), builder (`30-build`), review (`50-review`, a different schema) and release; **the tester writes none**. `10-spec` calls `run_record.py` without `--status`, so every spec-writer record says `reason: unknown`. Models are hard-coded strings in the call (round 7 A3). No tokens, cost, start time or duration, tier, tool-call count or data class in the record (review's table has tokens, the record does not). Add `started_at`, `tokens_in/out` (where the action reports them), `tier`, `data_class` from the charter, and one schema for all roles.
- **A2 No cost per accepted change.** Nothing sums model spend per work item or per merged PR; the review table has tokens, the builder and tester have none. Until records are durable (B1) this cannot exist. Define it once: tokens x price per run, summed over a work item's runs, divided by merged work items per week; report it in STATUS weekly by hand first.
- **A3 Dead letters and reconciliation.** The only periodic job is `25-dispatch`. Labels `factory:builder-failed`, `escalated`, `infra-failure`, `needs-human-review`, `blocked` and `queued` have no owner or age limit: nothing lists work items stuck in one for more than 48 hours, a `wi-N` branch without a PR, or an issue with `queued` and no run. Build a daily read-only sweep that writes one "factory health" issue (or step summary) with those lists; together with round 3 B2 (`blocked` never cleared) this is the main reason an item can stall unnoticed.
- **A4 Golden set is G001 only and not a gate.** `factory/golden/G001` (task + acceptance test; its ACs use the old `AC-1` form) is used by `tools/skill_eval.py` by hand; no workflow runs it, and no change to `factory/**` (prompts, skills, models, charters) triggers an evaluation. P10 asks for one per factory-config change. Smallest step: a manual `workflow_dispatch` that runs G001 once with the current config and stores the pass/fail and token count in the run record; later add two more tasks (a red-tier refusal and a prompt-injection case, round 5 A1).
- **A5 Data-class labels are static.** Charters say `data_class: internal`; prompts, run records and review comments carry no label, and nothing checks that what goes to a model matches the class (round 7 A5: endpoint host check).
- **N1 R4 / separation of duties:** accepted gap, ADR-0017 (proposed); `merged_by` recording agreed in Q60 (b), not built yet.
- **Proven today:** run records exist per run for 4 of 5 roles with charter, prompt and skills-lock hashes (strong for traceability while they last); `Factory-Run` trailers are checked on release; one amber item reached staging (#25). **Not proven:** durability of records, cost metric, reconciliation, evaluation per config change, any production deploy (`60-release` deploy steps are placeholders, R6).

### Cowork status after round 9 (2026-11-17)
All nine audit rounds are done. Order for Claude Code (B first, one PR each, proof per step): (1) round 4 B1 (spec branch must touch only spec paths) and B2 (no Maven cache in the job that holds the scenario token) + policy rule; (2) round 3 B1 WIP limit and B2 `blocked` chain; (3) round 5 B1 kill switch with a drill; (4) round 6 B1/B2 (`.yaml` workflows, deny-by-default `uses:`); (5) round 9 B1 durable run records; (6) A items by theme. #42 merges first (it closes round 2 A1 and P1). Waiting for Qun: nothing new (parked items unchanged).

### Re-verification run 2026-11-18 (Cowork; STATUS + git diff since `5f7cb40`, HEAD `7856add` on `audit-round2-fixes`; no new QUESTIONS items)
Nothing new in QUESTIONS.md (hash unchanged); no new numbered question to answer. New in STATUS: brief 013 (PR #45, merged to master) and the #42 reconciliation merge. All nine audit rounds were already ticked, so this run re-audits only what changed (brief 013).

**Verified against code (not STATUS text)**
- `30-build.yml`: no `codex` string left; tester step runs `python3 tools/tester_loop.py` with `AZURE_OPENAI_API_KEY` only on that step; hash-pinned pip install; `tester-record` job takes `run_record.py` from `$WORKFLOW_SHA`; `persist-credentials: false` on all checkouts; `timeout-minutes: 25` on the agent job.
- `python3 tools/check_workflow_policy.py` on this branch: `30 rules, 9 workflows, 1 issue forms, 0 violations` (matches STATUS). Not run by me: pytest (not installed on the device), so the "271 / 275 passed" claims are STATUS text only; CI run id is not cited.
- `tester_loop.py`: write limited to new files under `app/src/test/**`, mvn allow-list is exact (`test-compile` or one `-Dtest=<name>`), key removed from the mvn child env. Matches the brief.
- Brief 013 AC3 (live run, canary grep) is **not proven**: STATUS says so itself; blocked on Actions billing (parked).

**Findings (Brief 013 tester loop)**
- **A1 read_file/list_files follow symlinks.** `validate_read_path` only checks the string (`unsafe()`), then `(repo_root / path).read_text()`. The tester checks out the builder's branch, and the symlink ban lives in `check_paths.py` at publish time, i.e. after the tester has run. A builder-committed symlink (`app/src/test/x -> /proc/self/environ`) lets the model read the tester's own environment, including `AZURE_OPENAI_API_KEY`, into the transcript/model context. Fix: in `read_file`/`list_files` resolve the path and require `resolve()` to stay inside `repo_root` and refuse `is_symlink()` on any component (same fail-closed idea as `check_paths.py` lines ~117-135); add a test with a planted symlink. This is a code change for Claude Code, not for me.
- **A2 The env scrub does not protect the key from code run by mvn.** `run_mvn` strips the key from the child env, but the child runs builder-authored and tester-authored Java as the same Linux user, which can read `/proc/<parent pid>/environ`. Decision 6 therefore only holds if the job has no outbound network during mvn (round 3 covered egress for `30-build`; confirm the tester job is covered too) or the key is passed some other way (a file descriptor, or the Python process reads it into memory and deletes it from `os.environ` before spawning). State in ADR-0010 which of the two is relied on.
- **N1** `list_files` on `.` returns the whole tree (rglob) with no cap; token/cost risk only. `MAX_TURNS=60` is a backstop, fine.
- **N2** `agent_job_steps_do_not_print_the_transcript` is a pattern rule (`cat` of `*transcript*`); `tee`, `python -c print` or `less` are not covered. Acceptable as a tripwire; the real proof is the canary run (AC3).

**#42 / R items**
- #42 reported `MERGEABLE/CLEAN` at `7f3f98b`; I did not see a merge to master yet, so R2 A1 and P1 stay **open** (closing needs the merge commit + one CI run). The stash on master (`stash@{0}`, duplicate Cowork pass) is harmless; drop it after #42 merges, as Claude Code planned. Working tree is clean.
- Order for Claude Code unchanged from 'Cowork status after round 9'; add A1 above as a small PR before the first live tester run, because that run is the first time the key and untrusted branch content meet.

**Waiting for Qun**: nothing new (parked items unchanged).

### Re-verification run 2 2026-11-18 (Cowork; HEAD `d5735d8` on `brief-013-a1-symlink`; no new QUESTIONS items, hash unchanged)
New since last run: PR #42 merged (`0c5fb0e`), and Claude Code's A1 fix `d5735d8` (STATUS "Brief 013 A1 fix"). Skills (`factory/skills`, `factory/skills.lock.yaml`, `vendor/`): no diff since the last run, so round 8 stands (`pstack` stays `reviewed: pending`; `create-verification-skill` stays `use: interactive`).

**Verified against code**
- **Brief 013 A1 (symlink read): fix correct on the branch, not closed.** `resolve_contained()` in `tools/tester_loop.py` refuses a direct symlink, resolves with `strict=True`, requires `relative_to(root)`, fails closed on `OSError`. `read_file` and `list_files` both go through it; `list_files` skips symlink and escaping entries. Matches my finding. Missing for closure: PR not opened yet, and 4 of the 5 new tests skip on the Windows checkout, so they have not run for real. Close when the PR's ubuntu CI run shows them passing (cite the run id). N1: a symlinked file inside the repo that points to another in-repo file is also refused (stricter than needed, fine).
- **Brief 013 A2 (key readable by mvn child): honestly recorded as open** in ADR-0010 (Consequences + Re-evaluation Triggers). Agreed. It is the same item as round 3 "egress for 30-build". Cheapest fix that needs no egress block: in `tester_loop.py` read the key once into a variable and `del os.environ[...]` before spawning mvn (the child then has no key in the parent's `/proc/<pid>/environ` either). Code change for Claude Code; keep the ADR trigger until done.
- **R2 / round 2 A1 (tools/tests in CI): closed.** Evidence: `40-verify.yml` line 37 `python3 -m unittest discover -s tools/tests -v` present on this branch; PR #42 checks green in run 44165783900 (ANSWERS line 634); merge commit `0c5fb0e`. Caveat: I did not see a CI run on the merge commit itself.
- **Round 2 P1 (tier default): closed.** Evidence: `tools/review.py` `tier_of()` (falls back to `check_tier.diff_tier`, `red` on error) plus `tools/tests/test_review.py` (+57 lines) merged in `0c5fb0e`, run under the same green CI run.
- **R4: still an accepted gap** (ADR-0017, Q60). **R1, R3, R5, R6: still open**, untouched in this diff.
- **Brief 019 (PR feedback loop): not built.** Brief and merge #32 exist; no revise workflow in `.github/workflows/`, no `tools/pr_feedback.py`, no STATUS row. State: todo.
- Not run by me: pytest (not installed on the device); the "272 passed, 6 skipped" claim is STATUS text only.

**Audit round 10 (small, changed-code only: `tester_loop.py` + ADR-0010)**
- **N1** `resolve_contained` and `list_files` check symlinks at read time only; a builder could swap a file between check and read (TOCTOU), but the tester job has a single process and no concurrent builder, so negligible.
- **N2** ADR-0010 header now says "built", while AC3 (live canary run) is not proven and blocked on billing (parked). Suggest wording "built; AC3 live proof pending" so the ADR does not overstate.
- **A3** Order of work unchanged: A1 PR first, then A2 (`del os.environ`), then round 4 B1/B2.

**Waiting for Qun**: nothing new (parked items unchanged).
