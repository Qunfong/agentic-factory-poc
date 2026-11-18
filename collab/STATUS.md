# Status (maintained by Claude Code)

Work order (Qun, 2026-11-11, updated with ANSWERS Q2/Q5/Q7+Q9):
004 → 005 / 006 → 007 → 009 → all merged into `master` → **fresh-repo snapshot** (Q7+Q9: archive this repo, new private repo with one root commit, pre-publish scan, recreate vars/secrets) → **Qun flips the new repo to public** → 008 `--apply` → 003 → 001 → 002.

The code for 008 can be written any time. Only `--apply` waits for the flip, because rulesets return 403 on a private free repo.

| Order | Brief | Branch | State | What changed | Evidence |
| --- | --- | --- | --- | --- | --- |
| — | Q5 master setup | master | done | `master` pushed from `155dc19` (the one authorised push), set as default; PRs #1 and #2 target `master` | `gh api repos/Qunfong/agentic-factory-poc --jq .default_branch` → `master` |
| — | Phase 0: bootstrap scripts, .gitattributes, design review | phase-0 | review | `tools/bootstrap.{sh,ps1}` (dry run by default), `docs/review/2026-11-10-design-review.md` | PR #2. Dry runs match; `bash -n` and the PS parser are clean |
| — | Collab setup | collab-setup | review | Cowork files, ANSWERS Q1–Q6, briefs 004–008 | PR #1 |
| — | Collab plan | collab-plan | review | Briefs 007/008 updated with Q4/Q6, new brief 009, this STATUS, QUESTIONS Q7–Q8 | Stacked on collab-setup |
| 1 | 004 factory-bot App + token isolation | brief-004 | review | `publish.yml` (App token, the only push/PR path); 10-spec and 30-build split into prepare → agent (read-only, no cache) → publish; `tools/publish.py` (role table, boundary parsing, guard from base, idempotent commits); `tools/check_workflow_policy.py` run in 40-verify; Q10–Q12 | 15 unit tests pass locally (`python -I -m unittest discover -s tools/tests`); grep checks pass; policy check over real YAML runs in the PR's 40-verify; no live factory run yet |
| 2 | 005 path guard + risk tier | brief-005 | review | Guard diffs the index against an explicit base (A/M only, no links, HEAD pinned, case-sensitive glob, `..` rejected); tier = max over matching rules with a red floor for `tools/`, `.github/`, `factory/`; guard tools come from `job.workflow_sha`; spec writer narrowed to its charter in publish and in its tool list; `python3 tools/*` agent permission removed; Q17-Q21 | 56 tests OK, 2 skipped (fs symlink privilege, pyyaml); policy over combined workflows (SnakeYAML) 0 violations; bypasses shown red on old code |
| 2 | 006 workflow injection | brief-006 | review | No `${{ }}` inside any `run:` (event values via env); 45/50 act only on same-repo `wi-<n>` heads; review.py finds the PR by head sha; gate check `grep -Fxq`; 3 new policy rules; actionlint 1.7.12 (sha256-checked) in 40-verify; Q13-Q16 | 18 unit tests pass; policy over real YAML (via SnakeYAML) 24 violations at 8297d66, 0 at head; grep and multi-line scan find 0; actionlint first runs in CI |
| 3 | 007 verify fail-closed + AC scope | brief-007 | review | New `scope` job (scope from base specs + GitHub's merged-PR record; spec PRs check AC IDs); acceptance runs once per AC with `-Dgroups`, prints only `AC-F<n>-<k>: pass|FAIL`; app starts as `nobody` before scenarios are on disk; missing repo/token, unhealthy app, no scenario, run error all fail; `required` needs every job; 2 new policy rules; example repo tagged; Q23-Q26 | 86 tests OK; policy 14 rules, 0 violations; scope, run and failure paths proven against the real app locally; first CI run pending |
| 4 | 009 public-repo hardening | brief-009 | review | `authorize` job (actor and triggering actor must be maintain/admin or the factory bot) before every agent job; 4 policy rules (authorize, retention ≤ 7, trusted tools via `github.workflow_sha`, quiet transcripts); run records in their own jobs; `tools/prepublish_check.{sh,ps1}`; bootstrap sets fork-PR approval, private vulnerability reporting, Discussions off, `FACTORY_BOT_LOGIN`; `SECURITY.md`; Q27–Q30 | 105 tests OK (2 skipped, pyyaml); policy 17 rules, 0 violations; prepublish pass/fail proven on fixtures in both shells with the pinned gitleaks image; bootstrap dry runs show the calls; real scan runs on the snapshot repo (Q7+Q9) |
| 5 | 008 bootstrap for personal account | brief-008 | review | Personal-account mode (owner-type detection, logins for teams); two rulesets: `factory-default-branch` (deletion, no force-push, required check, merge queue unless `--no-merge-queue`, never bypassable) and `factory-default-branch-review` (review rule only; `--admin-bypass-via-pr` adds the admin role, PR-only); `--allow-self-review` for production; plan check before any write; read-back of each ruleset's bypass; `factory:builder-failed` label; publish on `client-id` (`FACTORY_APP_CLIENT_ID` var set); CODEOWNERS `@Qunfong`; `master` triggers; ADR 0002; Q31–Q33 | 111 tests OK (2 skipped); policy 17 rules, 0 violations; both dry runs byte-identical payloads; mutation tests red/green; `--apply` waits for the public snapshot repo |
| 6 | 003 model credentials | brief-003 | review | Claude via `claude_code_oauth_token`; tester on Azure `gpt-5` through codex-action `responses-api-endpoint` (live 200); reviews `gemini/gemini-3.6-flash` + `azure/gpt-5` (api_version 2024-10-21) per Q22; red tier and any missing family → `needs-human-review`; 429/503/timeout after backoff → `infra-failure`, never a pass; merge model only groups duplicates; 50-review gets authorize, `persist-credentials: false`, pinned litellm 1.106.3; `tools/check_secrets_env.py` preflight; Q34–Q37 | 138 tests OK (2 skipped); policy 18 rules, 0 violations; grep finds only `AZURE_OPENAI_API_KEY`; live one-word calls to Azure gpt-5 and gemini-3.6-flash returned 200; litellm path and codex-on-Azure in Actions not yet run |
| 7 | 001 lean skills | brief-001 | review | `tools/load_skills.py` loads exactly each charter's skills, hash-checked against `factory/skills.lock.yaml`; vendored architect, blast-radius, create-verification-skill (cursor/plugins `5866df5`) and ponytail (`96608e0`), all `reviewed: pending`; no plugin inputs (2 new policy rules); Codex tester gets inlined skill bodies; ArchUnit lint for meter-conventions; draft `verify-meter` skill; `tools/skill_eval.py`; Q38–Q45 | 164 tests OK (2 skipped); policy 20 rules, 0 violations; `load_skills.py --check` 5 charters, 8 skills, 0 problems; `mvn verify` green on JDK 21; always-on description tokens (estimate, chars/4): builder 136, spec-writer 0, tester 360 (inlined), review/verifier 0; live A/B eval BLOCKED: local `claude` CLI login expired (Q38) |
| 7b | 010 skill fixes after 001 | brief-010 | review | Always-on skills inlined into every role's prompt (hash-checked); `.claude/skills/` holds only on-trigger skills (builder: impact-check); own `spec-shape` and `impact-check` replace vendored architect and blast-radius; verify-meter out of CI charters; `reviewed: pending` sources refused (policy: no workflow passes `--allow-pending`); reference check in `--check`; Cowork text applied verbatim; README/HANDOFF updated; Q46 (setup C = B + the charter's on-trigger skills), Q48 (`--check` fails on a backticked skill name the role does not load) | 186 tests OK (2 skipped); policy 21 rules, 0 violations; `--check` 0 problems; builder runs FAIL CLOSED until Qun reviews ponytail and pstack pins (Q44); always-on tokens (chars/4): builder 1098, spec-writer 332, tester 386, review/verifier 0 |
| 7c | 011 hardening follow-ups | brief-011 | review | Pre-snapshot items 1, 2, 5, 6: risk map + floor red for `tools/`, `.claude/`, `AGENTS.md`, `CLAUDE.md`; `^wi-([1-9][0-9]*)$` everywhere; 45 has an authorize job and 25 dispatches only items labelled by the bot, the workflow bot or maintain/admin; `nobody` egress block with negative and positive probes. Then: pinned shellcheck v0.11.0; gitleaks from the pinned image (`--network none`); hash-pinned requirements via `tools/pin_requirements.py` (fixed a real pin bug: litellm needs pyyaml ≥ 6.0.3); bootstrap `--azure-openai-endpoint` and review labels; stubbed `--apply` test; dedupe prompt in `factory/prompts/dedupe.md` + partition check; item 8 confirmed (brief 009); 5 policy rules; Q49–Q53 | 216 tests OK with 010 merged (2 skipped); policy 26 rules, 0 violations; gitleaks and pip hash controls proven locally; NOT yet run in CI: shellcheck download, gitleaks in Actions, iptables + probe, hash installs |
| 8 | 002 context hygiene | brief-002 | todo | | Starts after 001 is merged |

