# ADR-0004: Agents never write to GitHub; one App-token publish job does

- **Status:** Proposed (brief 004, ANSWERS Q3, Q11; implemented on `brief-004`, not merged)
- **Date:** 2026-11-11
- **Decision makers:** Cowork (brief 004); App created by @Qunfong
- **Confidence:** not stated

## Decision

**Agent jobs are read-only.** Each agent workflow is split into `prepare → agent → publish`. Only the reusable `publish.yml` pushes or opens PRs. It uses a token from the `agentic-factory-bot-qunfong` GitHub App, which has Contents, Pull requests and Issues write, Metadata read, and no Workflows permission. The tester and the builder publish separately: the tests land first, and the builder may edit only `app/src/main/**`.

## Context

An agent with a push token can bypass every guard. Splitting the jobs keeps model output (an artifact) apart from the credential that writes it.

## Consequences

- If the builder fails, the branch `wi-<n>` holds only the tests, gets the label `factory:builder-failed`, and a rerun continues idempotently (Q11).
- The builder can't add test helpers; that goes through a protected-change request.
- The App id/client id is public (`FACTORY_APP_CLIENT_ID`). The private key is the secret `FACTORY_APP_PRIVATE_KEY`.
- Agent jobs use no cache; release builds without a cache (Q10, decided by @Qunfong).

## Re-evaluation Triggers

- Production moves to a tool gateway with per-tool scopes (README "POC shortcuts").
