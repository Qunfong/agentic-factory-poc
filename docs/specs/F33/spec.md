# F33: GET /readings filters by date range and paginates

Source: feature issue #33.

## Problem

An operator wants to browse stored readings in manageable pages and limit them to a time window. Today `GET /readings` returns every reading of one meter, in insertion order, and cannot be called without `meterId`.

## Grounding

- Capability touched: readings, package `com.example.meter`. `ReadingController` holds the HTTP mapping, the nested `Reading(meterId, takenAt, kwh)` record and the in-memory storage (`CopyOnWriteArrayList<Reading>`), with `POST /readings`, `GET /readings?meterId=` (required), `GET /readings/count` (F21) and `DELETE /readings?meterId=` (F16). There is no reading service, repository or persistence. `MeterProblemHandler` extends `ResponseEntityExceptionHandler`, so Spring MVC's own 400s are already rendered as `ProblemDetail` (`about:blank`).
- ADRs: 0001 applies; no accepted ADR covers the readings module. `ArchitectureTest` forbids field injection and controllers depending on `@Repository` classes; this feature adds neither.
- F7 WI-2 (not built yet) would move readings into `MeterService` ([proposed-meter-service-storage](../../adr/proposed-meter-service-storage.md)) and rename `kwh` to `quantity`. This spec follows the code as it is today (see plan risks); the HTTP contract here does not depend on either.
- One real design decision: the response stays a bare JSON array and `meterId` becomes optional. See [proposed-readings-page-as-array](../../adr/proposed-readings-page-as-array.md).
- No new top-level technical packages, no `app/pom.xml` change (Boot 3.5 / Spring 6.2 already has `spring-boot-starter-validation` and built-in controller method validation), no migration.

## Data shape

No new records. The response element is the existing `Reading`; the response body is a JSON array of it (one page), for example:

```json
[{"meterId":"m1","takenAt":"2026-01-01T00:00:00Z","kwh":12.5}]
```

- `from`, `to`: `java.time.Instant` (UTC), ISO-8601 instant form, e.g. `2026-01-01T00:00:00Z`. An offset form (`2026-01-01T01:00:00+01:00`) is also an instant and is accepted; the `+` must be URL-encoded as `%2B`.
- `page`: `int`, 0-based. `size`: `int`. Offsets are computed as `long` (`(long) page * size`) so a large `page` cannot overflow.
- `kwh` stays `BigDecimal`; it is not touched.

## Interfaces

HTTP:

```
GET /readings[?meterId=<id>][&from=<instant>][&to=<instant>][&page=<int>][&size=<int>]
  -> 200 OK, application/json, [ Reading, ... ]   (at most size elements)
  -> 400 Bad Request, application/problem+json     (see error cases)
```

Java (in `ReadingController`, replacing the current `list(String meterId)`; validation at the boundary via constraint annotations on the parameters. Spring 6.2 built-in method validation picks these up; do **not** add class-level `@Validated`, which switches to AOP validation and turns violations into `ConstraintViolationException`, a 500 here):

```java
@GetMapping
public List<Reading> list(@RequestParam(required = false) String meterId,
                          @RequestParam(required = false) Instant from,
                          @RequestParam(required = false) Instant to,
                          @RequestParam(defaultValue = "0") @Min(0) int page,
                          @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
    // not implemented:
    // readings snapshot
    //   .filter(meterId == null || r.meterId().equals(meterId))
    //   .filter(from == null || !r.takenAt().isBefore(from))
    //   .filter(to == null   || !r.takenAt().isAfter(to))
    //   .sorted(comparing(Reading::takenAt))      // stable: ties keep insertion order
    //   .skip((long) page * size).limit(size).toList();
}
```

Storage: the existing `CopyOnWriteArrayList<Reading>`; one `stream()` reads one consistent snapshot. No repository method is added.

Error cases (all `400`, `ProblemDetail` type `about:blank`, produced by Spring MVC through `MeterProblemHandler`; no custom problem type):

