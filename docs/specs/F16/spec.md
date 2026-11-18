# F16: Delete the readings of a meter

Source: feature issue #16.

## Problem

An operator must be able to remove all readings of one meter (for example after the meter is replaced), so that old readings no longer show up for that meter id in `GET /readings?meterId=<id>`.

## Grounding

- Capability touched: readings, package `com.example.meter`. Today the controller, the (in-memory) storage and the `Reading` model all live in `ReadingController`. There is no service, repository, persistence layer or security package yet.
- ADRs: 0001 (reference architecture) applies. No ADR covers the readings module specifically. `ArchitectureTest` forbids controllers depending on `@Repository` classes, so this feature adds no repository.
- No new top-level technical packages, no `app/pom.xml` change and no migration are needed.

## Data shape

No change. The existing record stays as it is:

```java
public record Reading(@NotBlank String meterId, @NotNull Instant takenAt,
                      @NotNull @DecimalMin("0") BigDecimal kwh) {}
```

`kwh` stays `BigDecimal` and `takenAt` stays `Instant` (UTC). The delete request has no body and the response has no body.

## Interfaces

HTTP:

```
DELETE /readings?meterId=<id>   -> 204 No Content (no body)
```

Java (in `ReadingController`, next to `add` and `list`):

```java
@DeleteMapping
@ResponseStatus(HttpStatus.NO_CONTENT)
public void deleteByMeter(@RequestParam String meterId) {
    // not implemented: readings.removeIf(r -> r.meterId().equals(meterId));
}
```

Storage: the existing `CopyOnWriteArrayList<Reading>`. `removeIf` on it is atomic, so there is no partial delete and concurrent `GET`s see either all or none of the meter's readings.

Error cases (boundary validation, Spring defaults, `ProblemDetail` body when `spring.mvc.problemdetails` is enabled):

| Case | Type | Status |
| --- | --- | --- |
| `meterId` query parameter missing | `MissingServletRequestParameterException` -> `about:blank` | 400 Bad Request |

Blank `meterId` (`?meterId=`): see Open questions; this spec does not define it.

Idempotency: `DELETE` is idempotent by nature. The idempotency key is the `meterId` itself: repeating the same request removes nothing more and still returns 204. No idempotency header is needed.

## Behaviour per AC

### AC-F16-1

`DELETE /readings?meterId=<id>` removes all readings whose `meterId` equals `<id>` (exact, case-sensitive match, the same match `GET /readings` uses) and returns `204 No Content` with an empty body.

- Readings of other meters are untouched.
- After the call, `GET /readings?meterId=<id>` returns `200` with `[]`.
- When the meter has no readings (never seen, or already deleted), the call still returns `204` and changes nothing.
- Readings posted for the same `meterId` after the delete are stored and listed normally (the delete is not a block on the meter id).

## Out of scope

- Deleting single readings, or readings in a time range.
- Soft delete, audit trail, undo or archive of deleted readings.
- Authentication and authorization of the "operator" role (the service has no security today).
- Persistence beyond the existing in-memory list.
- Blocking future readings for a replaced meter id.

## Open questions

1. Who may call the delete? The issue speaks of "an operator", but the service has no authentication. This spec ships the endpoint unauthenticated like the existing `POST` and `GET`. If it must be restricted, that is a security-path (red tier) change and a separate feature.
2. Blank `meterId` (`DELETE /readings?meterId=`): reject with 400, or treat as a meter id that has no readings and return 204? The issue does not say. Note that `POST` already rejects a blank `meterId` (`@NotBlank`), so no stored reading can match a blank id; either answer deletes nothing. The builder should not add `@NotBlank` validation until this is answered.
3. Retention: is a hard delete acceptable for internal-class data, or must deleted readings be kept for audit? This spec assumes hard delete as the issue says "remove".
