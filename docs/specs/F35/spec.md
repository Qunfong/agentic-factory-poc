# F35: README documents the HTTP API

Source: feature issue #35. Docs-only.

## Problem

New developers cannot see which endpoints the meter service offers without reading the controllers. The README gets one section that lists the endpoints, their status codes and two curl examples.

## Grounding

- Capability packages touched: none in code. The section describes `com.example.meter` as it is on the base commit: `MeterController` (`/meters`), `ReadingController` (`/readings`), `MeterProblemHandler` (extends `ResponseEntityExceptionHandler`, so framework 400s are `ProblemDetail` with type `about:blank`; 409 uses `/problems/meter-already-registered`), `MeterType` (wire values `electricity`, `solar`, `ev_charger`, `gas`, `battery`, `transformer`; an unknown or wrong-case value fails JSON parsing, so 400).
- ADRs: 0001 applies. No ADR covers documentation. No design decision, so no ADR proposal.
- No `app/**` change, no `app/pom.xml`, no migration. Path `README.md` is green tier (`**/*.md` in `factory/risk-map.yaml`).
- The service has no `application.properties`, so it listens on Spring Boot's default port 8080; the curl examples use `http://localhost:8080`.

## Data shape

No Java types change. The section documents the existing types; for reference (unchanged):

```java
// MeterController
public record RegisterMeterRequest(@NotBlank String id, @NotNull MeterType type) {}
public record MeterResponse(String id, MeterType type, String unit) {}
// ReadingController
public record Reading(@NotBlank String meterId, @NotNull Instant takenAt,
                      @NotNull @DecimalMin("0") BigDecimal kwh) {}
public record ReadingCount(long count) {}
```

## Interfaces

The only interface is the README section. Shape (Markdown, in the root `README.md`):

```
## HTTP API
<one sentence: base URL http://localhost:8080 when run with `mvn -f app/pom.xml spring-boot:run`; errors are application/problem+json>

| Method | Path | Success | Errors |
| --- | --- | --- | --- |
| POST   | /meters                   | 201 Created    | 400, 409 |
| POST   | /readings                 | 201 Created    | 400 |
| GET    | /readings?meterId={id}    | 200 OK         | 400 |
| GET    | /readings/count           | 200 OK         | none specific |
| DELETE | /readings?meterId={id}    | 204 No Content | 400 |

<curl example: register a meter>
<curl example: post a reading>
```

The endpoint list is the contract on the base commit, taken from the controllers:

| Endpoint | Success | Error statuses and cause |
| --- | --- | --- |
| `POST /meters` | `201`, body `MeterResponse` | `400` blank or missing `id`, missing or unknown `type`, unreadable JSON (`about:blank`); `409` id already registered (`/problems/meter-already-registered`) |
| `POST /readings` | `201`, body echoes the `Reading` | `400` blank or missing `meterId`, missing or unparsable `takenAt`, missing or negative `kwh`, unreadable JSON |
| `GET /readings?meterId=` | `200`, JSON array of `Reading` (empty if none) | `400` `meterId` parameter missing |
| `GET /readings/count` | `200`, `{"count": n}` | none specific |
| `DELETE /readings?meterId=` | `204`, no body; also for a meter with no readings | `400` `meterId` parameter missing |

Generic framework responses (405 wrong method, 415 wrong content type, 500) apply to every endpoint; the section may mention them once in a sentence, not per row.

Idempotency: no writes in this feature.

## Behaviour per AC

### AC-F35-1

`README.md` has a heading titled exactly `HTTP API` (level 2, `## HTTP API`). Under it, a table or list names every endpoint in the code on the base commit, each with its HTTP method and path: the five rows above. Query parameters that are required (`meterId`) appear in the path column. No endpoint that does not exist is listed.

### AC-F35-2

For each endpoint listed under AC-F35-1, the section names its success status code and its error status codes, as in the contract table above: `POST /meters` 201 / 400, 409; `POST /readings` 201 / 400; `GET /readings?meterId=` 200 / 400; `GET /readings/count` 200 / no endpoint-specific error (stated explicitly, not left blank); `DELETE /readings?meterId=` 204 / 400. Codes are given as numbers; a short reason per error code is welcome.

### AC-F35-3

The section shows exactly one curl example for registering a meter and one for posting a reading, in fenced `bash` blocks, against `http://localhost:8080`:

```bash
curl -i -X POST http://localhost:8080/meters \
  -H 'Content-Type: application/json' \
  -d '{"id": "m-1", "type": "electricity"}'

curl -i -X POST http://localhost:8080/readings \
  -H 'Content-Type: application/json' \
  -d '{"meterId": "m-1", "takenAt": "2026-01-01T00:00:00Z", "kwh": 12.5}'
```

Both examples must be valid against the current code (they return 201 on a fresh service). `takenAt` is an ISO-8601 UTC `Instant`, `kwh` a non-negative decimal.

## Out of scope

- Any change to code, tests or build files (issue).
- An OpenAPI file (issue).
- Documenting the factory flow or rewriting the rest of `README.md`.
- Endpoints from specs that are not built on the base commit (for example a reading-to-meter link from F7 storage); if code changes the API before this lands, the builder documents the code as it is on its base.

## Open questions

None blocking. Note for the plan gate: the root `README.md` today describes the factory, not the meter service; this spec adds the `HTTP API` section there because the issue names `README.md` and no `app/README.md` exists. If a separate service README was meant, AC-F35-1 must name that file.
