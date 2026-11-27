# F60 plan: class-level validation errors and "is required" for missing parameters

Spec: [spec.md](spec.md). Work items: [work-items.json](work-items.json). ADR proposal: [proposed-problem-global-errors](../../adr/proposed-problem-global-errors.md), extending [proposed-problem-field-errors](../../adr/proposed-problem-field-errors.md).

## Modules that change

All in `com.example.meter` (no new package):

- `MeterProblemHandler`: `handleMethodArgumentNotValid` also maps global errors; `handleMissingServletRequestParameter` uses `is required`; `validationFailed` builds `detail` from named fields only, with a fallback for class-level-only failures.
- Tests: one new class, `GlobalValidationProblemTest`. No existing test changes.

`FieldError`, controllers, request records, `app/pom.xml`, resources: unchanged. No migration, no red-tier path.

One work item: both ACs touch the same three methods of one class, and splitting them would only create a serial chain with a merge conflict.

## Ordered steps (WI-1)

1. `handleMethodArgumentNotValid`: concatenate `getFieldErrors()` mapped as today with `getGlobalErrors()` mapped to `new FieldError("", e.getDefaultMessage())`.
2. `handleMissingServletRequestParameter`: message `is required`.
3. `validationFailed`: keep the sort (field, then message, nulls first); compute named fields as the distinct non-empty `field`s; `detail` = `Invalid field(s): <named>` if any, else `Invalid request: <distinct messages of "" entries joined by "; ">`.
4. `GlobalValidationProblemTest` (`@WebMvcTest` with a test-only `@RestController` and a test-only class-level constraint, both nested in the test class and registered with `@Import`; `@Import(MeterService.class)` if it also hits `/readings` or `/meters`). Tagged `@Tag("AC-F60-1")` / `@Tag("AC-F60-2")`:
   - class-level violation only: 400 problem+json, `errors` has one entry, `field` `""`, `message` the constraint message, `detail` starts with `Invalid request:`;
   - class-level plus field violation: both entries, class-level first, `detail` = `Invalid field(s): <field>`;
   - `DELETE /readings` without `meterId`: `errors[0]` = `{"field": "meterId", "message": "is required"}` and the body does not contain `must not be null`;
   - regression: `POST /readings` without `takenAt` still says `must not be null` for `takenAt`.
5. `mvn -B -f app/pom.xml verify`.

## Risks

- **Hidden scenario shape for AC-F60-1.** No production request has a class-level constraint, so a hidden scenario can only exercise this through its own test controller or a business rule the issue does not give (spec Open questions 1). If it targets a real endpoint, WI-1 cannot satisfy it without a new rule.
- **Interpretation of AC-F60-2** (spec Open questions 2). If body properties must also say `is required`, the work item grows to the request records and needs a protected edit of `FieldValidationProblemTest`.
- **Hidden F34 scenarios.** If any hidden F34 scenario asserts `must not be null` for a missing query parameter, it turns red with this change and QA must update it. The visible tests do not.
- **Test-only constraint in a `@WebMvcTest` slice.** The nested test controller must be picked up (`@Import` or `controllers = ...`); `ArchitectureTest` rules (constructor injection, no `@Repository` from controllers) apply to test classes only if it scans them, so keep the test controller field-injection-free.
