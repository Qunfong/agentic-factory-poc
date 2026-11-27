# D68: Repair work-item PRs whose `build-test` fails for reasons no builder can fix

Idea: #68. Status: sparring document for the idea sign-off (ADR-0018). This is also the first real
idea to go through the design-idea tier.

## What exists today (grounding)

- **Automatic fix rounds already exist.** `.github/workflows/45-fix-round.yml` runs on every
  completed `40 verify` for a `wi-<n>` branch. When the `required` job itself failed, it adds
  `round:<n>` and dispatches `30 build` again, up to 2 rounds. After that it adds `escalated` and
  comments "Fix-round limit reached". So a red work-item PR does not sit idle. What it gets is a
  **builder** round, and that is the problem:
- **The builder can never touch tests.** `tools/publish.py`'s builder guard is the work item's
  `Paths:` minus `app/src/test/**`, or `app/src/main/**` when that leaves nothing (ADR-0020).
  `30-build.yml`'s `builder_tools` drops test paths the same way. The builder charter denies
  "existing tests". Neither of the idea's two failure patterns can be fixed with that write
  access. A fix round on them burns two builder runs, often with "produced no changes", and then
  escalates. The escalation says nothing about *why* it failed.
- **The tester writes new files only.** The `tester` role in `tools/publish.py` uses
  `--allow app/src/test/** --new-files-only`. `tools/tester_loop.py`'s `write_file` refuses
  existing files. The tester runs once per work item, on round 0, and its charter sets
  `max_fix_rounds: 0`.
- **Compile-time stubs are a known pattern.** The tester may write a stub whose first line is
  `// factory-test-stub`. `publish.py`'s `remove_shadowed_stubs()` deletes it once the builder adds
  the real class.
- **Correction to the issue's context.** No `factory:fix` label or human-triggered fix round
  exists on `main`. `tools/review.py`'s `merge_decision` (brief 034) only decides whether a
  reviewed work-item PR may auto-merge (ADR-0019). This design builds on `45-fix-round.yml`, the
  automatic path that does exist. If PR #59's mechanism lives elsewhere, see Open question 4.

## The problem

Two failure classes reach `required` as red PRs, and no role can fix them:

1. **Collateral breakage of a pre-existing test.** Work item A changes main code, for example by
   adding a constructor dependency to `ReadingController`. An older test that A does not own, such
   as `ReadingControllerTest` (`@WebMvcTest` without a `@MockBean` for the new dependency), then
   fails to compile or to load its context. This happened in PR #56 (F7 WI-2) and PR #62 (F34
   WI-3). The tester cannot edit the file because it is not new, and the builder cannot edit it
   because it is a test.
2. **A broken or empty tester output.** PR #65 (F60 WI-1) had a test file with a misused
   annotation and no `@Test` methods. Nothing checks the tester's output before the builder runs,
   so the defect surfaces only as a red `build-test`. A builder fix round cannot repair it either.

The rule that the agent writing the code never edits the tests that judge it is a real control.
It is why ADR-0020 removes `app/src/test/**` from the builder's paths. Any fix has to keep that
control, not trade it away for convenience.

## Alternatives

### A. Let the fix-round builder repair pre-existing tests (the issue's hunch)

On a fix round (round ≥ 1), the builder's guard also allows *modifying* existing files under
`app/src/test/**`, except the files this work item's tester added.

- **For:** smallest change to the existing machinery. Fully automatic, and it catches breakage no
  one anticipated.
- **Against:** in that round the same agent edits both the code and its judge. Excluding "this work
  item's own test files" protects the new ACs, but not older behaviour. An `@MockBean` fix and an
  "assertion deleted" fix look the same to the guard. Hidden acceptance (ADR-0007) covers only the
  ACs in scope, not every older test. This reverses the intent of ADR-0020 and the builder
  charter's `denied: existing tests`.

### B. A separate test-repair role, dispatched only for collateral breakage

A trusted, deterministic classifier in `45-fix-round` reads the build output. If every failure
is in a test file that existed at the base commit and is outside the work item's paths, it
dispatches a new `test-repairer` role instead of a builder. That role may modify only those failing
files, may not reduce their test-method count, and cannot touch main code.

