# F60: Class-level validation errors in the problem+json `errors` array; missing parameters say "is required"

Source: feature issue #60.

## Problem

`MeterProblemHandler.handleMethodArgumentNotValid` builds the `errors` extension property from `getBindingResult().getFieldErrors()` only. A constraint declared on a request type as a whole (a class-level constraint) produces a global `ObjectError`, not a `FieldError`, so the client gets a 400 `/problems/validation-failed` whose `errors` array is empty and whose `detail` is `Invalid field(s): ` with nothing after it. Separately, a missing required query parameter is reported as `must not be null`, a Bean Validation phrase that does not describe a parameter the client left out.

## Grounding

- Capability touched: validation problems, package `com.example.meter`. No new package.
  - `MeterProblemHandler` (`@RestControllerAdvice`, extends `ResponseEntityExceptionHandler`): `handleMethodArgumentNotValid` maps field errors only; `handleMissingServletRequestParameter` emits `FieldError(<param>, "must not be null")`; both go through `validationFailed(...)`, which sorts by field then message and writes `detail` = `Invalid field(s): <fields>`.
  - `FieldError(String field, String message)`: entry of `errors`. Unchanged.
  - Request types: `MeterController.RegisterMeterRequest(@NotBlank id, @NotNull type)`, `ReadingController.Reading(@NotBlank meterId, @NotNull takenAt, @NotNull @DecimalMin("0") kwh)`. **Neither has a class-level constraint today**, and no custom constraint exists in `app/src/main`.
  - The only required query parameter is `meterId` on `DELETE /readings` (`@RequestParam String meterId`). `GET /readings` parameters are optional or defaulted.
- ADRs: 0001; [proposed-problem-field-errors](../../adr/proposed-problem-field-errors.md) (F34) defines `errors`, its sort order and `detail`, and is followed. New design choice, proposed for the plan gate: [proposed-problem-global-errors](../../adr/proposed-problem-global-errors.md), what `field` is for an error that belongs to no field.
- No `app/pom.xml` change, no migration, no red-tier path. No existing test asserts the `must not be null` text for a missing parameter (`ReadingDeleteTest` only checks 400), so no protected test edit is needed.

## Data shape

```java
package com.example.meter;

/** Unchanged. field is the JSON property or query parameter name; "" (the JSON Pointer of the whole body) for a class-level error. */
public record FieldError(String field, String message) {}
```

Example bodies (the class-level constraint is illustrative; see Open questions 1):

```json
POST <endpoint whose body type carries a class-level constraint>, body violates only that constraint
-> 400 application/problem+json
{"type": "/problems/validation-failed", "title": "Invalid request", "status": 400,
 "detail": "Invalid request: <constraint message>", "instance": "...",
 "errors": [{"field": "", "message": "<constraint message>"}]}

Same body, also with a blank field "id"
-> 400 application/problem+json
{"type": "/problems/validation-failed", "title": "Invalid request", "status": 400,
 "detail": "Invalid field(s): id", "instance": "...",
 "errors": [{"field": "", "message": "<constraint message>"},
            {"field": "id", "message": "must not be blank"}]}

DELETE /readings            (no meterId)
-> 400 application/problem+json
{"type": "/problems/validation-failed", "title": "Invalid request", "status": 400,
 "detail": "Invalid field(s): meterId", "instance": "/readings",
 "errors": [{"field": "meterId", "message": "is required"}]}
```

- Sort order stays field, then message; `""` sorts before any name, so class-level entries come first.
- `detail` lists only named fields (no empty name, no dangling `, `). When there are no named fields it is `Invalid request: <distinct class-level messages joined by "; ">`.
- `message` is the constraint's resolved default message (`ObjectError.getDefaultMessage()`); it never contains the Java object name (`registerMeterRequest`) or a class name.

## Interfaces

No HTTP route changes. Handler (`MeterProblemHandler`):

