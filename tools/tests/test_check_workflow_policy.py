"""Rule logic over hand-parsed workflow dicts. These mirror the YAML before and after briefs 004 and 006,
so the rules run without pyyaml; tools/check_workflow_policy.py checks the real files."""
import pathlib, sys, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_workflow_policy as policy  # noqa: E402

APP = "${{ steps.app.outputs.token }}"
CLAUDE = {"uses": "anthropics/claude-code-action@v1", "with": {"github_token": "${{ github.token }}"},
          "env": {"ACTIONS_STEP_DEBUG": "false"}}
AUTHORIZE = {"permissions": {"contents": "read"}, "steps": [
    {"uses": "actions/checkout@v4", "with": {"ref": "${{ github.workflow_sha }}", "persist-credentials": False}},
    {"run": 'python3 tools/authorize.py --event "$EVENT" "$ACTOR" "$TRIGGERING_ACTOR"'}]}
TRUSTED_RECORD = {"env": {"WORKFLOW_SHA": "${{ github.workflow_sha }}"}, "run": (
    'git fetch -q --depth 1 origin "$WORKFLOW_SHA"\n'
    'git show "$WORKFLOW_SHA:tools/run_record.py" > "$RUNNER_TEMP/run_record.py"\n'
    'python3 "$RUNNER_TEMP/run_record.py" --role builder')}
LOAD = {"run": "python3 tools/load_skills.py builder"}
UPLOAD = {"uses": "actions/upload-artifact@v4", "with": {"name": "patch-builder", "retention-days": 7}}
EGRESS = {"run": (
    "sudo -n iptables -A OUTPUT -m owner --uid-owner nobody ! -o lo -j REJECT\n"
    "sudo -n ip6tables -A OUTPUT -m owner --uid-owner nobody ! -o lo -j REJECT\n"
    'curl -sS --max-time 10 -o /dev/null https://api.github.com || { echo "::error::egress probe inconclusive"; exit 1; }\n'
    "if sudo -n -u nobody curl -sS --max-time 5 -o /dev/null https://api.github.com; then exit 1; fi")}
APP_START = {"run": 'sudo -n -u nobody "$JAVA_HOME/bin/java" -jar /tmp/aut/app.jar &'}

OLD_BUILD = {"30-build.yml": {"permissions": {"contents": "write"}, "jobs": {"build": {
    "env": {"GH_TOKEN": "${{ github.token }}"},
    "steps": [
        {"uses": "actions/checkout@v4", "with": {"fetch-depth": 0}},
        {"uses": "actions/setup-java@v4", "with": {"distribution": "temurin", "cache": "maven"}},
        CLAUDE,
        {"run": "git push -u origin \"wi-$ISSUE\"\ngh pr create --head x"},
        {"uses": "actions/upload-artifact@v4", "with": {"name": "run-record"}},
    ]}}}}

