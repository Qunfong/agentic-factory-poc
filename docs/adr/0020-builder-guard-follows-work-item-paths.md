# ADR-0020: The builder's path guard follows its own work item's `paths`, not a fixed `app/src/main/**`

- **Status:** Accepted (Claude Code, 2026-11-24, found verifying the flow-test features)
- **Date:** 2026-11-24
- **Decision makers:** @Qunfong
- **Confidence:** medium - implemented and unit-tested, not yet exercised by a real work item

## Decision

`tools/publish.py`'s `builder` role could only ever write under `app/src/main/**` - hardcoded,
regardless of what `work-items.json` actually scoped the work item to. A docs-only or build-file
work item (F35: "README HTTP API section", `paths: ["README.md"]`) gives the builder nothing it
may touch, so it correctly produces an empty patch and fails with "produced no changes to
publish" - not a builder failure, a guard that doesn't know about the one file it needs.

The guard now reads the work item's own `Paths:` line from its issue body (written by
`tools/create_work_items.py` from `work-items.json`), drops anything under `app/src/test/**`
(the tester's own files, never the builder's), and uses what's left as the `--allow` list -
falling back to the old static `app/src/main/**` when there is nothing left (no paths declared,
or every one is a test file), so an older or path-less work item behaves exactly as before.

Any declared path a spec writer may also never touch (`.github/**`, `factory/**`, `.claude/**`,
`AGENTS.md`, `CLAUDE.md`) still raises `Rejected` rather than silently narrowing the guard, so a
typo'd or malicious path in `work-items.json` fails loudly instead of quietly widening write
access.

## Alternatives considered

- **Only allow `README.md` specifically.** Rejected: fixes this one feature, not the general case;
  the next doc/build-file work item hits the identical wall.
- **Let the spec writer choose the builder's guard directly.** Rejected: the spec writer already
  writes `paths` for exactly this purpose; a second, separate guard-configuration surface would be
  one more thing that can drift from the real paths.

## Consequences

The builder's effective write access is now exactly what the spec writer declared, per work item,
checked against the same deny-list a spec writer already can't cross. `tools/publish.py` gains
`builder_allowed_paths()`; `publish.yml`'s `apply` step extracts `Paths:` from the issue body and
passes it as `--issue-paths`.

## Revisit when

A real work item exercises this (F35 is the first candidate) - confirm the guard actually lets
the builder write `README.md` and nothing else, and that a mixed main+test `paths` list still
drops the test file correctly.
