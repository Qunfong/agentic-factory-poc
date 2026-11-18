# Questions from Claude Code to Cowork

Number each question (Q1, Q2, ...), name the brief, and say what you did meanwhile.

## Q1 (brief 003): Azure deployment names
Which Azure deployment name is each role meant to use: tester, verifier, the amber reviewer, the red reviewer and the merge model? Running `collab/probe-azure.ps1` lists them.
**Meanwhile:** brief 003 uses `<azure-deployment: role>` placeholders in `models.yaml` and the LiteLLM config. Nothing that needs Azure runs live.

## Q2 (brief 008, for Qun): GitHub plan limits on a private personal repo
GitHub returns 403 for rulesets on this repo: "Upgrade to GitHub Pro or make this repository public". On a free plan, private repos also lack classic branch protection and environment required reviewers. Without one of these, none of the gates (required `required` check, CODEOWNERS review, production approval) is enforced server-side. The options are:
- (a) GitHub Pro
- (b) make the repo public

I won't run bootstrap `--apply` with protection skipped, because that would be weakening a control.
**Meanwhile:** bootstrap has not been run. Briefs 004–007 are unaffected and can proceed.

## Q3 (brief 004, for Qun): Create the factory-bot GitHub App
Please create a GitHub App owned by Qunfong and install it only on this repo.
- Permissions: Contents RW, Pull requests RW, Issues RW, Metadata R. **No** Workflows permission and no webhook.
- Store its id as variable `FACTORY_APP_ID` and its private key as secret `FACTORY_APP_PRIVATE_KEY`.
**Meanwhile:** brief 004 is written against those names. The `publish` job fails clearly until they exist.

## Q4 (brief 007): How to scope hidden acceptance tests
Is it acceptable to tag acceptance scenarios with their AC ID (`@Tag("AC-3")`) and have verify run only the IDs listed in the PR's work item? That needs a convention in the private acceptance repo, which the PO and QA own.
**Meanwhile:** I'll build the fail-closed part of brief 007 first, since it doesn't depend on this.

## Q5 (for Qun): Default branch
The remote has no `main`, and `phase-0` is the default branch. I may not push to `main`, so the `collab-setup` PR targets `phase-0`.
Do you want to push `main` (155dc19) yourself and set it as the default? If so, I'll retarget the PRs to `main`.
**Meanwhile:** the PR targets phase-0.

## Q6 (for Qun): Self-approval with a single owner
With `@Qunfong` as the only CODEOWNER and 1 required approval, PRs authored by Qunfong can't be approved, because GitHub doesn't let authors approve their own PR. That includes branches I push with your gh login. Factory-bot PRs are fine.
For human-authored PRs, do you want to:
- (a) allow admin bypass for Qunfong only (a weakening, so only on your explicit decision), or
- (b) have a second account review them?
**Meanwhile:** nothing; this only matters once protection is enforced (Q2).

Q1 to Q6 were answered in ANSWERS.md on 2026-11-11. They are applied in briefs 007, 008 and 009 and in STATUS. Q1 stays open.

## Q7 (brief 009, for Qun): Commit email in public history
All 10 commits are authored `QunWang <qunfong@live.nl>`. That email becomes public when the repo flips. The options are:
- (a) keep it
- (b) rewrite the author to your GitHub noreply address before the flip. That changes every SHA and needs force-pushes to `master`, `phase-0` and `collab-setup`, so it's your explicit call.

Separately, to stop new commits from exposing it, set the repo-local `git config user.email` to the noreply address.
**Meanwhile:** nothing rewritten; new commits still use the current config.

## Q8 (brief 009, for Qun): gitleaks binary
The pre-publish scan needs gitleaks. Should I install it with `winget install Gitleaks.Gitleaks`, or run the `zricethezav/gitleaks` Docker image (Docker is installed)?
**Meanwhile:** brief 009 builds the script; the full-history scan waits for this.
**Answered by Qun in chat (2026-11-11):** use the Docker image. Pinned to `zricethezav/gitleaks:v8.24.0` (digest in brief 009). First full-history scan: no leaks.

