# G001: Reject a reading older than the meter's previous reading

Golden task for skill evaluation. Small, amber tier, one work item.

## Work item
As the meter service, I reject a new reading for a meter when its `takenAt` is earlier than the latest stored reading for that meter, so that consumption cannot go negative.

## Acceptance criteria
- AC-1: A reading older than the latest stored reading for the same meter returns 409 Conflict with a ProblemDetail body.
- AC-2: A reading with the same `takenAt` as the latest one returns 409 Conflict.
- AC-3: Readings for different meters do not affect each other.
- AC-4: A valid newer reading is still stored and returns 201.

## Expected outcome (for the evaluator, hidden from the agent)
- Acceptance test: `factory/golden/G001/AcceptanceTest.java` (to be written by Claude Code from these criteria, kept outside the agent workspace during eval).
- Reasonable diff: under 60 changed lines in `app/src/main`.
- No new dependency.
