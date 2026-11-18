# Learnings

What we learned building this factory: what surprised us, what broke, and what we changed because of it. Maintained by the Cowork design session; newest first within each group. Decisions themselves are in [docs/adr](../adr/index.md), the flow in [factory-flow.md](factory-flow.md).

Each line: **the learning** · what happened · what we changed (where).

## Way of working

- **Agents read files, not conversations.** · Spec PR #29 raised eight open questions; answering them in a PR comment would have changed nothing, because the builder reads only `spec.md`. · Answers committed into the spec ("Decisions at the plan gate"); brief 019 makes the factory act on PR comments.

- **Prove one end-to-end run before adding controls.** · After two days: 11 stacked branches, ~11k lines of hardening, zero live runs; Qun: "the pipeline doesn't work at all". · Brief 012 (walking skeleton) and a hardening freeze until it is green.
- **Stacked branches make early PRs red for reasons fixed later.** · PR #4 failed on a missing token and gitleaks-action, both fixed in 007/011. · Fix once on the earliest branch that needs it and merge it up the chain (ANSWERS, "Per-brief PRs green on their own").
- **Provision a control's inputs before judging the control.** · Verify failed closed because the acceptance repo and token didn't exist, and that looked like "broken". · Configuration first, then re-run, then fix code (brief 012 addendum).
- **Design notes must be read where they are written.** · Claude Code's questions sat on branches that weren't checked out, so the scheduled answers missed them. · The scheduled task reads `git show <branch>:collab/QUESTIONS.md`.
- **A local schedule only runs while the PC is awake, and only in its hours.** · No reactions for hours: the schedule skipped 15:00–18:00. · Runs every 20 min, 08:00–21:00 on weekdays; GitHub Actions is what runs without the PC.

## GitHub and Actions

- **A named list of sensitive things goes stale when one is retired.** · Retiring Gemini would have dropped `GEMINI_API_KEY` from the policy's list of model secrets while the secret stays in the repo, so a job could read it without the `authorize` gate. · Deny by default: every secret outside three named non-model secrets counts as a model key (`741f195`, `tools/check_workflow_policy.py`).
- **A fail-closed check needs permission to see what it checks.** · 60-release 43294559180 refused production with "cannot read the production environment": the job's token cannot read the environment, so it would refuse even with a reviewer set. · Kept fail-closed; the snapshot repo gets the least permission that can read the rule, proven red and waiting (ANSWERS 2026-11-13, ADR-0014).

- **The first real run surfaces config, not code.** · Issue #16: the Claude token had expired ("Not logged in"), and the App was created but not installed on the repo (404). · `claude setup-token` (long-lived) and the App installed; check both before a run (STATUS, run 43280109890).
- **Third-party actions do their own actor checks.** · codex-action refused `github-actions[bot]` when 20-breakdown dispatched 30-build, although our `authorize` allowed it. · Re-dispatched by a maintainer; brief 013 (LiteLLM tester) removes codex-action.
- **Rename leftovers hide in code paths that never ran.** · `check_tier.py --base origin/main` failed at the first `publish-code`; the branch has been `master` since Q5. · PR #23 plus a test against old branch names.

- **GitHub silently ignores an invalid issue form.** · Issue #16 opened as a blank issue without the `feature` label: an unquoted label with commas inside a YAML `{…}` mapping split into extra keys. Valid YAML, invalid issue form, and no error anywhere. · Label quoted; a schema check for issue forms in the workflow policy tool, run by 40-verify (`tools/check_workflow_policy.py`, branch `fix-issue-form`).

