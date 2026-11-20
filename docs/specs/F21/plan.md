# F21 plan: Count the stored readings

Spec: [spec.md](spec.md). One work item, WI-1, covering both ACs: they share one endpoint and one test class, and neither can merge usefully alone.

## Modules that change

- `app/src/main/java/com/example/meter/ReadingController.java`: add the `ReadingCount` record and the `GET /readings/count` mapping.
- `app/src/test/java/com/example/meter/ReadingCountTest.java`: new test class. Existing tests stay untouched (changing them is a protected change).

No change to `app/pom.xml`, migrations, security, billing or factory paths. Risk tier: amber (default for `app/src/main/java`).

## Steps (WI-1)

1. In `ReadingController`, add `public record ReadingCount(long count) {}` and
   `@GetMapping("/count") public ReadingCount count()` returning `new ReadingCount(readings.size())`.
2. Add `ReadingCountTest` (`@WebMvcTest(ReadingController.class)`), with `@DisplayName`s naming the AC IDs:
   - AC-F21-1: on a fresh context, `GET /readings/count` -> 200, `$.count` is `0`; post two readings -> count rises by 2; a rejected post (negative `kwh`) leaves it unchanged.
   - AC-F21-2: post readings for two meters, read the count, `DELETE /readings?meterId=<one>` -> 204, count drops by exactly that meter's readings; delete of an unknown meter leaves the count unchanged.
3. Run `mvn -B -f app/pom.xml verify`.

## Risks

- Shared state: the in-memory list lives per cached Spring context, and `ReadingControllerTest` / `ReadingDeleteTest` use the same `@WebMvcTest(ReadingController.class)` slice, so they may share a context. Tests must assert on deltas (count before vs after) rather than absolute values, except where the test class forces a fresh context (for example `@DirtiesContext`) for the `{"count": 0}` case.
- Hidden acceptance scenarios may assert `{"count": 0}` on a fresh context; the implementation must not seed data.
- F7 (not built yet) would move storage into `MeterService`. If F7 lands first, the builder computes the count through `MeterService` instead of the controller's list, and the web test must `@Import(MeterService.class)`; the HTTP contract here does not change.