```java
@Override
protected ResponseEntity<Object> handleMethodArgumentNotValid(MethodArgumentNotValidException ex, HttpHeaders headers,
                                                              HttpStatusCode status, WebRequest request) {
    // not implemented: field errors as today, plus every getBindingResult().getGlobalErrors() entry
    // as new FieldError("", e.getDefaultMessage())
}

@Override
protected ResponseEntity<Object> handleMissingServletRequestParameter(MissingServletRequestParameterException ex, HttpHeaders headers,
                                                                      HttpStatusCode status, WebRequest request) {
    // not implemented: List.of(new FieldError(ex.getParameterName(), "is required"))
}

/** 400 /problems/validation-failed; errors sorted by field then message; detail per the rules above. */
private ResponseEntity<Object> validationFailed(Exception ex, List<FieldError> errors, HttpHeaders headers,
                                                WebRequest request) { /* not implemented */ }
```

Error cases (unchanged types; new content):

| Case | `type` | Status | Source | `errors` |
| --- | --- | --- | --- | --- |
| Class-level constraint on a `@Valid @RequestBody` fails | `/problems/validation-failed` | 400 | `MethodArgumentNotValidException` (global error) | one `{"field": "", ...}` per violation |
| Field constraint fails | `/problems/validation-failed` | 400 | `MethodArgumentNotValidException` (field error) | unchanged |
| Required query parameter missing | `/problems/validation-failed` | 400 | `MissingServletRequestParameterException` | `{"field": "<param>", "message": "is required"}` |

Validation stays at the boundary: constraints on request records plus `@Valid`; the handler only formats. No write is added, so there is no idempotency key to define.

## Behaviour per AC

### AC-F60-1

A request whose `@Valid @RequestBody` violates a constraint declared on the body type itself (not on one of its components) returns 400 `Content-Type: application/problem+json`, `type` `/problems/validation-failed`, with a non-empty `errors` array: one entry per class-level violation, `field` `""`, `message` the constraint's message. Field-level violations in the same body are listed alongside, as today. `detail` is never `Invalid field(s): ` with an empty list. Because no request type in the service has a class-level constraint today, the delivering work item proves this with a constraint and controller declared in test sources only; no production request type gains a constraint (see Open questions 1).

### AC-F60-2

A request that omits a required request parameter (today: `meterId` on `DELETE /readings`) returns 400 `/problems/validation-failed` with `errors` = `[{"field": "<param>", "message": "is required"}]`; the text `must not be null` no longer appears for it. `detail` stays `Invalid field(s): <param>`. Missing or `null` JSON body components keep their Bean Validation messages (`must not be null`, `must not be blank`); this spec reads "missing parameter" in the issue as a request parameter, not a body property (see Open questions 2).

## Out of scope

- Adding a class-level constraint (a real cross-field business rule) to `RegisterMeterRequest` or `Reading`.
- Method-level validation of `@RequestParam` constraints such as `@Min(0) page` (`HandlerMethodValidationException`) and cross-parameter constraints; they do not go through `handleMethodArgumentNotValid`.
- Other "missing" exceptions (`MissingRequestHeaderException`, `MissingPathVariableException`, `MissingServletRequestPartException`); the service declares none.
- Localised messages; changing Bean Validation default messages for body fields.
- A JSON Pointer path (`/id`) for named fields; `field` keeps the bare name (F34).

## Open questions

1. **Which class-level constraint, on which request?** The issue states the symptom but names no class-level rule, and the service has none. This spec makes the handler map any global error and proves it with a test-only constraint. If the hidden scenario expects a real endpoint to reject a specific cross-field combination, that business rule must be given in the issue.
2. **"Missing request field" vs "missing parameter".** The AC says both. This spec changes only missing request (query) parameters to `is required`. If missing JSON body properties must also say `is required`, that needs custom messages on `@NotNull`/`@NotBlank` (which then also apply to an explicit `null`, and a blank string would need a different message), and it changes the existing `FieldValidationProblemTest` assertion `must not be null` for a missing `takenAt` (a protected test edit). Please confirm.
3. **`field` for a class-level error.** The spec uses `""` (ADR proposal). Alternatives are `null`/absent, the Java object name, or a fixed token such as `$`. If the hidden scenario checks a specific `field` value for AC-F60-1, it must say which.
4. **Exact text.** Is `is required` the full message (like `must not be null` today, without the field name), or should it read `<param> is required`? The spec uses the bare `is required`.
