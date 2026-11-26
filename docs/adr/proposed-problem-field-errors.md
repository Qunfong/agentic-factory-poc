# Proposed: validation problems name fields in an `errors` array, and every problem is `application/problem+json`

- **Status:** Proposed (spec writer, feature F34); to be accepted at the plan gate
- **Modules:** `com.example.meter` (`MeterProblemHandler`, `FieldError`), `app/src/main/resources/application.properties`

## Context

Feature F34 asks for one error shape on every endpoint and for validation errors that "name the offending field". RFC 9457 fixes `type`, `title`, `status`, `detail` and `instance`, but not how to name fields; that needs an extension property. Spring's default validation problem has `detail` "Invalid request content." and no field list. Spring also picks the content type of a `ProblemDetail` from the `Accept` header, so a client asking for `application/json` does not get `application/problem+json`. And an unknown path with a non-GET method reaches the static-resource handler and returns 405. Clients will code against whatever we choose, so changing it later is a breaking change.

## Decision

1. A validation problem (`/problems/validation-failed`, 400) carries an extension property `errors`: an array of `{"field": "<JSON property or query parameter name>", "message": "<constraint message>"}`, sorted by field then message. `detail` also lists the field names (`Invalid field(s): id, type`) for humans and simple clients.
2. `MeterProblemHandler` is the one place problems leave the service: it overrides `createResponseEntity` to set `Content-Type: application/problem+json` regardless of `Accept`, and fills a null `detail`.
3. Problem `type`s are relative URIs under `/problems/` (as the existing 409 already does); Spring's other MVC errors keep `about:blank`.
4. Static resource mappings are turned off (`spring.web.resources.add-mappings=false`), so every unmapped path is a `NoHandlerFoundException` and a 404 problem for every method.

## Alternatives

1. **Only `detail` names the field.** No extension property, but clients must parse English text, which defeats "handle errors generically".
2. **A single top-level `field` property.** Simple, but cannot report two offending fields at once, and AC-F34-3 has three independent rules on one body.
3. **A map `{"id": "must not be blank"}`.** Compact, but a field with two violations loses one, and map keys are awkward for typed clients.
4. **Leave content type to negotiation.** Spring's default; but a client sending `Accept: application/json` then gets a different content type for the same error, which AC-F34-1 rules out.
5. **Keep static mappings and add a catch-all `@RequestMapping("/**")` controller that throws 404.** Works without a property, but a catch-all handler competes with real mappings and with Actuator, and hides 405s on known paths.

## Consequences

- Clients can rely on `errors[].field` for every 400 validation problem; adding fields to the entries later is compatible, renaming or removing `errors` is not.
- `field` uses wire names, so the `kwh` → `quantity` rename proposed in F7 also changes the `field` value clients see.
- Clients that require `application/json` strictly and reject `application/problem+json` get the problem anyway (it is still JSON).
- The service cannot serve static files without revisiting point 4.

## Re-evaluation triggers

- A client needs machine-readable error codes per field (add a `code` to each entry).
- Static content or a UI is added to the service.
- Localised messages come into scope.
