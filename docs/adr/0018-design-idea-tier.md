# ADR-0018: A design-idea tier, one level above a feature, feeds the same pipeline

- **Status:** Accepted (Claude Code, 2026-11-24, from Qun's own scoping questions in chat)
- **Date:** 2026-11-24
- **Decision makers:** @Qunfong
- **Confidence:** medium - first iteration, expect revision once a real idea has gone through it

## Decision

A new issue type, labelled `design`, sits one level above `feature`. It carries a problem or a
question, not acceptance criteria. The same intent gate (`gate:intent-approved`, ADR-016) starts a
new `design-writer` agent (08-design.yml), charter-scoped to `docs/design/D<issue>/**` and
`docs/adr/proposed-*.md` only - the same shape as the spec writer, one level up: alternatives and
tradeoffs instead of interfaces and work items (factory/skills/design-shape).

The design writer's PR is the **idea sign-off**: a person merges it, same as the spec PR's plan
gate, and it is explicitly excluded from the auto-merge in ADR-0019. If the design doc lists
"Proposed features" (one bullet per feature, "AC-n: ..." lines under each), merging that PR fires
12-decompose.yml, which creates one feature issue per bullet from the merged doc - labelled
`feature`, with no `gate:intent-approved` label. A product owner still approves each one before
08-design/10-spec can touch it; decomposition only drafts the issue.

## Alternatives considered

- **GitHub Discussions only, no PR.** Rejected for now: Qun asked for "the same idea regarding
  process" as features, i.e. a PR a person signs off on, with open questions handled as comments
  on that PR (the existing structural rule), not a separate medium. Discussions stay available for
  looser back-and-forth; this ADR does not wire them into the pipeline.
- **Skip decomposition, keep it manual.** Rejected: Qun asked for automatic feature generation on
  sign-off. The intent gate on each generated issue still requires a human (ADR-016), so this does
  not weaken that control.

## Consequences

A fifth role (`design-writer`) and branch shape (`design/D<n>`) exist in `tools/publish.py`,
alongside `spec-writer`/`tester`/`builder`. `tools/decompose.py` is a small, trusted, deterministic
parser (no agent, no model call) - it only ever reads the already-merged, already-signed-off
design.md, so a bad parse means no issues are created, never a wrong one silently approved.

## Revisit when

A real design idea has gone through this once. Likely candidates to reconsider: whether
`design.md`'s "Proposed features" shape is the right contract for `tools/decompose.py`, and
whether design ideas should get their own AI review pass (today 50-review only fires from
40-verify, which design PRs never enter, since they touch no code).
