# F70: The tester may update existing test files its work item declares in `Paths:`

Source: feature issue #70, decomposed from design idea #68 ([docs/design/D68/design.md](../../design/D68/design.md), alternative C, failure class 1).
Decision followed: [proposed-tester-updates-declared-tests](../../adr/proposed-tester-updates-declared-tests.md) (points 1-3; point 4, the fix-round classifier, is a separate feature).

## Problem

A work item's main-code change can break an older test it does not own (PR #56, PR #62: `ReadingControllerTest` stopped loading its context after `ReadingController` got a `MeterService` constructor parameter). Today no role can repair that test. The `tester` publish role runs with `--allow app/src/test/** --new-files-only`, so it may only add files. The `builder` never writes under `app/src/test/**` (ADR-0020). The design moves that judgment to the plan gate: when the spec writer lists an existing test file in a work item's `paths`, and a person merges the spec, the round-0 tester may modify that one file. It may not delete or rename it, and it may not reduce its number of test methods. The builder's guard does not change.

## Grounding

This is a factory-tooling change. No Spring capability package is touched, so the spec-shape rules about Java records, `BigDecimal` and `Instant` do not apply, and the shape below is sketched in Python, the language of the code that changes.

- `tools/publish.py` (trusted; `publish.yml` copies it from the workflow's own commit, ADR-0006):
  - `ROLES["tester"].guard = ("--allow", "app/src/test/**", "--new-files-only")`.
  - `builder_allowed_paths(paths)`: the work item's `Paths:` minus `app/src/test/**`, falling back to `app/src/main/**`; denied prefixes raise `Rejected` (ADR-0020).
  - `publish(...)` already receives `issue_paths` for **every** role. `publish.yml`'s `apply` step reads `Paths:` from the issue body and passes `--issue-paths` whatever the role is. Only the builder uses it today.
  - `remove_shadowed_stubs()`: a builder-only trusted side effect after the guard. It is unchanged.
- `tools/check_paths.py` (trusted, same copy step): `Policy(allow, protect_existing, new_files_only)`. Statuses other than `A`/`M` are always rejected, and `--no-renames` turns a rename into `D` + `A`, so a delete or rename is already rejected for every role. `--new-files-only` rejects every `M`.
- `publish.yml` copies exactly `publish.py check_paths.py check_tier.py requirements.txt` into the trusted directory. **Any new logic must live in those two files.** A new module would need a `.github/**` change, which is a protected change.
- `tools/create_work_items.py` writes `Paths: a, b, c` into the work-item issue body from `work-items.json`.
- `tools/tester_loop.py`'s `write_file` refuses to overwrite an existing file. `factory/prompts/tester.md` says "Never edit existing tests". `factory/charters/tester.yaml` denies "existing test files". All three are outside this feature's scope. See Open questions 1.
- Tests: `tools/tests/test_publish.py` (it builds a git repo in a temp dir and already has `test_tester_may_add_but_not_change_tests` and `test_builder_may_not_touch_tests`), and `tools/tests/test_check_paths.py`.
- ADRs read: 0004, 0005, 0006, 0020, proposed-tester-updates-declared-tests.
- No `app/pom.xml` change and no migration. Every changed path is under `tools/**`, which is **red tier** (risk-map red floor).

## Data shape

A **declared existing test file** for work item `n` at base commit `B` is a `Paths:` entry `p` that meets all of these:

1. `p` starts with `app/src/test/`;
2. `p` is a literal path: no `*`, `?`, `[`, and `check_paths.unsafe(p) == ""`;
3. `p` is a tracked blob at `B` (`git cat-file -e B:p`), with exact, case-sensitive equality.

Any other `Paths:` entry gives the tester nothing new. A non-test entry belongs to the builder, and a glob grants no modify right (Open questions 2). A test path that does not exist at `B` stays a new file, which the tester may add as today.

A **test method count** of a Java source text is the number of annotation uses `@Test` or `@ParameterizedTest` (also fully qualified, `@org.junit.jupiter.api.Test`, `@org.junit.jupiter.params.ParameterizedTest`), counted after `//` line comments, `/* */` block comments, string literals and text blocks have been blanked out. `@TestFactory`, `@RepeatedTest`, `@TestTemplate` and `@Disabled` are not counted and not treated specially (Open questions 3). The ADR proposal [proposed-test-method-count-by-annotation-scan](../../adr/proposed-test-method-count-by-annotation-scan.md) covers this choice.

## Interfaces

```python
# tools/check_paths.py
@dataclasses.dataclass(frozen=True)
class Policy:
    allow: tuple
    protect_existing: tuple = ()
    new_files_only: bool = False
    modify_allowed: frozenset = frozenset()   # exact repo paths whose status M is allowed even under new_files_only

def violations(changes, policy, base_paths=frozenset()):
    # not implemented: as today, except that an M on a path in policy.modify_allowed is not an
    # "existing file changed" violation. It still has to match policy.allow, and D/R/symlinks stay rejected.
    ...

# CLI: --modify-allowed PATH (repeatable; a literal path, rejected if unsafe() or if it contains a glob character)
```

```python
# tools/publish.py
def tester_modifiable_paths(paths, base_sha) -> list[str]:
    """Declared existing test files (see Data shape), sorted, de-duplicated. Never raises for a
    non-test or glob entry; ignores it."""
    # not implemented

def count_test_methods(java_source: str) -> int:
    """@Test / @ParameterizedTest annotation uses outside comments and string literals."""
    # not implemented

def check_test_method_counts(paths, base_sha) -> None:
    """For each declared path the staged patch modified: raise Rejected when
    count(index blob) < count(base blob). Names the file and both counts."""
    # not implemented

# in publish(): when role_name == "tester":
#   modifiable = tester_modifiable_paths(issue_paths or [], base_sha)
#   role_guard += tuple(x for p in modifiable for x in ("--modify-allowed", p))
#   ...after a green path guard: check_test_method_counts(modifiable, base_sha)
# The builder branch is unchanged and never gets --modify-allowed.
```

Error cases. Each raises `Rejected`; `main()` prints `::error::publish rejected: ...` and exits 1, so the push step never runs.

| Case | Message contains |
| --- | --- |
| tester modifies an existing test not declared | `path guard failed for role tester` (check_paths: `existing file changed; needs a protected-change request`) |
| tester deletes or renames any existing test, declared or not | `path guard failed for role tester` (check_paths: `status D is not publishable`) |
| declared file has fewer test methods than at base | `test method count for <path> dropped from <b> to <h>` |
| builder patch touches `app/src/test/**` | `path guard failed for role builder` |

Idempotency: publish is already deterministic per `(role, issue, base_sha, patch)` (fixed commit date, so a rerun rebuilds the same commit and its push is a no-op). The new checks read only the base commit, the index and the issue's `Paths:`, so a rerun gives the same verdict.

## Behaviour per AC

- **AC-F70-1.** The work item's `Paths:` lists `app/src/test/java/com/example/meter/ReadingControllerTest.java`, which exists at the base. A tester patch that modifies only that file (for example, it adds a `@MockBean MeterService`) passes the path guard and the method-count check. `publish()` returns `("tester" role, "wi-<n>")`, commits it as `test: WI #<n>`, and `publish.yml` pushes it to `wi-<n>`. A patch that also adds new test files is accepted as today.
- **AC-F70-2.** A tester patch is rejected and nothing is committed or pushed when it does any of these: modifies an existing `app/src/test/**` file that is not a declared existing test file; deletes any existing test file (declared or not); renames one (seen as `D` + `A`). A declared glob (`app/src/test/**`) does not count as declaring a file. Rejecting a mixed patch (one allowed modification and one forbidden one) rejects the whole patch.
- **AC-F70-3.** For each declared existing test file that the patch modifies, the test method count of the patched blob must be at least the count at the base commit. Moving a method from `@Test` to `@ParameterizedTest` keeps the count, and adding methods is allowed. Removing one, or commenting it out (`// @Test`), is rejected with both counts in the message.
- **AC-F70-4.** The builder role ignores the new tester rule completely. Whether `Paths:` lists a test file, an existing test file, only test files (fallback `app/src/main/**`), or nothing, a builder patch that adds, modifies, deletes or renames any `app/src/test/**` file is rejected by the path guard. `builder_allowed_paths()` keeps dropping test paths, and the builder guard never receives `--modify-allowed`.

## Out of scope

- `tools/tester_loop.py` letting the tester agent overwrite a declared file, `30-build.yml` passing the paths to it, and the tester prompt and charter wording (Open questions 1).
- The `45-fix-round` classifier and its immediate escalation (D68 feature 2) and the post-tester gate (D68 feature 3).
- Whether a PR that modifies an existing test still auto-merges (D68 open question 3, ADR-0019).
- Any check on assertion strength beyond the method count.

## Open questions

1. **The guard alone does not let a tester modify a test in practice.** `tester_loop.py`'s `write_file` refuses existing files. To relax it, the loop needs the declared paths, which means `30-build.yml` must pass the work item's `Paths:` (a protected `.github/**` change). Otherwise it would have to parse the prompt, which is fragile. `factory/prompts/tester.md` and `factory/charters/tester.yaml` must also change from "never edit existing tests" to "only the declared ones" (`factory/**`, a human change, red tier). Should F70 stay guard-only, with a follow-up feature plus a protected-change request for the loop, workflow, prompt and charter? Or should the loop change join this feature? This spec assumes guard-only, because that is what AC-1 to AC-4 describe.
2. **May a glob in `Paths:` grant a modify right?** This spec says no: only literal file paths grant it, so `app/src/test/**` can never open the whole test suite. Please confirm.
3. **What counts as a test method?** The AC names `@Test` and `@ParameterizedTest`. Should `@RepeatedTest`, `@TestFactory` and `@TestTemplate` count too? Should adding `@Disabled` to an existing test count as a reduction? This spec counts only the two named annotations and ignores `@Disabled`, which lets a tester silence a test without lowering the count.
4. **Who builds this work item?** Every path is `tools/**` (red tier), and its tests are Python under `tools/tests/`. The tester role can only add files under `app/src/test/**`, and hidden acceptance is Java (ADR-0007). So in the factory flow, the builder would write both the guard and the tests that judge it, which is the pattern D68 rejects. Should WI-1 be built by the factory at all, or by an interactive session on the factory (HANDOFF.md) with a human review?
