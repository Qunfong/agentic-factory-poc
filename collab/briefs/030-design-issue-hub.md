# Brief 030: design issue as hub (draft, after the happy flow works)

Precondition: one feature runs green from issue to staging (blockers in ANSWERS "Happy-flow diagnosis 2026-11-24" closed). Do not start before.

Build, in order, each as its own PR:
1. `.github/ISSUE_TEMPLATE/design.yml` (title, problem, constraints, options, non-goals) + labels `design`, `factory:design`, `gate:design-approved` in bootstrap.
2. Charter `factory/charters/designer.md` (read-only; output = one issue comment; skills: spec-shape + a new `design-options` skill, own text, no vendoring).
3. `15-design.yml`: trigger `issues: labeled` and `issue_comment` on `design` issues; `authorize` first; prepare -> agent (read-only) -> comment via publish.yml; round cap from a repo variable `DESIGN_MAX_ROUNDS`.
4. `publish.py`: role `designer`, allowed paths `docs/design/**` and `docs/adr/**`, only after `gate:design-approved`.
5. Policy rules: no `${{ }}` in `run:`, agent job has no write token, comment bodies passed via env.
AC: each step has a policy test; one live run on a throwaway design issue with the round cap hit once.
