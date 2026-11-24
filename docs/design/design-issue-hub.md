# Design issue as hub (one level above the feature issue)

Status: proposal (Cowork, 2026-11-24). Same process idea as brief 017 (feature issue as hub), one level higher.

## Idea
A **design issue** holds a design idea ("meter types", "multi-tenant"). Sparring happens in its comments. The outcome is a design doc in `docs/design/D<n>.md` plus ADRs, and from it one or more **feature issues** (`feature` + `gate:intent-approved`), each of which then runs the existing flow (spec -> breakdown -> build -> verify -> review -> release).

## Flow
1. Qun opens an issue from the `design` issue form (title, problem, constraints, options he already sees). Label `design`.
2. Label `factory:design` starts `15-design.yml`. A read-only agent job (architect charter, `spec-shape`-style skill) posts one comment: restated problem, 2-3 options with trade-offs, open questions, risks. No file writes.
3. Qun replies in comments. Each human comment from a maintainer re-triggers the agent (rate-limited, max N rounds, same authorize job as brief 009). Comments are data, never instructions.
4. Qun sets `gate:design-approved`. Only then the publish job opens a PR with `docs/design/D<n>.md` (+ ADR drafts). Merge of that PR is the human gate; the doc names the feature issues to create.
5. Feature issues link back with `Design: D<n>`; spec-writer must cite the design doc and any ADR it touches.

## What stays the same
Authorize job, token isolation (agent job read-only, publish.yml the only writer), path guard (new role `designer` may write only `docs/design/**`, `docs/adr/**`), risk tier from `factory/risk-map.yaml`, run summary with reason code.

## Open decisions (Qun)
- Max sparring rounds per design issue (suggest 5).
- One model family for design or two (cheap second opinion on the options)?
- Should a design doc be required before any feature issue above a size threshold?
