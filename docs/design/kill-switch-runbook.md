# Stop the factory in 5 minutes (draft by Cowork, 2026-11-17; Claude Code builds the pause variable, Qun runs this by hand)

Architecture: "a kill switch stops all runs within 5 minutes". No such switch exists yet (Audit round 5, B1). Until the pause variable below is built, this is the manual path. Every step is a command or a click that Qun does; none is run by an agent.

## 1. Stop new spend (30 seconds)
- Set the repository variable `FACTORY_PAUSED=true` once it exists (see "To build"). Until then: GitHub, Actions, Workflows, disable `25 dispatch`, `30 build`, `45 fix round`, `50 review`, `10 spec` (five clicks, or `gh workflow disable <name>` for each).
- Remove the `queued` label from open work items so a re-enable does not start them at once.

## 2. Stop what is running (1 minute)
`gh run list --status in_progress --json databaseId,workflowName -q '.[] | select(.workflowName|test("^(10|25|30|45|50)")) | .databaseId' | xargs -n1 gh run cancel`
Repeat with `--status queued`.

## 3. Cut the keys (2 minutes, only if you suspect abuse or a leak)
- Azure: rotate `AZURE_OPENAI_API_KEY` in the Azure portal, then update the repository secret. One key serves gpt-5, Grok and DeepSeek, so one rotation stops all three.
- Claude: revoke the token behind `CLAUDE_CODE_OAUTH_TOKEN` (claude.ai settings), then `claude setup-token` for a new one when you restart.
- factory-bot App: suspend the installation (GitHub, Settings, Applications, Installed GitHub Apps) to stop every push and PR from the factory.

## 4. Prove it stopped (1 minute)
`gh run list --limit 10` shows no `in_progress` or `queued` factory run; the Azure usage page shows no calls for 5 minutes. Write the time you stopped and why in the STATUS Bypass log.

## To build (Claude Code, one PR, red path)
1. Repository variable `FACTORY_PAUSED`; `tools/authorize.py` and `25-dispatch` refuse to start when it is `true` (fail closed when the variable cannot be read).
2. `tools/review.py` and the build jobs check it once more before the first model call, so queued runs stop too.
3. A test for each, and one drill in STATUS: set the variable, start a run, show it refuses, with run id.
