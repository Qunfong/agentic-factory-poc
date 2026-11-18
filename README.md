# Agentic factory POC: feature to production

A base setup that takes one feature from design to production with AI agents and four human gates,
following the *Agentic Software Factory – Logical Reference Architecture*.

## Flow

| Stage | Trigger | Who | Workflow |
| --- | --- | --- | --- |
| 1 Design and intent | Feature issue (template) + label `gate:intent-approved` | Product owner | `10-spec.yml` checks the role |
| 2 Spec and plan | Intent gate | Spec writer (Claude + spec-shape skill) opens a spec PR | `10-spec.yml` |
| 3 Breakdown | **Merging the spec PR = plan gate** (CODEOWNERS: tech lead) | Script creates work-item issues | `20-breakdown.yml`, `25-dispatch.yml` (WIP limit) |
| 4 Implementation | Dispatch per work item | Tester (OpenAI Codex) writes tests, builder (Claude Code + its pinned skills) implements | `30-build.yml` |
| 5 Verify | PR or merge queue | Build, tests, gitleaks, Semgrep, hidden acceptance (separate repo) | `40-verify.yml`, `45-fix-round.yml` (max 2 rounds) |
| 6 Review and merge | Verify green | AI review: OpenAI, Grok and DeepSeek, 2-of-3 consensus, cross-family verification of single-source findings; **merge = human** | `50-review.yml`, branch protection |
| 7 Release | Merge to `master` | Staging automatic; **production = release owner** (environment approval) | `60-release.yml` |

Orchestration in this POC is GitHub Actions plus issue labels and workflow dispatch. Production replaces this with a durable workflow engine (ADR-015).

## Model families

| Role | Family | Why |
| --- | --- | --- |
| Spec writer, builder | Claude (Claude Code) | Strongest coding harness; skills and plugins |
| Tester | OpenAI (Codex) | Another family than the builder, so tests do not share its blind spots |
| Reviewers amber and red | OpenAI + xAI (Grok) + DeepSeek | Three independent families, none the builder's. A finding raised by 2 of 3 is strong; a single-source finding is verified by another family |

Routing lives in `factory/models.yaml`: Claude `claude-opus-5-5` through claude-code-action, Azure OpenAI deployment `gpt-5`, Azure deployments `grok-4.7` and `DeepSeek-V4.1-Flash-1017` on the same resource and key. Red-tier PRs always get `needs-human-review`. A reviewer the providers rate-limit is an `infra-failure`; with fewer than 2 reviewers answering the review is incomplete and gets `needs-human-review`, never a pass. `python tools/check_secrets_env.py` shows which roles can run.

## One-time setup (GitHub)

1. **Secrets:** `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`), `AZURE_OPENAI_API_KEY`, `ACCEPTANCE_REPO_TOKEN` (read-only, acceptance repo only), `FACTORY_APP_PRIVATE_KEY`.
2. **Variables:**
   - `GATE_ROLES` = `{"gate:intent-approved": ["<po-login>"]}`
   - `WIP_LIMIT` = `3`
   - `AZURE_OPENAI_ENDPOINT` = `https://<resource>.openai.azure.com` (no trailing slash)
   - `AZURE_AI_V1_ENDPOINT` = `https://<resource>.services.ai.azure.com/openai/v1` (Grok reviewer; same key as `AZURE_OPENAI_API_KEY`)
   - `ACCEPTANCE_REPO` = `<org>/meter-acceptance`
   - `FACTORY_APP_ID` = the factory-bot App's id (publish reads it; `FACTORY_APP_CLIENT_ID` replaces it once publish moves to `client-id`)
   - `FACTORY_APP_CLIENT_ID` = the App's public client id
3. **Labels:** `feature`, `gate:intent-approved`, `spec`, `work-item`, `queued`, `blocked`, `agent`, `escalated`, `tier:green`, `tier:amber`, `tier:red`, `round:1`, `round:2`, `factory:builder-failed`, `needs-human-review`, `infra-failure`.
4. **Branch protection on the default branch, `master`:**
   - require a PR with 1 approval, plus CODEOWNERS review;
   - dismiss stale approvals on new commits (ADR-009);
   - require the status check `required`, reported by GitHub Actions only ([ADR-0013](docs/adr/0013-ruleset-tightenings.md));
   - squash merges only, and linear history (ADR-0013);
   - require the merge queue, which squashes too;
   - do not let agents (factory-bot) approve.
5. **Environments:** `staging`; `production` with required reviewer = release owner and "prevent self-review".
6. **Acceptance repo:** create a private repo from `acceptance-repo-example/`. Only the product owner and QA can write to it.
7. **Skills:** each agent loads only its charter's skills, pinned by hash in `factory/skills.lock.yaml`, via `tools/load_skills.py <role>`. Third-party skills are vendored at a reviewed commit by `tools/vendor_skills.sh`. No workflow installs a plugin.

### Bootstrap