NEW = {
    "30-build.yml": {"permissions": {}, "jobs": {
        "authorize": AUTHORIZE,
        "builder": {"needs": ["authorize"], "permissions": {"contents": "read"}, "steps": [
            {"uses": "actions/checkout@v4", "with": {"persist-credentials": False}},
            {"uses": "actions/setup-java@v4", "with": {"distribution": "temurin"}},
            LOAD, CLAUDE, UPLOAD]},
        "builder-record": {"needs": ["builder"], "steps": [TRUSTED_RECORD, UPLOAD]},
        "publish-code": {"uses": policy.PUBLISH_REF, "with": {"client_id": "${{ vars.FACTORY_APP_CLIENT_ID }}"},
                         "secrets": {"FACTORY_APP_PRIVATE_KEY": "${{ secrets.FACTORY_APP_PRIVATE_KEY }}"}}}},
    "40-verify.yml": {"jobs": {
        "build-test": {"steps": [{"uses": "actions/setup-java@v4", "with": {"cache": "maven"}}]},
        "acceptance": {"needs": ["build-test"], "steps": [
            EGRESS, APP_START,
            {"run": "python3 tools/acceptance_run.py run --scope \"$SCOPE\" --log \"$RUNNER_TEMP/private/a.log\""}]},
        "required": {"if": "always()", "needs": ["build-test", "acceptance"], "steps": [
            {"env": {"B": "${{ needs.build-test.result }}", "A": "${{ needs.acceptance.result }}"},
             "run": "for r in \"$B\" \"$A\"; do [ \"$r\" = success ] || exit 1; done"}]}}},
    "45-fix-round.yml": {True: {"workflow_run": {"workflows": ["40 verify"]}}, "jobs": {"next-round": {
        "if": policy.SAME_REPO_HEAD + " &&\n  github.event.workflow_run.conclusion == 'failure'",
        "env": {"BRANCH": "${{ github.event.workflow_run.head_branch }}"},
        "needs": "authorize",
        "steps": [{"run": "[[ \"$BRANCH\" =~ ^wi-([1-9][0-9]*)$ ]] || exit 1\n"
                          "gh workflow run \"30 build\" -R \"$GITHUB_REPOSITORY\" -f issue=\"$issue\""}]},
        "authorize": {**AUTHORIZE, "if": policy.SAME_REPO_HEAD + " && github.event.workflow_run.conclusion == 'failure'"}}},
    "25-dispatch.yml": {"jobs": {"dispatch": {"steps": [
        {"env": {"FACTORY_BOT_LOGIN": "${{ vars.FACTORY_BOT_LOGIN }}"},
         "run": "python3 tools/create_work_items.py --dispatch-queued"}]}}},
    "publish.yml": {"jobs": {"publish": {"permissions": {}, "steps": [
        {"env": {"HAS_KEY": "${{ secrets.FACTORY_APP_PRIVATE_KEY != '' }}"}, "run": "[ \"$HAS_KEY\" = true ] || exit 1"},
        {"id": "app", "uses": "actions/create-github-app-token@" + "a" * 40,
         "with": {"client-id": "${{ inputs.client_id }}", "private-key": "${{ secrets.FACTORY_APP_PRIVATE_KEY }}"}},
        {"uses": "actions/checkout@v4", "with": {"token": APP}},
        {"env": {"GH_TOKEN": APP}, "run": "git push origin HEAD\ngh pr create --head x"},
    ]}}},
}