- **For:** keeps "author never edits its judge" (a different role and model run). Still automatic.
  Its scope is narrow and mechanical.
- **Against:** a sixth role means a charter, skills, a model route, a publish role, policy-check
  rules and secrets wiring. That is a lot of red-tier `.github/**`/`factory/**` surface for a
  failure seen twice. An unattended agent still changes an existing test with no human ever seeing
  that decision. A method-count check catches deleted tests, not weakened assertions.

### C. Decide at the plan gate: the tester may update existing tests the work item declares

The spec writer already declares a work item's `paths` in `work-items.json`, and the plan gate is
where a person signs that off. If a work item will break an existing test (plan.md says
"`ReadingController` gets a `MeterService` dependency"), the spec writer lists that test file in
`paths`. The round-0 tester may then modify exactly the declared existing test files, under a
trusted check that no `@Test` method disappears. The tester already runs before the builder, so the
adjusted test (for example an added `@MockBean MeterService`) stays green before and after the
builder's change. The builder's guard does not change. For breakage nobody anticipated, add only a
classifier: when every failure is in an undeclared pre-existing test, `45-fix-round` skips the
pointless builder rounds and escalates right away. The escalation names the files and the failure
kind.

- **For:** no new role. The tester's guard follows the work item's `paths` the same way ADR-0020
  made the builder's guard follow them, so the change is symmetric and familiar. A human sees and
  approves "this work item touches that test" at the plan gate. The builder still never touches
  tests. It also saves two wasted builder rounds per incident.
- **Against:** the fix for anticipated breakage depends on the spec writer foreseeing it.
  Unanticipated breakage still needs a person, but now with a precise diagnosis right away instead
  of after two rounds. The tester now edits existing files, a new capability, gated by `paths` and
  a method-count check.

### D. Prevent it inside the builder: it must keep existing tests green

Leave every guard as it is. The builder's prompt (the `impact-check` skill) requires it to run the
full `mvn verify` and to choose a change that keeps existing tests compiling. That could mean a
second constructor, a default bean, or making the dependency optional. If it cannot, it stops with
a protected-change request.

- **For:** no new authority at all. It pushes the builder toward backward-compatible changes.
- **Against:** it bends production code to fit stale tests, such as adding a constructor only for a
  test. That is the wrong way round and goes against `minimal-change`. It also does nothing for
  failure class 2.

### Failure class 2 (tester output), two options

- **2a. Completion gate inside the tester loop.** `tools/tester_loop.py` does not accept "done"
  while `test-compile` fails or while a new `*Test.java` has no test method. It tells the model why
  and continues within its existing limits. This is cheap and fixes the problem where it happens,
  but the loop runs in the agent's job, so it is not trusted on its own (ADR-0006).
- **2b. Trusted post-tester gate in `publish-tests`.** The same two checks run again in the trusted
  publish path, and it fails closed: a work-item label, no builder start. Optionally the tester is
  re-dispatched once. Running `test-compile` there executes agent-written code, so it must run in a
  job without secrets, as `40-verify` already does.

## Tradeoffs

| | A: builder fixes tests | B: test-repair role | C: plan-gate declared + classifier | D: builder stays compatible |
| --- | --- | --- | --- | --- |
| Keeps "author never edits its judge" | no | yes | yes | yes |
| A human sees an existing test change | no | no | yes (plan gate) | n/a |
| Handles unanticipated breakage automatically | yes | yes | no (fast escalation instead) | partly |
| New red-tier surface | guard + 45 | role, charter, models, publish, 45 | tester guard, 45 classifier, charter | skill only |
| Stops wasted builder rounds | no | yes | yes | no |

## Recommendation

**C for failure class 1, and 2a plus 2b (no auto-retry yet) for failure class 2.**