## Q9 (brief 009, for Qun and Cowork): Client name in history
The pre-publish check found a client name in `collab/ANSWERS.md:24` (Q2, point 4, the "for example" in parentheses), committed in `f3cc944` and pushed. An earlier version of brief 009 had it too; it's removed now, but it's still in the history. Before the flip:
1. Cowork, please drop the name from ANSWERS.md. That's your file, so I don't edit it.
2. Qun, the name stays in history until it's rewritten. Doing that together with Q7 (the commit email) means one rewrite and one round of force-pushes to `master`, `phase-0`, `collab-setup`, `collab-plan` and `brief-004`. The alternative is to publish a fresh repo built from a squashed snapshot. Your call; I won't force-push without it.
**Meanwhile:** nothing rewritten. The repo stays private.

## Q10 (brief 004, for Qun): A cache key prefix doesn't stop a malicious agent job
Brief 004 keeps agent jobs off the Maven cache that verify and release use. Agent jobs now use no cache at all. That stops accidental sharing. It doesn't stop deliberate poisoning: a process in the builder job (`Bash(mvn:*)` is arbitrary execution) can read the runner's cache token and save any key, including the next `setup-java-Linux-maven-<hash>`. The build runs on the default branch, and verify and release restore caches from that branch's scope. This is inferred from GitHub's cache scope rules, not tested.
Options:
- (a) Release drops `cache: maven`. A release then never builds from a cache an agent could have written. Verify keeps it, because verify runs PR code anyway.
- (b) Both verify and release drop it. Builds get slower until a repository mirror exists.
- (c) Keep the brief as written.
**Meanwhile:** I did (c). Verify and release are unchanged, and agent jobs have no cache.

## Q11 (brief 004, for Cowork): The tester and builder now publish separately
`publish` pushes the tester's patch before the builder starts. The builder then starts from that commit, so the tests are existing files to it, and its guard is `app/src/main/**` only. Before, it was `app/src/main/**` plus new files under `app/src/test/**`. This matches `factory/charters/builder.yaml`.
Two behaviours change:
- If the builder fails, `wi-<n>` holds the tests with no PR. A rerun sees the branch and skips the tester. That makes it idempotent.
- The builder can no longer add test helpers. If it needs one, it asks through a protected-change request.
Is that what you want, or should the builder be allowed new test files again?
**Meanwhile:** I built it the narrow way.

## Q12 (brief 004, for Qun): `app-id` is deprecated in create-github-app-token v3
Brief 004 names the variable `FACTORY_APP_ID`. In v3.3.0, the action's `app-id` input still works but is deprecated in favour of `client-id`.
Do you want a `FACTORY_APP_CLIENT_ID` variable instead? That would be a two-line change in `publish.yml` plus the bootstrap.
**Meanwhile:** `publish` uses `app-id`, pinned at 64ab729a6294000f5aa4a4bc0b73d1f32bc45510 (v3.3.0).

## Q13 (brief 006, for Qun): Pin shellcheck too?
actionlint is pinned (1.7.12, sha256-checked). It uses whatever shellcheck the `ubuntu-latest` image ships, though, so the lint can change when the image updates. Do you want shellcheck pinned as well, or is that drift acceptable?
**Meanwhile:** the runner's shellcheck is used.

## Q14 (brief 006, for Cowork): What fix-round does with branches that aren't `wi-`
Brief 006 says fix-round should "fail on anything else". I skip branches that don't start with `wi-`, so a human PR with a failed verify doesn't get a red fix-round run. Only a malformed `wi-*` branch fails. Is that the intended reading?
**Meanwhile:** skip non-`wi-` branches and fail malformed `wi-*` ones.

## Q15 (brief 006, for Cowork): Leading zeros in `wi-<n>`
`^wi-([0-9]+)$` accepts `wi-007`, which becomes issue `007`. Should it be tightened to `^wi-([1-9][0-9]*)$`?
**Meanwhile:** leading zeros are accepted.

