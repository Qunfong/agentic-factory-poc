---
name: design-shape
description: Use when writing a design idea's proposal under docs/design/D<issue>/ and docs/adr/proposed-*.md. One level above a feature: settles direction and tradeoffs, not interfaces.
---

# Design shape

1. Ground. Read AGENTS.md, docs/adr/index.md and the ADRs for the systems or areas this idea touches. Name what already exists before proposing anything new.
2. Write docs/design/D<issue>/design.md: the problem this idea addresses, 2-4 real alternatives (not one strawman), the tradeoffs between them, a recommendation, and what it would mean for existing ADRs.
3. For the chosen direction, write docs/adr/proposed-<short-name>.md (context, decision, alternatives, consequences) only when the idea is concrete enough to commit to; otherwise leave it open and say why.
4. This is a sparring document, not a spec: no AC IDs, no work-items.json, no code signatures. If it recommends follow-up work, list it under a "Proposed features" heading in design.md as one bullet per feature: a one-line title, then 2-4 acceptance criteria indented below it, one per line starting "AC-n:" - this exact shape is what turns a signed-off idea into feature issues automatically.
5. If a real tradeoff is unclear or needs a decision only a human can make, list it under "Open questions" in design.md, and also post it as a comment on this idea's PR once one exists - never resolve it by guessing.
