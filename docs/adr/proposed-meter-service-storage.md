# Proposed: meters and readings live in one in-memory `MeterService`

- **Status:** Proposed (spec writer, feature F7); to be accepted at the plan gate
- **Modules:** `com.example.meter` (`MeterService`, `ReadingController`, `MeterController`, `SummaryController`, web tests)

## Context

Today `ReadingController` holds its readings in a private list. Feature F7 needs that data in three places: `POST /readings` must check the meter registry, `GET /summary` must sum readings per type, and `POST /meters` owns the registry. `ArchitectureTest` forbids controllers depending on `@Repository` classes and forbids field injection. There is no persistence, and adding it would change `app/pom.xml` and add migrations (protected, red tier).

## Decision

One `@Service` class, `MeterService`, holds both the meter registry (`ConcurrentHashMap`) and the readings (`CopyOnWriteArrayList`), in memory. Controllers get it by constructor injection and keep no state. Web tests use `@WebMvcTest(<controllers>)` plus `@Import(MeterService.class)`.

## Alternatives

1. **Keep the readings in `ReadingController` and put summaries and registration there too.** No new bean and existing `@WebMvcTest(ReadingController.class)` slices keep loading, but one controller then owns three resources and state lives in the web layer.
2. **Two services (`MeterRegistry`, `ReadingStore`).** Cleaner split, but summaries need both, and two beans must be imported into every web test for a POC with a few dozen lines of storage.
3. **A real repository with persistence.** Survives restarts, but needs a dependency change and a migration (protected), and is out of scope for F7.

## Consequences

- Every web test, including the hidden acceptance scenarios, must import `MeterService`; a test that slices only a controller fails to start.
- State is shared per cached Spring context; tests must use unique meter ids.
- Moving to persistence later replaces `MeterService`'s fields with a repository behind the same method signatures; controllers do not change.

## Re-evaluation triggers

- Data must survive a restart, or a second instance is deployed.
