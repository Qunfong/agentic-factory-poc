# F21: Count the stored readings

Source: feature issue #21.

## Problem

An operator wants a quick count of how many readings are stored right now, without paging through the full list, so they can sanity-check data volume at a glance.

## Grounding

- Capability touched: readings, package `com.example.meter`. Today `ReadingController` holds the HTTP mapping, the `Reading` record and the in-memory storage (`CopyOnWriteArrayList<Reading>`), plus `POST /readings`, `GET /readings?meterId=` and `DELETE /readings?meterId=` (F16). There is no service, repository, persistence or security package.
- ADRs: 0001 (reference architecture) applies. No accepted ADR covers the readings module. `ArchitectureTest` forbids field injection and controllers depending on `@Repository` classes; this feature adds neither.
- F7 is specified but not built: [proposed-meter-service-storage](../../adr/proposed-meter-service-storage.md) would move the readings into a `MeterService`. This spec follows the code as it is today (see plan risks). No new design decision, so no ADR proposal.
- No new top-level technical packages, no `app/pom.xml` change, no migration.

## Data shape

Response body, a new nested record next to `Reading` in `ReadingController`:

```java
/** Total number of stored readings; never negative. */
public record ReadingCount(long count) {}
```

Wire form: `{"count": <non-negative integer>}`, for example `{"count": 0}`. `long`, not `BigDecimal`: this is a count of records, not money or energy. No request body, no time fields.

## Interfaces

HTTP:

```
GET /readings/count   -> 200 OK, application/json, {"count": <n>}
```

Java (in `ReadingController`, next to `add`, `list` and `deleteByMeter`):

```java
@GetMapping("/count")
public ReadingCount count() {
    // not implemented: return new ReadingCount(readings.size());
}
```

Storage: the existing `CopyOnWriteArrayList<Reading>`; `size()` reads one consistent snapshot, so a count taken during a concurrent `DELETE` sees either all or none of that meter's readings.

Routing: `/readings/count` is a distinct path from `/readings`, so it does not collide with `GET /readings?meterId=` (which still requires `meterId`). Query parameters on `/readings/count` are not part of the contract (see Out of scope).

Error cases: none specific to this endpoint. The request takes no input to validate. Non-GET methods on `/readings/count` get Spring's default `405 Method Not Allowed` (`ProblemDetail` `about:blank` when problem details are enabled).

Idempotency: read-only `GET`, no writes, so no idempotency key is needed.

## Behaviour per AC

### AC-F21-1

`GET /readings/count` returns `200` with a JSON object `{"count": n}`, where `n` is the total number of readings currently stored, over all meters.

- With no readings stored, the body is `{"count": 0}`.
- Each successful `POST /readings` (201) adds 1 to the count; a rejected post (400) does not change it.
- Duplicate readings (same meter, time and value posted twice) are stored twice today, so they count twice.
- `count` is a JSON integer, not a string or decimal.

### AC-F21-2

The count reflects deletions. After `DELETE /readings?meterId=<id>` (204) removes the readings of meter `<id>`, `GET /readings/count` no longer includes them: the count drops by exactly the number of readings that meter had, and readings of other meters still count.

- Deleting a meter with no readings leaves the count unchanged.
- Readings posted for `<id>` after the delete count again.

## Out of scope

- Counting per meter or per type (issue).
- Pagination of the full reading list (issue).
- Authentication of the "operator" (the service has no security; see F16 open question 1).
- Persistence beyond the in-memory list; the count resets on restart like the data does.

## Open questions

None blocking. Note for the plan gate: the issue says "a plain integer count (e.g. `{"count": 0}`)". This spec follows the example (a JSON object with an integer `count` field), not a bare `0` body. If a bare integer was meant, AC-F21-1 must be restated.
