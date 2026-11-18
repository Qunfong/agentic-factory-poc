# Brief 003: Model credentials without direct vendor API keys

Can run in parallel with 001; touches workflows, `models.yaml`, LiteLLM config.

## Context
Qun has no Anthropic/OpenAI/Gemini API keys. Available:
| Secret / variable | Source | Used for |
| --- | --- | --- |
| `CLAUDE_CODE_OAUTH_TOKEN` (secret) | Claude subscription via `claude setup-token` | spec-writer, builder (claude-code-action input `claude_code_oauth_token`) |
| `AZURE_OPENAI_API_KEY` (secret) + `AZURE_OPENAI_ENDPOINT` (variable) | Azure resource `ai-services-qun` | tester, verifier, reviewers via LiteLLM |
| `GEMINI_API_KEY` (secret, optional) | Google AI Studio free tier | third-family reviewer; demo code only |

Qun sets these with `collab/setup-keys.ps1` (locally and with `-GitHub` as repo secrets). Do not ask for the values; never print them.

Azure deployment names are unknown until Qun runs `collab/probe-azure.ps1`. Use placeholders `<azure-deployment: ...>` and add a question to QUESTIONS.md.

## What to build
1. `10-spec.yml`, `30-build.yml`: claude-code-action uses `claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`; remove `anthropic_api_key`. Secret only in the agent step.
2. Tester: verify whether Codex CLI / codex-action can use Azure OpenAI (provider config with `base_url = $AZURE_OPENAI_ENDPOINT/openai/v1`, `env_key = AZURE_OPENAI_API_KEY`). If yes, use it. If not, run the tester with claude-code-action in a separate job and session with its own prompt, and record in STATUS that tester and builder now share a family (review stays cross-family).
3. `factory/models.yaml`: openai family → `provider: azure`, models as `<azure-deployment: ...>`; gemini family stays optional (`enabled: false` when `GEMINI_API_KEY` is absent; red tier then uses Azure GPT + a second Azure family such as Mistral if deployed, else escalate to human review — never silently drop a reviewer).
4. `factory/gateway/litellm-config.yaml` and `tools/review.py`: Azure models as `azure/<deployment>` with `api_base: os.environ/AZURE_OPENAI_ENDPOINT`, `api_key: os.environ/AZURE_OPENAI_API_KEY`.
5. `.gitignore` gets `.env*`; gitleaks runs on every PR (already in 40-verify; confirm it also scans `collab/`).
6. `tools/check_secrets_env.py`: preflight that reports which of the three are set (yes/no only) and which roles are therefore runnable. Called at the start of each agent workflow; fails clearly instead of mid-run.

## Acceptance criteria
- `grep -ri "ANTHROPIC_API_KEY\|OPENAI_API_KEY" .github` returns nothing (except `AZURE_OPENAI_API_KEY`).
- Running `python tools/check_secrets_env.py` locally prints a role/readiness table with no secret values.
- A red-tier PR with Gemini disabled ends with `needs-human-review`, not with fewer reviewers.
- No secret is exposed to a step that runs agent-written code (build/test steps have none).