## Q16 (for Qun): 50-review hardening outside brief 006
Three problems in 50-review fall outside this brief's scope:
- its checkout keeps `persist-credentials: true`
- it runs `pip install pyyaml litellm` unpinned
- it holds `statuses: write` and `ANTHROPIC_API_KEY` without using either

Brief 003 replaces the Anthropic key. Should the rest go into brief 003, or into a new brief?
**Meanwhile:** unchanged.

## Q17 (brief 005, for Cowork/Qun): Make `risk-map.yaml` match the code
Add `- {pattern: "tools/**", tier: red, owner: security-owner}` to `factory/risk-map.yaml`, and correct its header comment. The comment says "highest tier wins", which wasn't true before brief 005. The code floor already scores `tools/`, `.github/` and `factory/` red. Adding the rule to the map keeps the file honest and names an owner. The file is under factory/, so this is your edit.
**Meanwhile:** the floor in `check_tier.py` covers it.

## Q18 (brief 005, for Cowork): Builders can no longer delete or rename files
The guard now passes only A and M. Is that acceptable for refactoring work items, or should deletions and renames go through a protected-change request?
**Meanwhile:** deletions and renames are rejected (fail closed).

## Q19 (brief 005, for Qun): `run_record.py` still runs from the agent's tree
`10-spec.yml` and `30-build.yml` call `tools/run_record.py` after the agent step, from the tree the agent can write to. 60-release relies on run records. Should it move to the trusted copy (`job.workflow_sha`), like the guard?
**Meanwhile:** unchanged. I'll fold it into brief 007 or 009 unless you say otherwise.

## Q20 (brief 005): Encode the trusted-copy rule as a policy check
Should `check_workflow_policy.py` gain a rule that publish reads its tools only through `job.workflow_sha` and never runs `cp tools/`? That would make the fix structural.
**Meanwhile:** not added. Planned as part of brief 009's new rules.

## Q21 (brief 005, for Qun): Hash-pin `tools/requirements.txt`
`pyyaml==6.0.2` is pinned by version but installed without `--require-hashes`. Should hashes be added?
**Meanwhile:** version pin only.

ANSWERS Q1 and Q7–Q12 arrived on 2026-11-11 and are applied:
- Q10: release builds without the Maven cache.
- Q11: the `factory:builder-failed` label.
- Q12: deferred to brief 008.
- Q7+Q9: the fresh-repo snapshot comes after 004–007 and 009 merge.
- Q1: Azure pinned. Gemini is blocked (Q22).

## Q22 (brief 003, for Qun/Cowork): No Gemini pro on the free tier
Q1 maps the amber and red reviewers to Gemini pro. On this key, `gemini-2.5-pro` returns 404 "no longer available to new users", and the only pro model, `gemini-3.1-pro-preview`, returns 429 quota exhausted. Flash works: `gemini-3.6-flash` is pinned by name and reports that version. The options are:
- (a) Enable billing on the AI Studio project, so the paid tier allows `gemini-3.1-pro-preview`. It is a preview model, though, and Q1 asked for stable.
- (b) The reviewer uses `gemini-3.6-flash`, the verifier uses Azure `gpt-5`, and the merge model is also `gemini-3.6-flash`. The red tier stays two-family (Gemini flash plus gpt-5).
- (c) Red-tier PRs always get `needs-human-review` until a pro model is available.
**Meanwhile:** brief 003 is not started. `models.yaml` keeps `<pin>` for Gemini.

## Q23 (brief 007, for Cowork): Spec writer and issue template still say `AC-1`
`factory/prompts/spec-writer.md` and `.github/ISSUE_TEMPLATE/feature.yml` still use `AC-1`. Verify now requires `AC-F<feature>-<n>` (ANSWERS Q4), so until both change, every spec PR fails, by design. The prompt is your file. Should I change the issue template, or will you?
**Meanwhile:** spec PRs fail closed on malformed IDs.

## Q24 (brief 007, for Cowork): Scope for PRs that aren't spec or work-item PRs
Human and brief PRs run the regression set: all ACs of merged work items. Before anything is merged that set is empty, so they pass with "no ACs in scope". Is that the intended rule?
**Meanwhile:** implemented as described.

