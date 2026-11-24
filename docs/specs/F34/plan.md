# F34 plan: input validation and one uniform error format

Spec: [spec.md](spec.md). Work items: [work-items.json](work-items.json). ADR proposal: [proposed-problem-field-errors](../../adr/proposed-problem-field-errors.md).

## Modules that change

All in `com.example.meter` (no new package):

- `MeterProblemHandler`: forced `application/problem+json`, non-null `detail`, typed problems for validation, malformed body, not-found path and unregistered meter. Touched by every work item, hence the serial chain.
- `FieldError` (new record): entries of the `errors` extension property.
- `MeterService` (`require(id)`), `MeterNotFoundException` (new), `ReadingController` (constructor-injected `MeterService`, check before storing).
- `app/src/main/resources/application.properties` (new): `spring.web.resources.add-mappings=false`.
- Tests: one new test class per work item; WI-3 also edits three existing test classes (protected, see risks).

No `app/pom.xml` change, no migration, no red-tier path.

## Ordered steps

1. **WI-1: format foundation** (AC-F34-1, AC-F34-5, AC-F34-6).
   - Override `createResponseEntity` so every `ProblemDetail` body leaves with `Content-Type: application/problem+json` (a preset content type skips `Accept` negotiation) and a non-null `detail` (fallback: the title).
   - Change `alreadyRegistered` to return `ResponseEntity<ProblemDetail>` with the same content type; type and title unchanged.
   - Override `handleHttpMessageNotReadable`: 400 `/problems/malformed-request`, fixed title and detail.
   - Add `application.properties` with `spring.web.resources.add-mappings=false`; override `handleNoHandlerFoundException`: 404 `/problems/not-found`, detail `No endpoint <METHOD> <path>`.
   - `ProblemFormatTest` (`@WebMvcTest` + `@Import(MeterService.class)`): 409 with `Accept: application/json` is problem+json with all four fields; truncated / empty / array bodies on both POST endpoints are 400 problem+json; `GET /nope`, `POST /readings/abc`, `DELETE /meters/x` are 404 problem+json; `PUT /meters` stays 405.
2. **WI-2: field-level validation** (AC-F34-2, AC-F34-3), after WI-1.
   - Override `handleMethodArgumentNotValid`: 400 `/problems/validation-failed`, `errors` = sorted `FieldError(field, message)` from the binding result, `detail` = `Invalid field(s): <comma-separated fields>`.
   - Override `handleMissingServletRequestParameter` with the same type and one `FieldError` for the parameter.
   - `FieldValidationProblemTest`: blank / missing `id`; negative `kwh`, blank `meterId`, missing `takenAt`, and all three at once; each asserts `$.errors[*].field` and that `detail` contains the field name.
3. **WI-3: unregistered meter** (AC-F34-4), after WI-2. Blocked until the protected change in spec open question 1 is approved.
   - `MeterNotFoundException`, `MeterService.require(id)`, `ReadingController` constructor injection and the check after `@Valid` and before `readings.add`.
   - Handler: 404 `/problems/meter-not-found`, title `Meter not found`.
   - `UnregisteredMeterReadingTest`: 404 problem+json and count unchanged; registered meter still 201; negative `kwh` for an unregistered id is 400.
   - Existing tests: add `@Import(MeterService.class)` and register the meters they post for in `ReadingControllerTest`, `ReadingDeleteTest`, `ReadingCountTest`.

Verify for each: `mvn -B -f app/pom.xml verify`.

## Risks

- **Protected test edits (WI-3).** Three existing test classes must change, and the hidden F16 and F21 scenarios post readings for unregistered meters; they turn red on WI-3 and on every later work-item PR until QA updates them. WI-3 is ordered last so WI-1 and WI-2 can merge without it.
- **Overlap with F7 WI-2.** Same 404, same type URI, both touch `ReadingController` and `MeterService`. Whichever lands second must rebase; F7 WI-2 should drop its registration check if F34 WI-3 merges first.
- **`add-mappings=false`** turns off static resource serving, so every unmapped path raises `NoHandlerFoundException`. The service serves no static files today; if one is added later this needs revisiting. In `@WebMvcTest` the property is picked up from `application.properties`, so slice tests see the same 404 behaviour as production.
- **Existing assertions on bodies.** `AC_F7_1_MeterRegistrationTest` asserts only status codes on errors, so the new content type and types do not break it; the hidden F7 scenario may assert `about:blank` or `application/json` on a 400 and would then need QA's update.
- **Spring internals.** Forcing the content type relies on `ResponseEntity` headers taking precedence over content negotiation (Spring Framework 6.x behaviour). A Boot upgrade should keep `ProblemFormatTest`'s `Accept: application/json` case to catch a change.
- **Merge conflicts.** All three items edit `MeterProblemHandler`; the chain WI-1 → WI-2 → WI-3 avoids parallel edits to it.