`tools/bootstrap.sh` (bash) and `tools/bootstrap.ps1` (Windows PowerShell 5.1+) script steps 2 to 5: labels, variables, environments and two rulesets on the default branch (`~DEFAULT_BRANCH`, here `master`). `factory-default-branch` blocks deletion and force pushes, requires linear history, and requires the `required` check and, unless `--no-merge-queue`, the merge queue with squash merges. The check is pinned to the GitHub Actions app (`integration_id` 15368), so a commit status named `required` from any other app or token does not satisfy it. `factory-default-branch-review` requires a code-owner approval and allows only squash merges. `--apply` reads both rulesets back and stops unless GitHub shows these values. The scripts print what they would do by default; add `--apply` / `-Apply` to execute. They never set secrets: they print the `gh secret set` commands for you to run.

```bash
tools/bootstrap.sh --org my-org --repo agentic-factory-poc --po-logins po-user --release-owner rel-owner \
  --factory-bot-login 'agentic-factory-bot-qunfong[bot]'
tools/bootstrap.sh --org my-org --repo agentic-factory-poc --po-logins po-user --release-owner rel-owner \
  --factory-bot-login 'agentic-factory-bot-qunfong[bot]' --apply
```

```powershell
.\tools\bootstrap.ps1 -Org my-org -Repo agentic-factory-poc -PoLogins po-user -ReleaseOwner rel-owner -FactoryBotLogin 'agentic-factory-bot-qunfong[bot]'
.\tools\bootstrap.ps1 -Org my-org -Repo agentic-factory-poc -PoLogins po-user -ReleaseOwner rel-owner -FactoryBotLogin 'agentic-factory-bot-qunfong[bot]' -Apply
```

Run with `--help` / `-Help` for team slugs, `--azure-openai-endpoint` and the other options.

**Personal account (this repo).** Bootstrap looks up whether `--org` is a user or an organisation, or takes `--owner-type user|org` for a dry run without network. A personal account has no teams, so code owners are logins and the team checks are skipped. A merge queue needs an organisation, so pass `--no-merge-queue`. With one maintainer, two weakenings are approved in [ADR 0002](docs/adr/0002-single-maintainer-bypass.md), each behind its own flag and off by default: `--admin-bypass-via-pr` lets repository admins merge a PR without an approving review. It bypasses only `factory-default-branch-review`, so required checks still block and direct pushes stay blocked. It also skips the squash-only setting, but linear history still holds, so a bypassed merge can squash or rebase and never adds a merge commit. `--allow-self-review` lets the production reviewer approve their own deploy. Run `--apply` only after the repo is public. Before that, GitHub Free refuses rulesets on the private repo, and bootstrap stops before it changes anything.

```bash
tools/bootstrap.sh --org Qunfong --repo agentic-factory-poc --po-logins Qunfong --release-owner Qunfong   --factory-bot-login 'agentic-factory-bot-qunfong[bot]' --factory-app-client-id Iv23li9hQDpqKkPJL1vo   --no-merge-queue --admin-bypass-via-pr --allow-self-review --apply
```

`--apply` also turns Discussions off, turns on private vulnerability reporting (the route in `SECURITY.md`), and makes every outside contributor's fork PR wait for approval before workflows run. GitHub accepts the last two only on a public repo, so rerun `--apply` right after the repo goes public. `FACTORY_BOT_LOGIN` is the App's bot login: the `authorize` job lets it, a maintainer or an admin start an agent, and nobody else.

### Before the repo goes public

Run the pre-publish scan on a full clone (not a linked worktree), with the client-name deny-list kept outside the repo. It needs Docker and prints only counts and commit or file ids. It exits 0 only when gitleaks and the deny-list both pass.

```bash
tools/prepublish_check.sh --deny-list ~/private/deny-list.txt --repo path/to/clone
```

```powershell
.\tools\prepublish_check.ps1 -DenyList $HOME\private\deny-list.txt -Repo path\to\clone
```

## Local or cloud

- **Local (devcontainer or your machine with Claude Code):** write and test skills, prompts and charters; run one builder by hand on a branch.
- **Cloud (GitHub Actions):** every factory run. Only there do you get ephemeral runners, scoped secrets per job, run records and required checks.

## POC shortcuts (fix before production)

| Shortcut | Production form |
| --- | --- |
| Provider keys as job secrets | Model gateway with a key per run (`factory/gateway/litellm-config.yaml`) |
| Path guard script after each agent | Tool gateway with per-tool scopes |
| Labels and workflow dispatch as state | Durable workflow engine |
| Run records as artifacts | Append-only, hash-chained store |
| Factory config in this repo under CODEOWNERS | Separate factory-config repo that agents cannot write to |
| GitHub-hosted runners | Untrusted runner pool without network access to internal systems |
| Azure `gpt-5` is both the tester and a verifier/reviewer (one OpenAI deployment) | A separate model family, or at least a separate deployment, per role (ANSWERS Q1) |
| DeepSeek reviewer is a flash model the Azure catalog lists as Preview; red tier keeps mandatory human review | A generally available DeepSeek model, and a decision on the red-tier rule from brief 015's measurements |
| A reverted work item's ACs stay in the regression scope: the regression goes red and a person decides. Retiring them takes a spec PR that marks them retired | An AC lifecycle with an explicit retire step (ANSWERS Q25) |
