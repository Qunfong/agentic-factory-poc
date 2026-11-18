---
name: verify-meter
description: Use after changing app/src/main of the meter service, before you report done, to prove the change through the running service's HTTP API (POST/GET /readings, /actuator/health) the way a client calls it. mvn verify proves the tests; this proves the app.
---

# Verify the meter service

The meter service is a Spring Boot HTTP API (`app/`, Java 21, Maven). Its only user surface is HTTP: clients post and list meter readings. You prove a change by starting the real jar on a free port, calling the endpoints the change affects, and keeping the requests and responses as evidence. Tests are not this proof; run `mvn -B -f app/pom.xml verify` first, then drive the app.

Needs shell access to `mvn`, `java`, `curl` and background processes. If your allowed tools give you only `mvn`, say so in your run summary ("verify-meter: not run, curl not allowed") and rely on `mvn verify`; never claim a live proof you did not run.

## Launch

Run from the repository root, in one shell, so the variables survive:

```bash
RUN_ID=$(date +%s)
PORT=18080                                   # pick another if the doctor says it is taken
EVIDENCE="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/verify-meter-$RUN_ID"
mkdir -p "$EVIDENCE"
curl -s -o /dev/null "http://127.0.0.1:$PORT/" && echo "port $PORT is taken; choose another"
mvn -B -q -f app/pom.xml -DskipTests package
java -jar app/target/meter-service-0.1.0.jar --server.port=$PORT > "$EVIDENCE/app.log" 2>&1 &
APP_PID=$!
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/actuator/health" > /dev/null && break; sleep 1; done
```

Ready means `/actuator/health` answers `{"status":"UP"}`. Readings live in memory, so every launch starts empty; there is nothing to migrate or seed.

## Doctor

Run this first, and again whenever a call surprises you:

```bash
curl -s "http://127.0.0.1:$PORT/actuator/health"; echo
kill -0 "$APP_PID" && echo "pid $APP_PID is ours"
```

Healthy means `{"status":"UP"}` and the PID you started is alive. If health answers but your PID is dead, another process owns the port: stop, pick another port, launch again. Never drive an instance you did not start.

## Drive

Use the recipe in `features/` for the feature you changed. Read [`features/README.md`](features/README.md) first. Every call goes through `curl` with `-i` so the status line and headers are captured, and its output is written to `$EVIDENCE`:

```bash
curl -s -i -X POST "http://127.0.0.1:$PORT/readings" -H 'Content-Type: application/json' \
  -d '{"meterId":"m-verify","takenAt":"2026-01-02T00:00:00Z","kwh":10}' | tee "$EVIDENCE/01-post.txt"
```

## Evidence

- Keep one file per call in `$EVIDENCE`, numbered in call order, holding the full request intent (the command) and the response status, headers and body.
- Prove both the action and the resulting state: after a write, read back with `GET /readings?meterId=...` and keep that response too.
- For a rejection, prove the status, the `Content-Type: application/problem+json` header and the ProblemDetail fields, then prove the store did not change.
- Name `$EVIDENCE` and list its files in your run summary.

## Cleanup

```bash
kill "$APP_PID"; wait "$APP_PID" 2>/dev/null
```

Kill only the PID you started, never by process name. Cleanup leaves `$EVIDENCE` in place: it is the proof.

## Gotchas

- `kwh` is a JSON number, `takenAt` an ISO-8601 instant with `Z`. A missing or negative field gives 400 from Bean Validation, not from your code.
- State is per process: a restart forgets every reading. Run a whole recipe against one launch.
- `mvn spring-boot:run` forks a second JVM that `kill $!` does not stop; launch the jar with `java -jar` as above.
