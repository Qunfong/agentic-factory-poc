# Meter service verification map

The maintained source for verifying what a client of the meter service can observe. Read this index, then follow the feature file for what you changed.

## Baseline preconditions

- The service runs from `app/target/meter-service-0.1.0.jar` on `$PORT`, started by this run (see SKILL.md Launch).
- The doctor reports `{"status":"UP"}` and your PID is alive.
- The store is empty at launch; use a meter ID unique to the run, such as `m-verify-$RUN_ID`.

## Features

| ID | File | Surface |
| --- | --- | --- |
| `readings` | [readings.md](readings.md) | `POST /readings`, `GET /readings?meterId=` |
| `health` | (SKILL.md Doctor) | `GET /actuator/health` |

## Proof and skip reporting

- Each call's status, headers and body go to `$EVIDENCE`, numbered in call order.
- A write is proven only by a read-back through `GET /readings`.
- An unreachable path is reported with the attempted command and the unmet precondition.
