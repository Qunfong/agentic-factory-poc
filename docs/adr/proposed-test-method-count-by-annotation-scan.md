# Proposed ADR: The trusted publish job counts test methods by scanning annotations, not by parsing or running Java

- **Status:** Proposed (spec writer, F70, 2026-11-27)
- **Decision makers:** tech lead at the plan gate; security owner (red tier, `tools/**`)
- **Modules:** `tools/publish.py`
- **Spec:** [docs/specs/F70/spec.md](../specs/F70/spec.md); follows [proposed-tester-updates-declared-tests](proposed-tester-updates-declared-tests.md) point 2

## Context

F70 lets the tester modify existing test files that its work item declares. A trusted check must reject a patch that leaves such a file with fewer `@Test` or `@ParameterizedTest` methods than at the base commit (AC-F70-3). The check runs inside `publish.py`, in the App-token publish job. That job holds a write token, executes no agent code (ADR-0004, ADR-0006), and gets only the files `publish.yml` copies (`publish.py`, `check_paths.py`, `check_tier.py`, `requirements.txt`).

## Decision

Count with a pure-Python text scan in `publish.py`. Blank out comments, string and char literals and text blocks. Then count `@Test` / `@ParameterizedTest` annotation uses, plain or fully qualified, in the base blob and in the staged blob. Reject when the staged count is lower. There is no new dependency, no new file, and no Java execution.

## Alternatives considered

- **A Java parser (e.g. `javalang` from PyPI).** It is more exact: it sees annotations on real method declarations only. Rejected for now: it adds a hash-pinned dependency to the trusted publish requirements (ADR-0009). It would also be the first third-party parser to run on agent-written input in a job that holds the App token.
- **Run `mvn test-compile` plus JUnit discovery and count discovered tests.** This is the most exact. Rejected here: it executes agent-written code, so it cannot run in the publish job (ADR-0006). It would need a separate job without secrets. That is the post-tester gate of D68 feature 3, which can later add this as a second, stronger check.
- **Compare method names instead of counts.** Rejected: it blocks legitimate renames, and the AC asks for a count.

## Consequences

- The check is cheap, deterministic and dependency-free, and it is testable in `tools/tests/test_publish.py`.
- It catches deleted or commented-out test methods. It does not catch a test whose body was emptied, or one silenced with `@Disabled`. Assertion strength is still left to review.
- Undoing this decision (a switch to a parser or to discovery) means replacing `count_test_methods()` and, for discovery, moving the check to another job.

## Revisit when

D68 feature 3's secret-free `test-compile` job exists. JUnit discovery there can then replace or back up the scan.
