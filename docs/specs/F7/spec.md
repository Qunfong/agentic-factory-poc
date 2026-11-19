# F7: Meter types, per-type units and summaries

Source: feature issue #7.

## Problem

A site has meters of several types (electricity, solar panels, EV chargers, gas meters, batteries, transformers), each with its own natural unit. An operator registers a meter once with its type, posts readings against it, and sees totals per type. Today the service accepts readings for any meter id, has no notion of a meter type, and calls the quantity `kwh` for every reading.

## Grounding

- Capability touched: readings, package `com.example.meter`. Today `ReadingController` holds the HTTP mapping, the `Reading` record and the in-memory storage (`CopyOnWriteArrayList`). There is no service, repository, persistence or security package.
- ADRs: 0001 (reference architecture). No ADR covers the readings module. `ArchitectureTest` forbids controllers depending on `@Repository` classes and forbids field injection, so storage moves into a constructor-injected `@Service`, not a `@Repository`.
- Existing tests: `ReadingControllerTest` and `ReadingDeleteTest` post readings for meters that are never registered. After this feature those posts return 404, so both classes must change. That is a protected change (see Open questions 1).
- New design choices, proposed for the plan gate:
  - [proposed-reading-quantity-field](../../adr/proposed-reading-quantity-field.md): the reading field `kwh` becomes `quantity`.
  - [proposed-meter-service-storage](../../adr/proposed-meter-service-storage.md): meters and readings live in one in-memory `MeterService`, shared by the controllers.
- No new top-level technical packages, no `app/pom.xml` change, no migration (storage stays in memory).

## Data shape

```java
package com.example.meter;

/** Wire value is the lowercase name; the unit is fixed per type. */
public enum MeterType {
    ELECTRICITY("electricity", "kWh"),
    SOLAR("solar", "kWh"),
    EV_CHARGER("ev_charger", "kWh"),
    GAS("gas", "m3"),
    BATTERY("battery", "kWh"),
    TRANSFORMER("transformer", "kW");

    MeterType(String wire, String unit) { /* not implemented */ }

    @JsonValue public String wire() { /* not implemented */ }
    public String unit() { /* not implemented */ }

    /** Exact, case-sensitive match on the wire value; throws UnknownMeterTypeException otherwise. */
    @JsonCreator public static MeterType fromWire(String value) { /* not implemented */ }
}

public record Meter(String id, MeterType type) {
    public String unit() { /* not implemented: type.unit() */ }
}

// POST /meters request and response
public record RegisterMeterRequest(@NotBlank String id, @NotNull MeterType type) {}
public record MeterResponse(String id, MeterType type, String unit) {}

// POST /readings request: the client sends no type or unit
public record ReadingRequest(@NotBlank String meterId, @NotNull Instant takenAt,
                             @NotNull @DecimalMin("0") @JsonAlias("kwh") BigDecimal quantity) {}

// stored reading and the response of POST /readings and GET /readings
public record Reading(String meterId, Instant takenAt, BigDecimal quantity,
                      MeterType type, String unit) {}

// GET /summary
public record TypeSummary(MeterType type, String unit, BigDecimal total) {}
```

- `quantity` and `total` are `BigDecimal`; `takenAt` is `Instant` (UTC). Totals are exact sums, no rounding.
- `type` and `unit` on a reading are set by the server from the registered meter. A meter's type cannot change (there is no update endpoint), so stamping them at post time is the same as looking them up at read time. Any `type` or `unit` a client sends in a reading body is ignored.
- Units are the literal strings `kWh`, `m3` and `kW`.

Example bodies:

```json
POST /meters      {"id": "pv-1", "type": "solar"}
-> 201            {"id": "pv-1", "type": "solar", "unit": "kWh"}

POST /readings    {"meterId": "pv-1", "takenAt": "2026-01-01T00:00:00Z", "quantity": 12.5}
-> 201            {"meterId": "pv-1", "takenAt": "2026-01-01T00:00:00Z", "quantity": 12.5, "type": "solar", "unit": "kWh"}

GET /summary?type=solar
-> 200            {"type": "solar", "unit": "kWh", "total": 12.5}

GET /summary
-> 200            [{"type": "electricity", "unit": "kWh", "total": 0},
                   {"type": "solar", "unit": "kWh", "total": 12.5},
                   {"type": "ev_charger", "unit": "kWh", "total": 0},
                   {"type": "gas", "unit": "m3", "total": 0},
                   {"type": "battery", "unit": "kWh", "total": 0},
                   {"type": "transformer", "unit": "kW", "total": 0}]
```

## Interfaces

HTTP:

```
POST   /meters                 -> 201 MeterResponse | 400 | 409
POST   /readings               -> 201 Reading       | 400 | 404
GET    /readings?meterId=<id>  -> 200 List<Reading>
DELETE /readings?meterId=<id>  -> 204 (unchanged)
GET    /summary?type=<type>    -> 200 TypeSummary   | 400
GET    /summary                -> 200 List<TypeSummary> (one entry per MeterType, enum order)
```

