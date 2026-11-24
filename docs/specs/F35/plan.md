# F35 plan: README documents the HTTP API

Spec: [spec.md](spec.md). One work item, WI-1, covering all three ACs: they are one README section and cannot merge usefully apart.

## Modules that change

- `README.md`: add a `## HTTP API` section. Nothing else.

No change under `app/**`, `app/pom.xml`, migrations, security, billing or factory paths. Risk tier: green (`**/*.md`), so no AI review is expected.

## Steps (WI-1)

1. Re-read `MeterController`, `ReadingController`, `MeterProblemHandler` and `MeterType` on the base commit and confirm the five endpoints and their statuses match the contract table in the spec.
2. Add `## HTTP API` to `README.md`, after the intro and before `## Flow` (or at the end; placement is the builder's call): one sentence on base URL and `application/problem+json` errors, the endpoint table (method, path, success, errors), then the two curl examples from AC-F35-3.
3. Optional check: run the service (`mvn -f app/pom.xml spring-boot:run`) and run both curl examples; both return 201.
4. Run `mvn -B -f app/pom.xml verify` (must stay green; nothing in `app` changes).

## Risks

- Drift: the README is not generated from code, so a later endpoint change can leave it stale. Accepted for now (OpenAPI is out of scope); later features that change the API should update this section.
- No hidden acceptance scenarios exist for these ACs (issue readiness; ADR-0007), and no JUnit test can tag a README check, so acceptance is by review of the spec contract table against the README.
- Root `README.md` is the factory README; see the open-question note in the spec.
- If another feature lands new endpoints first, the builder documents the code on its own base commit.