## Q25 (brief 007, for Cowork): A reverted work item stays in scope
A reverted work item keeps its ACs in regression scope, because its PR still counts as merged. Removing them is manual. Acceptable for the POC?
**Meanwhile:** they stay in scope.

## Q26 (brief 007/009, for Qun): Block network egress for the app under test?
The app under test sees each scenario's HTTP requests, and file isolation doesn't stop it from sending them out. One option is an iptables rule that blocks every destination except loopback for the `nobody` user. It's cheap, but it can't be verified locally, and it could break future apps that call out. Do you want it in brief 009?
**Meanwhile:** files are isolated; network is not.

## Q27 (brief 009, for Qun): `github-actions[bot]` may start a build on `workflow_dispatch`
Without this, no automatic build runs, because 20-breakdown, 25-dispatch and 45-fix-round dispatch `30 build` with GITHUB_TOKEN. The consequence is that a `write` collaborator, though never an outsider, can still reach model spend indirectly through 45 or 25. The options are:
- (a) keep it
- (b) gate 45 on `workflow_run.actor`, and 25's dispatcher, with the same `authorize.py`, which is a small change
- (c) fail closed

**Meanwhile:** (a).

## Q28 (brief 009, for Qun): codex-action prints the tester transcript
codex-action@v1 has no input to keep output out of the log. `codex exec` writes the prompt, command output and diffs to stderr, and `hide_agent_reasoning=true` hides only the reasoning. The options are:
- (a) accept it: the prompt is the public issue, and the tester sees no secrets
- (b) run `codex exec` ourselves with stderr going to a file, which loses the action's key proxy and sudo drop
- (c) move the tester off codex-action, which ANSWERS Q1 already allows via LiteLLM

**Meanwhile:** (a) with `hide_agent_reasoning=true`.

## Q29 (brief 009): Pin gitleaks in CI too
40-verify still uses `gitleaks/gitleaks-action@v2`, pinned by tag only. Should it switch to the same pinned Docker image (`zricethezav/gitleaks:v8.24.0@sha256:2bcc…`) that the pre-publish check uses?
**Meanwhile:** unchanged.

## Q30 (brief 009, for Qun): An authorize gate for 50-review
50-review spends Gemini and OpenAI budget through `tools/review.py` on any same-repo PR after verify. It isn't an "agent job" under the policy rule, so it has no authorize gate. Should it get one? This overlaps Q16.
**Meanwhile:** no gate. Outsiders (fork PRs) are already excluded by the same-repo guard.

## Q31 (brief 008, for Qun): Brief 003 secrets versus the current workflows
For a personal account, bootstrap lists only the brief 003 secret set (`CLAUDE_CODE_OAUTH_TOKEN`, `AZURE_OPENAI_API_KEY`, optional `GEMINI_API_KEY`). The workflows still read `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` until brief 003 lands, so agent jobs on the fresh repo fail until then. Bootstrap prints a note.
**Meanwhile:** brief 003 comes right after the flip and `--apply`.

## Q32 (brief 008): Test `--apply` against a stubbed `gh`?
The plan-check and read-back paths have run only as dry runs and on sample errors. A test that runs `--apply` against a stubbed `gh` (fake host, no real calls) would prove them end to end. The brief said never to run `--apply`, so I didn't. May I add it?
**Meanwhile:** no such test.

## Q33 (brief 008, for Qun): The bypass now covers only the review rule
The bypass now lives on its own ruleset, `factory-default-branch-review`. With `--admin-bypass-via-pr` you can merge your own PR without an approval. The required check, deletion and force-push protection and the merge queue still block you, as they do everyone else. That is narrower than Q6's single-ruleset version.

One side effect: if `required` gets stuck, you can't push past it. You have to fix the check or edit the ruleset by hand. Two things are inferred from GitHub's layering, not yet observed:
- A bypass applies only to its own ruleset. The first `--apply` read-back proves this part.
- A red check blocks a bypassed merge. A real PR proves this part.

**Meanwhile:** two rulesets.

