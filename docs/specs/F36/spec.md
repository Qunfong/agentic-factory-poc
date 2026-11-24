# F36: Export the stored readings as CSV

Source: feature issue #36.

## Problem

An analyst wants to pull the stored readings into a spreadsheet. Today the only read paths are JSON (`GET /readings?meterId=`, per meter, and `GET /readings/count`). There is no way to get all readings at once in a format a spreadsheet opens directly.

## Grounding

- Capability touched: readings, package `com.example.meter`. Today `ReadingController` holds the HTTP mapping, the `Reading(meterId, takenAt, kwh)` record and the in-memory storage (`CopyOnWriteArrayList<Reading>`), plus `POST /readings`, `GET /readings?meterId=`, `GET /readings/count` (F21) and `DELETE /readings?meterId=` (F16). There is no service, repository, persistence or security package.
- ADRs: 0001 (reference architecture) applies. No accepted ADR covers the readings module. `ArchitectureTest` forbids field injection, standard streams and controllers depending on `@Repository` classes; this feature adds none of them.
- F7 is specified but not built: [proposed-meter-service-storage](../../adr/proposed-meter-service-storage.md) would move the readings into a `MeterService` and [proposed-reading-quantity-field](../../adr/proposed-reading-quantity-field.md) would rename `kwh` to `quantity`. This spec follows the code as it is today; the CSV column names do not depend on either (see plan risks).
- New design choice, proposed for the plan gate: [proposed-readings-csv-format](../../adr/proposed-readings-csv-format.md) (hand-written RFC 4180 writer, quote only when needed, CRLF line ends, UTF-8).
- No new top-level technical packages, no `app/pom.xml` change (no CSV library), no migration.

## Data shape

No new stored data. The export is a view of the existing `Reading` record:

```java
public record Reading(@NotBlank String meterId, @NotNull Instant takenAt,
                      @NotNull @DecimalMin("0") BigDecimal kwh) {}
```

CSV columns, in this order:

| Column      | Source field | Rendering |
| ----------- | ------------ | --------- |
| `meterId`   | `meterId`    | the string as stored, escaped per RFC 4180 (AC-F36-3) |
| `timestamp` | `takenAt`    | `Instant.toString()`, ISO-8601 UTC, e.g. `2026-01-01T00:00:00Z` (same form as the JSON API) |
| `value`     | `kwh`        | `BigDecimal.toPlainString()`, never scientific notation, scale kept as stored, e.g. `12.5`, `1000` |

Wire form (`\r\n` shown explicitly):

```
meterId,timestamp,value\r\n
m1,2026-01-01T00:00:00Z,12.5\r\n
"a,b",2026-01-02T00:00:00Z,3\r\n
"say ""hi""",2026-01-03T00:00:00Z,0\r\n
```

## Interfaces

HTTP:

```
GET /readings/export   -> 200 OK, Content-Type: text/csv;charset=UTF-8, body as above
```

Java (in `ReadingController`, next to the existing mappings):

```java
static final String CSV_HEADER = "meterId,timestamp,value";
static final MediaType TEXT_CSV_UTF8 = new MediaType("text", "csv", StandardCharsets.UTF_8);

@GetMapping("/export")
public ResponseEntity<String> export() {
    // not implemented: header line + one line per reading, each ending in CRLF;
    // ResponseEntity.ok().contentType(TEXT_CSV_UTF8).body(csv)
}

/** RFC 4180 field: quoted iff it contains ',', '"', CR or LF; inner '"' doubled. */
static String csvField(String raw) {
    // not implemented
}
```

The content type is set explicitly on the `ResponseEntity`, so it does not depend on the request's `Accept` header and the charset is UTF-8, not `StringHttpMessageConverter`'s ISO-8859-1 default (which would mangle non-ASCII meter ids).

Storage: iterate the existing `CopyOnWriteArrayList<Reading>`; its iterator is a snapshot, so an export taken during a concurrent `POST` or `DELETE` is consistent (it sees a reading entirely or not at all).

Routing: `/readings/export` is a distinct path from `/readings`, so it does not collide with `GET /readings?meterId=` (which still requires `meterId`). Query parameters on `/readings/export` are not part of the contract.

Error cases: none specific to this endpoint; it takes no input to validate. Non-GET methods on `/readings/export` get Spring's default `405 Method Not Allowed` (`ProblemDetail` `about:blank`). An `Accept` header that excludes `text/csv` is not negotiated against (see Open questions 3).

Idempotency: read-only `GET`, no writes, so no idempotency key is needed.

## Behaviour per AC

### AC-F36-1

`GET /readings/export` returns `200`. The `Content-Type` media type is `text/csv` (with the parameter `charset=UTF-8`; a check of the type is `contentTypeCompatibleWith("text/csv")`). The first line of the body is exactly `meterId,timestamp,value`, followed by CRLF.

### AC-F36-2

After the header, each stored reading is exactly one CSV line with the columns `meterId,timestamp,value` in that order, rendered as in the Data shape table, each line ending in CRLF.

- Lines appear in storage order (the order the readings were posted); this order is not a sorting guarantee clients should rely on beyond that.
- All meters are included; there is no filter.
- Duplicate readings (same meter, time and value posted twice) are stored twice today, so they appear as two lines.
- Readings removed by `DELETE /readings?meterId=` no longer appear; rejected posts (400) never appear.
- With no readings stored, the body is only the header line: `meterId,timestamp,value\r\n`.
- The number of lines after the header equals `GET /readings/count` taken at the same moment.

### AC-F36-3

A `meterId` that contains a comma (`,`) or a double quote (`"`) is written as an RFC 4180 quoted field: wrapped in double quotes, with each inner double quote doubled.

- `a,b` becomes `"a,b"`; `say "hi"` becomes `"say ""hi"""`; `x"` becomes `"x"""`.
- A `meterId` containing CR or LF is quoted the same way (RFC 4180 requires it; the line break stays inside the quoted field).
- A `meterId` with none of these characters is written as is, unquoted (e.g. `m1`).
- `timestamp` and `value` never contain these characters, so they are never quoted; they go through the same `csvField` helper anyway.

## Out of scope

- Filtering, pagination, other formats such as Excel or JSON lines (issue).
- Streaming very large exports; the in-memory store is small, so the body is built as one `String`.
- A `Content-Disposition: attachment` filename (not asked for).
- Authentication of the "analyst" (the service has no security; see F16 open question 1).
- Spreadsheet formula-injection mitigation (see Open questions 2).

## Open questions

None blocking; the spec takes the defaults below and the plan gate can change them before build.

1. Format details the issue does not fix: line ends are CRLF (RFC 4180), the last line also ends in CRLF, `timestamp` is ISO-8601 UTC with `Z`, `value` is the plain decimal as stored. If the hidden scenarios expect LF or no trailing line break, AC-F36-1/AC-F36-2 must be restated.
2. CSV injection: a `meterId` starting with `=`, `+`, `-` or `@` can run as a formula when the file is opened in a spreadsheet. AC-F36-2 asks for the stored value as is, so this spec does not prefix or alter it. Should the security owner want a mitigation (for example a leading `'`), that is a new AC.
3. `Accept` handling: a client sending `Accept: application/json` still gets `text/csv`. The alternative is `406 Not Acceptable`; the issue does not say.