## Q49–Q53 applied on brief-011 (2026-11-11)
- Q49 (`249fe7b`): in post-agent steps, the only allowed `tools` reference is the `$WORKFLOW_SHA:tools/` git-show operand. After the agent step, an agent job may not reference `tools` at all, because replace refs could redirect `git show`.
- Q51 (`6082b89`): Semgrep runs from `semgrep/semgrep:1.182.1@sha256:451b3d87…` with `--network none --metrics off`. Its rules are fetched at run time and checked against a pinned sha256, not vendored (licence, Q55). Policy bans `pipx`/`uvx`.
- Q52 (`5ea7b47`): both egress probes use `https://api.github.com`. A failed positive control fails the step as "egress probe inconclusive".
- Q53 (`e5ec02c`, `31bd0b5`): pins must be at least 14 days old. Exceptions go only through `tools/young-pins.txt`, currently empty. Re-pinned versions in `requirements-review.txt`: anyio 4.16.0→4.15.1, boto3 and botocore 1.44.0→1.43.120, click 8.5.1→8.5.0, hf-xet 1.8.0→1.7.0, pydantic 2.14.3→2.14.1, pydantic-core 2.50.4→2.50.1, typing-inspection 0.4.5→0.4.4. `requirements.txt` is unchanged (pyyaml 6.0.3).
- Checks: 227 tests OK (2 skipped); policy 28 rules, 0 violations; both requirements files pass a `pip --dry-run --require-hashes` for the runner platform. The Semgrep container and the egress step first run in CI.

## To verify (ANSWERS Q33)
- A bypass applies only to its own ruleset. Closed by the first `--apply` read-back: core `never`, review `pull_requests_only`.
- A red required check blocks a bypassed merge. Closed by the first real PR on the new repo.
- 011's CI-only controls are the shellcheck download, gitleaks in Actions, iptables egress block and probe, and hash-pinned installs. Run one scratch-branch CI pass before the flip, including the egress probe with the rule removed once.

## Bypass log
Every merge that used the admin bypass and every self-approved production deploy (ANSWERS Q6, ADR 0002).

