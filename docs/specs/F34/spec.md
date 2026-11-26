# F34: Input validation and one uniform error format on every endpoint

Source: feature issue #34.

## Problem

API clients get errors in different shapes today, so they cannot handle failures generically. Every endpoint must validate its input and return every failure in one predictable `application/problem+json` shape (RFC 9457) that names the offending field where there is one.

## Grounding

- Capability touched: meters and readings, package `com.example.meter`. No new package.
  - `MeterProblemHandler` (`@RestControllerAdvice`, extends `ResponseEntityExceptionHandler`): Spring's built-in MVC exceptions already become `ProblemDetail` (`about:blank`); `MeterAlreadyRegisteredException` becomes 409 `/problems/meter-already-registered`.
  - `MeterController` (`POST /meters`, `RegisterMeterRequest(@NotBlank id, @NotNull type)`), `MeterService` (in-memory registry, `register` only).
  - `ReadingController` (`POST /readings`, `GET /readings?meterId=`, `GET /readings/count`, `DELETE /readings?meterId=`); `Reading(@NotBlank meterId, @NotNull takenAt, @NotNull @DecimalMin("0") kwh)`; readings are still stored in the controller and never checked against the registry.
- What is wrong today, measured against the ACs:
  - Bean-validation 400s have `detail` "Invalid request content." and do not name the field (AC-F34-2, AC-F34-3).
  - The content type of a problem follows the request's `Accept` header, so a client sending `Accept: application/json` gets `application/json` (AC-F34-1).
  - `POST` (or `PUT`, `DELETE`) on an unknown path reaches the static-resource handler and returns 405, not 404 (AC-F34-6).
  - `POST /readings` for an unregistered meter returns 201 (AC-F34-4).
- ADRs: 0001 (reference architecture). [proposed-meter-service-storage](../../adr/proposed-meter-service-storage.md) (F7) is followed for the registry check. `ArchitectureTest` (no field injection, controllers never call `@Repository`) is respected.
- New design choice, proposed for the plan gate: [proposed-problem-field-errors](../../adr/proposed-problem-field-errors.md), how a problem names its offending fields.
- No `app/pom.xml` change (`spring-boot-starter-validation` is already there), no migration. One new non-protected file: `app/src/main/resources/application.properties`.
- Overlap: AC-F34-4 is the same behaviour as F7's registration check (F7 WI-2), which is specified but not built (see Open questions 1).

## Data shape

```java
package com.example.meter;

// Every error body is a org.springframework.http.ProblemDetail, serialised as RFC 9457:
// {"type": "...", "title": "...", "status": 400, "detail": "...", "instance": "/meters", ...extensions}
// type, title, status and detail are always present and non-null.

/** One offending input; extension property "errors" on validation problems (ADR proposal). */
public record FieldError(String field, String message) {}

/** Thrown by MeterService when a reading names a meter id that is not registered. */
public class MeterNotFoundException extends RuntimeException {
    public MeterNotFoundException(String id) { /* not implemented: "Meter '<id>' is not registered" */ }
}
```

Example bodies:

```json
POST /meters {"id": "", "type": "solar"}
-> 400 application/problem+json
{"type": "/problems/validation-failed", "title": "Invalid request", "status": 400,
 "detail": "Invalid field(s): id", "instance": "/meters",
 "errors": [{"field": "id", "message": "must not be blank"}]}

POST /readings {"meterId": "m1", "takenAt": "2026-01-01T00:00:00Z", "kwh": 1} (m1 not registered)
-> 404 application/problem+json
{"type": "/problems/meter-not-found", "title": "Meter not found", "status": 404,
 "detail": "Meter 'm1' is not registered", "instance": "/readings"}

POST /readings {not json
-> 400 application/problem+json
{"type": "/problems/malformed-request", "title": "Malformed request body", "status": 400,
 "detail": "The request body is not valid JSON or does not match the expected shape", "instance": "/readings"}

GET /nope
-> 404 application/problem+json
{"type": "/problems/not-found", "title": "Not Found", "status": 404,
 "detail": "No endpoint GET /nope", "instance": "/nope"}
```

- `field` is the JSON property name as the client sent it (`id`, `meterId`, `takenAt`, `kwh`), not a Java path. For a query parameter it is the parameter name.
- `errors` is sorted by `field`, then `message`, so the body is deterministic.
- `detail` never contains stack traces, class names or Jackson parser messages.
- Money/energy stays `BigDecimal` (`kwh`), time stays `Instant`; no data type changes.

## Interfaces

