# Proposed: a class-level validation error is an `errors` entry with `field` `""`

- **Status:** Proposed (spec writer, feature F60); to be accepted at the plan gate
- **Modules:** `com.example.meter` (`MeterProblemHandler`)
- **Extends:** [proposed-problem-field-errors](proposed-problem-field-errors.md) (F34)

## Context

F34 put an `errors` array of `{"field", "message"}` on every 400 `/problems/validation-failed` and lists field names in `detail`. A constraint on a request type as a whole (a class-level or cross-field constraint) produces a Spring `ObjectError` that belongs to no field, so today it is dropped and `errors` is empty. F60 requires it to appear. Every entry needs some `field` value, and clients will code against whichever one we choose (for example to show the message as a form-level error rather than next to an input), so changing it later breaks them.

## Decision

1. Each class-level violation becomes an `errors` entry `{"field": "", "message": "<constraint message>"}`. The empty string is the RFC 6901 JSON Pointer of the whole request body, so it reads as "the body as a whole".
2. `field` stays a non-null string in every entry; the existing sort (field, then message) puts class-level entries first.
3. `detail` lists only non-empty field names. If there are none, it is `Invalid request: <distinct class-level messages joined by "; ">`.
4. The Java object name Spring reports (`registerMeterRequest`, `reading`) is never exposed.

## Alternatives

1. **`field` is `null` or the key is absent.** Distinguishes "no field" clearly, but clients that assume `field` is always a string break, and the sort needs a null rule.
2. **`field` is Spring's object name (`registerMeterRequest`).** Zero code, but leaks a Java identifier that changes with a class rename and means nothing to a client.
3. **A fixed token such as `$` or `_body`.** Readable, but an invented convention; `$` is JSONPath, which the rest of the shape does not use.
4. **A separate `globalErrors` array.** Keeps `errors` purely per-field, but clients then have two lists to check, and the F60 issue asks for the existing `errors` array.
5. **Attribute the error to one of the involved fields** (via the constraint's `propertyPath`/`addPropertyNode`). Best UX per rule, but needs a decision per constraint, not a handler rule; still possible later for specific constraints, which then become ordinary field errors.

## Consequences

- Clients can treat `field == ""` as a form-level error without parsing `message`.
- Moving later to JSON Pointer paths for named fields (`/id`) would be consistent with `""`; the reverse (a token) would not.
- A constraint that reports itself on a property node keeps showing as a normal field error; this rule only covers errors with no field.

## Re-evaluation triggers

- Per-entry error codes are added (`code`), or `field` moves to full JSON Pointer paths.
- A client needs to tell apart several class-level rules without parsing messages.
