# Design review, 2026-11-10 (before first run)

This review was done by reading the files only: `actionlint` is not installed. All `tools/*.py` compile on Python 3.10.6, and `bash -n tools/vendor_skills.sh` passes.
Severity: **H** means it fails to run or weakens a control. **M** means it is wrong or risky. **L** means it should be cleaned up.

## Phase 0: Repo bootstrap
| Sev | Where | Problem | Fix |
|---|---|---|---|
| H | README:47, 10-spec:71, 30-build:77 | `gh pr create` with GITHUB_TOKEN needs "Allow Actions to create and approve PRs". That setting also lets workflows approve PRs. "factory-bot" is only a commit name, not an identity. | Make a factory-bot GitHub App, keep the Actions setting off, and never give the App approve rights |
| H | 40-verify:27-29 | gitleaks-action v2 needs `GITLEAKS_LICENSE` on org repos and `pull-requests: read`. It probably doesn't support `merge_group`. | Add the secret and permission. Run the gitleaks CLI directly for merge_group |
| M | CODEOWNERS:2-11 | The `<org>/` placeholders are ignored. `/tools/` (the control code) has no owner. | Fill in real teams. Add `/tools/ @<org>/security` |
| M | CODEOWNERS:7-8 vs vendor_skills.sh:3 | "Two reviewers" for factory config isn't enforced: either team listed on a line satisfies the rule. | Use a ruleset with 2 approvals on `factory/**` and `.github/**`, or drop the claim |
| L | CODEOWNERS:3 | Has an inline comment after the owner. | Move it to its own line |
| M | README:48 | Environments have no deployment-branch restriction. | bootstrap now restricts them to protected branches |
| L | README:44-47 | Doesn't say that bypassing protection is not allowed. | bootstrap ruleset has empty `bypass_actors` |
| L | repo root | No `.gitattributes`. `autocrlf=true` breaks `.sh` files on Windows. | Fixed in phase-0 (`693cee6`) |
| L | README:15, workflows | ADR-003/006/008/009/011/013/015/016 are cited, but only ADR 0001 exists. | Add stub ADRs or remove the citations |

## Phase 1: Pin models and skills
| Sev | Where | Problem | Fix |
|---|---|---|---|
| M | models.yaml:7-16, litellm-config:7-11 | The sonnet/haiku IDs are unverified. The OpenAI/Gemini IDs are `<pin>` placeholders. | User confirms every ID |
| M | 10-spec:57,69,76; 30-build:65,72,83 | `claude-opus-5-5` is hardcoded in the workflows. The tester model comes from `vars.OPENAI_TESTER_MODEL`, not models.yaml. | Read the model IDs from models.yaml in a setup step |
| H | 10-spec:54-55, 30-build:62-63 | pstack is loaded from the marketplace HEAD, and `skills.lock.yaml` ref is never used. | Pin to the locked SHA, or vendor the plugin (brief 001 removes the plugin input) |
| M | skills.lock.yaml:14 vs README:39 | The marketplace URL is defined in two places. | Keep one source |
| M | vendor_skills.sh:13 | Accepts any ref, including mutable tags. | Require a 40-hex SHA and check `rev-parse HEAD` |
| L | vendor_skills.sh:11 | The temp clone is never deleted. | Clean it up |
| L | tester.yaml:10 | Codex doesn't read `.claude/skills`, so the tester never gets ponytail. | Inject the skill text into the prompt |

## Phase 2: Local dry run and path guards
| Sev | Where | Problem | Fix |
|---|---|---|---|
| H | check_paths.py:14-23 | Can be bypassed: it only sees uncommitted changes. It runs from the tree the agent writes to (as do check_tier and run_record). Renames `a -> b` match on the old path. MM/RM/T/C status codes are missed. Ignored files are invisible. | Record the base SHA. Run the guard from `git show $BASE:tools/…`. Use `git diff --name-status -M $BASE` plus untracked files. Check both sides of a rename. Reject any status other than A/M. Fail if HEAD moved |
| M | check_paths.py:20 | fnmatch `*` crosses `/`. `normcase` makes matching case-insensitive on Windows. | Use explicit, case-sensitive matching |
| M | 10-spec:60 | `--allow 'docs/**'` is wider than the spec-writer charter. | Allow only `docs/specs/F<n>/*` and `docs/adr/proposed-*.md` |
| H | risk-map.yaml:5-12, check_tier.py:11 | The first matching rule wins, so `**/*.md` makes `factory/prompts/*.md` green. `tools/**` is missing. | Take the max tier over all matching rules. Add `tools/**` as red |
| M | .claude/settings.json:11 | `Bash(python3 tools/*)` lets agents run `create_work_items.py` and `review.py`. | Remove it, or narrow it to read-only tools |
| M | build_prompt.py, check_tier.py, review.py | Use the default encoding (cp1252 on Windows). | Pass `encoding="utf-8"` and reconfigure stdout |
| M | check_tier.py, review.py, vendor_skills.sh | No requirements file. Scripts call `python3`, which is the Store stub here. | Add a pinned `tools/requirements.txt` and use `${PYTHON:-python}` |