- **A stored secret is not a working credential.** · 10-spec on #16 failed three times with `is_error:true` and empty `modelUsage`; the stored Claude token was "Not logged in". · Qun re-ran `claude setup-token` and stored the long-lived token (STATUS, run #16); test a credential once before the first run.
- **An App needs an installation on the repo, not just a key.** · `publish` got 404 "get a repository installation" from `create-github-app-token`. · Qun installed the App on this repo; the snapshot checklist must include it (STATUS, run #16).
- **A green review with zero findings proves only half the review stage.** · 50-review on spec PR #21 was green, but the Azure verifier had nothing to verify. · Verifier counts as proven only on a PR with at least one finding (ANSWERS, "Run #16 so far").
- **A missing environment is not a closed gate.** · The first `60 release` (43277109349) auto-created `production` with no protection and deployed without a reviewer; a private Free repo cannot add one. · `production` now fails closed without a required-reviewer rule (#17, `60-release.yml`, ADR-0014).
- **AC IDs carry the issue number, so hidden scenarios can only be tagged after the issue exists.** · The prepared scenario is tagged `AC-F1-4`; a new test issue gets another number. · QA re-tags the scenario before the work-item PR is verified (ANSWERS, pre-test checklist).

- **Label, dispatch, cron and `workflow_run` workflows always run the default branch's YAML.** · Every factory run and every 50-review failed on `master`'s initial import, whatever the branches contained; a draft PR only tests `pull_request` workflows. · Fixes count only after merge; 45/50 are proven in the first run after the merge (brief 012 addendum).
- **GitHub Free has no rulesets or branch protection on private repos.** · Bootstrap got 403. · The repo goes public from a fresh snapshot (ADR-0008).
- **History is public forever once the repo flips.** · A client name and a private email were in pushed commits. · A deny-list scan before publishing, and a new one-commit repo instead of a rewrite (ADR-0008).
- **A write collaborator can read repo-level secrets through their own workflow.** · Found in brief 011 (Q50). · Model secrets go into a `master`-only environment (ADR-0011).
- **Anyone who can run code in a job can poison the shared cache.** · Q10. · Release builds without a cache; agent jobs use none (ADR-0009).
- **After an agent has run, git itself can't be trusted.** · The agent can write `.git/refs/replace/`, and `git show` honours it. · Tools run only in later jobs, from `github.workflow_sha` (ADR-0006).
- **GitHub App private keys can only be made in the UI.** · No API exists. · Qun generates one at snapshot time; nobody uploads a key into a chat.

## Models

- **A free tier is not a production dependency.** · The free Gemini key ran out of daily quota on almost every busy evening, and the first three-family review got only 1 of 3 answers. · All reviewers on one paid Azure resource: gpt-5, Grok, DeepSeek (brief 020).

- **One timeout does not fit every model.** · A Grok review of PR #29's 28 KB diff took 239 s (8140 tokens in), past the shared 180 s call timeout. · `timeout_s` per family in `factory/models.yaml` (Grok 480 s), one retry of a timeout, 50-review limit 45 min (`fix-reviewer-timeouts`, ADR-0015).

- **One free-tier provider can take the whole review down.** · 50-review #213/#216/#217 failed on a rate limit (no model named in the log); amber had one reviewer, one exception aborted the run, and the merge model was the same provider. · Per-reviewer failure isolation, a mechanical grouping fallback and the model named in errors (brief 018).

- **The third independent reviewer family can come from the same cloud.** · Without Claude (the author's family), only Gemini and OpenAI were left for review; Grok (xAI) deployed on the existing Azure resource gives a third family without a new provider. · Brief 018.

- **Free tiers and aliases move under you.** · Gemini pro: 404/429 on the free key; `gemini-3.5-flash` silently answers as 3.6. · Pin exact names only, no preview models; Azure `NoAutoUpgrade` (ADR-0003).
- **The Claude subscription token only works inside claude-code-action.** · No Claude for raw review or dedupe calls. · Gemini and Azure do the reviews; Claude only builds (ADR-0003).
- **Agent actions can print transcripts into public logs.** · codex-action logs the tester's reasoning. · LiteLLM tester loop with nothing in the log (ADR-0010, brief 013).
- **"Never drop a review silently" also covers size limits.** · `review.py` cut diffs at 120k characters without saying so. · Label `needs-human-review` when truncated; better coverage is evaluated in brief 015.

## Skills and supply chain

- **Read third-party skill text before an agent loads it.** · Ponytail told the builder to write tests, which its charter forbids, and carried interactive-only modes. · Keep only the relevant rules as our own skill `minimal-change` (brief 014, ADR-0012).
- **Licences limit what you can vendor.** · The Semgrep rules licence forbids redistribution. · Fetch at run time and check a pinned sha256 (ADR-0009).
- **Brand-new package releases are a risk.** · The resolver picked versions only days old. · 14-day minimum age, exceptions only in a reviewed file (ADR-0009).
