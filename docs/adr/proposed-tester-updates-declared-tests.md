# Proposed ADR: The tester may update existing tests its work item declares; the builder still never touches tests

- **Status:** Proposed (design writer, D68, 2026-11-27)
- **Decision makers:** @Qunfong (idea sign-off), then the tech lead for the charter and guard change
- **Modules:** `tools/publish.py` (tester role guard), `tools/tester_loop.py`, `factory/charters/tester.yaml`, `45-fix-round.yml`
- **Design:** [docs/design/D68/design.md](../design/D68/design.md)

## Context

A work item's main-code change can break a pre-existing test that it does not own. In PR #56 and
PR #62, `ReadingControllerTest` stopped loading its context after `ReadingController` got a
constructor dependency. The tester writes new files only (`--new-files-only`), and the builder
never writes under `app/src/test/**` (ADR-0020, builder charter). So no role can repair such a
test. `45-fix-round.yml` still dispatches up to two builder rounds that cannot help, then
escalates without a diagnosis.

## Decision

1. When a work item's `Paths:` line lists an **existing** file under `app/src/test/**`, the round-0
   tester may modify that file. It may still not delete or rename it, and may not modify any
   undeclared existing test. The guard follows the work item's `paths`, the same pattern ADR-0020
   uses for the builder.
2. A trusted check rejects a tester patch that reduces the number of test methods in a declared
   existing file.
3. The builder's guard is unchanged: never `app/src/test/**`.
4. `45-fix-round` uses a trusted classifier on the build output. When every failure is in an
   undeclared pre-existing test, it dispatches no builder round and escalates right away, naming
   the files and the failure kind.

The judgment "this work item may change that existing test" is made by the spec writer and signed
off by a person at the plan gate. It is never made by an agent at fix-round time.

## Alternatives considered

- **Let the fix-round builder modify pre-existing tests** (the idea's original hunch). Rejected for
  now: the author of the code would then edit the tests that judge it, which reverses the intent of
  ADR-0020.
- **A separate test-repair role dispatched by the classifier.** Deferred. It keeps separation of
  duties but adds a full red-tier role for a failure seen twice, and still changes tests without a
  human. The classifier from point 4 is what it would dispatch on, so it can be added later without
  rework.
- **Make the builder keep every existing test green by bending main code.** Rejected as a fix: it
  shapes production code around stale tests. It is kept only as advice in the `impact-check` skill.

## Consequences

- Anticipated breakage is fixed in round 0, before the builder runs, and stays visible in the plan.
- Unanticipated breakage still needs a person, but they get a diagnosis immediately instead of
  after two wasted builder rounds.
- `tester.yaml`'s `denied: existing test files` narrows to "existing test files not declared in
  paths". That is a red-tier `factory/**` change a person makes.
- Spec writers must name the existing tests a work item will break. Missing one costs a fast
  escalation, not a silent wrong merge.

## Revisit when

The classifier has escalated undeclared breakage a few times. If it is common, add the separate
test-repair role (design D68, alternative B) rather than widening the builder.