class PolicyTest(unittest.TestCase):
    def test_compliant_workflows_pass_every_rule(self):
        self.assertEqual(policy.check(NEW), [])

    def test_pre_brief_004_build_job_fails_each_agent_rule(self):
        found = "\n".join(policy.check(OLD_BUILD))
        for expected in ("must set its own permissions", "sets GH_TOKEN", "persist-credentials",
                         "setup-java cache", "cache: maven outside", "git push or gh pr write",
                         "retention-days", "publish.yml is missing"):
            self.assertIn(expected, found)

    def test_publish_without_guard_or_pin_or_with_github_token_fails(self):
        publish = NEW["publish.yml"]["jobs"]["publish"]
        broken = dict(publish, steps=[
            {**publish["steps"][1], "uses": "actions/create-github-app-token@v3"},
            {"uses": "actions/checkout@v4"},
            {"env": {"GH_TOKEN": "${{ github.token }}"}, "run": "git push"},
        ])
        found = "\n".join(policy.check({**NEW, "publish.yml": {"jobs": {"publish": broken}}}))
        for expected in ("not pinned", "fails clearly", "GH_TOKEN is not the App token",
                         "checkout must use the App token", "references github.token"):
            self.assertIn(expected, found)

    def test_callers_may_not_inherit_secrets(self):
        wf = {**NEW, "10-spec.yml": {"jobs": {"publish": {"uses": policy.PUBLISH_REF, "secrets": "inherit",
                                                          "with": {"client_id": "${{ vars.FACTORY_APP_CLIENT_ID }}"}}}}}
        self.assertIn("no secrets: inherit", "\n".join(policy.check(wf)))

    def test_expressions_inside_run_fail_on_any_line(self):
        scripts = [
            'echo "## Feature issue: ${{ github.event.issue.title }}"',
            'set -e\nbranch="${{github.event.workflow_run.head_branch}}"\necho "$branch"',
            "echo hi\ngh issue edit ${{ inputs.issue }} \\\n  --add-label x",
            "python3 x.py --ref ${{ github.head_ref }}",
            'docker push "${{ steps.meta.outputs.image }}"',
        ]
        for script in scripts:
            wf = {"x.yml": {"jobs": {"j": {"steps": [{"env": {"A": "${{ github.event.issue.title }}"}, "run": script}]}}}}
            found = policy.check({**NEW, **wf})
            self.assertEqual(len(found), 1, script)
            self.assertIn("run: contains ${{", found[0])

    def test_pull_request_target_fails_in_every_trigger_form(self):
        for on in ("pull_request_target", ["push", "pull_request_target"], {"pull_request_target": {"types": ["opened"]}}):
            for key in ("on", True):
                found = policy.check({**NEW, "x.yml": {key: on, "jobs": {}}})
                self.assertEqual(found, ["x.yml: pull_request_target runs fork code with the base repo's token and secrets"])

    def test_workflow_run_job_needs_the_same_repo_guard_first_and_alone(self):
        conditions = [
            None,
            "github.event.workflow_run.conclusion == 'failure'",
            "github.event.workflow_run.conclusion == 'failure' && " + policy.SAME_REPO_HEAD,
            policy.SAME_REPO_HEAD + " && x || github.event.workflow_run.event == 'pull_request'",
            "!" + policy.SAME_REPO_HEAD,
        ]
        for cond in conditions:
            job = {"steps": []} if cond is None else {"if": cond, "steps": []}
            found = policy.check({**NEW, "50-review.yml": {True: {"workflow_run": {}}, "jobs": {"review": job}}})
            self.assertEqual(len(found), 1, cond)
            self.assertIn("50-review.yml:review: if: must start with", found[0])
        guarded = {"if": "${{ " + policy.SAME_REPO_HEAD + " && github.event.workflow_run.conclusion == 'success' }}"}
        self.assertEqual(policy.check({**NEW, "50-review.yml": {True: {"workflow_run": {}}, "jobs": {"review": guarded}}}), [])


    def verify_with(self, **jobs):
        return {**NEW, "40-verify.yml": {"jobs": {**NEW["40-verify.yml"]["jobs"], **jobs}}}

    def test_pre_brief_007_acceptance_job_fails_for_each_swallowed_failure(self):
        old = {"needs": "build-test", "steps": [{"run": (
            "java -jar app.jar > /dev/null 2>&1 &\n"
            "for _ in $(seq 1 30); do curl -sf localhost:8080/actuator/health >/dev/null && break; sleep 2; done\n"
            "mvn -B -q -f acceptance/pom.xml test > /dev/null 2>&1 || true")}]}
        found = [f for f in policy.check(self.verify_with(acceptance=old)) if "starts the app" not in f]
        self.assertEqual(len(found), 4, found)
        self.assertTrue(all("swallows a failure" in f for f in found))
        for snippet in ("set +e\nmvn test", "mvn test || :", "mvn test || exit 0"):
            found = policy.check(self.verify_with(acceptance={"steps": [EGRESS, APP_START, {"run": snippet}]}))
            self.assertEqual(len(found), 1, snippet)

    def test_acceptance_job_may_not_continue_on_error_or_upload(self):
        job = {"continue-on-error": True, "steps": [
            {"run": "mvn test", "continue-on-error": True},
            {"uses": "actions/upload-artifact@v4", "with": {"name": "surefire", "retention-days": 1}}]}
        found = "\n".join(policy.check(self.verify_with(acceptance=job)))
        self.assertEqual(found.count("continue-on-error"), 2)
        self.assertIn("uploads an artifact", found)

    def test_required_must_need_and_check_every_job_and_always_run(self):
        req = NEW["40-verify.yml"]["jobs"]["required"]
        self.assertIn("40-verify.yml:required: does not need scope",
                      policy.check(self.verify_with(scope={"steps": []})))
        unchecked = dict(req, steps=[{"run": "true"}])
        found = policy.check(self.verify_with(required=unchecked))
        self.assertEqual(found, ["40-verify.yml:required: does not check needs.acceptance.result",
                                 "40-verify.yml:required: does not check needs.build-test.result"])
        self.assertIn("must run with if: always()", policy.check(self.verify_with(required=dict(req, **{"if": ""})))[0])

    def test_verify_without_acceptance_or_required_fails(self):
        bare = {**NEW, "40-verify.yml": {"jobs": {"build-test": {"steps": []}}}}
        self.assertEqual(policy.check(bare), ["40-verify.yml: no acceptance job", "40-verify.yml: no required job"])

    def build_with(self, **jobs):
        return {**NEW, "30-build.yml": {"jobs": {**NEW["30-build.yml"]["jobs"], **jobs}}}

    def test_every_upload_sets_retention_of_at_most_seven_days(self):
        for w in ({"name": "x"}, {"name": "x", "retention-days": 30}, {"name": "x", "retention-days": "${{ vars.DAYS }}"}):
            found = policy.check(self.verify_with(jar={"steps": [{"uses": "actions/upload-artifact@v4", "with": w}]}))
            self.assertIn("40-verify.yml:jar: upload-artifact must set retention-days of at most 7", found, w)
        for days in (1, 7, "7"):
            ok = {"steps": [{"uses": "actions/upload-artifact@v4", "with": {"name": "x", "retention-days": days}}]}
            self.assertEqual(policy.check(self.build_with(jar=ok)), [], days)

    def test_agent_job_must_need_a_real_authorize_job(self):
        builder = NEW["30-build.yml"]["jobs"]["builder"]
        cases = {
            "needs no authorize": self.build_with(builder={**builder, "needs": ["prepare"]}),
            "missing authorize job": {**NEW, "30-build.yml": {"jobs": {
                k: v for k, v in NEW["30-build.yml"]["jobs"].items() if k != "authorize"}}},
            "authorize runs no check": self.build_with(authorize={"steps": [{"run": "echo ok"}]}),
            "status function skips the check": self.build_with(builder={**builder, "if": "${{ !cancelled() }}"}),
        }
        for case, wf in cases.items():
            found = [v for v in policy.check(wf) if "authorize" in v]
            self.assertTrue(found and all(v.startswith("30-build.yml:builder: ") for v in found), (case, found))
        guarded = {**builder, "if": "${{ !cancelled() && needs.authorize.result == 'success' }}"}
        self.assertEqual(policy.check(self.build_with(builder=guarded)), [])

    def test_tester_loop_job_is_an_agent_job_too(self):
        # Brief 013: the tester is a plain run: step (tools/tester_loop.py), not a uses: action.
        tester_loop = {"needs": "authorize", "permissions": {"contents": "read"}, "steps": [LOAD,
            {"env": {"AZURE_OPENAI_API_KEY": "${{ secrets.AZURE_OPENAI_API_KEY }}"},
             "run": "python3 tools/tester_loop.py"}]}
        self.assertEqual(policy.check(self.build_with(tester=tester_loop)), [])
        found = policy.check(self.build_with(tester={**tester_loop, "needs": "prepare"}))
        self.assertIn("30-build.yml:tester: model job must list authorize in needs", found)

    def test_codex_action_is_rejected_everywhere(self):
        codex = {"needs": "authorize", "permissions": {"contents": "read"}, "steps": [LOAD,
            {"uses": "openai/codex-action@v1", "with": {"codex-args": '["--config","hide_agent_reasoning=true"]'}}]}
        found = policy.check(self.build_with(tester=codex))
        self.assertIn("30-build.yml: tester: step 2 still uses openai/codex-action@, which brief 013 removed", found)

    def test_agent_job_must_not_print_the_transcript_or_trace_the_shell(self):
        base = {"needs": "authorize", "permissions": {"contents": "read"}, "steps": [LOAD,
            {"run": "python3 tools/tester_loop.py"}]}
        self.assertEqual(policy.check(self.build_with(tester=base)), [])
        cats = {**base, "steps": [*base["steps"], {"run": "cat $RUNNER_TEMP/out/tester-transcript.json"}]}
        found = policy.check(self.build_with(tester=cats))
        self.assertIn("30-build.yml:tester: step 3 cats the run-record/transcript file to the log", found)
        traced = {**base, "steps": [{"run": "set -ex\npython3 tools/load_skills.py tester"}, base["steps"][1]]}
        found = policy.check(self.build_with(tester=traced))
        self.assertIn("30-build.yml:tester: step 1 enables shell tracing, which echoes commands to the log", found)

    def test_a_job_holding_a_model_key_needs_authorize(self):
        guard = policy.SAME_REPO_HEAD + " && github.event.workflow_run.conclusion == 'success'"
        review = {"if": guard, "permissions": {"contents": "read"}, "steps": [
            {"env": {"AZURE_OPENAI_API_KEY": "${{ secrets.AZURE_OPENAI_API_KEY }}"}, "run": "python3 tools/review.py"}]}
        wf = {True: {"workflow_run": {"workflows": ["40 verify"]}}, "jobs": {"review": review}}
        found = policy.check({**NEW, "50-review.yml": wf})
        self.assertIn("50-review.yml:review: no authorize job that runs tools/authorize.py", found)
        self.assertIn("50-review.yml:review: model job must list authorize in needs", found)
        preflight = {"env": {"AZURE_OPENAI_API_KEY": "${{ secrets.AZURE_OPENAI_API_KEY != '' && 'set' || '' }}"},
                     "run": "python3 tools/check_secrets_env.py --role review"}
        gated = {True: wf[True], "jobs": {
            "authorize": {**AUTHORIZE, "if": guard, "steps": AUTHORIZE["steps"] + [preflight]},
            "review": {**review, "needs": "authorize"}}}
        self.assertEqual(policy.check({**NEW, "50-review.yml": gated}), [])

    def test_any_secret_but_the_factory_app_and_acceptance_tokens_counts_as_a_model_key(self):
        guard = policy.SAME_REPO_HEAD + " && github.event.workflow_run.conclusion == 'success'"
        for name in ("RETIRED_MODEL_API_KEY", "SOME_NEW_PROVIDER_KEY"):
            job = {"if": guard, "permissions": {"contents": "read"}, "steps": [
                {"env": {"K": "${{ secrets.%s }}" % name}, "run": "python3 tools/review.py"}]}
            wf = {True: {"workflow_run": {"workflows": ["40 verify"]}}, "jobs": {"review": job}}
            self.assertIn("50-review.yml:review: model job must list authorize in needs",
                          policy.check({**NEW, "50-review.yml": wf}), msg=name)
        for name in sorted(policy.NON_MODEL_SECRETS):
            self.assertFalse(policy.spends_model_budget({"steps": [{"env": {"K": "${{ secrets.%s }}" % name}}]}), msg=name)

    def test_agent_job_reads_secret_values_only_on_the_agent_step(self):
        builder = NEW["30-build.yml"]["jobs"]["builder"]
        keyed = {**CLAUDE, "with": {**CLAUDE["with"], "claude_code_oauth_token": "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"}}
        presence = {"env": {"CLAUDE_CODE_OAUTH_TOKEN": "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN != '' && 'set' || '' }}"},
                    "run": "python3 tools/check_secrets_env.py --role builder"}
        ok = {**builder, "steps": [presence] + [keyed if s is CLAUDE else s for s in builder["steps"]]}
        self.assertEqual(policy.check(self.build_with(builder=ok)), [])
        after = {**ok, "steps": ok["steps"] + [{"env": {"K": "${{ secrets.AZURE_OPENAI_API_KEY }}"}, "run": "mvn test"}]}
        self.assertEqual(policy.check(self.build_with(builder=after)),
                         ["30-build.yml:builder: step 7 reads a secret value outside the agent step"])
        job_env = {**ok, "env": {"K": "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"}}
        self.assertEqual(policy.check(self.build_with(builder=job_env)),
                         ["30-build.yml:builder: job env reads a secret; put it on the agent step"])

    def test_a_secret_value_is_allowed_on_a_step_before_the_agent_step(self):
        # Cowork A2: a step that writes a model key to a file and exits before the agent step
        # starts never shares a live process with it, so it's in the trusted zone, not the agent's.
        write_key = {"env": {"K": "${{ secrets.AZURE_OPENAI_API_KEY }}"}, "run": "printf '%s' \"$K\" > key"}
        tester = {"needs": "authorize", "permissions": {"contents": "read"}, "steps": [
            LOAD, write_key, {"run": "python3 tools/tester_loop.py"}]}
        self.assertEqual(policy.check(self.build_with(tester=tester)), [])
        after = {**tester, "steps": tester["steps"] + [write_key]}
        self.assertEqual(policy.check(self.build_with(tester=after)),
                         ["30-build.yml:tester: step 4 reads a secret value outside the agent step"])

    def test_tools_after_agent_code_come_from_workflow_sha(self):
        builder = NEW["30-build.yml"]["jobs"]["builder"]
        in_job = {**builder, "steps": builder["steps"] + [{"run": "python3 tools/run_record.py --role builder"}]}
        self.assertIn("30-build.yml:builder: names tools/ after the agent step; run tools in a later job "
                      "from git show \"$WORKFLOW_SHA:tools/...\"", policy.check(self.build_with(builder=in_job)))
        git_show_in_agent_job = {**builder, "steps": builder["steps"] + [TRUSTED_RECORD]}
        self.assertEqual(policy.check(self.build_with(builder=git_show_in_agent_job)),
                         ["30-build.yml:builder: names tools/ after the agent step; run tools in a later job "
                          "from git show \"$WORKFLOW_SHA:tools/...\""])
        before_agent = {**builder, "steps": [{"run": "python3 tools/build_prompt.py builder x"}] + builder["steps"]}
        self.assertEqual(policy.check(self.build_with(builder=before_agent)), [])
        for run in ("python3 tools/run_record.py", "cp tools/publish.py \"$RUNNER_TEMP/trusted/\"",
                    'git show "$BASE_SHA:tools/run_record.py" > r.py',
                    'cp -r tools "$X"', "cp -r ./tools/ x", 'cp -a "tools/." x', "rsync -a tools x",
                    "python tools/publish.py", "bash ./tools/x.sh", "cd tools && python3 run_record.py",
                    'git show "$WORKFLOW_SHA:tools/run_record.py" > tools/run_record.py',
                    'git show "${WORKFLOW_SHA}:tools/run_record.py" > r.py'):
            with self.subTest(run=run):
                record = {"needs": ["builder"], "steps": [{**TRUSTED_RECORD, "run": run}, UPLOAD]}
                found = policy.check(self.build_with(**{"builder-record": record}))
                self.assertEqual(found, ["30-build.yml:builder-record: reads tools/ other than via git show \"$WORKFLOW_SHA:tools/...\""])
        trusted = {"needs": ["builder"], "steps": [{**TRUSTED_RECORD, "run": (
            'mkdir -p "$RUNNER_TEMP/trusted"\n'
            'for f in publish.py check_paths.py; do git show "$WORKFLOW_SHA:tools/$f" > "$RUNNER_TEMP/trusted/$f"; done\n'
            'python "$RUNNER_TEMP/trusted/publish.py" --trusted "$RUNNER_TEMP/trusted" --tool-dir my-tools')}, UPLOAD]}
        self.assertEqual(policy.check(self.build_with(**{"builder-record": trusted})), [])
        unpinned = {"needs": ["builder"], "steps": [{**TRUSTED_RECORD, "env": {"WORKFLOW_SHA": "${{ github.sha }}"}}]}
        self.assertEqual(policy.check(self.build_with(**{"builder-record": unpinned})),
                         ["30-build.yml:builder-record: WORKFLOW_SHA must be ${{ github.workflow_sha }}"])

    def test_publish_never_copies_tools_from_the_branch(self):
        publish = NEW["publish.yml"]["jobs"]["publish"]
        copied = dict(publish, steps=[{"run": "mkdir t && cp tools/publish.py tools/check_paths.py t/"}] + publish["steps"])
        found = policy.check({**NEW, "publish.yml": {"jobs": {"publish": copied}}})
        self.assertIn("publish.yml:publish: reads tools/ other than via git show \"$WORKFLOW_SHA:tools/...\"", found)

    def test_agent_transcripts_stay_off_logs(self):
        builder = NEW["30-build.yml"]["jobs"]["builder"]
        def with_claude(step):
            return self.build_with(builder={**builder, "steps": [step if s is CLAUDE else s for s in builder["steps"]]})
        loud = [
            {**CLAUDE, "with": {**CLAUDE["with"], "show_full_output": True}},
            {**CLAUDE, "with": {**CLAUDE["with"], "show_full_output": "true"}},
            {**CLAUDE, "with": {**CLAUDE["with"], "display_report": "true"}},
            {**CLAUDE, "env": {}},
            {**CLAUDE, "env": {"ACTIONS_STEP_DEBUG": "${{ vars.DEBUG }}"}},
        ]
        for step in loud:
            found = policy.check(with_claude(step))
            self.assertEqual(len(found), 1, step)
            self.assertIn("30-build.yml:builder: agent output", found[0])

    def test_no_workflow_installs_a_plugin(self):
        builder = NEW["30-build.yml"]["jobs"]["builder"]
        pstack = {**CLAUDE, "with": {**CLAUDE["with"], "plugins": "pstack@cursor-plugins",
                                     "plugin_marketplaces": "${{ vars.PSTACK_MARKETPLACE }}"}}
        found = policy.check(self.build_with(builder={**builder, "steps": [pstack if s is CLAUDE else s for s in builder["steps"]]}))
        self.assertEqual(found, ["30-build.yml:builder: step 4 sets `plugins:`; load pinned skills with tools/load_skills.py",
                                 "30-build.yml:builder: step 4 sets `plugin_marketplaces:`; load pinned skills with tools/load_skills.py"])
        caller = {"uses": "./.github/workflows/agent.yml", "with": {"plugins": "x"}}
        self.assertIn("30-build.yml:caller: job sets `plugins:`; load pinned skills with tools/load_skills.py",
                      policy.check(self.build_with(caller=caller)))

    def test_agent_step_must_follow_load_skills(self):
        builder = NEW["30-build.yml"]["jobs"]["builder"]
        for order in ([s for s in builder["steps"] if s is not LOAD], [CLAUDE, LOAD, UPLOAD]):
            self.assertIn("30-build.yml:builder: agent step runs before tools/load_skills.py",
                          policy.check(self.build_with(builder={**builder, "steps": order})))

    def test_work_item_numbers_have_no_leading_zeros(self):
        def with_run(run):
            job = {"steps": [{"run": run}]}
            return policy.check({**NEW, "20-x.yml": {"jobs": {"j": job}}})
        for run in ('[[ "$BRANCH" =~ ^wi-([0-9]+)$ ]]', '[[ "$B" =~ wi-[0-9]+ ]]',
                    '[[ "$ISSUE" =~ ^[0-9]+$ ]] || exit 1'):
            found = with_run(run)
            self.assertEqual(len(found), 1, run)
            self.assertTrue(found[0].startswith("20-x.yml:j: "), found)
        for run in ('[[ "$BRANCH" =~ ^wi-([1-9][0-9]*)$ ]]', '[[ "$ISSUE" =~ ^[1-9][0-9]*$ ]]', 'echo "wi-$ISSUE"'):
            self.assertEqual(with_run(run), [], run)

    def test_fix_round_without_authorize_fails(self):
        fix = NEW["45-fix-round.yml"]
        next_round = fix["jobs"]["next-round"]
        cases = {
            "no authorize job": {"jobs": {"next-round": next_round}},
            "does not need it": {"jobs": {**fix["jobs"], "next-round": {k: v for k, v in next_round.items() if k != "needs"}}},
            "authorize runs no check": {"jobs": {**fix["jobs"], "authorize": {**fix["jobs"]["authorize"], "steps": [{"run": "true"}]}}},
        }
        for case, jobs in cases.items():
            found = policy.check({**NEW, "45-fix-round.yml": {**fix, **jobs}})
            self.assertIn("45-fix-round.yml:next-round: dispatches 30 build without needing an authorize job "
                          "that runs tools/authorize.py", found, case)

    def test_app_under_test_starts_only_after_its_egress_is_blocked_and_probed(self):
        acc = NEW["40-verify.yml"]["jobs"]["acceptance"]
        rest = [s for s in acc["steps"] if s not in (EGRESS, APP_START)]
        def verify_with(steps):
            jobs = {**NEW["40-verify.yml"]["jobs"], "acceptance": {**acc, "steps": steps}}
            return [v for v in policy.check({**NEW, "40-verify.yml": {"jobs": jobs}}) if "egress" in v or "starts the app" in v]
        v4_only = {"run": EGRESS["run"].replace("sudo -n ip6tables", "# ip6tables")}
        no_probe = {"run": EGRESS["run"].split("\nif ")[0]}
        no_positive_control = {"run": "\n".join(l for l in EGRESS["run"].splitlines() if not l.startswith("curl "))}
        other_host = {"run": EGRESS["run"].replace("nobody curl -sS --max-time 5 -o /dev/null https://api.github.com",
                                                   "nobody curl -sS --max-time 5 -o /dev/null https://example.com")}
        for steps in ([APP_START] + rest, [APP_START, EGRESS] + rest, [v4_only, APP_START] + rest,
                      [no_probe, APP_START] + rest, [no_positive_control, APP_START] + rest,
                      [other_host, APP_START] + rest):
            self.assertEqual(len(verify_with(steps)), 1, steps)
        self.assertEqual(verify_with([EGRESS] + rest), ['40-verify.yml:acceptance: no step starts the app with '
                                                        'sudo -n -u nobody "$JAVA_HOME/bin/java"'])
        self.assertEqual(verify_with(acc["steps"]), [])

    def test_gitleaks_runs_only_from_the_pinned_image(self):
        pinned = {"env": {"GITLEAKS_IMAGE": "zricethezav/gitleaks:v8.24.0@sha256:" + "2b" * 32},
                  "run": 'docker run --rm --network none "$GITLEAKS_IMAGE" git /repo --log-opts="$BASE_SHA..$HEAD_SHA"'}
        def check_static(*steps):
            wf = {**NEW, "40-verify.yml": {"jobs": {**NEW["40-verify.yml"]["jobs"], "static": {"steps": list(steps)}}}}
            return [v for v in policy.check(wf) if "gitleaks" in v]
        self.assertEqual(check_static(pinned), [])
        by_tag = {"uses": "gitleaks/gitleaks-action@v2", "env": {"GITHUB_TOKEN": "${{ github.token }}"}}
        self.assertEqual(check_static(by_tag), [
            "40-verify.yml:static: gitleaks action by tag; run the image pinned by digest instead",
            "40-verify.yml:static: no secret scan with the pinned gitleaks image"])
        unpinned = {**pinned, "env": {"GITLEAKS_IMAGE": "zricethezav/gitleaks:v8.24.0"}}
        self.assertIn("40-verify.yml:static: gitleaks image zricethezav/gitleaks:v8.24.0 is not pinned by sha256 digest",
                      check_static(unpinned))

    def test_semgrep_runs_from_the_pinned_image_offline_with_pinned_local_rules(self):
        scan = {"env": {"SEMGREP_IMAGE": "semgrep/semgrep:1.182.1@sha256:" + "45" * 32,
                        "SEMGREP_RULES_SHA256": "80" * 32},
                "run": ('curl -fsSL -o "$RUNNER_TEMP/semgrep/java.yml" "$SEMGREP_RULES_URL"\n'
                        'echo "$SEMGREP_RULES_SHA256  $RUNNER_TEMP/semgrep/java.yml" | sha256sum -c -\n'
                        'docker run --rm --network none -v "$RUNNER_TEMP/semgrep:/rules:ro" "$SEMGREP_IMAGE" \\\n'
                        '  semgrep scan --metrics off --config /rules/java.yml --error app/src/main')}
        def check_static(*steps):
            wf = {**NEW, "40-verify.yml": {"jobs": {**NEW["40-verify.yml"]["jobs"], "static": {"steps": list(steps)}}}}
            return [v for v in policy.check(wf) if "emgrep" in v or "pipx" in v]
        self.assertEqual(check_static(scan), [])
        self.assertEqual(check_static({"run": "echo no scanner"}), ["40-verify.yml:static: no Semgrep scan"])
        broken = {
            "pipx run semgrep scan --config p/java": ["`pipx` installs an unpinned tool", "pinned image",
                                                      "local .yml files only", "pinned sha256"],
            "unpinned image": ["semgrep/semgrep:1.182.1 is not pinned by sha256 digest"],
            "--network none": ["pinned image with docker run, --network none, --metrics off"],
            "--metrics off": ["pinned image with docker run, --network none, --metrics off"],
            "/rules/java.yml": ["local .yml files only, got ['p/java']"],
            "--config=https://x/java.yml": ["local .yml files only"],
            "sha256sum -c -": ["pinned sha256"],
        }
        for case, expected in broken.items():
            with self.subTest(case=case):
                if case.startswith("pipx"):
                    step = {"run": case}
                elif case == "unpinned image":
                    step = {**scan, "env": {**scan["env"], "SEMGREP_IMAGE": "semgrep/semgrep:1.182.1"}}
                elif case == "--config=https://x/java.yml":
                    step = {**scan, "run": scan["run"].replace("--config /rules/java.yml", case)}
                else:
                    step = {**scan, "run": scan["run"].replace(case, "p/java" if case.endswith(".yml") else "")}
                found = check_static(step)
                self.assertEqual(len(found), len(expected), found)
                for want, got in zip(expected, found):
                    self.assertIn(want, got)

    def test_no_unpinned_tool_runner_anywhere(self):
        for run in ("pipx run semgrep --version", "pipx install ruff", "uvx ruff check", "uv tool run ruff"):
            with self.subTest(run=run):
                found = policy.check({**NEW, "20-x.yml": {"jobs": {"j": {"steps": [{"run": run}]}}}})
                self.assertEqual(len(found), 1, found)
                self.assertIn("installs an unpinned tool", found[0])

    def test_every_pip_install_is_hash_pinned(self):
        def check_run(run):
            return policy.check({**NEW, "20-x.yml": {"jobs": {"j": {"steps": [{"run": run}]}}}})
        for run in ("pip install pyyaml", "pip install -q -r tools/requirements.txt",
                    "pip install --require-hashes -r tools/requirements.txt",
                    "pip install -q --require-hashes --only-binary=:all: -r r.txt litellm",
                    "python3 -m pip install --upgrade pip", "echo ok && pip3 install requests",
                    "pip install \\\n  -r tools/requirements.txt"):
            found = check_run(run)
            self.assertEqual(len(found), 1, run)
            self.assertIn("must be pip install --require-hashes", found[0])
        for run in ("pip install -q --require-hashes --only-binary=:all: -r tools/requirements.txt && python3 x.py",
                    'pip install --require-hashes --only-binary=:all: -r "$RUNNER_TEMP/trusted/requirements.txt"'):
            self.assertEqual(check_run(run), [], run)

    def test_dispatch_queued_must_know_the_bot_login(self):
        step = {"run": "python3 tools/create_work_items.py --dispatch-queued"}
        found = policy.check({**NEW, "25-dispatch.yml": {"jobs": {"dispatch": {"steps": [step]}}}})
        self.assertEqual(found, ["25-dispatch.yml:dispatch: create_work_items.py --dispatch-queued needs env "
                                 "FACTORY_BOT_LOGIN: ${{ vars.FACTORY_BOT_LOGIN }} to judge labelers"])


if __name__ == "__main__":
    unittest.main()
