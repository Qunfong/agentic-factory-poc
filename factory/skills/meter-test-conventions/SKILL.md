---
name: meter-test-conventions
description: Use when writing tests for the meter service. Gives test types, naming by acceptance-criterion ID and the tools to use.
---

# Meter service test conventions

- Name each test after the acceptance criterion it proves: `ac<N>_<behaviour>`, e.g. `ac2_rejects_reading_older_than_previous`.
- Web layer: `@WebMvcTest` with MockMvc; assert status and JSON body, not internal calls.
- Persistence: `@DataJpaTest` with Testcontainers (PostgreSQL); never an in-memory database for SQL behaviour.
- Use `BigDecimal` comparisons with `compareTo` or `isEqualByComparingTo`; never `equals` on scale-sensitive values.
- One behaviour per test; arrange data inline so a reader sees the case without opening fixtures.
- Put new test classes next to the code under test in `app/src/test/java/...`, mirroring the package.
