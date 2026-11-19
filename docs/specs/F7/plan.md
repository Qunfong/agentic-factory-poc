# F7 plan: Meter types, per-type units and summaries

Spec: [spec.md](spec.md). Three work items, merged in order WI-1 -> WI-2 -> WI-3.

## Modules that change

All in `com.example.meter` (no new top-level packages):

| File | WI | Change |
| --- | --- | --- |
| `MeterType.java` | 1 | new enum: wire value, unit, `fromWire` |
| `Meter.java` | 1 | new record |
| `MeterService.java` | 1, 2, 3 | new `@Service`: meters map (WI-1), readings storage (WI-2), summaries (WI-3) |
| `MeterController.java` | 1 | new: `POST /meters` |
| `MeterProblemHandler.java` | 1, 2, 3 | new `@RestControllerAdvice`: 409 (WI-1), 404 (WI-2), 400 unknown type (WI-3) |
| `MeterAlreadyRegisteredException.java`, `UnknownMeterTypeException.java` | 1 | new |
| `MeterNotFoundException.java` | 2 | new |
| `Reading.java`, `ReadingRequest.java` | 2 | new top-level records; replace the nested `ReadingController.Reading` |
| `ReadingController.java` | 2 | constructor-inject `MeterService`; storage moves out |
| `SummaryController.java` | 3 | new: `GET /summary` |
| tests: `MeterRegistrationTest`, `ReadingMeterTypeTest`, `SummaryTest` | 1, 2, 3 | new |
| tests: `ReadingControllerTest`, `ReadingDeleteTest` | 2 | **protected change**: register meters first; `kwh` -> `quantity` in the `jsonPath` assertion |

No change to `app/pom.xml` (validation and Jackson are already on the classpath), migrations, security, billing or factory paths. Risk tier: amber (default for `app/src/main/java` and `app/src/test`).

## Steps

### WI-1: register meters by type (AC-F7-1)

1. Add `MeterType` with the six constants, `@JsonValue wire()`, `unit()` and `@JsonCreator fromWire` (exact match, otherwise `UnknownMeterTypeException`).
2. Add `Meter`, `MeterService.register` (`ConcurrentHashMap.putIfAbsent`; existing id -> `MeterAlreadyRegisteredException`).
3. Add `MeterController` with `POST /meters` (`@Valid RegisterMeterRequest`, 201 `MeterResponse`), and `MeterProblemHandler` mapping the duplicate to 409 `ProblemDetail`.
4. `MeterRegistrationTest` (`@WebMvcTest(MeterController.class)` + `@Import(MeterService.class)`): 201 for each of the six types with the right unit; 409 on a duplicate id (same and different type); 400 for an unknown type, a wrong-case type, a missing type, a blank id.
5. `mvn -B -f app/pom.xml verify`. Existing tests stay green: readings are not touched yet.

### WI-2: readings belong to a registered meter and carry its type and unit (AC-F7-2, AC-F7-3, AC-F7-4, AC-F7-7)

Blocked until open question 1 of the spec is answered (protected change).

1. Add top-level `Reading` and `ReadingRequest` (`quantity` with `@JsonAlias("kwh")`, `@DecimalMin("0")`).
2. Move the readings list into `MeterService`: `addReading` (unknown meter -> `MeterNotFoundException`), `readingsOf`, `deleteReadingsOf`. Map the exception to 404 in `MeterProblemHandler`.
3. `ReadingController` gets `MeterService` by constructor and delegates; its three mappings and paths stay the same.
4. `ReadingMeterTypeTest` (`@WebMvcTest({ReadingController.class, MeterController.class})` + `@Import(MeterService.class)`): 404 for an unregistered meter; 400 before 404 for a negative quantity; type and unit in the POST response and the GET list for kWh, m3 and kW types; `kwh` accepted as input alias; negative quantity 400 for a gas meter; delete removes only its own meter's readings across types, keeps the registration, and new readings after the delete still carry the type.
5. With approval: change `ReadingControllerTest` and `ReadingDeleteTest` to register their meters first, to `@Import(MeterService.class)`, and to assert `quantity` instead of `kwh`. Keep the test intent unchanged.
6. `mvn -B -f app/pom.xml verify`.

### WI-3: summaries per type (AC-F7-5, AC-F7-6)

1. `MeterService.summary(type)` and `summaries()`: sum `quantity` of readings with that type, `BigDecimal.ZERO` start; all six types in enum order.
2. `SummaryController`: `GET /summary` with `params = "type"` (parse with `MeterType.fromWire`) and `params = "!type"`. Map `UnknownMeterTypeException` to 400 in `MeterProblemHandler`.
3. `SummaryTest` (`@WebMvcTest({SummaryController.class, ReadingController.class, MeterController.class})` + `@Import(MeterService.class)`): total of one type over several meters; other types not mixed in; 0 for an empty type; deleted readings not counted; 400 for `type=` and an unknown type; full summary has six entries in order with units.
4. `mvn -B -f app/pom.xml verify`.

## Risks

- **Existing tests and the F16 scenario go red in WI-2** unless the protected change is approved and the hidden F16 scenario is updated first (spec, open question 1). WI-2 cannot pass verify without both.
- **Shared state across tests.** `MeterService` is one bean per cached Spring context, so tests in the same context see each other's meters and readings. Use unique meter ids per test, and in summary tests assert on differences or use types no other test in that context writes to; do not assert absolute totals that other tests could change.
- **Wire break.** Responses no longer carry `kwh` (ADR proposal `proposed-reading-quantity-field`). Any client that reads `kwh` breaks.
- **`@WebMvcTest` slicing.** A `@Service` is not part of a `@WebMvcTest` slice; every web test must `@Import(MeterService.class)` or the context fails to start (ADR proposal `proposed-meter-service-storage`).
- **Transformer totals** are a sum of kW values (spec, open question 4); the meaning may change after the product owner answers.
- `MeterService` and `MeterProblemHandler` appear in the paths of all three work items; the strict order WI-1 -> WI-2 -> WI-3 avoids merge conflicts.
