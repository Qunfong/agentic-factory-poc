# Hidden acceptance scenarios (example)

This folder shows what lives in the **separate private repo** set in the `ACCEPTANCE_REPO` variable.
Do not keep it in the product repo: agents must not be able to read it (ADR-006).

- Written and owned by the product owner or QA; a second person approves changes.
- Tag each scenario with the ID of the acceptance criterion it proves: `@Tag("AC-F1-3")`.
  The ID is `AC-F<feature>-<n>`, the same ID the spec declares in `docs/specs/F<feature>/work-items.json`.
  One AC can have several scenarios; give each the same tag.
- Verify runs only the ACs in a PR's scope (brief 007): the work item's own ACs plus those of every
  work item already merged. Scenarios for work not built yet stay in this repo and do not run.
  An AC in scope without a tagged scenario fails verify.
- Verify selects each AC with `-Dgroups=<AC ID>` and prints only `AC-F1-3: pass|FAIL`.
  Test names, assertion messages and output stay in a log that is not printed or uploaded,
  so name tests freely.
- Tests call the running app over HTTP at `-Dapp.url`.

Here `AC-F1-4` stands for a work item that is not built yet. Try the selection against a local app:

```
mvn -f app/pom.xml verify && java -jar app/target/meter-service-0.1.0.jar &
python tools/acceptance_run.py run --pom acceptance-repo-example/pom.xml \
  --scope "AC-F1-1 AC-F1-2 AC-F1-3" --app-url http://localhost:8080 --log acceptance.log
```
