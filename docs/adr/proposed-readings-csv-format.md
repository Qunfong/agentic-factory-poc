# Proposed: readings CSV is a hand-written RFC 4180 writer, minimal quoting, CRLF, UTF-8

- **Status:** Proposed (spec writer, feature F36); to be accepted at the plan gate
- **Modules:** `com.example.meter` readings (`ReadingController`, `GET /readings/export`)

## Context

Feature F36 adds `GET /readings/export`, which returns all readings as CSV for spreadsheets. The issue fixes the header (`meterId,timestamp,value`) and RFC 4180 escaping for meter ids with commas or quotes. It does not fix line ends, the charset, when to quote, or how a timestamp and a decimal are rendered. Once analysts build spreadsheets and scripts on the file, changing any of these is a format break. A CSV library (Commons CSV, Jackson CSV) would need an `app/pom.xml` change, which is protected.

## Decision

- A small helper in `ReadingController` writes the CSV; no new dependency.
- A field is quoted only when it contains `,`, `"`, CR or LF; inner `"` are doubled (RFC 4180, section 2.6-2.7).
- Every line, including the last, ends in CRLF (RFC 4180, section 2.1-2.2).
- The response is `text/csv;charset=UTF-8`, set explicitly; no BOM.
- `timestamp` is `Instant.toString()` (ISO-8601 UTC, `Z`), the same form as the JSON API. `value` is `BigDecimal.toPlainString()` (no scientific notation, scale as stored).

## Alternatives

1. **Add a CSV library.** Handles edge cases for free, but needs a protected `app/pom.xml` change for about ten lines of code.
2. **Quote every field.** Simpler rule and safe, but every line differs from the plain form analysts expect, and AC-F36-3 reads as quoting being the exception.
3. **LF line ends.** What most Unix tools emit and many tests assume, but not RFC 4180, which the issue cites.
4. **UTF-8 with BOM.** Older Excel versions then detect UTF-8, but the BOM breaks a byte-exact header check and most non-Excel parsers.

## Consequences

- Clients get a stable, RFC 4180 format; a later switch to LF, full quoting or a BOM is a client-visible change.
- Formula injection (`=`, `+`, `-`, `@` at the start of a meter id) is not mitigated; values are exported as stored (spec F36 open question 2).
- The writer is in-memory; a large store would need streaming (`StreamingResponseBody`), with the same format.

## Re-evaluation triggers

- More CSV exports appear (then a shared writer or a library pays off).
- The store grows beyond what fits comfortably in one response string.
- The security owner asks for formula-injection protection.
