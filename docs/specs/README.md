One folder per feature: `F<issue>/spec.md`, `plan.md`, `work-items.json`. Written by the spec writer, approved by merging the spec PR.

## Acceptance criterion IDs

- Each AC has the ID `AC-F<issue>-<n>`, for example `AC-F1-3`. The feature number makes it unique across features.
- `work-items.json` declares every AC exactly once, in the `ac_ids` of the one work item that delivers it.
  Work item `id`s are unique within the feature and hold no spaces or colons.
- `spec.md` describes the behaviour of each declared AC and mentions no other `AC-` ID.
- The hidden scenario for an AC carries the same ID as its JUnit tag: `@Tag("AC-F1-3")`.

Verify checks a spec PR (`spec/F<n>`) against these rules and runs no scenarios for it.
A work-item PR (`wi-<issue>`) runs the scenarios of its own ACs plus those of every work item already merged
into its base. The ACs come from this folder at the base commit, never from the PR. See `tools/acceptance_scope.py`.
