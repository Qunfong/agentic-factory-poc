# Brief 019: the factory answers clarifications and review comments on its PRs

Qun (2026-11-13), on spec PR #29: "how do you handle clarifications or comments on PRs? they should lead to updates too." Today they don't: agents read only files (`spec.md`, tests), so a PR comment changes nothing. Spec PR #29's eight open questions could only be answered by a manual commit. Starts after brief 017; it builds on 017's status comment.

## Decisions
1. **Trigger.** A maintainer or admin (same `authorize` rule as everywhere, ADR-0008) asks for a revision on a factory PR (`spec/F<n>` or `wi-<n>`):
   - a review with **Request changes**; or
   - a comment starting with `/factory revise`.
   Anyone else's comments are ignored. The workflow logic always runs from the default branch (use a trigger that does, or a thin trigger that dispatches a `master` workflow). The PR branch's YAML never decides anything.
2. **Input to the agent.** All unresolved review threads and the triggering comment from authorized people: file, line, text and author. They are wrapped in `<untrusted-pr-comments>` like issue text today. Also the latest 50-review findings marked strong or verified, if the reviewer asks for them with `/factory revise --with-ai-findings`.
3. **Spec PR → spec writer re-runs** on the existing branch. It updates `spec.md`, `plan.md` and `work-items.json`, and records answers in a section **"Decisions at the plan gate"**: question, answer, who, date, comment link. An answered open question is removed from "Open questions". AC IDs never change (Q23); a new or changed AC is a new spec PR, not a revision.
4. **Work-item PR → builder revision round** with the same guard as today (`app/src/main/**` only). A comment that needs a test change triggers the tester first, also within its guard. A change outside both is a protected-change request, never a silent edit.
5. **No cap on human-requested revisions** (Qun, 2026-11-13: a fixed cap is odd when a person asks for each one). Each revision needs an explicit request by a maintainer, so a person is always in the loop. Guards instead of a cap: one revision at a time per PR (concurrency group; a new request while one runs is queued, not started twice); a revision that produces no change replies "No change made: <reason>" on each thread and does not push; the token and cost use per revision and in total for the PR are shown in the status comment, so spend stays visible. The 2 automatic fix rounds (45, no person involved) keep their cap.
6. **Reply on every thread.** The bot answers each thread it was given: "Changed in `<sha>`: …" or "Not changed: <reason>". It never resolves a thread itself; the reviewer does.
7. **Every revision goes through 40-verify and 50-review again**, as any push does, and updates the status comment on the feature issue (brief 017).
8. **Publishing** only through `publish.yml` with the App token (ADR-0004). The agent jobs stay read-only.

## What to build
- A revise workflow (trigger + authorize + prepare → agent → publish), reusing the 10-spec and 30-build agent jobs with a `revision` input.
- `tools/pr_feedback.py` (+ tests): collect unresolved threads by authorized authors, render the untrusted block, and post the per-thread replies after publish.
- Prompt additions in `factory/prompts/spec-writer.md` and `builder.md` for revision mode (Cowork drafts the text).
- Policy rules: the revise workflow has `authorize`, runs default-branch logic, and passes comments only inside the untrusted wrapper.

## Acceptance criteria
- On a spec PR, a Request-changes review that answers an open question leads to a new commit. The spec then shows the answer under "Decisions at the plan gate", the question is gone, the thread has a bot reply, and verify and review rerun.
- On a `wi-<n>` PR, a `/factory revise` comment leads to a builder commit within its guard and a reply per thread.
- A comment by a non-maintainer does nothing (test with a stubbed permission).
- A second request while a revision runs is queued, not run in parallel; a revision without changes replies and pushes nothing; the status comment shows tokens and cost per revision.
