# F32: GET /meters/{id} returns one registered meter

Source: feature issue #32.

## Problem

An operator wants to look up a single registered meter by its id, without fetching every meter.

## Grounding

- Capability touched: meters, package `com.example.meter`. Today `MeterController` exposes only `POST /meters` (F7 WI-1, built). `MeterService` keeps registrations in a `ConcurrentMap<String, Meter>`. `Meter(id, type)` exposes `unit()` from `MeterType`. `MeterProblemHandler` (extends `ResponseEntityExceptionHandler`) maps `MeterAlreadyRegisteredException` to 409 `/problems/meter-already-registered`.
- `MeterNotFoundException` does not exist yet. F7 WI-2 plans it, with problem type `/problems/meter-not-found` (see [F7 spec](../F7/spec.md)), but WI-2 has not been built. This feature introduces the same class and type URI, so F7 WI-2 can reuse them (see plan risks).
- ADRs: 0001 applies. [proposed-meter-service-storage](../../adr/proposed-meter-service-storage.md) already puts meter storage in `MeterService`, and this spec follows it. `ArchitectureTest` forbids field injection and controllers depending on `@Repository`. This feature adds neither. No new design decision, so no ADR proposal.
- No new top-level packages, no `app/pom.xml` change, no migration, no red-tier path.

## Data shape

The response reuses the existing `MeterController.MeterResponse`, so `GET` and `POST /meters` return the same shape:

```java
public record MeterResponse(String id, MeterType type, String unit) {}
```

Wire form: `{"id": "m-1", "type": "electricity", "unit": "kWh"}`. `type` is the lowercase wire value (`MeterType` `@JsonValue`). The AC asks for id and type. `unit` is extra: it is part of the existing response record (see Open questions 1). There is no money, energy or time field.

## Interfaces

HTTP:

```
GET /meters/{id}   -> 200 MeterResponse | 404 ProblemDetail /problems/meter-not-found
```

Java:

```java
// MeterController
@GetMapping("/{id}")
public MeterResponse get(@PathVariable String id) {
    // not implemented: Meter m = service.find(id); return new MeterResponse(m.id(), m.type(), m.unit());
}

// MeterService
/** Returns the registered meter; throws MeterNotFoundException if no meter has this id. */
public Meter find(String id) { /* not implemented */ }

// MeterNotFoundException (new)
public class MeterNotFoundException extends RuntimeException {
    public MeterNotFoundException(String id) { /* not implemented: "Meter '" + id + "' is not registered" */ }
}

// MeterProblemHandler
@ExceptionHandler
ProblemDetail notFound(MeterNotFoundException e) {
    // not implemented: 404, type /problems/meter-not-found, title "Meter not found", detail = message
}
```

Storage: the existing `ConcurrentMap<String, Meter>` in `MeterService`. `find` is a single `get(id)`. There is no repository, and no new storage.

Error cases:

| Case | ProblemDetail type | Status |
| --- | --- | --- |
| No meter registered with `{id}` | `/problems/meter-not-found` | 404 |

Validation at the boundary: `{id}` is a path segment and is always non-empty when the route matches. `GET /meters/` (empty id) does not match this mapping, so its behaviour is not part of this contract. The id match is exact and case-sensitive, the same as the map key used by `POST /meters`.

Idempotency: a read-only `GET` with no writes, so it needs no idempotency key.

## Behaviour per AC

### AC-F32-1

After `POST /meters` has registered `{"id": "<id>", "type": "<type>"}`, `GET /meters/<id>` returns `200` with `application/json` body `{"id": "<id>", "type": "<type>", "unit": "<unit of type>"}`.

- This holds for every one of the six types. The returned `type` is the wire value that was registered.
- Looking up one meter returns only that meter, even when other meters are registered.
- Repeated GETs return the same body and change nothing.

### AC-F32-2

`GET /meters/<id>` for an id that no `POST /meters` has registered returns `404` with a `ProblemDetail` body (`application/problem+json`): type `/problems/meter-not-found`, title `Meter not found`, and a detail that names the id.

- Before any registration, every id returns 404.
- The match is case-sensitive: if `m-1` is registered, `GET /meters/M-1` returns 404.
- A failed registration (a 400 for an unknown type) does not make the id findable.

## Out of scope

- Updating or deleting meters (issue).
- Listing all meters (issue).
- Authentication of the operator (the service has no security layer).
- Persistence beyond the in-memory map. Registrations reset on restart.
- Changing `POST /readings` to return 404 for unregistered meters (that is F7 WI-2).

## Open questions

1. **Extra `unit` field (not blocking).** AC-F32-1 asks for "id and type". This spec returns the existing `MeterResponse`, which also carries `unit`, to match `POST /meters`. If the response must hold only `id` and `type`, the plan gate should say so, and WI-1 would then add a separate record.
