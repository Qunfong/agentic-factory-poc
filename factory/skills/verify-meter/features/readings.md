# Readings

A client stores a meter reading and lists the readings of one meter.

## Sub-features

- `readings-add` stores a valid reading and answers 201 with the stored reading.
- `readings-reject` answers 400 for an invalid body (missing field, negative `kwh`), and 409 with a ProblemDetail when a business rule refuses the reading.
- `readings-list` lists the readings of one meter only.

## How to get to it (user POV)

- `POST /readings` with a JSON body `{"meterId": "...", "takenAt": "<instant>", "kwh": <number>}`.
- `GET /readings?meterId=<id>`.

## Driving it with curl

Preconditions: the doctor is healthy and `M=m-verify-$RUN_ID` has no readings.

- **Add.** `curl -s -i -X POST "http://127.0.0.1:$PORT/readings" -H 'Content-Type: application/json' -d "{\"meterId\":\"$M\",\"takenAt\":\"2026-01-02T00:00:00Z\",\"kwh\":10}" | tee "$EVIDENCE/01-add.txt"`. Status `201`, body echoes the reading.
- **Read back.** `curl -s -i "http://127.0.0.1:$PORT/readings?meterId=$M" | tee "$EVIDENCE/02-list.txt"`. Status `200`, a JSON array with that one reading.
- **Reject invalid.** Repeat Add with `"kwh":-1` into `03-invalid.txt`. Status `400`. Read back again into `04-list.txt`: still one reading.
- **Other meter.** Add a reading for `$M-other` into `05-other.txt`, then list `$M` into `06-list.txt`. The list of `$M` is unchanged.
- **Your change.** Add the calls your work item's acceptance criteria name, each followed by a read-back. For a 409, also check `Content-Type: application/problem+json` and `"status":409` in the body.

## Gotchas

- `GET /readings` without `meterId` answers 400: the parameter is required.
- The store keeps insertion order; do not assert a sort order the code does not promise.
- `kwh` echoes as a number (`10`, not `10.0` or `"10"`); compare values, not text, when the scale may differ.
