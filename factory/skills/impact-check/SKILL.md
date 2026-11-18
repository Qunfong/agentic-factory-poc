---
name: impact-check
description: Use before reporting done when your change alters a public method signature, a request/response record, a JSON field, a configuration key, or code used by more than one capability package.
---

# Impact check

Find what your change can break outside the diff, and prove the one fact it is safe because of.

1. List what changed beyond the lines: public signatures, serialized JSON (field names, nullability, number format), HTTP status codes, configuration keys, behaviour on retry.
2. Find the users. Search for callers of each changed symbol and for the JSON field names in tests and docs. A search that finds nothing is an answer; write it down.
3. Name the one fact the change is safe because of (for example "no caller relies on the old field name"). Point at the `file:line` that shows it.
4. Prove it by running code: `mvn -B -f app/pom.xml verify` with an existing test that exercises that path. You may not add or edit tests; if no test covers it, write "unproven" and say which test is missing.
5. In the run summary, under "Impact": the fact, its proof or "unproven", and each remaining risk with its `file:line`.