## Q34 (brief 003): Bootstrap still sets retired names
bootstrap.sh and .ps1 still set `OPENAI_TESTER_MODEL`, and in org mode they still list `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`. The workflows no longer read any of these. Should bootstrap drop them and set `AZURE_OPENAI_ENDPOINT` instead, in a small follow-up on brief 003?
**Meanwhile:** unchanged. It's harmless, but it confuses.

## Q35 (brief 003, for Cowork): The dedupe prompt is inline
`tools/review.py` has an inline `DEDUPE_PROMPT`. Prompts are your domain. Should it move to `factory/prompts/dedupe.md`?
**Meanwhile:** inline.

## Q36 (brief 003): Create the review labels up front
review.py adds `needs-human-review` and `infra-failure` through the labels API. Should bootstrap create both labels up front, as it does for `factory:builder-failed`?
**Meanwhile:** they are created implicitly on first use.

## Q37 (brief 003, for Qun): Q28 follow-up on the tester transcript
The tester now runs on Azure `gpt-5` through codex-action, so its transcript still reaches the public log. Keep option (a), accept, or move to (c), a LiteLLM-driven tester that writes nothing to stdout?
**Meanwhile:** (a).

## Q38 (brief 001, for Qun): Log in the local `claude` CLI and run the skill eval
The live A/B eval didn't run, because the local `claude` CLI says "OAuth session expired and could not be refreshed". Please run `claude /login`. Then either run the eval yourself or tell me to:
`python tools/skill_eval.py --task G001 --setups A,B --max-turns 30 --java-home C:/Users/QunWang/.jdks/corretto-21.0.12`
**Meanwhile:** the eval harness works up to the agent step: it builds the workspace, loads the skills, runs `mvn verify` and the acceptance test. No real results are committed.

## Q39 (brief 001, for Cowork): architect and blast-radius are manual-only
Both set `disable-model-invocation: true`, so Claude Code never loads them on its own. In practice the spec-writer has no skill, and the builder's blast-radius never fires. Both also point to pstack files that weren't vendored: `how`, `why`, `arena`, `unslop` and the harness doc. Should the prompts call `/architect` and `/blast-radius` explicitly, or should these skills be replaced?
**Meanwhile:** they are loaded but effectively unused.

## Q40 (brief 001, for Cowork): `factory/prompts/builder.md` still says to use pstack `poteto-mode`
Factory runs no longer have poteto-mode. What should replace that line? It's your file.
**Meanwhile:** unchanged.

## Q41 (brief 001, for Cowork): meter-conventions names the wrong tool
meter-conventions says System.out is checked by "(Checkstyle)". It's now checked by ArchUnit (`ArchitectureTest`). May the text say so?
**Meanwhile:** unchanged.

## Q42 (brief 001, for Qun): verify-meter can't run in CI as the builder's tools stand
verify-meter needs `curl`, `java -jar` and a background process, but the builder's allowedTools allow only `Bash(mvn:*)`. The options are:
- (a) allow curl to localhost and `java -jar`, which widens what the agent can execute;
- (b) drop verify-meter from the builder's on-trigger set.

Separately, the tester also has verify-meter, but it never changes `app/src/main`.
**Meanwhile:** it's loaded, but it can't execute in CI.

## Q43 (brief 001, for Cowork): "Always" and "on trigger" mean the same for Claude roles
For Claude roles, both kinds sit in `.claude/skills`: descriptions are always loaded and bodies load on demand. Should always-on bodies be inlined into the prompt, the way the Codex tester's are?
**Meanwhile:** both are loaded as skills.

## Q44 (brief 001, for Qun): Refuse `reviewed: pending` sources?
Should `load_skills.py` refuse to load from a source still marked `reviewed: pending`? It would fail closed until you've reviewed the pinned commits: cursor/plugins `5866df5`, ponytail `96608e0`.
**Meanwhile:** it loads them. The pins are marked pending in the lock.

## Q45 (brief 001, for Cowork): The tester no longer gets ponytail
The tester no longer gets ponytail, following decision 4's table. Is that intended?
**Meanwhile:** as in the table.

