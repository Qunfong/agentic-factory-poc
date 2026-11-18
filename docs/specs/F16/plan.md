# F16 plan: Delete the readings of a meter

Spec: [spec.md](spec.md). One work item, WI-1.

## Modules that change

- `app/src/main/java/com/example/meter/ReadingController.java`: add the `DELETE` mapping.
- `app/src/test/java/com/example/meter/ReadingDeleteTest.java`: new test class (existing tests stay untouched; changing them is a protected change).

No change to `app/pom.xml`, migrations, security, billing or factory paths. Risk tier: amber (default for `app/src/main/java`).

## Steps (WI-1)

1. Add `deleteByMeter(@RequestParam String meterId)` with `@DeleteMapping` and `@ResponseStatus(HttpStatus.NO_CONTENT)` to `ReadingController`; body `readings.removeIf(r -> r.meterId().equals(meterId))`.
2. Add `ReadingDeleteTest` (`@WebMvcTest(ReadingController.class)`), covering:
   - post readings for `m1` and `m2`, delete `m1` -> 204, `GET m1` -> `[]`, `GET m2` still has its reading;
   - delete a meter with no readings -> 204;
   - delete twice -> 204 both times;
   - delete without `meterId` -> 400.
3. Run `mvn -B -f app/pom.xml verify`.

## Risks

- The in-memory list is shared per application context; tests that post to the same meter id can see each other's data if the context is reused. Use unique meter ids per test.
- Unauthenticated delete is a data-loss path once the service has real data (open question 1 in the spec).
- Blank `meterId` behaviour is not defined yet (open question 2); do not add validation for it in WI-1.
