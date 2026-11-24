# Proposed: a page of readings is a bare JSON array, and `meterId` becomes optional on `GET /readings`

- **Status:** Proposed (spec writer, feature F33); to be accepted at the plan gate
- **Modules:** `com.example.meter` readings (`ReadingController`, web tests)

## Context

Feature F33 adds `from`, `to`, `page` and `size` to `GET /readings`. Today the endpoint returns a bare JSON array of `Reading` and requires `meterId`; a call without it is a 400. The issue asks for browsing "stored readings" and says filtering by meter is out of scope, so an operator must be able to call `GET /readings?from=...&to=...` without a meter id. Existing clients and `ReadingControllerTest` read `$[0]` from the array.

## Decision

1. The response stays a bare JSON array of `Reading`: one page, at most `size` elements. No envelope, no total count, no links. A client knows it has reached the end when a page has fewer than `size` elements.
2. `meterId` becomes an optional query parameter. When present, it still filters as before, combined with the range and the paging.
3. Paging is offset-based (`page`, `size`) over the filtered list sorted by `takenAt` ascending, ties in insertion order.

## Alternatives

1. **Page envelope** `{"content": [...], "page": 0, "size": 20, "totalElements": n}` (Spring Data `Page` style). Gives clients a total, but breaks every reader of the array today and duplicates `GET /readings/count` (F21) for the unfiltered total. Moving to it later is a wire break, which is why this is decided now.
2. **Total count in a header** (`X-Total-Count`) next to the array. No body break, but nothing asks for a total, and the header becomes a contract to keep.
3. **Keep `meterId` required.** No change for existing callers, but an operator cannot browse all readings, which is the problem the issue states.
4. **A new path** (`GET /readings/page`) for the paged view, leaving `GET /readings?meterId=` unpaged. No behaviour change for existing callers, but the issue names `GET /readings`, and two list endpoints drift apart.

## Consequences

- Existing `GET /readings?meterId=` callers now get readings sorted by `takenAt` and at most 20 by default; a meter with more than 20 readings needs `page`/`size` to see them all (spec Open question 3).
- Clients that need a total for a filtered range cannot get one without paging through; adding it later is additive only as a header or a separate endpoint, not in the body.
- Offset paging over an in-memory list can skip or repeat a reading when writes happen between page requests; acceptable for an internal browsing use.

## Re-evaluation triggers

- A client needs a filtered total or page count.
- Readings move to persistence and offset paging becomes slow, or concurrent writes make page drift visible.