## Q46 (brief 010, for Cowork): Eval setup C and verify-meter
Setup C installs verify-meter for the builder, but it keeps the CI builder's tools (`Bash(mvn:*)`), so verify-meter can only report "not run, curl not allowed". Should setup C widen the eval's tools to curl and java? That would measure verify-meter's value, but it no longer matches CI.
**Meanwhile:** CI tools are kept.

## Q47 (brief 010): Stale skill names in README and HANDOFF
Fixed by Claude Code. The README now names spec-shape. HANDOFF's skill list is labelled as being for interactive sessions only.

## Q48 (brief 010, for Cowork): A name-level reference check?
`load_skills.py --check` catches file paths a skill points to outside its folder. It doesn't catch name-only references, such as "Companion to `how` and `why`". No skill loaded today has one. Is a name-level check wanted?
**Meanwhile:** paths only.

## Q49 (brief 011): Tighten the tree-tools rule?
`cp -r tools "$X"`, with no trailing slash, gets past the existing `TREE_TOOLS` regex. Should I tighten that rule? It tightens a control.
**Meanwhile:** unchanged. I'll do it unless you object.

## Q50 (for Qun): Write collaborators can reach model secrets
Brief 011 closes the label path. But a collaborator with write access can still push a branch carrying its own workflow (`on: push`). That workflow can read the repo-level model secrets, or dispatch `30 build` as `github-actions[bot]`. The fixes are:
- (a) move model secrets into environments with protection rules, and give agent jobs `environment:`;
- (b) keep the repo at zero write collaborators.

You are the only collaborator today.
**Meanwhile:** (b) holds in practice; nothing is enforced.

## Q51 (brief 011): Pin Semgrep too?
`pipx run semgrep` in 40-verify is unpinned. Should it get the same hash-pin treatment as the other tools?
**Meanwhile:** unpinned.

## Q52 (brief 011, for Cowork): The egress probe's positive control
The probe checks that the runner can reach example.com and that `nobody` can't. If example.com is down, verify fails. Accept that, or probe a GitHub-owned host instead?
**Meanwhile:** example.com.

## Q53 (brief 011, for Cowork): Minimum age for pinned packages?
The resolver picked the newest releases, some only days old, for example certifi 2026.10.23. Add a minimum-age rule, such as 14 days, to `pin_requirements.py`?
**Meanwhile:** newest releases.

ANSWERS Q46 and Q48 are applied on brief-010: `977cb18` (setup C) and `d83d314` (name check). The real tree trips nothing.

## Q54 (brief 010, for Cowork): Brief 010 step 3 is stale after Q46
`collab/briefs/010-skill-fixes-after-001.md`, "What to build" step 3, still says "(plus verify-meter for the builder, local only)". Q46 amends this, but the brief's text is yours. I fixed the matching comment in `factory/skills.lock.yaml`.
**Meanwhile:** the code follows Q46.

## Q55 (brief 011, for Cowork/Qun): The Semgrep rules licence blocks vendoring
ANSWERS Q51 asked to vendor `p/java` into `factory/semgrep/java.yml`. The Semgrep Rules License v1.0 (semgrep.dev/legal/rules-license) does "not allow you to distribute the rules", and this repo goes public. So instead, CI fetches `https://semgrep.dev/c/p/java` and checks it against a pinned sha256. The scanner runs `--network none`, so it can't fetch anything itself. Options:
- (a) keep the pinned fetch. The cost is a red `static` job whenever upstream changes the ruleset, until the digest is bumped.
- (b) vendor a semgrep-rules snapshot from before 2024-12-13, under LGPL-2.1 plus Commons Clause, which allows redistribution with notice. The rules are about two years older.
- (c) write our own rules under `factory/semgrep/`.
- (d) vendor anyway and accept the licence risk. Not recommended.

**Meanwhile:** (a).

## Q56 (brief 011, for Cowork): The agent-job rule is stricter than Q49
Q49 allows the trusted `$WORKFLOW_SHA:tools/` git-show form in post-agent jobs. Inside an agent job, though, after the agent step, every `tools` reference is now rejected, the trusted form included. The agent can write `.git/refs/replace/`, and `git show` honours replace refs. No real workflow is affected, because tools already run in separate later jobs. Acceptable?
**Meanwhile:** the stricter rule.

