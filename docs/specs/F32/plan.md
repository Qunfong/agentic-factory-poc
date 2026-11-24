# F32 plan: GET /meters/{id}

Spec: [spec.md](spec.md). Work items: [work-items.json](work-items.json).

## Modules that change

| File | WI | Change |
| --- | --- | --- |
| `MeterController.java` | 1 | add `@GetMapping("/{id}") get(id)` |
| `MeterService.java` | 1 | add `find(id)`, which throws `MeterNotFoundException` |
| `MeterNotFoundException.java` | 1 | new |
| `MeterProblemHandler.java` | 1 | add 404 handler `/problems/meter-not-found` |
| `MeterLookupTest.java` (test) | 1 | new test class. No existing test changes |

## Steps (WI-1, AC-F32-1 and AC-F32-2)

1. Add `MeterNotFoundException(String id)` with the message `Meter '<id>' is not registered`.
2. Add `MeterService.find(id)`: `meters.get(id)`, and throw `MeterNotFoundException` on null.
3. Add an `@ExceptionHandler` in `MeterProblemHandler` that returns a 404 `ProblemDetail` with type `/problems/meter-not-found` and title `Meter not found`.
4. Add `MeterController.get(@PathVariable String id)`, mapping `Meter` to `MeterResponse`.
5. Add `MeterLookupTest` (`@WebMvcTest(MeterController.class)` with `@Import(MeterService.class)`, like `AC_F7_1_MeterRegistrationTest`). Test names carry the AC IDs. It covers:
   - AC-F32-1: register, then GET returns 200 with id, type and unit, for each of the six types; one meter among several.
   - AC-F32-2: 404 problem+json with the type URI on an empty registry; a case-sensitive miss; an id whose registration failed is still a 404.
6. Run `mvn -B -f app/pom.xml verify`.

## Risks

- **Overlap with F7 WI-2 (not built).** F7 WI-2 also plans `MeterNotFoundException` and a 404 handler in `MeterProblemHandler`. Whichever WI lands second must reuse the existing class and handler instead of adding a duplicate. Both use the same type URI, `/problems/meter-not-found`, so the wire contract is the same either way.
- **The response shape includes `unit`** (spec open question 1). If the plan gate wants only id and type, step 4 changes and the record becomes a separate one.
- Neither step is protected: no pom, no migration, no existing-test change, no red-tier path.
