# F70 plan: the tester may update declared existing tests; the builder still never touches tests

Spec: [spec.md](spec.md). Work items: [work-items.json](work-items.json). Decision followed: [proposed-tester-updates-declared-tests](../../adr/proposed-tester-updates-declared-tests.md). New ADR proposal: [proposed-test-method-count-by-annotation-scan](../../adr/proposed-test-method-count-by-annotation-scan.md).

## Modules that change

- `tools/check_paths.py`: `Policy.modify_allowed` and a `--modify-allowed PATH` option. It exempts exact paths from the `new_files_only` / `protect_existing` "existing file changed" rule. Nothing else changes.
- `tools/publish.py`: `tester_modifiable_paths()`, `count_test_methods()`, `check_test_method_counts()`; the `tester` branch in `publish()`. The builder branch is unchanged.
- `tools/tests/test_check_paths.py`, `tools/tests/test_publish.py`: new cases. Existing cases stay as they are; the new ones are added, not rewritten.

Unchanged: `publish.yml` (it already passes `--issue-paths` for every role, and the trusted copy list already holds both files), `30-build.yml`, `tools/tester_loop.py`, `factory/**`, `app/**`.

One work item. All four ACs are the same publish-guard slice in the same two files, and AC-4 is the regression boundary of AC-1. Splitting them would give two items that edit `test_publish.py` at once.

## Ordered steps (WI-1)

1. `check_paths.py`: add `modify_allowed: frozenset` to `Policy`. In `violations()`, skip the "existing file changed" reason when `c.paths[0] in policy.modify_allowed`; the allow-glob, status and link checks still apply. CLI `--modify-allowed`: each value must pass `unsafe()` and contain no `*?[`, otherwise exit 1. Tests:
   - M on an allowed path is ok under `--new-files-only`;
   - M on another path is still rejected;
   - D on an allowed path is still rejected;
   - a glob value is refused.
2. `publish.py`: `tester_modifiable_paths(paths, base_sha)` filters per the spec's Data shape, using `git cat-file -e <base>:<p>`.
3. `publish.py`: `count_test_methods(src)`. Blank text blocks, string and char literals, `/* */` and `//` comments in a single left-to-right scan, then count `@(?:org\.junit\.jupiter\.api\.)?Test\b(?!\w)` and `@(?:org\.junit\.jupiter\.params\.)?ParameterizedTest\b`. Make sure `@TestFactory` and `@TestTemplate` do not match `@Test`.
4. `publish.py`: in `publish()` for `role_name == "tester"`, extend `role_guard` with `--modify-allowed` per declared path. After the guard passes, call `check_test_method_counts(modifiable, base_sha)`. It compares `git show <base>:<p>` with `git show :<p>` (the index) for each path that `git diff --cached --name-status --no-renames <base>` lists as `M`.
5. `test_publish.py`, one test per AC (the temp repo base already has `app/src/test/ATest.java`; give it two `@Test` methods):
   - AC-F70-1: `Paths: app/src/test/ATest.java`; the patch adds a third method; publish returns `wi-7` and makes one `test: WI #7` commit.
   - AC-F70-2: three cases rejected, with HEAD still at base: modify an undeclared `app/src/test/BTest.java`; delete the declared `ATest.java`; `git mv` the declared file. A fourth case: `Paths: app/src/test/**`, modify `ATest.java`, rejected.
   - AC-F70-3: declared `ATest.java` loses one `@Test`, rejected with `dropped from 2 to 1`. A second case comments one out with `// @Test`, also rejected. A third case changes `@Test` to `@ParameterizedTest`, accepted.
   - AC-F70-4: builder with `Paths: app/src/main/A.java, app/src/test/ATest.java`, modifying `ATest.java`, rejected. The same with `Paths:` of only `app/src/test/ATest.java` (fallback guard), and with no `Paths:`, both rejected.
   - Plus unit tests for `count_test_methods` (comments, strings, text blocks, fully qualified names, `@TestFactory`).
6. Run `python -m unittest discover -s tools/tests` and `mvn -B -f app/pom.xml verify`. The app is untouched, so this only checks for regressions.

## Risks

- **Red tier, trusted code.** Both files run in the App-token publish job. A bug that widens `modify_allowed`, for example by matching a glob or a case variant, would let an agent change tests unseen. Mitigations: exact string equality, literal paths only, and the same deny checks as before. This needs the security owner's review per the risk map.
- **Text-based counting can be fooled**, for example by an annotation inside a string the scanner mis-blanks, or by `@Test` on a method whose body is emptied. The count catches deleted tests, not weakened ones (ADR proposal, Consequences).
- **The feature is inert until spec Open questions 1 is resolved.** The guard will accept a modifying patch, but the tester agent cannot yet produce one.
- **Issue-body trust.** `Paths:` comes from the work-item issue body, the same source and trust as ADR-0020. Anyone who can edit the issue can widen which tests the tester may modify. This is already true for the builder, and it does not get worse here.
- **Self-judging build** (spec Open questions 4). If the factory builds WI-1, the builder writes both the guard and its Python tests.