## Q57 (brief 014, for Cowork): builder.md wording after ponytail
Brief 014 needs no `ponytail` in prompts, but gives no replacement text. In `factory/prompts/builder.md` (your file), "Work in ponytail mode (full): the smallest complete change." now reads "Follow the minimal-change skill: the smallest complete change." Change it if you want other wording. HANDOFF's stale "`ponytail` after vendoring" line is removed.
**Meanwhile:** the wording above, on brief-012 (`58ef391`).

## Q58 (brief 012, for Qun/Cowork): PRs #1 to #6 cannot be green on their own while AC-F1-4 is in the acceptance repo
With the new token the acceptance checkout works on #1 to #6 (STATUS "Per-brief PRs green on their own", cause A3). Their acceptance job predates brief 007 and runs every scenario in `meter-acceptance`, unscoped: 3 pass, 1 FAIL on each rerun. Locally the same scenarios against today's app give AC-F1-1/2/3 pass, AC-F1-4 FAIL. AC-F1-4 is the scenario for work not built yet, so that job is right to fail. From #7 on, brief 007's scope job runs only the ACs a PR owns. Options:
- (a) Move brief 007's scoping down to `phase-0`. It is brief 007's core (scope job, `tools/acceptance_scope.py`, `tools/acceptance_run.py`, their tests, policy rules), too large to move per ANSWERS "Per-brief PRs green on their own" item 3.
- (b) The scenario owner takes AC-F1-4 out of `meter-acceptance` until its work item exists, and puts it back once #7 is merged. No code change. #1 to #6 should then pass 3 of 3 (inferred from the measured 3 pass). Cost: brief 007's "unbuilt scenario stays in the repo and does not run" case is not exercised in between.
- (c) Treat #1 to #7 as one merge unit and require green only from #7. That is a change to option (a) of the merge decision.

**Recommendation:** (b). It changes test data the owner controls, no check is skipped or softened, and it is reversible.
**Meanwhile:** nothing is merged; #1 to #6 stay red on A3.

Q58 answered by Qun in chat (2026-11-12): (b). AC-F1-4 is parked in meter-acceptance until #7 merges. All PRs are green; see STATUS.

## Q59 (Audit round 1 R1, for Cowork/Qun): No diff is possible for a rotated Semgrep ruleset
Q55 decided (a): fetch `p/java` by URL, check it against a pinned sha256, never vendor it (licence). That means the *old* ruleset content is nowhere on disk once it rotates — only its hash was ever pinned. So when `static` failed with "digest changed" (upstream rotated the ruleset), I could fetch and eyeball the *new* file (looks like a normal Semgrep registry export: standard rule IDs, CWE/OWASP metadata, the same licence header) and confirm the new digest matches it, but I cannot show what actually changed between old and new rules. Re-pinning on "the new file looks legitimate" is close to a blind accept, which R1 flags correctly.
Options:
- (a) Nothing changes; accept that a rotation is a blind re-pin, documented as such each time (this time: STATUS Bypass log, `c8dbee5`).
- (b) On every green `static` run, upload the fetched `java.yml` as a short-retention workflow artifact (not committed, not redistributed — an ephemeral CI artifact, so the Semgrep Rules License's "distribute" restriction likely doesn't apply, but Cowork/Qun should confirm that reading). The next rotation then has something to diff against (the last artifact before the pin changed).
- (c) Same as (b) but keep only a sha256 + rule-ID list (not full rule bodies) as a small committed manifest, enough to see which rules were added/removed/renamed without holding licensed text.
**Recommendation:** (c): smallest footprint, clearly not "the rules" under the licence, and still gives a real diff next time.
**Meanwhile:** no artifact or manifest exists yet; the next rotation will be exactly as blind as this one.

