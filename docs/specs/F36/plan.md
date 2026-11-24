# F36 plan: Export the stored readings as CSV

Spec: [spec.md](spec.md). One work item, WI-1, covering all three ACs: they share one endpoint, one line writer and one test class; the header (AC-F36-1) without lines (AC-F36-2) or escaping (AC-F36-3) would not be a usable export, so none can merge usefully alone.

## Modules that change

- `app/src/main/java/com/example/meter/ReadingController.java`: add `CSV_HEADER`, the `text/csv;charset=UTF-8` media type, the `GET /readings/export` mapping and the `csvField` helper.
- `app/src/test/java/com/example/meter/ReadingExportTest.java`: new test class. Existing tests stay untouched (changing them is a protected change).

No change to `app/pom.xml` (no CSV library), migrations, security, billing or factory paths. Risk tier: amber (default for `app/src/main/java`).

## Steps (WI-1)

1. In `ReadingController`, add `static String csvField(String raw)`: if `raw` contains `,`, `"`, `\r` or `\n`, return `"` + `raw.replace("\"", "\"\"")` + `"`, else `raw`.
2. Add `@GetMapping("/export") public ResponseEntity<String> export()`: a `StringBuilder` with `CSV_HEADER` + `\r\n`, then for each reading in `readings` (snapshot iteration) `csvField(meterId),csvField(takenAt.toString()),csvField(kwh.toPlainString())` + `\r\n`; return `ResponseEntity.ok().contentType(new MediaType("text", "csv", StandardCharsets.UTF_8)).body(...)`.
3. Add `ReadingExportTest` (`@WebMvcTest(ReadingController.class)`, `@DirtiesContext(classMode = BEFORE_EACH_TEST_METHOD)` so each test starts empty), with `@DisplayName`s naming the AC IDs:
   - AC-F36-1: `GET /readings/export` -> 200, `contentTypeCompatibleWith("text/csv")`, first line is `meterId,timestamp,value`.
   - AC-F36-2: empty store -> body equals `meterId,timestamp,value\r\n`; post three readings for two meters (one with `kwh` `1E+3`) -> exactly three data lines in post order, `m1,2026-01-01T00:00:00Z,12.5`, value `1000` not `1E+3`; delete one meter -> its lines are gone.
   - AC-F36-3: meter ids `a,b`, `say "hi"` and `m1` -> lines start with `"a,b",`, `"say ""hi""",` and `m1,`.
   - Non-ASCII meter id (e.g. `zähler`) round-trips in UTF-8 (read the body with `getContentAsString(StandardCharsets.UTF_8)`).
4. Run `mvn -B -f app/pom.xml verify`.

## Risks

- Charset: returning a `String` with only `produces = "text/csv"` makes `StringHttpMessageConverter` add `charset=ISO-8859-1`. The builder must set the UTF-8 media type explicitly, and tests must check the type with `contentTypeCompatibleWith`, not exact string equality.
- Format defaults (CRLF, trailing line break, `toPlainString`) are spec choices, not issue text (spec Open questions 1). A hidden scenario that compares the whole body to an LF form would fail; it is informational only in this iteration (ADR-0007).
- Shared state: the in-memory list lives per cached Spring context, shared with `ReadingControllerTest`, `ReadingDeleteTest` and `ReadingCountTest` slices. The empty-export case needs a fresh context (`@DirtiesContext`); hidden scenarios may expect a header-only body on a fresh context, so the implementation must not seed data.
- F7 (not built yet) would move storage into `MeterService` and rename `kwh` to `quantity`. If F7 lands first, the builder reads readings through `MeterService` and the test must `@Import(MeterService.class)`; the CSV column `value` maps to `quantity` and the HTTP contract here does not change.
