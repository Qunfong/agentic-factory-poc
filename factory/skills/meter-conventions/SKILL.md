---
name: meter-conventions
description: Use when changing Java code in app/src/main of the meter service. Gives the module layout, naming and the few rules that are not enforced by tooling.
---

# Meter service conventions

## Layout
- One package per capability under `com.example.meter.<capability>`: controller, service, repository, model together. No technical top-level packages (`controllers/`, `services/`).
- Request and response bodies are Java `record`s next to their controller.

## Rules not enforced by tooling
1. Money and energy are `BigDecimal` with an explicit scale and `RoundingMode.HALF_EVEN`; never `double`. Reason: rounding errors in readings and billing.
2. Time is `Instant` in UTC at boundaries; convert to a zone only for display. Reason: daylight-saving gaps in interval data.
3. Validate at the boundary (controller, message consumer) with Bean Validation; trust types inside.
4. A write that can be retried (ingest, message handler) is idempotent: same input, same end state.
5. Errors to clients use `ProblemDetail` (RFC 9457); never leak stack traces.

## Enforced by tooling (do not repeat in reviews; fix when the build fails)
- No `System.out` / `printStackTrace` (ArchUnit, `ArchitectureTest`).
- No field injection; constructor injection only (ArchUnit).
- Controllers do not call repositories directly (ArchUnit).

## When unsure
Read `docs/adr/index.md` and the ADRs for the package you touch before inventing a pattern.