Service (`MeterService`, `@Service`, constructor-injected into controllers; holds the storage):

```java
@Service
public class MeterService {
    private final ConcurrentMap<String, Meter> meters = new ConcurrentHashMap<>();
    private final List<Reading> readings = new CopyOnWriteArrayList<>();

    /** Atomic putIfAbsent; throws MeterAlreadyRegisteredException if the id exists. */
    public Meter register(String id, MeterType type) { /* not implemented */ }

    /** Throws MeterNotFoundException if the meter is not registered. */
    public Reading addReading(ReadingRequest request) { /* not implemented */ }

    public List<Reading> readingsOf(String meterId) { /* not implemented */ }

    /** removeIf on meterId; registration of the meter stays. */
    public void deleteReadingsOf(String meterId) { /* not implemented */ }

    public TypeSummary summary(MeterType type) { /* not implemented */ }

    public List<TypeSummary> summaries() { /* not implemented */ }
}
```

Controllers (all in `com.example.meter`):

```java
@RestController @RequestMapping("/meters")
public class MeterController {
    public MeterController(MeterService service) { /* not implemented */ }

    @PostMapping @ResponseStatus(HttpStatus.CREATED)
    public MeterResponse register(@Valid @RequestBody RegisterMeterRequest request) { /* not implemented */ }
}

@RestController @RequestMapping("/readings")
public class ReadingController {
    public ReadingController(MeterService service) { /* not implemented */ }

    @PostMapping @ResponseStatus(HttpStatus.CREATED)
    public Reading add(@Valid @RequestBody ReadingRequest request) { /* not implemented */ }

    @GetMapping
    public List<Reading> list(@RequestParam String meterId) { /* not implemented */ }

    @DeleteMapping @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteByMeter(@RequestParam String meterId) { /* not implemented */ }
}

@RestController @RequestMapping("/summary")
public class SummaryController {
    public SummaryController(MeterService service) { /* not implemented */ }

    @GetMapping(params = "type")
    public TypeSummary byType(@RequestParam String type) { /* not implemented: MeterType.fromWire(type) */ }

    @GetMapping(params = "!type")
    public List<TypeSummary> all() { /* not implemented */ }
}

@RestControllerAdvice
public class MeterProblemHandler {
    @ExceptionHandler ProblemDetail alreadyRegistered(MeterAlreadyRegisteredException e) { /* not implemented */ }
    @ExceptionHandler ProblemDetail notFound(MeterNotFoundException e) { /* not implemented */ }
    @ExceptionHandler ProblemDetail unknownType(UnknownMeterTypeException e) { /* not implemented */ }
}

public class MeterAlreadyRegisteredException extends RuntimeException { /* not implemented */ }
public class MeterNotFoundException extends RuntimeException { /* not implemented */ }
public class UnknownMeterTypeException extends RuntimeException { /* not implemented */ }
```

The three exceptions and the advice may live as nested types of `MeterService` and `MeterController` if the builder prefers fewer files, but they stay inside the paths of the work item that introduces them.

Error cases:

| Case | `ProblemDetail` type | Status |
| --- | --- | --- |
| `POST /meters` with blank or missing `id`, or missing `type` | `about:blank` (bean validation) | 400 |
| `POST /meters` with a `type` that is not one of the six wire values | `about:blank` (`HttpMessageNotReadableException`) | 400 |
| `POST /meters` with an id that is already registered | `/problems/meter-already-registered` | 409 |
| `POST /readings` failing bean validation (blank `meterId`, missing `takenAt`, missing or negative `quantity`) | `about:blank` | 400 |
| `POST /readings` for a meter id that is not registered | `/problems/meter-not-found` | 404 |
| `GET /summary?type=` with an empty or unknown type | `/problems/unknown-meter-type` | 400 |
| `meterId` query parameter missing on `GET` or `DELETE /readings` | `about:blank` | 400 (unchanged) |

Order on `POST /readings`: bean validation runs first (400), then the registration check (404). A negative quantity for an unregistered meter is a 400.

Idempotency:
- `POST /meters`: the key is the meter `id`. Registration is a single atomic `putIfAbsent`, so a retried request never creates a second meter and never changes the type. A retry after a success gets 409, as the issue asks for a duplicate id (see Open questions 3).
- `DELETE /readings`: idempotent, key `meterId` (unchanged).
- `POST /readings`: not idempotent today; a retried post stores a second reading and the summary counts it twice. This feature does not change that (see Open questions 9).

Concurrency: meters are never removed, so checking registration and then appending the reading has no race that matters.

## Behaviour per AC

### AC-F7-1

`POST /meters` with `{"id": <id>, "type": <type>}` registers a meter and returns 201 with `{id, type, unit}`.
- `type` must be one of `electricity`, `solar`, `ev_charger`, `gas`, `battery`, `transformer`, matched exactly (lowercase). Anything else, including `"Solar"`, `"EV_CHARGER"` or a missing type, is rejected with 400 and nothing is stored.
- An `id` that is already registered is rejected with 409, whatever type the second request carries; the first registration is unchanged.
- A blank or missing `id` is rejected with 400.
- Meter ids match exactly and case-sensitively, the same match `GET /readings` uses.

