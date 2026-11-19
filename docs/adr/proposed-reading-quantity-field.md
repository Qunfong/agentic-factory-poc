# Proposed: the reading field `kwh` becomes `quantity`

- **Status:** Proposed (spec writer, feature F7); to be accepted at the plan gate
- **Modules:** `com.example.meter` readings (`Reading`, `ReadingRequest`, `ReadingController`)

## Context

Today every reading has a `BigDecimal kwh`. Feature F7 adds meter types with their own units: gas readings are in m3 and transformer readings in kW. A field called `kwh` that holds m3 or kW is misleading for clients and for anyone reading the code. Existing tests and clients send and read `kwh`.

## Decision

The reading field is called `quantity` (`BigDecimal`, at least 0). Its unit is the `unit` field of the reading, taken from the meter's type. On input, `kwh` is still accepted as an alias (`@JsonAlias("kwh")`), so existing writers keep working. Responses carry only `quantity`.

## Alternatives

1. **Keep `kwh` on the wire and in the code.** No break for anyone, but the name is wrong for gas and transformer meters, and every later feature inherits the confusion.
2. **Keep `kwh` in responses next to `quantity`.** No break for readers, but two fields with the same value, and `kwh` is still wrong for m3 and kW readings.
3. **Rename without an input alias.** Cleanest, but breaks every existing writer at once.

## Consequences

- Readers of `kwh` in responses break; the existing `ReadingControllerTest` assertion on `$[0].kwh` must change (part of the protected change F7 already needs).
- The input alias is debt: remove it once no writer sends `kwh`. Undoing this decision later is another wire break, which is why it is decided now.

## Re-evaluation triggers

- A client that cannot change and reads `kwh` from responses.