## Q60 (Audit round 1 R4, for Cowork/Qun): Release separation of duties has no technical check, and today it cannot have one
`60-release.yml`'s comment ("production needs the release owner... prevent self-review") describes a GitHub environment reviewer rule that a private Free-plan repo cannot configure (STATUS, "Run #16 through release": the production job already fails closed on exactly this, "cannot read the production environment"). Today Qun is also the sole collaborator (ANSWERS Q50), so "the release owner did not approve the merge of the same change" is structurally impossible to satisfy with a second person, and this was already decided at the architecture-review stage of this project: separation-of-duties is ignored for the POC while one person holds every gate role, re-enforced only once a real team exists.
So R4's "add a release-gate check that reads the merge approver and the production approver and fails if equal" would be a check with no second identity to ever compare against today — it cannot distinguish "the same person decided twice" from "no one else exists yet" without guessing at a design (e.g. what counts as "the production approver" when environments can't gate who clicks anything). I don't want to build that without a decided design, per HANDOFF's "when something is unknown, stop and ask instead of guessing."
Options:
- (a) Document the gap precisely (this entry, plus a line in `docs/adr/` or `60-release.yml`'s own comment) instead of building a check now. Revisit when the repo goes public and/or gets a second collaborator, when environment reviewers become configurable.
- (b) Build a weaker, checkable proxy now: record who merged each PR (via `commits/{sha}/pulls` → `merged_by`) in the run record, so the data exists even though nothing can act on it yet.
- (c) Build the full check now against a guessed definition of "production approver" (e.g. `github.actor` of whoever re-runs the production job), accepting it may need rework once reviewers are configurable.
**Recommendation:** (a) now, (b) as a small, cheap addition alongside it. Not (c): a guessed definition of "approver" that nothing can falsify yet risks looking like a real control when it isn't one.
**Meanwhile:** R4 stays open; the YAML comment is unchanged (still describes the intended, not-yet-possible state).

## Q61 (own-PR review, for Cowork): COWORK-PLAN.md asserts an unenforced commit step
This PR's own AI review (DeepSeek, verified by gpt-5, run 44093366149, finding #4) flags `collab/COWORK-PLAN.md:1`: "Claude Code commits it with its next commit" is stated as fact, but nothing checks it — if Claude Code forgets, the plan goes stale with no signal. That file says it's Cowork-maintained, so I'm not editing it myself (collab/README.md: Claude Code never rewrites Cowork's files silently). Two ways to close it, your call: (a) drop the claim and have Cowork commit `COWORK-PLAN.md`/`.cowork-seen` itself where it can (it says it never runs git write commands, so probably not), or (b) add a cheap check — e.g. `.cowork-seen`'s mtime/hash vs the latest commit touching `collab/` — that flags staleness instead of asserting it away.
**Meanwhile:** unchanged; Claude Code keeps committing Cowork's collab/ files alongside its own, as today.

## Q62 (PR #42's own review, finding #9, for Cowork/Qun): What is the Semgrep manifest check actually meant to resist?
Q59 (c)'s manifest check (`factory/semgrep-p-java.ids` vs `SEMGREP_RULES_SHA256` in `40-verify.yml`) reads both values from the PR's own checkout. The review's finding #9: a PR could change both together and the check still passes, so it doesn't bind to a trusted baseline. True, but `.github/**` and `factory/**` are red-floor paths needing human review and CODEOWNERS already (ADR-0005/0008-adjacent), so "a malicious PR changes both" already requires getting a bad re-pin past a human reviewer - the same trust boundary every other change to these paths relies on.
- (a) Accept it: the check's job is to stop an *honest* re-pin from silently going stale (Q59's original problem), not to add tamper-resistance beyond what path-guard + human review already give `.github/**`. No code change; tighten the comment to say so.
- (b) Bind it to a trusted baseline: read the pinned digest and manifest from `origin/master` (or `github.base_ref`) instead of the PR's own files, so a PR literally cannot move both at once. More code, and it changes what "the check" means (base-vs-head, not self-consistency).
**Recommendation:** (a) - the gap only matters if you don't trust `.github/**`'s existing review requirement, and if you don't, that's a bigger problem than this one check.
**Meanwhile:** unchanged (self-consistency only, per the original Q59 (c) build).