### AC-F7-2

`POST /readings` for a `meterId` that has not been registered through `POST /meters` returns 404 and stores nothing. For a registered meter it returns 201 as before. Bean validation of the body still comes first (400 before 404).

### AC-F7-3

Each type has a fixed unit: `kWh` for `electricity`, `solar`, `battery` and `ev_charger`; `m3` for `gas`; `kW` for `transformer`. The reading's `quantity` is validated as before: required, `BigDecimal`, at least 0 (a negative value returns 400 for every type). The client does not send a unit; the unit of a reading is the unit of its meter's type. The old field name `kwh` is still accepted on input as an alias of `quantity` (ADR proposal).

### AC-F7-4

`GET /readings?meterId=<id>` returns each reading with `meterId`, `takenAt`, `quantity`, `type` and `unit`, where `type` is the meter's registered type and `unit` its unit. The `POST /readings` response has the same shape. For an id with no readings (registered or not) the response is 200 with `[]`, as today (see Open questions 7).

### AC-F7-5

`GET /summary?type=<type>` returns 200 with `{type, unit, total}`, where `total` is the exact `BigDecimal` sum of `quantity` over all stored readings whose meter has that type. Readings removed by `DELETE /readings` are not counted. If the type has no meters or no readings, `total` is `0`. An empty or unknown `type` returns 400.

### AC-F7-6

`GET /summary` without a `type` parameter returns 200 with a list of exactly six `TypeSummary` entries, one for every meter type in the order `electricity`, `solar`, `ev_charger`, `gas`, `battery`, `transformer`, each computed as in the per-type summary. Types without readings appear with `total` `0`. Totals of different types are never added together.

### AC-F7-7

`DELETE /readings?meterId=<id>` behaves as before for every meter type: it removes only the readings whose `meterId` equals `<id>`, returns 204 with no body, also when there is nothing to delete or the id is not registered, and returns 400 without `meterId`. It does not unregister the meter: after the delete, new readings for that id are accepted and carry the same type and unit. The per-type summaries drop the deleted readings and keep all others.

## Out of scope

- Unit conversion between types; adding totals across types.
- Time-windowed summaries (daily, monthly).
- Authentication and authorization of who may register a meter or post readings.
- Listing, updating, changing the type of, or deleting meters.
- Persistence beyond memory: meters and readings are lost on restart, as readings are today.
- Idempotency of `POST /readings`.

## Open questions

1. **Protected change and the F16 scenario.** Requiring registration before posting breaks `ReadingControllerTest` and `ReadingDeleteTest`, which post readings for meters that are never registered. These are existing tests under `app/src/test` (ask first). The hidden acceptance scenario for the F16 delete feature probably does the same; it runs on every later work-item PR and would go red. Needed before the readings work item can pass verify: (a) the product owner confirms there is no grandfathering or auto-registration of unknown meter ids; (b) approval to add a meter registration step (and the `quantity` field name, if that ADR is accepted) to the two existing test classes; (c) QA updates the F16 scenario to register its meters first.
2. **Status codes for a rejected registration.** The issue says "rejected" without a status. This spec uses 409 for a duplicate id and 400 for an unknown type. Please confirm, since the hidden scenarios will check them.
3. **Duplicate id with the same type.** The issue rejects every duplicate id. A client that retries a successful registration then gets 409 instead of a success. Should a repeat with the same id and the same type return 200 (an idempotent replay) instead? This spec follows the issue: 409.
4. **Transformer in kW.** kW is power, not energy. A sum of kW readings has no physical meaning. Should the transformer summary still be a sum (as this spec does, following the issue), or something else such as the maximum or the average, or should transformers be left out of the summaries?
5. **Field name.** Readings of gas and transformer meters are not in kWh, so this spec renames `kwh` to `quantity` and keeps `kwh` as an input alias (ADR proposal). The response no longer has `kwh`, which breaks clients that read it. Accept, or keep `kwh` on the wire?
6. **Case of type values.** This spec accepts only the exact lowercase wire values. Should `Solar` or `EV_CHARGER` also be accepted?
7. **`GET /readings` for an unregistered meter.** The issue only asks for 404 on posting. This spec keeps 200 with `[]` for listing. Should listing an unregistered meter also return 404?
8. **Empty types in the full summary.** This spec lists all six types and shows 0 for types with no meters or readings. Should types without registered meters be left out?
9. **Duplicate readings.** A retried `POST /readings` stores the reading twice, and the summaries now count it twice. Is there a business key (for example `meterId` + `takenAt`) that should make a repeat a no-op? Not defined by the issue, so this spec does not change it.
10. **Battery discharge.** The issue keeps the non-negative rule for all types, so a battery cannot report discharge as a negative quantity. Is that intended?
