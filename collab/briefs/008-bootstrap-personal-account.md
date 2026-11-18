# Brief 008: Bootstrap for the personal-account repo Qunfong/agentic-factory-poc

Drafted by Claude Code at Qun's request (2026-11-11). Updated with ANSWERS Q2, Q5 and Q6.

## Context
- The repo is owned by a personal (User) account, not an org, so there are no teams.
- While the repo is private, `GET /repos/Qunfong/agentic-factory-poc/rulesets` returns 403: "Upgrade to GitHub Pro or make this repository public to enable this feature."
- Qun decided to make the repo public (Q2). He flips visibility himself after brief 009 passes. So `--apply` runs after the flip, with full protection and nothing skipped.
- `master` (from `155dc19`) is the default branch (Q5, done 2026-11-11).

## Decisions (from Qun)
- CODEOWNERS owner and GATE_ROLES: `@Qunfong`. He is the only code owner.
- Bootstrap runs with `--no-merge-queue`.
- App id: variable `FACTORY_APP_ID`. Private key: secret `FACTORY_APP_PRIVATE_KEY`.
- **Q6: admin bypass for Qunfong, as narrow as possible.** This is an approved weakening.
  - Ruleset `bypass_actors` holds exactly one entry: the repository admin role (`actor_type: RepositoryRole`, `actor_id: 5`) with `bypass_mode: pull_request`. Bypass works only through a PR, and direct pushes stay blocked.
  - factory-bot never bypasses. Agent PRs still need Qun's approval.
  - Environment `production`: Qunfong is the sole required reviewer, and `prevent_self_review` is `false`.
  - Every bypassed merge and every self-approved production deploy gets a line under "Bypass log" in `collab/STATUS.md`.

## What to build
1. **Personal-account mode in bootstrap.sh/.ps1.** When the owner is a User:
   - skip the team checks
   - allow a login wherever a team is expected
   - list `FACTORY_APP_ID` (variable) and `FACTORY_APP_PRIVATE_KEY` (secret) as TODOs
   - replace the Anthropic/OpenAI secret list with the brief 003 set (`CLAUDE_CODE_OAUTH_TOKEN`, `AZURE_OPENAI_API_KEY`, optional `GEMINI_API_KEY`; `AZURE_OPENAI_ENDPOINT` is a variable)
2. **Bypass and production settings.** Add a `--admin-bypass-via-pr` flag that adds the single bypass actor above. It is off by default and prints a WARNING naming the ADR. Add a `--allow-self-review` flag for `production`, also off by default, with the same warning.
3. **CODEOWNERS.** Every `<org>/<team>` becomes `@Qunfong`, comments go on their own line, and add `/tools/ @Qunfong`.
4. **`main` → `master`.**
   - Workflows: the `branches: [main]` triggers in 20-breakdown and 60-release.
   - README, HANDOFF and AGENTS.
   - Rulesets keep targeting `~DEFAULT_BRANCH`.
   - Coordinate with any open brief branch that touches the same workflow lines; rebase rather than duplicate.
5. **ADR.** `docs/adr/0002-single-maintainer-bypass.md`, titled "POC: single maintainer, bypass via PR only; revert when a second reviewer exists". It records both weakenings and the revert trigger.
6. **Labels and App id (ANSWERS Q11, Q12).**
   - Add the label `factory:builder-failed`. 30-build also creates it on demand.
   - Switch publish to `client-id` with the variable `FACTORY_APP_CLIENT_ID` (public value `Iv23li9hQDpqKkPJL1vo`, recorded in STATUS). Low priority.
7. **Plan check.** Bootstrap fails clearly when GitHub rejects rulesets or environment reviewers for plan reasons, for example when it runs before the visibility flip. It never quietly continues without protection.

## Acceptance criteria
- A dry run with `--org Qunfong --no-merge-queue --admin-bypass-via-pr --allow-self-review` passes preflight without team calls. Its ruleset payload has exactly one bypass actor with `bypass_mode: pull_request`.
- A dry run without the two flags has empty `bypass_actors` and `prevent_self_review: true`.
- `grep -rn "\bmain\b" .github/workflows README.md HANDOFF.md AGENTS.md` shows no branch reference to `main`.
- `--apply` runs only after Qun has flipped the repo to public, and then succeeds.