| Date | PR / deploy | Reason |
| --- | --- | --- |
| 2026-11-17 | `c8dbee5` direct push to `master`, "Update 40-verify.yml" | Not a PR, not a factory-bot commit: Qun edited `.github/workflows/40-verify.yml` by hand (admin push). This went straight into a red-tier path (`.github/**`) with no PR and no second reviewer, which is only possible because `master` has no branch protection yet — a known, **open** gap (work order at the top of this file: rulesets wait for the fresh-repo snapshot and the public flip, since GitHub rulesets 403 on a private Free repo). This log entry records that the bypass happened and why; it does not close the gap. Claude Code drafted the one-line patch (bump `SEMGREP_RULES_SHA256` after the upstream `p/java` ruleset rotated, breaking PR #29's `static` job) but would not apply it itself: the Edit tool's own oversight check refused a change to a pinned security digest and asked for a human to apply it. Qun applied the exact patch Claude Code proposed. No check's *logic* was loosened, but the re-pin is a **blind accept**: per Q59, the old ruleset was never vendored, so there was nothing to diff the new one against — "looks like a normal Semgrep export" is not proof of what changed. |

## Setup log (2026-11-11)
- **factory-bot App.** Created through the manifest flow.
  - Slug: `agentic-factory-bot-qunfong`, app id `5709140`, client id `Iv23li9hQDpqKkPJL1vo` (public; relevant to Q12).
  - Bot login: `agentic-factory-bot-qunfong[bot]` (user id `355240777`), used by the brief 009 authorize step.
  - Permissions: contents write, pull_requests write, issues write, metadata read. No events, webhook inactive, not public.
  - Variable `FACTORY_APP_ID` and secret `FACTORY_APP_PRIVATE_KEY` are set. The pem only passed through memory into `gh secret set`, never to disk. Client secret and webhook secret were discarded.
  - Installation on this repo only: done by Qun.
- **Pre-publish scan.** Image `zricethezav/gitleaks:v8.24.0` (digest in brief 009). All refs: `master`, `phase-0`, `collab-setup`, `collab-plan`, `brief-004`, 18 commits.
  - gitleaks: no leaks.
  - Client-name deny-list (1 name, kept outside the repo): **FAIL**. The name is in `collab/ANSWERS.md` in 9 commits on `collab-setup`, `collab-plan` and `brief-004` (first `f3cc944`), and in `collab/briefs/009-public-repo-hardening.md` in `364b8b2` and `f1eb70d`. No commit message contains it.
  - `master` and `phase-0` are clean. A history rewrite or a fresh repo is needed before the flip (Q9).

- **Azure (for Q1).**
  - Resource `ai-services-qun`: kind AIServices, West Europe, resource group `Qun-zijn-Speeltuin`, subscription `1c1f62ec-…97a6`.
  - Endpoints: OpenAI `https://ai-services-qun.openai.azure.com/` and cognitive `https://ai-services-qun.cognitiveservices.azure.com/`.
  - key1 was regenerated on 2026-11-11. The new key went straight into the gh secret `AZURE_OPENAI_API_KEY` and the user env var `AZURE_OPENAI_API_KEY` without being printed. A data-plane check with the new key returned HTTP 200.
  - Variable `AZURE_OPENAI_ENDPOINT` = `https://ai-services-qun.openai.azure.com`.
  - Deployments, all of them:

    | Deployment | Model | Version | SKU | Capacity | Upgrade |
    | --- | --- | --- | --- | --- | --- |
    | `gpt-5` | gpt-5 | 2025-08-07 | GlobalStandard | 50 | OnceNewDefaultVersionAvailable |

  - Implication for Q1: there is one OpenAI deployment. Tester, verifier and every Azure reviewer would all run on `gpt-5`, and there is no second Azure family (such as Mistral) for the red tier. Mapping roles to deployments is Cowork's call in ANSWERS Q1.
  - Another resource, `ai-services-qun-us`, also exists. It is not used, and nothing was read from it.

- **Q1 pins (2026-11-11).**
  - Azure: the `gpt-5` deployment's upgrade option is set to `NoAutoUpgrade` (ARM PUT with the same model 2025-08-07, SKU GlobalStandard, capacity 50, RAI policy `Microsoft.DefaultV2`). Result: `Succeeded`.
  - Gemini: listed models with the key in a header, then smoke-tested with a one-word prompt.

    | Model | Result |
    | --- | --- |
    | `gemini-2.5-pro`, `gemini-2.5-flash` | 404 "no longer available to new users" |
    | `gemini-3.1-pro-preview` | 429 quota exhausted (free tier) |
    | `gemini-3.8-flash`, `gemini-3.7-flash` | 503 / timeout on two tries |
    | `gemini-3.6-flash` | ok, reports `modelVersion=gemini-3.6-flash` |
    | `gemini-3.5-flash` | ok, but reports `gemini-3.6-flash`, so it is an alias and not pinnable |
    | `gemini-3-flash-preview` | ok (preview) |

  - Consequence: no Gemini **pro** is usable on this key, so the Q1 reviewer roles can't run as mapped (Q22). Flash pin candidate: `gemini-3.6-flash`.

## Environment facts (checked 2026-11-11)
- Remote `origin` = Qunfong/agentic-factory-poc. Private, owned by a User account. Default branch `master`.
- Actions are enabled and running: `40 verify` on PRs, `45`/`50` through workflow_run, `25 dispatch` on cron. No harmful effects seen so far.
- Repo secrets: `CLAUDE_CODE_OAUTH_TOKEN`, `GEMINI_API_KEY`, `FACTORY_APP_PRIVATE_KEY`, `AZURE_OPENAI_API_KEY`. Variables: `FACTORY_APP_ID`, `AZURE_OPENAI_ENDPOINT`. Labels: GitHub defaults only. Environments: none.
- Local: JDK 21 at `~/.jdks/corretto-21.0.12` (not the default java). `mvn verify` passes. Python 3.10.6 has no pyyaml. `python3` is the MS Store stub. No actionlint, no gitleaks. Docker is installed.
- pstack (incl. poteto-mode) is in `~/.claude/skills` for interactive use only.

## Brief 012 runs
### Diagnosis (2026-11-12, before any fix)
Last run per workflow in Qunfong/agentic-factory-poc. Factory triggers (labels, dispatch, cron, `workflow_run`) run `master`'s YAML, which is still the initial import `155dc19`.

| Workflow | Last run | Trigger, branch | Result | First real error line |
| --- | --- | --- | --- | --- |
| 10 spec | none | | never ran | No `factory:spec` label exists (bootstrap never ran) |
| 20 breakdown | none | | never ran | Needs a merged spec PR |
| 25 dispatch | [43109795865](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43109795865) | schedule, master | success | None; master's `--dispatch-queued` finds nothing queued |
| 30 build | none | | never ran | Needs a dispatched work item |
| 40 verify | [43193091293](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43193091293) | pull_request, brief-011 (PR #13) | success | None. `acceptance` passed through "No ACs in scope", so the acceptance repo, egress block and probes did not run. static (policy, load_skills, shellcheck, actionlint, gitleaks image, Semgrep image + rules digest) ran green |
| 40 verify | [43193033165](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43193033165) | pull_request, brief-004 (PR #4) | failure | `acceptance`: "Input required and not supplied: token" (no `ACCEPTANCE_REPO_TOKEN`); `static` gitleaks-action: "Resource not accessible by integration". Same acceptance error on brief-005/006. Fixed later in the stack (007 scope, 011 gitleaks image) |
| 45 fix round | [43193221913](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43193221913) | workflow_run, master | skipped / success | None; "not an agent branch" for brief branches |
| 50 review | [43193221764](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43193221764) | workflow_run, master | failure | `models.yaml: pin a real model for gemini/frontier before running the review` (master's import has placeholder models). It fails after every 40-verify, on any branch |
| 60 release | none | | never ran | |

Conclusion: the combined code's 40-verify is green when no AC is in scope. Every factory stage fails or never runs because `master` has the initial-import workflows, no labels and no `ACCEPTANCE_REPO`/token (addendum causes 1 to 3, confirmed). `master`'s 50-review will also fail after the 012 draft PR's verify; only merging fixes that.

### Phase 1 result (2026-11-12)
- Draft PR [#14](https://github.com/Qunfong/agentic-factory-poc/pull/14) (`brief-012` → `master`). 40-verify run [43194602253](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43194602253): build-test, static, scope, acceptance and required all green on the first run. No CI fix was needed.
- static ran every step: policy (with the hash-pinned `--require-hashes` install), load_skills, shellcheck download, actionlint, gitleaks image, Semgrep image with the rules digest `OK`.
- acceptance passed through "No ACs in scope" (scope kind `other`, 0 merged work items). The acceptance repo, token, egress block and probes did not run. Their fail-closed path is not exercised by this PR.
- `master`'s 50-review after this verify failed again: [43194807480](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43194807480), `models.yaml: pin a real model`. Only merging fixes it.
- Brief 014 (`58ef391`): own `factory/skills/minimal-change` with NOTICE; builder `always:` = minimal-change; ponytail dir, lock source and skill removed; `ponytail` retired (Q48); builder prompt line names minimal-change. `vendor_skills.sh` reads sources from the lock, so it needed no edit. The builder no longer fails closed on a pending source. Builder always-on estimate (chars/4): 1097 → 825.
- Q55 (`cabab48`): digest mismatch prints "semgrep ruleset digest changed: bump required". Q56: the test already exists (`test_tools_after_agent_code_come_from_workflow_sha`, the `git show "$WORKFLOW_SHA:tools/run_record.py"` step appended to the builder job is rejected); no change.
- Checks: 224 tests OK (2 skipped); `--check` 0 problems; policy 28 rules, 0 violations.

### Per-brief PRs green on their own (2026-11-12)
Merge decision (Qun, 2026-11-12, confirmed in chat): option (a), every per-brief PR green on its own; no Bypass-log entries.

Config: repository variable `ACCEPTANCE_REPO` and secret `ACCEPTANCE_REPO_TOKEN` exist (names checked with `gh variable list` / `gh secret list`). The first token (10:44Z) got "Not Found" from `actions/checkout` of the acceptance repo (A2, runs of #1 to #6). Qun recreated it at 12:30:41Z; on the reruns below the checkout succeeds.

The scratch-base acceptance run was dropped (ANSWERS "Brief 012 after phase 1"). Nothing was created for it: no branch, label, issue or PR.

Red-job causes:
- **S1** static, Secret scan: `gitleaks/gitleaks-action@v2` fails "Resource not accessible by integration" (#1 to #4). Fix: `c50126a`'s `pull-requests: read` moved down to `phase-0` as `ea7b957` and merged up the chain. static is green on #1 to #4 since, including their unpinned Semgrep step, which had never run before.
- **A2** acceptance checkout "Not Found": the first token could not read the repo. Fixed by configuration (Qun's new token), no code.
- **A3** acceptance, #1 to #6 (pre-brief-007 YAML): the job runs every scenario in the acceptance repo, unscoped. Result on every rerun: 3 pass, 1 FAIL. Locally against today's app (`tools/acceptance_run.py`, same scenarios): AC-F1-1/2/3 pass, AC-F1-4 FAIL. AC-F1-4 is the scenario for work not built yet, so the FAIL is correct behaviour of the old job (which AC failed in CI is inferred: the old log labels are method-name prefixes shared by AC-F1-3 and AC-F1-4). Not fixed: it needs brief 007's scoping or a scenario-repo decision. Question Q58.

| PR | Brief / branch | Head | Latest 40-verify | Green | Fix commit |
| --- | --- | --- | --- | --- | --- |
| [#1](https://github.com/Qunfong/agentic-factory-poc/pull/1) | collab-setup | `cc26f4b` | [43207715655](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43207715655) (attempt 2, new token) | no, A3 | S1 `ea7b957` |
| [#2](https://github.com/Qunfong/agentic-factory-poc/pull/2) | phase-0 | `ea7b957` | [43207711951](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43207711951) (attempt 2) | no, A3 | S1 `ea7b957` |
| [#3](https://github.com/Qunfong/agentic-factory-poc/pull/3) | collab-plan | `c92c89a` | [43207723186](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43207723186) (attempt 2) | no, A3 | S1 `ea7b957` |
| [#4](https://github.com/Qunfong/agentic-factory-poc/pull/4) | brief-004 | `ddad5c9` | [43214372706](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43214372706) (attempt 2) | no, A3 | S1 `ea7b957` |
| [#5](https://github.com/Qunfong/agentic-factory-poc/pull/5) | brief-006 | `a9f0f87` | [43215076222](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43215076222) (attempt 2) | no, A3 | |
| [#6](https://github.com/Qunfong/agentic-factory-poc/pull/6) | brief-005 | `e70d3c8` | [43215081085](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43215081085) (attempt 2) | no, A3 | |
| [#7](https://github.com/Qunfong/agentic-factory-poc/pull/7) | brief-007 | `0c8ca94` | [43215085369](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43215085369) | yes | |
| [#8](https://github.com/Qunfong/agentic-factory-poc/pull/8) | brief-009 | `1bc8da3` | [43215091271](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43215091271) | yes | |
| [#9](https://github.com/Qunfong/agentic-factory-poc/pull/9) | brief-008 | `787665a` | [43215096504](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43215096504) | yes | |
| [#10](https://github.com/Qunfong/agentic-factory-poc/pull/10) | brief-003 | `4e6762c` | [43215101246](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43215101246) | yes | |
| [#11](https://github.com/Qunfong/agentic-factory-poc/pull/11) | brief-001 | `2beb976` | [43215108277](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43215108277) | yes | |
| [#12](https://github.com/Qunfong/agentic-factory-poc/pull/12) | brief-010 | `b89c790` | [43215112986](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43215112986) | yes | |
| [#13](https://github.com/Qunfong/agentic-factory-poc/pull/13) | brief-011 | `c0a8bde` | [43215116203](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43215116203) | yes | |
| [#14](https://github.com/Qunfong/agentic-factory-poc/pull/14) | brief-012 (draft) | `b846689` | [43215125811](https://github.com/Qunfong/agentic-factory-poc/actions/runs/43215125811) | yes | |

Notes:
- #7 to #14 are green with acceptance on the "No ACs in scope" path (no checkout, so the token change does not affect them). The acceptance repo checkout, egress block and probes with ACs in scope stay unproven until the first work-item PR (brief 012 step 4).
- #14's row is the head before this STATUS commit; the commit adds only collab files.
- Fold-back: Q55 `cabab48` cherry-picked onto brief-011 as `995e148`. Brief 014 `58ef391` stays on brief-012. Cowork's design doc and ADRs 0003 to 0012 committed verbatim on brief-012 (`b846689`).
- Review coverage (ANSWERS "no silent truncation"): on brief-003 `741befc` (test) and `33e5bc0` (fix), merged up through 001, 010, 011 and 012. A diff over 120000 chars is still reviewed in part, but gets `needs-human-review`, the line "Diff too large (N chars); only the first 120000 were reviewed." and `truncated: true` in the run record. Heads of #10 to #14 moved, so the CI rows above are stale for them.
- The pre-007 acceptance job prints labels from test method names, not AC IDs. Brief 009 changed that to AC IDs only. The repo is private, so this does not block (brief 012 decision 3).

## All per-brief PRs green (2026-11-12)
- Q58, Qun's decision (b): the scenario owner parked AC-F1-4 in `Qunfong/meter-acceptance` (`6bfcb84`, `@Disabled` with a reason). **After PR #7 merges, remove that `@Disabled` line.** From then on, brief 007's scope job decides which ACs run.
- Re-runs after parking, all success: #1 43207715655, #2 43207711951, #3 43207723186, #4 43220166000, #5 43220172307, #6 43220183039 (all at https://github.com/Qunfong/agentic-factory-poc/actions/runs/<id>).
- #7–#14 were already green on their current heads.
- The old pre-007 acceptance job reports a skipped test as `pass`, so AC-F1-4 shows `pass` in those six logs. The scenario was not run.
- Ready for Qun to merge in work order: #1 collab-setup and #2 phase-0, then #3 collab-plan, #4 (004), #5 (006), #6 (005), #7 (007), #8 (009), #9 (008), #10 (003), #11 (001), #12 (010), #13 (011), #14 (012, draft; mark ready first).
- Qun, 2026-11-12: no new suggestions or briefs until everything is green. Brief 015 and new hardening stay parked.
- Current heads after the review-truncation fix (`33e5bc0`), all green on 40-verify:

  | PR | Branch | Head | Run |
  | --- | --- | --- | --- |
  | #10 | brief-003 | `33e5bc0` | 43221367008 |
  | #11 | brief-001 | `e5ab2c2` | 43221831258 |
  | #12 | brief-010 | `e862fce` | 43222302173 |
  | #13 | brief-011 | `7c1f73e` | 43222852601 |
  | #14 | brief-012 | `c2ff7ff` | 43228776676 (re-verified after this STATUS commit; see below) |

- Collab-only commits are no longer merged up the stack until the merges are done, so the PR heads and their evidence stay stable. Cowork's ANSWERS `a6b6822` sits on brief-004 only (#4's head; its run is below).
- Run URLs for the last two head moves: #4 `a6b6822` → 43236372179 (success); #14 `275b840` → 43236447439 (success).

## Merged into master (2026-11-12, by Claude Code on Qun's instruction "You merge them")
- Method: merge commits, in work order. Each PR was retargeted to `master` and merged only while MERGEABLE and with every check passing.
  - #2 `0033dfb`, #1 `2bbdafb`, #3 `704a77d`, #4 `847c00a`, #5 `f676816`, #6 `a87159f`, #7 `d76d914`
  - #8 `7143682`, #9 `0f145ee`, #10 `9f31de9`, #11 `18c40c7`, #12 `85fede5`, #13 `96666f5`, #14 `a63864a`
- No PR was merged red, so there are no Bypass-log entries.
- After #7: AC-F1-4 was un-parked in `meter-acceptance` (`e60a297`).
- Before #11, Qun chose to let the release run ("Merge, run release"). First `60 release` run 43277109349 succeeded: build, staging, production. The run-record check printed "run-record check ok". It pushed an image to `ghcr.io/qunfong/agentic-factory-poc/meter-service`. GitHub auto-created environments `staging` and `production` with no protection rules; the deploy steps are placeholders. Bootstrap `--apply` on the new repo sets the rules.
- Next per brief 012: step 4, one factory run end to end on `master`. Then the skill eval (Q38), then brief 013.
- Factory labels and variables set on Qun's OK (2026-11-12 18:20 UTC), using exactly the `gh label create` and `gh variable set` lines from bootstrap's dry run (personal-account mode). There are no rulesets, environments or repo-setting changes; those wait for the snapshot repo.
  - 16 labels: the factory set plus `factory:builder-failed`, `needs-human-review` and `infra-failure`.
  - Variables: `GATE_ROLES={"gate:intent-approved":["Qunfong"]}`, `WIP_LIMIT=3`, `ACCEPTANCE_REPO`, `AZURE_OPENAI_ENDPOINT`, `FACTORY_BOT_LOGIN=agentic-factory-bot-qunfong[bot]`, `FACTORY_APP_CLIENT_ID`.
- `WIP_LIMIT` lowered to `1` for the first factory run (Cowork's checklist), 2026-11-12.

## Brief 012 step 4: factory run on issue #16 (2026-11-12)
Run URLs are https://github.com/Qunfong/agentic-factory-poc/actions/runs/<id>.

| Stage | Run | Result | First error line / note | Fix |
| --- | --- | --- | --- | --- |
| 10 spec, attempts 1–3 | 43280109890 | red at `spec` | claude-code-action `is_error:true`, `modelUsage: {}`. A local test of the stored token gave "Not logged in · Please run /login" | Qun re-ran `claude setup-token` and stored the long-lived token (secret updated 18:53:58Z) |
| 10 spec, attempt 4 | 43280109890 | spec green, `publish` red | `create-github-app-token`: "Not Found – get a repository installation for the authenticated app" (404) | Qun installed the App on this repo |
| 10 spec, attempt 5 | 43280109890 | **green** | spec PR #21 `spec/F16` opened by `app/agentic-factory-bot-qunfong`, files only under `docs/specs/F16/`, `AC-F16-1` | – |
| 40 verify on #21 | 43285356428 | **green** | triggered by the App's PR, which proves ADR-0004's reason for the App token | – |
| 50 review on #21 | 43285523343 | **green** | authorize ok; Gemini reviewer (amber) via litellm: 0 raised. The Azure verifier had nothing to verify | – |

- Next: Qun reviews and merges #21 (the plan gate). Then 20-breakdown, 25-dispatch, 30-build (tester on Azure, builder), publish, 40-verify with `AC-F16-1` in scope, and the egress proof.
- After the spec names `AC-F16-1`: re-tag the delete scenario in `meter-acceptance` from `AC-F1-4` to `AC-F16-1` (ANSWERS after-merge item 5).

## Follow-up PRs (2026-11-12)
| PR | Branch | Head | 40-verify | Note |
| --- | --- | --- | --- | --- |
| #17 | fix-production-gate | – | merged `fe056d3` | production fails closed without a required reviewer (ADR-0014) |
| #18 | collab-next | – | – | Cowork's ADR-0013/0014 and notes |
| #19 | brief-016-rulesets | `94aa99e` | 43282291002 success | ADR-0013 ruleset tightenings; takes effect at `--apply` |
| #20 | fix-issue-form | `cda1191` | 43283411386 success | issue-form label quoted, plus a schema check; merge before the next issue |

### Run #16 after the plan gate (2026-11-12)
| Stage | Run | Result | First error line / note | Fix |
| --- | --- | --- | --- | --- |
| Merge #21 (plan gate) | – | `f84b7a5` | Qun asked Claude Code to merge #21 and #19 (`0bd81a8`); #20 `4e58d57` and #18 `4ce3ed8` before them | – |
| 20 breakdown | 43289016415 | **green** | created work item #22, "F16 WI-1: DELETE /readings?meterId=<id> …", and dispatched `30 build` itself (25-dispatch did not run) | – |
| 30 build, dispatched by breakdown | 43289044064 | red at `tester` | codex-action: "Actor 'github-actions[bot]' is not permitted to run this action … Detected permission: 'none'". Our `authorize` passed (Q27 admits that bot on dispatch) | none yet. Re-dispatched by Qunfong (maintainer); brief 013 replaces codex-action |
| 30 build, dispatched by Qunfong | 43289283565 | tester, publish-tests, builder **green**; `publish-code` red | path guard ok, then `check_tier.py --base origin/main` failed: the branch no longer exists. `builder-failed` labelled #22 `factory:builder-failed` (Q11, as designed) | PR #23: `origin/master`, plus a test against old-branch references |
- `meter-acceptance`: the delete scenario is re-tagged `AC-F1-4` → `AC-F16-1` (`d9b97f9`), before the `wi-22` PR's verify.
- Tester on Azure via Codex, first real run: `884e7f2` on `wi-22` (`ReadingDeleteTest`, `Assisted-by: codex:azure/gpt-5`, `Factory-Run: 43289283565`).
- Not proven yet: the Azure verifier. It counts only on a review with at least one finding (Cowork); no finding will be planted.

### Run #16 through release (2026-11-12)
| Stage | Run | Result | Note |
| --- | --- | --- | --- |
| 30 build rerun after #23 (`5103eab`), dispatched by Qunfong | 43292923660 | **green** | tester skipped (tests already on `wi-22`, no second test commit, idempotent per Q11); builder and publish-code green. It opened **#25** by `app/agentic-factory-bot-qunfong` |
| 40 verify on #25 | 43293223375 | **green**, all five jobs | `kind=wi`, `scope=AC-F16-1`; hidden scenario `AC-F16-1: pass` (1 in scope, 1 pass, 0 FAIL, 0 without a scenario); egress probe "the runner reaches https://api.github.com and the app user cannot"; isolation check passed. Files: `ReadingController.java`, `ReadingDeleteTest.java`; `tier:amber` |
| 50 review on #25, attempt 1 | 43293464763 | red as designed | `infra-failure`: ServiceUnavailableError after 4 attempts; the comment says "not a pass" |
| 50 review on #25, attempt 2 | 43293464763 | **green** | Gemini raised 1 minor finding (`ReadingController.java:39`, null `meterId`) and the Azure gpt-5 verifier marked it **verified**, so the Azure verifier is proven. Claude Code judged it not actionable: every stored reading passed `@Valid @NotBlank meterId`, and the same pattern is in `list()` |
| Merge #25 | – | `f85274d` | merged by Qun (the permission check blocks Claude Code from merging factory-agent PRs). Work item #22 closed |
| 60 release | 43294559180 | build **green**, staging **green**, production red (fail-closed) | "cannot read the production environment; refusing to deploy". Follow-up for the snapshot: the production check needs a token that can read the environment, or it will refuse even with a reviewer |
| Egress negative proof (scratch PR #26) | 43294913361 | red **as required** | with the iptables lines removed: "the app user reached https://api.github.com; the egress block is not in force"; the policy check also failed (1 violation). PR closed unmerged, branch deleted |
- Not proven: 25-dispatch (no item waited in `queued`; accepted by Cowork). Feature issue #16 is still open (brief 017 closes features automatically).
- Leftover: #22 still has `factory:builder-failed` from the publish failure before #23.

## Brief 018: three-family review (2026-11-12 / 13)
| Item | Result |
| --- | --- |
| #31 three-family consensus | merged `5513515`. Reviewers `gemini/gemini-3.6-flash`, `azure/gpt-5`, `openai/grok-4.7` (Azure AI v1). Comment has a reviewer table, Strong / Verified / Unverified, a collapsed rejected list; the run record holds per-call and per-finding data |
| Grok deployment | `grok-4.7`, format xAI, version 1, GlobalStandard capacity 50, RAI `Microsoft.DefaultV2`, upgrade option set to `NoAutoUpgrade` (ARM PUT, Succeeded) |
| Grok smoke | HTTP 200, model `grok-4.7`, via the v1 endpoint and via LiteLLM, key from the user env var after Qun regenerated it |
| #33 provider outages | merged `4fa4505`. Every failure names the model; mechanical grouping when the merge model is down; test: Gemini 429 everywhere still completes with gpt-5 + Grok |
| First three-family run on a real PR | 43366402472 on spec PR #29: **incomplete** ("1 of 3 reviewers answered"). `RateLimitError from gemini/gemini-3.6-flash after 4 attempts` (free daily quota) and `Timeout from openai/grok-4.7 after 4 attempts`. So brief 018's acceptance is not met yet |
| Grok latency (measured locally) | one real review call on #29's 28 KB diff: 239 s, 8140 tokens in, 489 out, so over the old 180 s limit |
| #34 per-family timeouts | merged `4d6018f`. `timeout_s` per family (Grok 480), timeouts retried once, job limit 45 min. Not yet proven on a real review |
| Open | Verifiers still run sequentially, so a review with several single-source findings can exceed 45 min. Proposal: parallel verifiers with a wall-clock budget; unverified findings stay visible with `needs-human-review` |
| Waiting for Qun (blocked for Claude Code by the permission check) | remove `factory:builder-failed` from #22; close #16 by hand with a link to the run table |


## Audit round 1 response (Claude Code, 2026-11-17, branch `fix-audit-round1`)
Cowork's R1–R6 (`collab/ANSWERS.md`, "Audit round 1"). B items first, per instruction.
- **R2 (B) — done, with evidence.** `60-release.yml`: top-level `permissions` is now `contents: read` only; `packages: write` moved to the `build` job alone. `tools/tests/test_release_workflow_permissions.py` (new) asserts this against the real file per GitHub's own inheritance rule (a job's own `permissions` block replaces the workflow-level one, not merges with it): `build` resolves to `{contents: read, packages: write}`; `staging` and `production` have no job-level block, so they resolve to `{contents: read}` only. 3 tests pass locally.
- **R1 (B) — partly done.** Bypass log entry added above for `c8dbee5`. The part R1 also asked for — a diff of the Semgrep ruleset behind the new digest — is not possible with what's on disk today (Q59): nothing vendors the old ruleset, so there is nothing to diff against. Raised as Q59 with three options; recommended (c) but did not implement it (it changes what the repo stores and needs a steer).
- **R4 (B) — raised as a question, not implemented (Q60).** The release-separation check R4 asks for has no second identity to compare against yet: Qun is the sole collaborator, and GitHub environment reviewers aren't configurable on a private Free repo (the production job already fails closed on that, unrelated to this audit). Building the check now would mean guessing a definition of "production approver" that nothing can falsify. Asked Cowork/Qun to pick: document the gap now and revisit later (recommended), or also start recording `merged_by` per release in the run record as inert data for later.
- **R3, R5, R6 (A/N) — not started.** Left for a later pass; none blocks this branch.
- Commits on this branch also carry Cowork's own round-1 write: `collab/ANSWERS.md` (the "Audit round 1" section) and the new `collab/COWORK-PLAN.md` / `collab/.cowork-seen`, per collab/README.md ("Claude Code commits Cowork's files together with its own").
- No check's logic was loosened to close anything here. Two things this PR does *not* close, despite earlier wording here implying otherwise (own AI review on this PR, findings #1/#2, see below): `master` still has no branch protection (R1's bypass can recur the same way until the snapshot/flip), and the Semgrep re-pin stays a blind accept until Q59 is answered.

### Own AI review (DeepSeek + gpt-5, run [44093366149](https://github.com/Qunfong/agentic-factory-poc/actions/runs/44093366149), on `46c3f24`)
6 findings, all verified, 0 rejected — DeepSeek raised all 6, gpt-5 verified all 6 (the reverse of PR #29's pattern, where DeepSeek found nothing). Acted on directly: wording above now says the branch-protection and blind-accept gaps are open, not closed (#1, #2); added the permissions test above (#5); softened the brief 018/020 framing below (#6). Not acted on: #3 (R3, unpinned agent actions — already tracked, still open, no new action) and #4 (`collab/COWORK-PLAN.md`'s unenforced claim that Claude Code commits Cowork's files — that file is Cowork's to edit, not Claude Code's; raised as a note in `collab/QUESTIONS.md` instead of touched here).

## First complete three-family review, with DeepSeek (Claude Code, 2026-11-17)
Run [44089993015](https://github.com/Qunfong/agentic-factory-poc/actions/runs/44089993015) on PR #29 (`5857eae`, after merging master's `c8dbee5` semgrep fix forward onto `spec/F28`): **3 of 3 reviewers answered** — `azure/gpt-5`, `openai/grok-4.7`, `openai/DeepSeek-V4.1-Flash-1017`. This meets brief 018's/020's acceptance *mechanically* ("First three-family run on a real PR" was incomplete at 1/3; this run is not incomplete), but it is **provisional, not final acceptance**: it ran before Cowork's planted-defect check on DeepSeek, which that check existed precisely to gate (see below). Cowork/Qun should decide whether this run still counts once that check runs, especially if DeepSeek turns out not to review at all.
- 4 findings raised, 1 rejected, 3 verified (not "strong": each came from one reviewer, confirmed by a verifier from another family). All 3 verified findings are real: `ReadingStore.add`'s javadoc still names `DuplicateReadingException`/`CounterDecreasedException` instead of `MeterProblem`; the duplicate/decrease boundary check as specified would misfire on `floorEntry`/`ceilingEntry` (equal `takenAt` matches both); WI-1 never adds an `insufficient-data` `MeterProblem` factory although AC-F28-5/WI-3 need it. The rejected finding (#4, a test-coverage nit) has a substantive counter-argument, not a shrug.
- **DeepSeek as reviewer found 0 of 4** (2.0 s, 7 output tokens) on the same 28 KB diff that gpt-5 and Grok found 3 issues in combined. **DeepSeek as verifier was substantive**: it confirmed #2 and #3 with specific line-level reasoning, and rejected #4 with a real counter-argument, not a rubber stamp. So the "does DeepSeek actually review" concern (ANSWERS, "Brief 020 built on brief-020") is not resolved by this run alone — it engages when verifying but produced nothing when reviewing fresh. The planted-defect check Cowork asked for before trusting it as a reviewer still has not been done; this run went ahead without it (STATUS catches up after the fact, not before).
- Not yet acted on: these are spec findings on a plan-gate PR (#29), Qun's call as domain owner/tech lead, not Claude Code's to edit. Left for Qun to decide at the plan gate; Cowork may want to fold them into "Decisions at the plan gate" the way the first F28 round was (ANSWERS, "Spec PR #29 (F28)").

## Audit round 2 + PR #39 review + Q59/Q60/Q61 (Claude Code, 2026-11-17, branch `audit-round2-fixes`)
Cowork's "Cowork run 2026-11-17 (evening)" in `collab/ANSWERS.md`: answers to Q59-Q61, a review of how PR #39 went, and Audit round 2's B/A/N findings on `publish.yml`/`check_paths.py`/`check_tier.py`. B items first.
- **PR #39's own review, P1 (B) — fixed.** `tools/review.py`'s `tier_of()` (new) computes the real tier from the risk map and the PR's changed files when no `tier:*` label is present, instead of silently defaulting to amber — a hand-made or collab PR touching a red path (like #39 itself) no longer gets under-reviewed. Fails closed to `red` if the computation errors. 4 new tests in `test_review.py` (`TierOfTest`); 48 tests pass locally.
- **Audit round 2, A1 (B) — fixed.** `tools/tests` now runs in CI: a new step in `40-verify.yml`'s `static` job (`python3 -m unittest discover -s tools/tests -v`, 5 min timeout so a hang fails fast instead of eating the job). This is also A2's proof ground: it will show on the next PR's `static` run whether `test_publish.py`'s symlink test (red locally on this Windows checkout, per Cowork) is real on ubuntu-latest.
- **Q59 (B) — built option (c).** `factory/semgrep-p-java.ids`: the current pinned ruleset's sha256 plus its 60 rule IDs (fetched and reviewed, matches the pinned digest), not the rule bodies (licence). New `static` step fails if this file's recorded sha256 doesn't match `SEMGREP_RULES_SHA256`, so the manifest can't go stale silently — whoever bumps the digest must regenerate the ID list in the same commit.
- **Q60 (B) — built options (a) + (b).** `docs/adr/0017-separation-of-duties-not-enforced-in-poc.md` (Cowork's, proposed; committed here alongside this PR) states the gap and its trigger. `60-release.yml` has a new `release-record` job (its own minimal scope, `contents: read` + `pull-requests: read` - PR #42's own review, #10, flagged putting this on `build` as unnecessary scope widening) that records `merged_by` for the triggering commit into `release-record.json` (uploaded as a build artifact, 7-day retention) — inert data, nothing reads or gates on it yet. `60-release.yml`'s top comment now points to ADR-0017 instead of describing an unenforceable state as if it worked.
- **Q61 — Cowork's own fix**, committed here: `collab/COWORK-PLAN.md` no longer claims an unenforced commit step; staleness is caught by the existing `.cowork-seen` hash check.
- **A2 — investigated, and it was the test that was wrong, not the guard.** A1's CI run reproduced `test_publish.PublishTest.test_tester_may_not_swap_a_test_for_a_symlink` failing on ubuntu-latest, matching Cowork's worry. Root cause, found with a scratch diagnostic workflow (closed unmerged, PR #43): `agent_patch()` always runs `git add -A` after `edit()`. The old `swap()` staged a symlink only via `git update-index --cacheinfo`, which never touches the working tree; the file on disk stayed the original regular file. On a real symlink-capable filesystem (ubuntu-latest; not this Windows checkout, which is why it passed here and why Cowork couldn't tell from the mounted-filesystem run), that follow-up `git add -A` re-reads the actual working tree and **reverts the index back to the unmodified file** - the simulated attack never reached the guard at all. `check_paths.py` itself was never broken: `GuardTest.test_type_change_fails` and `.test_filesystem_symlink_fails` (which stage a real symlink the same way) already proved it catches one. Fixed `swap()` to create a real `os.symlink` (skips if the environment can't, same convention as `test_filesystem_symlink_fails`) instead of a bare index trick. Also added, as defence in depth and independent of this root cause: `check_paths.py`'s new `filesystem_link_violations()` checks `Path.is_symlink()` on every changed path against the actual working tree, not just the raw-diff mode field. Verified on ubuntu-latest via the scratch workflow: the fixed test now fails closed with three reasons (status T, symlink mode, and the new filesystem check).
- **Not acted on:** A3 (N, `tester_model` validation), A4 (A, pin `publish.yml`'s `actions/checkout` and `actions/download-artifact`), A5 (N, doc note on `workflow_dispatch` trust) — left for a later pass, none blocking.
- Commits here also carry Cowork's write: `collab/ANSWERS.md` ("Cowork run 2026-11-17 (evening)"), `collab/COWORK-PLAN.md`, `collab/.cowork-seen`, `docs/adr/0017-...md`, `docs/adr/index.md`.

### PR #42's own AI review (18 findings, run 44151797810, commit `80dd5a5`) — acted on
This is the PR carrying everything above; it got its own review. Real bugs in this PR's own code, fixed in place rather than as a follow-up:
- **#3 (strong, blocker).** `tier_of()` trusted a `tier:*` label outright - a hand-made/collab PR that can set labels could force `tier:green` on a red path. Fixed: always compute from the risk map too, return the *stricter* of computed and labelled.
- **#5, #12 (strong, major).** `filesystem_link_violations()`'s `except OSError: pass` failed **open** on a broken link or permission error. Fixed: any such error is now a violation, not a silent skip.
- **#4 (major).** The tier computation read only `.filename` from the PR-files API, missing `.previous_filename` - a rename out of a red path was under-tiered. Fixed: both are scored.
- **#6 (major).** The `merged_by` lookup filtered on `merge_commit_sha == GITHUB_SHA`, which the reviewer says can be null for some merge methods. Fixed: trust the API's own commit-to-PR association (`/commits/{sha}/pulls` is already scoped to that commit) and take its first result, no extra filter.
- **#8 (major, security).** `$GITHUB_SHA` was used unvalidated. Added a `^[0-9a-f]{40}$` check that fails the step closed. Kept "unknown" as the fallback when the API itself has nothing to report - this stays inert data (Q60), not a release gate; a sharper "fail the whole release if merged_by can't be resolved" is a design call for Cowork/Qun, not guessed here.
- **#10 (minor, security).** `pull-requests: read` on the whole `build` job widened scope for steps that don't need it. Fixed by moving the record into its own `release-record` job.
- **#13 (minor).** A malformed or duplicate `tier:*` label (e.g. `tier:` or two labels) is now treated as absent, not as an empty string or an arbitrary pick.
- **#1, #2 (verified, but false positives - checked, not changed).** Both assume `tools/tests` runs without PyYAML installed. It doesn't: the "Workflow security policy" step earlier in the same `static` job already runs `pip install -r tools/requirements.txt` (pyyaml), and the actual CI run shows all tests passing, `TierOfTest` included.
- **#9 (major, security) and #7 (rejected by the review's own verifier) — not changed, raised instead.** #9 is right that the Semgrep manifest check compares two values both read from the PR's own checkout, so a PR could change the pinned digest and the manifest together and still pass. Whether that is a real gap depends on how much Q59's check is meant to resist a reviewed-and-approved malicious PR (which `.github/**`'s red floor and CODEOWNERS already require) versus just catching an honest maintenance slip - that is a scope call, not something to fix by guessing. Left open; see `collab/QUESTIONS.md`.
- **#11 (rejected by the review's own verifier).** Correctly rejected: the permissions test does assert an exact minimal set and would fail if scope broadened.

All fixes verified (own review, finding #12: this number is distinct from the "48" two sections up, which was PR #39's count before `TierOfTest` was rewritten for stricter-of logic - not a conflicting claim, just two different points in this PR's history): `python -m pytest tools/tests/test_review.py tools/tests/test_check_paths.py tools/tests/test_publish.py tools/tests/test_release_workflow_permissions.py` → **88 passed, 2 skipped** locally, after this commit; `check_workflow_policy.py` still reports 0 violations. CI is the proof that matters (A1); this is what I ran locally before pushing.

### Second review round on PR #42 (13 findings, run 44155556815, commit `3073a65`) — acted on
Grok timed out (counted as `infra-failure`, review still complete on gpt-5 + DeepSeek). No "strong" findings this round; real ones fixed anyway:
- **#7 (verified).** `import check_tier` sat outside `tier_of()`'s `try`, so an import failure would raise instead of falling back to `red` as documented. Moved inside.
- **#6 (verified).** `filesystem_link_violations()` assumed `Path.cwd()` is the repo root. Now resolves the root via `git rev-parse --show-toplevel` and builds every path from that, so it no longer depends on the caller's cwd.
- **#8 (verified).** `gh api --paginate` without `--jq` returns concatenated JSON pages that a single `json.loads` can break on for a large PR. Switched to `--jq ".[] | .filename, (.previous_filename // empty)"`, one bare path per line across every page.
- **#5, #10 (verified).** Added explicit `set -euo pipefail` and a non-empty check on `merged_by` in the release-record step - belt and suspenders on top of GitHub Actions' own default `-e`, not a behaviour change: "unknown" is still a valid recorded value, only emptiness fails the step.
- **#12 (verified).** Fixed above (test-count wording).
- **#3 (verified, but not a bug - checked).** The bare SHA line at the end of `collab/.cowork-seen` has no filename by design (Cowork's own "last commit I've seen" marker, distinct from the hash-per-file lines above it, per `collab/COWORK-PLAN.md`'s token-frugal check). Not touched - it's Cowork's file.
- **#1 (verified, deferred).** Pin `actions/upload-artifact@v4` to a SHA: true, but every other action in this repo (`actions/checkout@v4`, `actions/setup-java@v4`, etc.) is equally unpinned, and R3/A4 already tracks "pin the unpinned actions" as one piece of work. Pinning just this one occurrence now would be inconsistent; left for that pass.
- **#4 (verified) and #11 (verified) - same ground as Q62, not re-litigated.** Both restate "the Semgrep manifest check doesn't bind to a trusted baseline" (#4) and "doesn't bind the ID list to the digest" (#11). Both are the accepted, documented limit of Q59 option (c); see Q62.
- **#2, #9 (rejected by the review's own verifier) — correctly rejected, no action.**

## Cowork closes out audit round 1/2, Q62 answered, Audit round 4 opened (Claude Code, 2026-11-17 night)
Cowork independently verified everything above against CI evidence (not STATUS text) and marked **A1, P1, A2 and Q59/Q60/Q61 CLOSED**: runs 44155222774 and 44161429032 both green, `release-record` scoped correctly, `COWORK-PLAN.md` no longer asserts the unenforced claim. One harmless note: the `[ -n "$merged_by" ]` check in `60-release.yml` can never actually fire, since the jq filter already falls back to `"unknown"` - true, left as-is (cheap, harmless, no behaviour to lose).
- **Q62 answered: (a).** Tighten the comments to say plainly what the manifest check does and doesn't resist, no code change - done in `40-verify.yml` and `factory/semgrep-p-java.ids`.
- **Audit round 4 opened** on `40-verify`'s `scope`/`acceptance` jobs and `acceptance_scope.py`/`acceptance_run.py`: R4-1 through R4-7, **all A or N, no B** - nothing here is urgent. Summary: `scope` and `acceptance_run.py` run from the PR head rather than the base (R4-1, same red-floor/human-review boundary as Q62); a timing window before the hidden-scenario directory is locked down (R4-2, not proven exploitable); no mutation/coverage signal on tester-written tests (R4-3); missing `timeout-minutes` on `acceptance` (R4-4); three N-level notes (R4-5/6/7). Left for a later pass - see `collab/ANSWERS.md` for the full writeup.
- Commits Cowork's write alongside: `collab/ANSWERS.md` ("Cowork run 2026-11-17 (night)"), `collab/COWORK-PLAN.md`, `collab/.cowork-seen`.

## Third review round on PR #42, last fixes before closing it out (10 findings, run 44166069338, commit `bd69859`)
Qun asked to finish this PR; fixing the one strong finding plus one cheap verified one, then stopping - the rest are single-source minor/edge-case items that don't block a PR this size from going to review.
- **#1 (strong, minor) — fixed.** The `[ -n "$merged_by" ]` check added two rounds ago was dead code: the jq filter's `// "unknown"` fallback means `merged_by` can never be empty, so the check could never fire. Removed it rather than making "unknown" a failure, which would turn inert data into a gate (not Q60's intent).
- **#3 (verified, major) — fixed.** `filesystem_link_violations()`'s `elif fp.is_file()` skipped any changed path that wasn't a regular file or a symlink (a directory, FIFO, or other entry reached through a symlinked ancestor). Broadened to `elif fp.exists()`.
- **#4, #5, #7 (verified, major/minor) — not fixed, judgment call to stop here.** #4: the tier computation doesn't detect GitHub's 3000-file PR-files cap. #5: the permissions test doesn't assert `release-record` can't be deleted outright. #7: the manifest check still can't bind the ID list itself to the digest (same limit as #11/Q62, restated). All are real, all are edge cases on code this PR already hardened twice; fixing every single-source finding as it arrives would never converge, since each fix is itself a diff the AI review will look at again. Noting them here for a later pass rather than chasing another round.
- **#2, #6 (rejected by the review's own verifier) — correctly rejected, no action.**
- Verified locally: 88 passed, 2 skipped (same four test files as before).

## Brief 013: tester without transcript in logs, LiteLLM-driven (Claude Code, 2026-11-18, branch `brief-013`)
Built per `collab/briefs/013-litellm-tester.md`, starting from `master` (brief 012 is merged there, so brief 013's own precondition holds).
- **`tools/tester_loop.py` (new).** A LiteLLM tool-calling loop on `azure/gpt-5` (same family/model/pin as 50-review), reusing `review.py`'s `completion_args`/`with_backoff`/`InfraFailure` and `check_paths.py`'s `unsafe`/`compile_glob`. Tools: `read_file`, `list_files` (anywhere in the repo, read-only), `write_file` (new files only, `app/src/test/**`), `run_mvn` (allow-list: `-B -q -f app/pom.xml test-compile`, or the same `test -Dtest=<Class>[#<method>]`). No shell, network or git tool. The prompt from `tools/build_prompt.py` (role + inlined always-on skills + issue + spec/plan, unchanged) goes in as the system message; stdout gets only step/tool names, counts, exit codes and a final `tester: result=success|infra-failure` line — model text, tool arguments and file contents go into a transcript JSON (`--out`), uploaded as the `run-record-tester-transcript-*` artifact (retention 7 days) instead of printed. `run_mvn`'s child process has `AZURE_OPENAI_API_KEY` stripped from its env (Decision 6); a disallowed mvn argument or a write outside the allowed glob is rejected before any subprocess or file write happens, never silently narrowed.
- **`.github/workflows/30-build.yml`.** Replaced the `openai/codex-action@v1` step in `tester` with `python3 tools/tester_loop.py` (env holds `AZURE_OPENAI_API_KEY`/`AZURE_OPENAI_ENDPOINT` only on that step, per `agent_secrets_only_on_the_agent_step`), added the hash-pinned `pip install -r tools/requirements-review.txt` step before it (same pin as 50-review: litellm, pyyaml), and added a `tester-record` job mirroring `builder-record` (fetches `run_record.py` via `$WORKFLOW_SHA` after the agent step, never trusts the tester's own checkout — QUESTIONS Q19).
- **`tools/check_workflow_policy.py`.** `AGENT_SCRIPTS = ("tools/tester_loop.py",)` plus a new `is_agent_step()` helper so every existing agent-job rule (read-only permissions, no token env, secrets only on the agent step, skills loaded first, tools only via `$WORKFLOW_SHA` after the agent step) now also covers a plain `run:` step, not only `uses:` actions. Two new rules: `tester_does_not_use_codex_action` (fails on any remaining `openai/codex-action@`, anywhere) and `agent_job_steps_do_not_print_the_transcript` (fails if an agent-job step `cat`s a `*transcript*`/`run-record*.json` file or turns on shell tracing — the "no step prints model output" half of the brief's policy ask). Removed the now-dead `codex-args`/`hide_agent_reasoning` check.
- **`tools/publish.py`** / **`tools/tests/test_publish.py`**: tester's `assisted_by` changed from `codex:{tester_model}` to `litellm:{tester_model}`; the commit-trailer test updated to match.
- **Unit tests (`tools/tests/test_tester_loop.py`, new)**: path escape (`../..`, absolute, backslash) rejected; write outside `app/src/test/**` rejected; overwriting an existing file rejected; a disallowed `mvn` argument (`install`, `-Dmaven.test.skip`, a `-Dtest` value with `;` or `..`) rejected *before* `subprocess.run` is ever called (asserted directly, not just by exit code); `AZURE_OPENAI_API_KEY` confirmed absent from `run_mvn`'s child env. Plus two new `test_check_workflow_policy.py` cases for the two new rules above.
- **Checked, not yet done**: policy check is 0 violations (`30 rules, 9 workflows, 1 issue forms, 0 violations`) and the full suite passes (275 passed, 4 skipped) on this branch. The brief's third acceptance criterion — one live run on the 012 test issue, confirming the job log has no model text by grepping a canary string — needs a real `30 build` dispatch with working Azure credentials, which is blocked by the same GitHub Actions billing issue as PR #44 (Qun's action, not mine). Flagging rather than claiming it's proven.
- No control was loosened to make anything pass. PR: [#45](https://github.com/Qunfong/agentic-factory-poc/pull/45), based on `master` (not `brief-021`, to keep the two independent).

## PR #42 reconciled with master after brief 013 landed (Claude Code, 2026-11-18)
Checking collab turned up two things at once: PR #42 (`audit-round2-fixes`) already carries the R2.1 fix and audit rounds 3/5-9, but had gone `CONFLICTING` because it branched before brief 013 merged; separately, a fresh Cowork pass against today's `master` had written a second, overlapping set of findings (same R2.1 bug, Q59/Q60/Q61 again) straight into the local working tree, uncommitted. Stashed that duplicate pass (`stash@{0}`, "cowork duplicate audit-round-2 pass on master, 2026-11-18") rather than lose or blindly commit it, and will reconcile or drop it once #42 is merged and the bug it describes no longer exists on `master`.
- Merged `master` into `audit-round2-fixes`: one conflict, in `collab/STATUS.md` (both sides only append sections; kept both, in date order). `.github/workflows/30-build.yml` and `tools/check_workflow_policy.py` merged with no conflict — confirmed by diffing each branch against their common ancestor that `audit-round2-fixes`'s only difference there was the pre-013 codex-action code brief 013 already superseded; none of this PR's own work (`tier_of`, `release-record`, `check_tier.py`, the Semgrep manifest check, the kill-switch runbook) touched those lines.
- Verified post-merge: `python tools/check_workflow_policy.py` → 30 rules, 9 workflows, 0 violations; every workflow YAML parses; `python -m pytest tools/tests/` → 271 passed, 2 skipped. Pushed `7f3f98b`. PR #42 is now `mergeable: MERGEABLE`, `mergeStateStatus: CLEAN`.
- Not merged — per our rule, merging is Qun's call, not mine.
- **Qun merged #42** (`0c5fb0e`, 2026-11-18). Dropped the stashed duplicate pass per Cowork's own note below (it described a bug #42 had already fixed on master).

## Brief 013 A1 fix: tester_loop read/list tools refuse symlinks (Claude Code, 2026-11-18, branch `brief-013-a1-symlink`)
After #42 merged, re-checked `collab/` and found Cowork had run a fresh re-verification pass against today's `master` (post brief-013 and post-#42), written straight into the local working tree. Its real finding: **A1 (Cowork, 2026-11-18)** — `tester_loop.py`'s `read_file`/`list_files` validated the path string (`unsafe()`) but never checked the filesystem itself, so a symlink already present in the checked-out tree (direct, or through a symlinked ancestor directory) could point outside the repo - for example at `/proc/self/environ` - and the model would read it as ordinary file content, landing the tester's own `AZURE_OPENAI_API_KEY` in its context and the transcript artifact.
- **Fixed.** New `resolve_contained()` in `tools/tester_loop.py`, mirroring `check_paths.py`'s `filesystem_link_violations()`: refuses a direct symlink, resolves the real path with `strict=True` and requires it stay under the repo root, fails closed on any `OSError`. `read_file` raises through it (hard refusal); `list_files` silently omits any entry that fails the same check (a listing shouldn't abort for one bad entry). 5 new tests in `test_tester_loop.py`; the 3 that create a real symlink skip on this Windows checkout (no symlink privilege here, same as `test_check_paths.py`'s existing convention) and should run for real on ubuntu-latest CI.
- **A2 — documented, not fixed; real open gap, not just a doc task.** Cowork asked which mitigation actually backs "the key is removed from `run_mvn`'s child env." Checked both candidates and found **neither exists for the tester job today**: `30-build.yml` has no egress block (the one in `40-verify.yml` only covers the acceptance app, not `30-build`'s agent jobs - this is exactly the still-open round-3 "sandbox/egress for 30-build" item in `collab/COWORK-PLAN.md`), and the loop doesn't remove the key from its own `os.environ`, only from the dict copy passed to the child. Recorded honestly in `docs/adr/0010-tester-without-public-transcript.md`'s Consequences and Re-evaluation Triggers, rather than writing a note that implies a protection that isn't there. Also updated that ADR's stale header (still said brief 013 "not built yet").
- **N1, N2 — accepted as-is**, per Cowork's own framing (`list_files` has no size cap, token/cost risk only, `MAX_TURNS` backstops it; the transcript-printing policy rule is a pattern tripwire, not the real proof - the live canary run is).
- Verified: `python tools/check_workflow_policy.py` → 0 violations; `python -m pytest tools/tests/` → 272 passed, 6 skipped (4 of those are the new symlink tests, which need a real symlink-capable filesystem).
- No control was loosened. PR: [#46](https://github.com/Qunfong/agentic-factory-poc/pull/46), merged by Qun (`f9a8057`, 2026-11-18).

## Brief 013 A2 fix + N2 wording (Claude Code, 2026-11-18, branch `brief-013-a1-symlink`, after #46 merged)
Checking collab again after #46 merged turned up a second Cowork re-verification pass (uncommitted on the working tree again, same pattern as before). It verified A1's fix as correct (not yet "closed": the 4 symlink tests still need a real run on ubuntu-latest CI, since they skip here), confirmed the round-2 R2.1/P1 closures against the actual merge commit `0c5fb0e`, and gave a concrete, cheap fix for A2 instead of leaving it as a documented gap:
- **A2 — fixed.** `tools/tester_loop.py`'s `main()` now pops `AZURE_OPENAI_API_KEY` from its own `os.environ` right after `completion_args()` captures it into `model_args` (every later `litellm.completion` call already takes the key from `model_args`, not the environment). This closes the gap ADR-0010 documented: a sibling process `run_mvn` spawns, running as the same Linux user, can no longer find the key via this process's own `/proc/<pid>/environ` either - not just absent from the child's own env as before. No egress block needed for this particular fix; round 3's egress-for-30-build item stays open as separate defence in depth, not a precondition. `docs/adr/0010-tester-without-public-transcript.md` updated accordingly.
- **N2 — fixed.** ADR-0010's header said "Accepted and built" with no caveat; now says "Accepted and built; AC3 live proof pending", since the live canary run is still blocked on Actions billing.
- **N1 (TOCTOU between check and read)** — accepted as negligible, per Cowork's own reasoning (single-process job, no concurrent builder). No action.
- Verified: `python tools/check_workflow_policy.py` → 0 violations; `python -m pytest tools/tests/test_tester_loop.py` → 10 passed, 4 skipped (same 4 symlink skips as before; unrelated to this change). Did not add a new unit test for the `os.environ.pop` line itself - it sits inline in `main()` among file/argparse I/O that would need substantial mocking to isolate; the change is two lines and directly matches the pattern Cowork specified.
- No control was loosened.

## Public-flip snapshot executed (Claude Code, 2026-11-18, per ADR-0008 / ANSWERS Q7+Q9)
All three of Qun's delegation preconditions held before touching anything: briefs 004-007, 009, 012 and 013 merged into `master` (confirmed by ancestor checks); the pre-publish scan ready to run; bootstrap `--apply` unchanged and still pending. Executed the Q7+Q9 steps that are Claude Code's to do:
1. **Renamed** `Qunfong/agentic-factory-poc` → `Qunfong/agentic-factory-poc-archive` (`gh repo rename`). Stays private. This checkout's `origin` repointed to it.
2. **Created** a new **private** repo `Qunfong/agentic-factory-poc` from a single root commit (`6f98c65`) holding `master`'s tree at `dad63b3` (166 files, via `git archive master | tar -x` into a clean directory, `git init`, one commit). Authored and committed as `Qunfong <11678460+Qunfong@users.noreply.github.com>` (the id+login noreply form, looked up via `gh api user`). Default branch `master`, confirmed via the API.
3. **Ran the brief 009 pre-publish scan** (`tools/prepublish_check.sh`) on the new repo's actual checkout: **PASS** - `gitleaks: 0 finding(s)`, `deny-list: 1 name(s), 1 commit(s): 0 content, 0 path, 0 message or author, 0 ref name, 0 tag hit(s)`. (A dry run against this old repo's full history first, same deny-list, correctly FAILed with 37 content hits across `collab/ANSWERS.md` and `collab/briefs/009-...md` history - exactly the reason ANSWERS Q7+Q9 chose a fresh snapshot over a history rewrite. Deny-list file: one name, found by reading this repo's own history at `f3cc944` where brief 009 used it as its own illustrative example of what to redact - kept outside the repo as the brief requires, path not recorded here.)
4. **Recreated repo variables** on the new repo (`gh variable set`, all 8 - the archive has more than Q7+Q9's two-item list from before briefs 018/020 added Grok/DeepSeek, so all were carried over for operational parity): `ACCEPTANCE_REPO`, `AZURE_AI_V1_ENDPOINT`, `AZURE_OPENAI_ENDPOINT`, `FACTORY_APP_CLIENT_ID`, `FACTORY_APP_ID`, `FACTORY_BOT_LOGIN`, `GATE_ROLES`, `WIP_LIMIT`.
5. **Recreated the Azure key**: piped fresh from `az cognitiveservices account keys list -n ai-services-qun -g Qun-zijn-Speeltuin` straight into `gh secret set AZURE_OPENAI_API_KEY`, never through a file or stdout.
6. **`GEMINI_API_KEY` not recreated** - confirmed unreferenced in any current workflow (grep over `.github/workflows/*.yml`), consistent with ANSWERS Q20's "delete after the first green run without Gemini." Not carried over.

**For Qun only, before any factory run on the new repo** (none of these are things I can do):
- Add the new repo to the `agentic-factory-bot-qunfong` App's installation.
- Generate a new App private key (GitHub has no API for this) and `gh secret set FACTORY_APP_PRIVATE_KEY --repo Qunfong/agentic-factory-poc`.
- `claude setup-token` (browser login) for a fresh `CLAUDE_CODE_OAUTH_TOKEN`, then `gh secret set` it on the new repo.
- **New, not in the original Q7+Q9 list**: `ACCEPTANCE_REPO_TOKEN` (read access to `Qunfong/meter-acceptance`) exists on the archive but its *value* can't be read back via the API - I can't regenerate it myself. Issue or reuse that token and `gh secret set ACCEPTANCE_REPO_TOKEN --repo Qunfong/agentic-factory-poc`.

**Not done, and not mine to do, per Q7+Q9's own text** ("Qun flips the new repo to public himself, and only after that does 008 `--apply` run"):
- Flipping `Qunfong/agentic-factory-poc`'s visibility to public.
- Running bootstrap `--apply` (branch protection rulesets, fork-PR approval, private vulnerability reporting, Discussions off) - only after the flip.
- Re-pointing this local checkout and any CI references at the new repo once Qun confirms it's ready (this STATUS entry and the collab files themselves currently live only in the archive and the new repo's single snapshot commit; `collab/` on the new repo will need its own update once work resumes there).