## Phase 3: Spec stage
| Sev | Where | Problem | Fix |
|---|---|---|---|
| H | 10-spec:71 | Script injection through `${{ github.event.issue.title }}` in `run:`. | Pass it via `env:` |
| H | 10-spec:71 | A PR opened with GITHUB_TOKEN never triggers 40-verify, so the `required` check never appears. | Use the App token |
| H | 40-verify:33-65 vs feature.yml:28-29 | Verify runs all hidden scenarios, so the spec PR and work-item PRs fail on AC IDs that aren't built yet. | Run only the AC IDs of the PR's work item |
| M | 10-spec:36,49-52 | Checkout keeps the default `persist-credentials: true`, so the agent can read the write token. | Set `persist-credentials: false` and push in a separate step |
| M | 10-spec:67-73 | Not idempotent: relabeling fails because the branch or PR already exists. | Reuse the branch and edit the existing PR |
| L | 10-spec:9-15 | Permissions and concurrency are set at workflow level. | Set them per job |
| L | 10-spec:25 | `grep -qx` treats the login as a regex. | Use `grep -Fxq` |

## Phase 4: Build stage
| Sev | Where | Problem | Fix |
|---|---|---|---|
| H | 30-build:28 | The Maven cache the agent writes is restored by verify and release, so poisoned jars could end up in a release. | No cache, or a separate key, for agent jobs |
| H | 30-build:20-23,43,59,66 | `Bash(mvn:*)` is arbitrary execution, with the API key, GH_TOKEN and persisted credentials in reach. | Run the agent with no write token. Push from a separate job that only takes a patch artifact |
| M | 30-build:79, review.py:32 | Old `tier:*` labels are never removed, and review picks the first one it finds. | Remove old tier labels, or recompute the tier in 50-review |
| M | create_work_items.py:8-15,36-38 | The WIP check ignores builds that are running but have no PR yet. No shared concurrency between breakdown and dispatch. | Count running builds too. Add a shared `concurrency: dispatch` group |
| M | create_work_items.py:40 | `blocked` is never removed, so dependent items never run. | Unblock in 25-dispatch once dependencies merge |
| M | 20-breakdown:24 | `HEAD~1` misses files from multi-commit pushes. | Diff `event.before..sha` |
| L | 20/25/30/50 | Unpinned `pip install` with no setup-python (PEP 668 may refuse). | Use setup-python and a pinned requirements file |
| L | 30-build:39-54 | No run record for the tester. | Add one |

## Phase 5: Verify, fix rounds, review
| Sev | Where | Problem | Fix |
|---|---|---|---|
| H | 45-fix-round:19 | Script injection through `head_branch`. A fork branch can burn fix rounds. | Pass it via `env:`, require a same-repo head, check the issue number is numeric |
| H | 30-build:73 | Fix-round pushes use GITHUB_TOKEN, so verify never reruns. | Push with the App token |
| H | 40-verify:54,58,64 | Acceptance fails open: if the app doesn't start or there are no reports, it passes. | Fail when reports are missing, the health check fails, or AC IDs are missing |
| M | 40-verify:40-52 | The PR's app runs with network access next to the checked-out hidden scenarios. | Isolate it in a container and restrict egress |
| M | review.py:90-95 | Not idempotent: comments aren't paginated, the marker isn't filtered by author, no concurrency. | Paginate, filter on the bot's login, add concurrency |
| M | review.py:27-28 | Finds the PR by branch name only and never checks the head SHA. | Use `workflow_run.pull_requests` and compare `headRefOid` |
| M | 45-fix-round:30 | The round-N builder gets no verify failure output. | Pass in a failure summary |
| L | 50-review:10,23 | `statuses: write` and `ANTHROPIC_API_KEY` are unused. | Remove them |
| L | review.py:25,32-33,47 | Crashes on bad model output. | Validate it and fall back to amber |

## Phase 6: Release
| Sev | Where | Problem | Fix |
|---|---|---|---|
| M | 60-release:42 | `production` needs only `staging`, so the image output is empty. | `needs: [build, staging]` |
| M | 60-release:40, README:48 | With a merge queue, the actor may be the queue bot, so prevent-self-review might not bite. | Verify the actor, or also require a different approver on the PR |
| L | 60-release:8-10 | `packages: write` is set at workflow level. | Grant it to the build job only |
| L | 60-release | No concurrency. | `concurrency: release` |
| L | 60-release:18-20, check_run_records.py:7 | `fetch-depth: 50`, and the check passes trivially when the trailer is absent. | Use `fetch-depth: 0` and check bot-authored commits |

## Phase 7: Harden
| Sev | Where | Problem | Fix |
|---|---|---|---|
| M | litellm-config:3-11, review.py:20 | Gateway names don't match models.yaml, mid tiers are missing, and review.py bypasses the proxy. | Generate the gateway list from models.yaml and use the proxy `api_base` |

## Cross-cutting
| Sev | Where | Problem | Fix |
|---|---|---|---|
| H | 10-spec:70-73, 30-build:73-80 | Pushes and PRs made with GITHUB_TOKEN don't trigger workflows, so verify, fix-round and review never fire for factory PRs. | Use a GitHub App installation token |
| M | all workflows | Third-party actions are pinned by tag. `litellm` is unpinned and runs with all keys. | Pin actions to SHAs and pin pip packages |
| M | README:34,55 | Promises "scoped secrets per job", but all secrets are repo-level. | Put keys in environments used only by the jobs that need them |
| L | 40, 45, 50 | No concurrency or cancel-on-update. | Add `concurrency: verify-${{ github.ref }}` |
| ? | 10-spec:49, 30-build:41,57 | Action input names couldn't be checked offline. | Check against each `action.yml` at the pinned SHA |
