# ADR index

Factory decisions (0002 and up) are written by the Cowork design session from `collab/ANSWERS.md` and briefs. "Proposed" means the decision is implemented but not yet accepted by @Qunfong. The flow they shape is in [docs/design/factory-flow.md](../design/factory-flow.md).

| ADR | Title | Status | Modules |
| --- | --- | --- | --- |
| 0001 | Use the factory reference architecture for this repo | Accepted | all |
| 0002 | [POC: single maintainer, bypass via PR only; revert when a second reviewer exists](0002-single-maintainer-bypass.md) | Accepted | `.github/`, bootstrap |
| 0003 | [Cross-family model routing, with fail-closed reviews](0003-cross-family-model-routing.md) | Proposed; review rows superseded by 0015 | `factory/models.yaml`, 30, 50 |
| 0004 | [Agents never write to GitHub; one App-token publish job does](0004-single-write-path-factory-bot.md) | Proposed | `publish.yml`, 10, 30 |
| 0005 | [Path guard from the base commit, and a risk tier with a red floor](0005-path-guard-and-risk-tier.md) | Proposed | `tools/publish.py`, `factory/risk-map.yaml` |
| 0006 | [After an agent has run, only trusted copies of factory tools execute](0006-trusted-tools-only-after-agents.md) | Proposed | all workflows, policy check |
| 0007 | [Verify fails closed, runs hidden acceptance tests by AC ID, and blocks egress](0007-verify-fail-closed-and-ac-scope.md) | Proposed | 40-verify, acceptance repo |
| 0008 | [Go public from a fresh one-commit snapshot, behind an authorize gate](0008-public-repo-from-fresh-snapshot.md) | Accepted | repo, bootstrap, all agent workflows |
| 0009 | [Pin everything a gate depends on](0009-supply-chain-pinning.md) | Proposed | 40-verify, `tools/requirements*.txt` |
| 0010 | [The tester runs as a LiteLLM tool loop that writes no transcript to logs](0010-tester-without-public-transcript.md) | Accepted (planned, brief 013) | 30-build |
| 0011 | [Model secrets live in a `master`-only environment](0011-model-secrets-in-environment.md) | Accepted (planned, snapshot) | agent workflows, bootstrap |
| 0012 | [Each agent loads only its charter's skills, pinned by hash; own skills before vendored ones](0012-lean-pinned-skills.md) | Proposed | `factory/charters`, `factory/skills*` |
| 0013 | [The `required` check must come from GitHub Actions, and merges are squash-only](0013-ruleset-tightenings.md) | Accepted (after the merge) | bootstrap, rulesets |
| 0014 | [Production deploys fail closed when the environment has no required reviewer](0014-production-fails-closed-without-reviewer.md) | Accepted | 60-release, bootstrap |
| 0015 | [Three reviewer families with 2-of-3 consensus, isolated per provider](0015-three-family-review-consensus.md) | Accepted; Gemini rows superseded by 0016 | `factory/models.yaml`, `tools/review.py`, 50 |
| 0016 | [DeepSeek on Azure replaces Gemini as a reviewer family; gpt-5 groups findings](0016-deepseek-replaces-gemini.md) | Accepted (built on `brief-020`) | `factory/models.yaml`, 50, policy check |
| 0017 | [Separation of duties at release is an accepted gap while one person holds every gate role](0017-separation-of-duties-not-enforced-in-poc.md) | Proposed | 60-release, run record |

Proposed ADRs from the spec writer arrive as `proposed-*.md` in a spec PR; the tech lead accepts them at the plan gate.
