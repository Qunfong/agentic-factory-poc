# Proposed ADR: The fix-round classifier reads the `build-test` job log through the API and maps it only onto repo paths

- **Status:** Proposed (spec writer, F71, 2026-11-27)
- **Decision makers:** tech lead at the plan gate; security owner for the red-tier change
- **Modules:** `.github/workflows/45-fix-round.yml`, `tools/classify_failures.py` (new)
- **Spec:** [docs/specs/F71/spec.md](../specs/F71/spec.md)

## Context

F71 makes `45-fix-round` decide between a builder round and an immediate escalation, based on which files failed in `40 verify`'s `build-test`. That job runs agent-written code, so every byte it produces is untrusted. Today it saves only its GitHub job log, with no surefire reports and no log artifact. The decision and the escalation comment must come from a trusted tool (ADR-0006). The comment must quote no raw log text.

## Decision

1. The trusted `classify` job in `45-fix-round` downloads the `build-test` **job log through the Actions API** (`actions: read`, the same jobs listing `gate` already uses). `40-verify.yml` does not change.
2. `tools/classify_failures.py`, run from `github.workflow_sha`, treats the log as data. It keeps a candidate path only if it matches `^app/src/(main|test)/java/[A-Za-z0-9_/]+\.java$` and exists in the head commit's git tree. The failure kind comes from a closed vocabulary. The comment is built only from those two things, plus fixed text and the numeric run id.
3. The classifier **fails toward today's behaviour**. Whenever it is not certain (unparsed shape, size cap, API or git error), the result is a normal builder round, never an escalation and never a dropped round.

## Alternatives considered

- **Upload `app/target/surefire-reports/*.xml` and the compiler output as an artifact from `build-test`.** This gives structured input instead of console regexes. Rejected for now: it changes `40-verify.yml`, the `required` check's own workflow. The artifact is written by the same untrusted job, so it is no more trustworthy than the log, and it would still need the same path and vocabulary filtering. Surefire XML also does not carry compile errors. Revisit if log parsing proves brittle.
- **Re-run the build in the trusted job.** Rejected: that runs agent code in a job holding `issues: write` / `actions: write` tokens, which reverses ADR-0006 and the "agent code runs without secrets" rule of `40-verify`.
- **Parse the log inline in shell in the workflow.** Rejected: it cannot be unit-tested in `tools/tests`, and shell handling of untrusted text invites injection.
- **Fail toward escalation when uncertain.** Rejected: it would turn every unfamiliar red into a human task and change the behaviour that F71's third criterion keeps as today's.

## Consequences

- No change to the verify workflow or to the `required` check.
- A Maven, surefire or GitHub log-format change degrades F71 to today's behaviour, silently except for the `reason` in the job summary. Fixture logs in `tools/tests` pin the expected formats.
- Agent code can print forged compiler lines. The worst result is an early escalation to a person (spec Open question 4).
- The classifier's output is exactly what a later test-repair role (D68 alternative B) would dispatch on, so adding one does not undo this decision.

## Revisit when

Log parsing is `unparsed` for a real collateral-breakage case, or `40-verify` starts publishing structured test reports for another reason.
