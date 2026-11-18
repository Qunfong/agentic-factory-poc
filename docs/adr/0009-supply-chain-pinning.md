# ADR-0009: Pin everything a gate depends on

- **Status:** Proposed (ANSWERS Q10, Q13, Q21, Q51, Q53, Q55; implemented in brief 006 and 011, not merged)
- **Date:** 2026-11-12
- **Decision makers:** Cowork; Q10 by @Qunfong
- **Confidence:** not stated

## Decision

**A gate whose tools can change underneath it is not reproducible, so every dependency is pinned:**
- Actions are pinned by commit SHA.
- actionlint 1.7.12 and shellcheck v0.11.0 are sha256-checked downloads.
- gitleaks `v8.24.0` and Semgrep `1.182.1` run as digest-pinned images with `--network none`.
- Python requirements are hash-pinned and installed with `--require-hashes`. `tools/pin_requirements.py` refuses versions younger than **14 days**; exceptions go only through a committed `tools/young-pins.txt` (a red path).
- The Semgrep `p/java` rules are fetched at run time and checked against a pinned sha256. They are not vendored, because the Semgrep Rules License forbids redistribution (Q55).
- Release builds without a Maven cache. Agent jobs have no cache.

## Consequences

- When upstream changes the Semgrep ruleset, `static` goes red until the digest is bumped in a reviewed PR. This is a deliberate fail-closed choice.
- Updates are deliberate PRs, not something that happens silently.

## Re-evaluation Triggers

- A dependency mirror or proxy exists, which can take over caching and pinning.
