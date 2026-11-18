---
name: minimal-change
description: The smallest complete change that makes the work item's tests pass. Always on for the builder.
---

# Minimal change

Solve the whole work item with the least new code. Be lazy about the solution, never about completeness.

## Before you edit
Read the work item, the spec, the tester's tests and the code they touch. List every place the change must reach: callers, wiring, config, mappers, error paths. That list is the scope. Features nobody asked for are not.

## Pick the first option that fully works
1. Already in this codebase (helper, service, pattern)? Use it the way the surrounding code does.
2. Java standard library or a Spring feature the project already uses? Use it.
3. A dependency already in `app/pom.xml`? Use it. A new dependency is a protected change: request it, never work around it.
4. Otherwise: the minimum code that works and that a reader understands at a glance.

## Rules
- Finish every part the tests and acceptance criteria need. A shorter diff that misses a caller or an edge case is not smaller, it is broken.
- No abstraction, interface, option, config property or "for later" code the work item does not need. Keep the existing layers, packages and conventions.
- Bug fix: find every caller of the code you touch, then fix the root cause once, in the shared code.
- Code you move keeps its validation and error handling.
- Between options of equal size, take the one that is correct on edge cases (null, empty, boundaries, concurrency the code already has).
- Comment only the why the code cannot show, in one line. A known shortcut gets `// shortcut: <limit>, <when to upgrade>`.
- Never cut: input validation at trust boundaries, error handling that prevents data loss, security checks, anything the work item or spec asks for.

## Tests
The tester owns all tests. You do not add, change or delete test files. If you believe a check is missing, name it in your summary.

## Summary
End with at most two lines: what you deliberately left out or did not verify, and any risk a reviewer must know.
