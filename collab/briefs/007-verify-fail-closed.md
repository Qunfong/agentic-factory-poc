# Brief 007: Verify fails closed and runs only the PR's acceptance scope

Drafted by Claude Code at Qun's request (2026-11-11), from the high-severity items in the design review. Cowork: please review. Decision 2 was settled by ANSWERS Q4 (2026-11-11).

## Goal
The `required` check can only be green when the right acceptance scenarios actually ran and passed. A spec PR, or a PR for one work item, isn't failed by scenarios for work that isn't built yet.

## What to build
1. **Fail closed.** `40-verify.yml` fails when:
   - the app health check never passes
   - the acceptance build or checkout fails (remove `|| true` and `>/dev/null`)
   - there are zero reports
   - any expected AC ID has no report
2. **Scope (ANSWERS Q4).**
   - Each acceptance scenario is tagged `@Tag("AC-<feature>-<n>")`, for example `AC-F1-3`. IDs are unique across features.
   - For a work-item PR (`wi-<n>`), the scope is that work item's ACs **plus** the ACs of every work item already merged (regression). Verify selects them with `-Dgroups` and fails closed when any AC in scope has no scenario.
   - A spec PR (`spec/F<n>`) runs no acceptance scenarios. It checks that every AC in the spec has a unique ID in that format. It also runs unit tests and gitleaks.
   - Update `acceptance-repo-example/` to the tag convention, so PO/QA have a template.
3. **Isolation (medium, if cheap).** The app under test can't read `acceptance/`. Start it before the acceptance checkout, or run it in a container without that mount.

## Acceptance criteria
- A PR whose app fails to start ends with `required` red.
- A PR for a work item with AC-F1-1 and AC-F1-2, after a merged item with AC-F1-3, runs exactly AC-F1-1..3.
- A PR whose scope contains an AC with no tagged scenario ends red.
- A spec PR goes green when its AC IDs are unique and well-formed, and red on a duplicate ID.
- Verify logs show only AC IDs and pass/fail, never scenario content (brief 009).
