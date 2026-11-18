# ADR-0017: Separation of duties at release is an accepted gap while one person holds every gate role

- **Status:** Proposed (Cowork, 2026-11-17, from QUESTIONS Q60 and Audit round 1 R4). Qun accepts it or not.
- **Date:** 2026-11-17
- **Decision makers:** @Qunfong
- **Confidence:** not stated

## Decision

The architecture rule "the release owner did not approve the merge of the same change" is **not enforced** today. A private Free repo cannot configure environment reviewers, and Qun is the only collaborator, so no second identity exists to compare against. We do not build a check against a guessed definition of "production approver": a check nothing can falsify looks like a control and is not one.

`60-release.yml` already fails closed for production when the environment has no required reviewer (ADR-0014). The run record gets `merged_by` per release as inert data (brief or PR by Claude Code, red path).

## Revisit when

A second collaborator exists, or environment reviewers become configurable (public repo or paid plan). Then add the release-gate check that fails when the merge approver and the production approver are the same person (audit R4).

## Consequences

R4 stays open in the audit list. Every production deploy by Qun is a self-approved deploy and is logged in the STATUS Bypass log.
