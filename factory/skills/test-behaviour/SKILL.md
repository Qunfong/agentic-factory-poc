---
name: test-behaviour
description: Use when writing or changing any test. Tests assert what a caller can observe, so they fail when behaviour breaks and pass when only internals change.
---

# Test behaviour, not implementation

1. Start from the acceptance criterion: what does a caller send, and what must they observe?
2. Test through the public interface (HTTP endpoint, public method, emitted message). Never through private methods or by inspecting internal state.
3. Mock only at system boundaries you do not own (external HTTP, clock, random). Do not mock the class under test's collaborators inside the service.
4. Each test fails for exactly one reason. If a refactor that keeps behaviour would break the test, rewrite the test.
5. Cover the edge each criterion implies: empty, boundary value, invalid input, repeated call.
6. A test you cannot write without a production-code decision becomes a question on the work item, not a guess.
