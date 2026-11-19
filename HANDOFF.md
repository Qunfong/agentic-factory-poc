# Handoff to Claude Code

This repo is a starter for the factory POC. It has been designed but **not yet run**. Your job in Claude Code is to make it run end to end, one phase at a time, and stop after each phase for review.

Reference: *Agentic Software Factory – Logical Reference Architecture* (Architecture, ADRs, Agent templates and Tool options tabs).

## Rules for this session
- Work in small, reviewable commits on a branch per phase; open a PR per phase. Do not merge.
- Do not weaken a control to make something pass (gates, path guards, secret scoping, branch protection).
- Treat `factory/**` as factory config: propose changes, explain why.
- When something is unknown (exact model names, plan limits), stop and ask instead of guessing.
- **Open questions on a feature, spec or PR go as a comment on that issue/PR, and the work stays paused until a reply lands there** - not resolved by a quick chat confirmation. Check back on that issue/PR for the reply (same idea as the "check collab" habit for `collab/QUESTIONS.md`/`ANSWERS.md`, applied to spec and feature work too) rather than assuming an answer given only in chat.

## Skills to use
These are for interactive sessions that work on the factory itself. Factory agents never load them; they get only the pinned skills their charter lists (`factory/charters/`, `tools/load_skills.py`).
- `pstack:poteto-mode` (playbooks: feature, bug fix, refactoring), `pstack:tdd`, `pstack:blast-radius`, `pstack:interrogate`
- `java-backend-skills:*` for the Spring service; `doc-authoring-skills:write-adr` for decisions
- `system-design-skills:resilience-failure` and `observability` when hardening phase 6

## Phases

| # | Phase | Done when |
| --- | --- | --- |
| 0 | Repo bootstrap: push to GitHub, create labels, secrets, variables, environments, branch protection (script it in `tools/bootstrap.sh` with `gh`) | `gh` shows all labels, variables and protection rules; `40 verify` passes on a no-op PR |
| 1 | Pin models and skills: fill `<pin: ...>` in `factory/models.yaml`; pin skills in `skills.lock.yaml` and run `tools/vendor_skills.sh` (brief 001) | No placeholders left; `python tools/load_skills.py --check` reports 0 problems |
| 2 | Local dry run: run tester and builder prompts locally on a sample work item; fix prompts and path guards | A sample work item reaches green `mvn verify` locally; path guard blocks a forbidden edit in a test |
| 3 | Spec stage live: create a feature issue, set the intent gate | Spec PR with spec.md, plan.md, work-items.json; an unauthorised label is removed |
| 4 | Build stage live: merge the spec PR (plan gate) | Work-item issues exist; one work item yields a PR with tester and builder commits and run records |
| 5 | Verify, fix rounds, review | Failing verify triggers round 1; AI review comment is posted once and updated, not duplicated |
| 6 | Release | Merge via queue; staging deploy runs; production waits for the release owner |
| 7 | Harden | Add model gateway (LiteLLM) and replace provider keys in jobs; write findings into the review log |

## First task (phase 0)
Read README.md, AGENTS.md and every workflow. List what is missing or wrong before changing anything, then write `tools/bootstrap.sh`.
