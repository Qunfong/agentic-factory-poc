# F33 plan: GET /readings filters by date range and paginates

Spec: [spec.md](spec.md). ADR proposal: [proposed-readings-page-as-array](../../adr/proposed-readings-page-as-array.md).

One work item, WI-1, covering all three ACs: they change the same method signature of `GET /readings`, AC-F33-3 validates the parameters AC-F33-1 and AC-F33-2 introduce, and the tests share one fixture. Splitting would make each slice rewrite the same handler.

## Modules that change

- `app/src/main/java/com/example/meter/ReadingController.java`: `list` gets optional `meterId`, `from`, `to`, `page`, `size`; filter, stable sort by `takenAt`, skip/limit.
- `app/src/test/java/com/example/meter/ReadingRangePageTest.java`: new test class. Existing tests stay untouched (changing them is a protected change); `ReadingControllerTest` keeps passing because the response is still an array.

No change to `MeterProblemHandler` (Spring's 400s are already `ProblemDetail`), `app/pom.xml`, migrations, security, billing or factory paths. Risk tier: amber (default for `app/src/main/java`).

## Steps (WI-1)

1. In `ReadingController.list`, make `meterId` `required = false`; add `Instant from`, `Instant to` (`required = false`), `int page` (`defaultValue = "0"`, `@Min(0)`), `int size` (`defaultValue = "20"`, `@Min(1)`, `@Max(100)`). No class-level `@Validated`.
2. Implement: stream the list snapshot, filter by `meterId` if present, by `!takenAt.isBefore(from)` and `!takenAt.isAfter(to)` if present, `sorted(Comparator.comparing(Reading::takenAt))`, `skip((long) page * size)`, `limit(size)`.
3. Add `ReadingRangePageTest` (`@WebMvcTest(ReadingController.class)`), `@DisplayName`s naming the AC IDs. Use a unique `meterId` per test and pass it, so shared context state from other test classes does not leak in; for the "no meterId" case assert only on readings of the test's own meters via the range (pick timestamps no other test uses, e.g. year 2031).
   - AC-F33-1: readings at t1 < t2 < t3; `from=t1&to=t2` returns t1 and t2 (bounds inclusive); only `from`, only `to`; `from` with `%2B01:00` offset equals the `Z` form; no `meterId` still works.
   - AC-F33-2: post 25 readings out of order; default returns 20 in ascending order; `page=1` returns 5; `size=100` ok; page past the end is `[]`; equal timestamps keep insertion order.
   - AC-F33-3: `size=101`, `page=-1`, `from=nope`, `to=2026-01-01` each -> 400 with `application/problem+json`; `size=100`, `page=0` -> 200.
4. Run `mvn -B -f app/pom.xml verify`.

## Risks

- Behaviour change for existing `GET /readings?meterId=` callers (sorted, capped at 20); spec Open question 3. Hidden scenarios for F16/F21 do not depend on it as far as the specs say.
- Spring validation mode: a class-level `@Validated` gives 500 instead of 400. The AC-F33-3 tests catch this.
- Shared in-memory state per cached Spring context (see F21 plan): tests that call without `meterId` must constrain by a private time range or use `@DirtiesContext`.
- F7 WI-2 (not built) rewrites `ReadingController` and moves storage into `MeterService`. If it lands first, the builder moves the filter/sort/page logic into a `MeterService` method with the same parameters and the web test must `@Import(MeterService.class)`; the HTTP contract does not change. Whichever lands second resolves the conflict in `list`.
- Open questions 1, 2 and 4 are provisional; the plan gate may change them without changing the work item's paths.