| Input | Spring exception | Status |
| --- | --- | --- |
| `from` or `to` not an ISO-8601 instant (e.g. `yesterday`, `2026-01-01`, `2026-13-01T00:00:00Z`) | `MethodArgumentTypeMismatchException` | 400 |
| `page` < 0 | `HandlerMethodValidationException` | 400 |
| `size` > 100 | `HandlerMethodValidationException` | 400 |
| `page` or `size` not an integer | `MethodArgumentTypeMismatchException` | 400 |
| `size` < 1 | `HandlerMethodValidationException` | 400 (provisional, see Open questions 2) |

Idempotency: read-only `GET`, no writes, so no idempotency key is needed.

## Behaviour per AC

### AC-F33-1

`GET /readings` accepts optional `from` and `to` (ISO-8601 instants) and returns only readings whose `takenAt` lies in the inclusive range `from <= takenAt <= to`.

- Both absent: no time filter.
- Only `from`: readings with `takenAt >= from`. Only `to`: readings with `takenAt <= to`.
- A reading exactly at `from` or exactly at `to` is included.
- Comparison is on the instant, so `2026-01-01T01:00:00%2B01:00` and `2026-01-01T00:00:00Z` are the same bound.
- `meterId` is no longer required. Without it, all meters' readings are considered; with it, the existing per-meter filter still applies on top of the range (no new meter filtering is added, see Out of scope).
- `from` later than `to`: the range is empty, so `200 []` (provisional, see Open questions 1).
- The range filter is applied before pagination (AC-F33-2): pages are pages of the filtered result.

### AC-F33-2

`GET /readings` accepts optional `page` (0-based, default `0`) and `size` (default `20`, maximum `100`) and returns at most `size` readings for that page, in ascending `takenAt` order.

- Without `page` and `size`, the first 20 readings in ascending `takenAt` order are returned.
- Page `p` holds the elements at positions `p*size` to `p*size + size - 1` of the filtered, sorted list.
- `size=100` is allowed and returns up to 100 readings.
- A page past the end returns `200 []`.
- Readings with the same `takenAt` keep their insertion order (stable sort), so paging through equal timestamps neither repeats nor skips a reading while no writes happen in between.
- The response is a bare JSON array, as today; there is no total count or next-page link (see the ADR proposal). Clients detect the last page by receiving fewer than `size` elements.
- This changes the existing `GET /readings?meterId=` behaviour: it is now sorted by `takenAt` and capped at 20 by default (see Open questions 3).

### AC-F33-3

`size` above 100, a negative `page`, or an unparsable `from`/`to` returns `400` with a `ProblemDetail` body, and no readings.

- `size=101` -> 400; `size=100` -> 200.
- `page=-1` -> 400; `page=0` -> 200.
- `from=not-a-date`, `to=2026-01-01` (date without time) or any other value `Instant` cannot parse -> 400.
- One invalid parameter is enough for 400, whatever the others are.
- An empty value (`from=`) is treated by Spring as absent, not as unparsable (see Open questions 4).

## Out of scope

- Sorting options other than ascending timestamp (issue).
- Filtering by meter or type beyond the existing optional `meterId` (issue).
- A page envelope (total count, total pages, links); see the ADR proposal.
- Cursor/keyset pagination and consistency of pages across concurrent writes.
- Authentication of the "operator" (the service has no security; see F16 open question 1).
- Persistence beyond the in-memory list.

## Open questions

1. `from` later than `to`: the issue lists the 400 cases in AC-F33-3 and this is not one of them. This spec returns `200 []` (an empty inclusive range). If it should be 400, AC-F33-3 must be extended.
2. `size=0` or a negative `size`: the issue gives only a maximum. A negative size cannot define a page, and `size=0` would always return `[]`. This spec rejects `size < 1` with 400 provisionally; the plan gate should confirm, because it is a 400 the issue does not name. The builder's tests must not assert on `size=0` until this is answered.
3. Existing callers of `GET /readings?meterId=`: they get at most 20 readings by default and in `takenAt` order instead of all readings in insertion order. The issue says "GET /readings ... returns at most size readings" without exempting `meterId` queries, so this spec applies paging to every call. Confirm this break is acceptable; the existing `ReadingControllerTest` (one reading) still passes.
4. Empty parameter values (`from=`, `size=`): Spring treats an empty `from`/`to` as absent and an empty `page`/`size` as the default. The issue does not say whether that counts as "unparsable". This spec keeps Spring's behaviour.