HTTP (success responses unchanged; error columns are what this feature guarantees):

```
POST   /meters                 -> 201 | 400 validation-failed | 400 malformed-request | 409 meter-already-registered
POST   /readings               -> 201 | 400 validation-failed | 400 malformed-request | 404 meter-not-found
GET    /readings?meterId=<id>  -> 200 | 400 validation-failed (missing meterId)
GET    /readings/count         -> 200
DELETE /readings?meterId=<id>  -> 204 | 400 validation-failed (missing meterId)
<any method> <unknown path>    -> 404 not-found
```

Error cases (`ProblemDetail` type, status, source):

| Case | `type` | Status | Source |
| --- | --- | --- | --- |
| Bean validation of a body fails | `/problems/validation-failed` | 400 | `MethodArgumentNotValidException` |
| Required query parameter missing or blank | `/problems/validation-failed` | 400 | `MissingServletRequestParameterException` |
| Body is not JSON, empty, wrong JSON type, unparseable `Instant`/`BigDecimal`, unknown meter type | `/problems/malformed-request` | 400 | `HttpMessageNotReadableException` |
| Meter id already registered | `/problems/meter-already-registered` (unchanged) | 409 | `MeterAlreadyRegisteredException` |
| Reading for an unregistered meter | `/problems/meter-not-found` | 404 | `MeterNotFoundException` |
| No handler for the path | `/problems/not-found` | 404 | `NoHandlerFoundException` |
| Other Spring MVC errors (405, 406, 415, ...) | `about:blank` | as Spring decides | `ResponseEntityExceptionHandler` |

Handler (`MeterProblemHandler`, still the single `@RestControllerAdvice`):

```java
public class MeterProblemHandler extends ResponseEntityExceptionHandler {

    /** Every problem leaves here: forces Content-Type application/problem+json, fills a null detail from the title. */
    @Override
    protected ResponseEntity<Object> createResponseEntity(Object body, HttpHeaders headers,
                                                          HttpStatusCode status, WebRequest request) { /* not implemented */ }

    @Override
    protected ResponseEntity<Object> handleMethodArgumentNotValid(MethodArgumentNotValidException ex, HttpHeaders headers,
                                                                  HttpStatusCode status, WebRequest request) { /* not implemented: errors[] + detail */ }

    @Override
    protected ResponseEntity<Object> handleMissingServletRequestParameter(MissingServletRequestParameterException ex, HttpHeaders headers,
                                                                          HttpStatusCode status, WebRequest request) { /* not implemented */ }

    @Override
    protected ResponseEntity<Object> handleHttpMessageNotReadable(HttpMessageNotReadableException ex, HttpHeaders headers,
                                                                  HttpStatusCode status, WebRequest request) { /* not implemented */ }

    @Override
    protected ResponseEntity<Object> handleNoHandlerFoundException(NoHandlerFoundException ex, HttpHeaders headers,
                                                                   HttpStatusCode status, WebRequest request) { /* not implemented */ }

    @ExceptionHandler
    ResponseEntity<ProblemDetail> alreadyRegistered(MeterAlreadyRegisteredException e) { /* not implemented: 409, now via ResponseEntity with problem+json */ }

    @ExceptionHandler
    ResponseEntity<ProblemDetail> meterNotFound(MeterNotFoundException e) { /* not implemented: 404 */ }
}
```

Service and controller:

```java
// MeterService
/** Throws MeterNotFoundException if no meter with this id is registered. */
public Meter require(String id) { /* not implemented */ }

// ReadingController: constructor-injected MeterService; add() calls service.require(reading.meterId())
// after bean validation and before storing. Storage stays in the controller (F7 WI-2 moves it).
public ReadingController(MeterService meters) { /* not implemented */ }
```

Configuration (`app/src/main/resources/application.properties`):

```
spring.web.resources.add-mappings=false   # no static resources: an unknown path raises NoHandlerFoundException for every method
```

Validation stays at the boundary: Jakarta constraints on the request records plus `@Valid`; the handler only formats. Query parameters `meterId` on `GET`/`DELETE /readings` are not annotated today; missing is already 400, blank is not required by any AC (see Out of scope).

Idempotency: this feature adds no new write. The 404 check is read-only and runs before storing, so a rejected post stores nothing and a retry of it is rejected again. A retried successful `POST /readings` still stores twice (pre-existing, F7 open question 9).

## Behaviour per AC

### AC-F34-1

