# Brief 004: factory-bot App token and agent credential isolation

Drafted by Claude Code at Qun's request (2026-11-11), from the high-severity items in `docs/review/2026-11-10-design-review.md`. Cowork: please review and answer in ANSWERS.md if you would change anything.

Runs first. It blocks a first run: without it, verify, fix rounds and review never fire.

## Goal
Every push and PR the factory makes comes from a GitHub App identity (factory-bot), so the `pull_request` and `workflow_run` chain fires. Agents never hold a write token, and they can't poison anything that later jobs trust.

## Decisions
1. App id: variable `FACTORY_APP_ID`. Private key: secret `FACTORY_APP_PRIVATE_KEY`. Mint the token with `actions/create-github-app-token`, pinned by SHA.
2. App permissions:
   - contents RW, pull requests RW, issues RW, metadata R.
   - **No** `workflows` permission, so the factory can't change `.github/workflows`.
   - **No** right to approve PRs: the App never calls the reviews API, and no ruleset treats it as a reviewer.
3. The repo setting "Allow GitHub Actions to create and approve pull requests" stays **off**.
4. Agent steps run with `persist-credentials: false`, no `GH_TOKEN`, and no App token in the environment.
   - Agent output leaves the job as a patch artifact.
   - A separate `publish` job applies the patch, re-runs the path guard from the base SHA (brief 005), then pushes and opens or updates the PR with the App token.
5. No shared Maven cache with agent jobs. Agent jobs get either no cache or a key prefixed `agent-`, which verify and release never restore. Verify and release use their own key.
6. Fix-round pushes (30-build in round mode) go through the same `publish` job.

## Acceptance criteria
- `grep -n "GITHUB_TOKEN\|GH_TOKEN" .github/workflows/*.yml`: no write-scoped token appears in any job that runs claude-code-action or codex-action.
- Every `actions/checkout` in an agent job has `persist-credentials: false`.
- `grep -n "cache: maven" .github/workflows/*.yml`: only in verify and release, or keyed so the two sets can't collide.
- A dry run (act, or reading the YAML) shows that `gh pr create` and `git push` only happen in `publish`, with the App token.
- If `FACTORY_APP_ID` or `FACTORY_APP_PRIVATE_KEY` is missing, `publish` fails clearly. It does not fall back to GITHUB_TOKEN.

## Out of scope
Creating the App: Qun does that (see QUESTIONS Q3). Model credentials: brief 003.