C keeps the control ADR-0020 deliberately built. It puts the one real judgment call ("this work
item may change that existing test") at the gate where a person already signs off, and it turns
today's slow, silent escalation into an immediate, diagnosed one. If the classifier then shows that
undeclared breakage is common, B is the next step, and the classifier C introduces is exactly what
B would dispatch on. A is not recommended: it would make the builder the author of both the change
and the tests that judge it, which is the trade the issue itself warns about. D is a useful line in
the builder's `impact-check` skill, but it is not a fix.

For class 2, the trusted gate (2b) is the control. The in-loop gate (2a) avoids most rejections in
the first place. Whether a failed gate re-dispatches the tester once is left to a human (Open
question 2). Until then it fails closed with a label, the same way `factory:builder-failed` works
today.

## What this means for existing ADRs

- **ADR-0020:** unchanged for the builder. Its pattern, a guard that follows the work item's own
  `paths`, is extended to the tester for declared existing test files. See
  [proposed-tester-updates-declared-tests.md](../../adr/proposed-tester-updates-declared-tests.md).
- **ADR-0019:** auto-merge stays as it is. Open question 3 asks whether a work-item PR that
  modifies an existing test should still auto-merge.
- **ADR-0007:** unchanged. Hidden acceptance still runs by AC ID. The classifier reads only the
  build-test output, never the acceptance job.
- **ADR-0006:** the classifier and the post-tester gate must be trusted tools from the workflow's
  own commit. The `test-compile` in 2b runs agent code, so it runs without secrets.
- **ADR-0018:** this is its first real exercise. One observation for its "revisit when": the issue
  text cited a mechanism (`factory:fix`) that does not exist on `main`. Design writers need the
  grounding step to correct an issue's context, not only to extend it.
- **Charters (`factory/**`, red tier, human change):** `tester.yaml` `denied: existing test files`
  becomes "existing test files not declared in the work item's paths". `builder.yaml` does not
  change.

## Proposed features

- Tester may update existing test files that its work item declares in paths
  AC-1: A tester patch that modifies an existing file under app/src/test/** listed in the work item's Paths: line is accepted by the publish guard and pushed to wi-<n>.
  AC-2: A tester patch that modifies, deletes or renames an existing test file not listed in Paths: is rejected and nothing is pushed.
  AC-3: A tester patch that leaves a declared existing test file with fewer @Test or @ParameterizedTest methods than at the base commit is rejected.
  AC-4: A builder patch that touches any file under app/src/test/** is still rejected, whatever the work item's Paths: line lists.
- Fix rounds escalate immediately when only undeclared pre-existing tests fail
  AC-1: When required fails on wi-<n> and every failing test class or compile error is in a test file that existed at the work item's base commit and is not in its Paths:, no 30 build round is dispatched and the work item gets the escalated label.
  AC-2: The escalation comment names each failing test file and its failure kind (compile error, context load failure, assertion failure), taken from build output parsed by a trusted tool, and quotes no raw log text.
  AC-3: When at least one failure is in a file this work item added or in app/src/main/**, the next builder round is dispatched as today, with the existing limit of 2 rounds.
- Tester output is checked before any builder starts
  AC-1: tools/tester_loop.py does not end with a success result while test-compile fails or while a new *Test.java file it wrote contains no @Test or @ParameterizedTest method; the model is told the reason and the loop continues within its existing limits.
  AC-2: publish-tests rejects a tester patch in which a new *Test.java file has no test method (files whose first line is // factory-test-stub are exempt) and labels the work item factory:tester-failed; no builder job starts.
  AC-3: publish-tests rejects a tester patch that fails mvn test-compile, in a job without model or App secrets, with the same label and no builder start.

## Open questions

1. **May an unattended agent ever modify an existing test that no human approved?** That is the
   line between C, which says no and escalates, and A or B, which say yes. It is a judgment about
   how much the test suite is trusted as an oracle, so a person has to decide it. The
   recommendation assumes "no, for now".
2. **Should a failed tester gate re-dispatch the tester once?** That means changing `tester.yaml`'s
   `max_fix_rounds: 0` to 1. A retry adds model cost and a second chance at the same mistake;
   without one, every bad tester output needs a person. The issue's hunch assumes a retry. The
   recommendation leaves it out until there is data.
3. **Should a work-item PR that modifies an existing test still auto-merge (ADR-0019)?** The plan
   gate approved the path, but not the exact edit. One option is to add `factory:human-review` when
   the diff modifies a pre-existing file under `app/src/test/**`.
4. **Where does the `factory:fix` / PR #59 fix-round mechanism live?** It is not on `main`: no
   label, no workflow, and `tools/review.py` has only `merge_decision`. If it exists on an open
   branch, this design should state how the two automatic paths relate before either is built.