Every 400, 404 and 409 response from any endpoint has `Content-Type: application/problem+json` and a JSON body with `type`, `title`, `status` and `detail`, all non-null; `status` equals the HTTP status code. This holds whatever `Accept` header the client sends (`application/json`, `*/*`, none). `type` is a relative URI from the table above, or `about:blank` for Spring's generic errors. `instance` (the request path) and extension properties may also appear. Applies to the existing 409 for a duplicate meter as well.

### AC-F34-2

`POST /meters` with an `id` that is missing, empty or only whitespace returns 400 `/problems/validation-failed`. The body names the field: `errors` contains `{"field": "id", ...}` and `detail` contains `id`. Nothing is registered. If `type` is also missing, both fields are listed.

### AC-F34-3

`POST /readings` returns 400 `/problems/validation-failed` and stores nothing when:

- `kwh` is negative → `errors` contains field `kwh`;
- `meterId` is missing, empty or only whitespace → field `meterId`;
- `takenAt` is missing or `null` → field `takenAt`.

`detail` names each offending field. Several offending fields are all listed. Bean validation runs before the registration check, so these are 400 even for an unregistered meter id. A `takenAt` that is present but not an ISO-8601 instant, or a `kwh` that is not a number, cannot be bound and is a 400 under AC-F34-5 instead (see Open questions 3).

### AC-F34-4

`POST /readings` whose body passes validation but whose `meterId` was never registered through `POST /meters` returns 404 `/problems/meter-not-found`, with `detail` naming the meter id, and stores nothing (`GET /readings/count` unchanged). A reading for a registered meter returns 201 as today. `GET` and `DELETE /readings` for an unregistered id are unchanged (200 `[]` and 204).

### AC-F34-5

A body on `POST /meters` or `POST /readings` that is not valid JSON (truncated, wrong syntax, empty, a JSON array or scalar instead of an object, a value of the wrong JSON type) returns 400 `/problems/malformed-request`, never 500. `detail` is a fixed sentence and does not echo parser internals. An unknown meter `type` value on `POST /meters` stays a 400 (it is raised during JSON binding) and uses the same type.

### AC-F34-6

A request to a path no controller maps (for example `GET /nope`, `POST /readings/abc`, `DELETE /meters/x`) returns 404 `/problems/not-found` for every HTTP method, not 405. A known path with a wrong method (for example `PUT /meters`) keeps Spring's 405, in problem+json. Actuator paths are unaffected.

## Out of scope

- Localised messages (issue). `message` in `errors` is the default Hibernate Validator English text.
- Authentication and authorisation errors (issue); there is no security layer.
- Changing success responses (issue), including the `kwh` → `quantity` rename and `type`/`unit` on readings (F7).
- Rejecting a blank (not missing) `meterId` query parameter on `GET`/`DELETE /readings`; no AC asks for it.
- A catch-all 500 problem for unexpected exceptions; the ACs cover 400, 404 and 409 only (see Open questions 4).
- Readings storage moving into `MeterService` (F7 WI-2).

## Open questions

1. **AC-F34-4 duplicates F7's registration check, and it needs a protected change.** F7 specified the same 404 (`/problems/meter-not-found`), but F7 WI-2 is not built. This spec delivers the check in F34 WI-3, with the same type URI, so F7 WI-2 would then only add `type`/`unit` and `quantity`. Please confirm which feature owns it. Either way, `ReadingControllerTest`, `ReadingDeleteTest` and `ReadingCountTest` post readings for meters they never register, and they slice `@WebMvcTest(ReadingController.class)` without importing `MeterService`; after WI-3 they fail. They are existing tests under `app/src/test` (ask first). Needed before WI-3 can pass verify: approval to add `@Import(MeterService.class)` and a `POST /meters` setup step to those three classes, and QA updating the hidden F16 and F21 scenarios the same way.
2. **How a problem "names the field".** The issue does not say where. This spec puts it in both an `errors` array and `detail` (ADR proposal). If the hidden scenarios expect a different property (for example a single top-level `field`), AC-F34-2 and AC-F34-3 must say so.
3. **Unparseable values.** `"takenAt": "yesterday"` or `"kwh": "abc"` fail during JSON binding, before bean validation, so this spec returns 400 `malformed-request` without naming the field. Should those also name the field (it is possible from Jackson's path, at the cost of more handler code)?
4. **500s.** AC-F34-1 lists 400, 404 and 409. Should an unexpected server error also be problem+json (with a generic `detail`), or stay Spring Boot's default error JSON?
5. **Type URIs.** This spec uses relative URIs under `/problems/` like the existing 409. They do not resolve to documentation. Is a relative, non-resolvable `type` acceptable to clients, or should they be absolute?
