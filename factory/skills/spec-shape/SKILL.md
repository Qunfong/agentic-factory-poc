---
name: spec-shape
description: Use when writing spec.md, plan.md and work-items.json for a feature of the meter service. Settles data shapes and interfaces before any code exists.
---

# Spec shape

1. Ground. Name the capability packages the feature touches and read their controller, service and model. Read the ADRs for those packages. If nothing exists yet, say "greenfield".
2. Sketch the shape in spec.md as Java signatures, not prose: request/response `record`s, service method signatures, repository methods, error cases as `ProblemDetail` type + status. Bodies are `// not implemented`.
3. Check the sketch against these rules and fix it before writing anything else:
   - money and energy are `BigDecimal`, time is `Instant` (UTC);
   - validation happens at the boundary;
   - retried writes are idempotent; say what the idempotency key is;
   - no new top-level technical packages.
4. One AC maps to exactly one work item. A work item is a vertical slice (HTTP to storage) that can merge alone; list its `paths` as narrowly as you can, because the guard enforces them.
5. Write an ADR proposal only for a real choice between alternatives that a later change would have to undo. Not for following an existing ADR.
6. Red flags; stop and list under Open questions: an AC that needs a business rule the issue does not give; a shape that needs `app/pom.xml` or a migration (that is a protected change); two ACs that contradict.
