"""Review decisions without network or litellm: tiers, consensus, verification, dedupe, retries, rendering."""
import contextlib, functools, io, json, os, pathlib, shutil, sys, tempfile, types, unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import review  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None

DEDUPE_PROMPT = (ROOT / review.DEDUPE_PROMPT_FILE).read_text(encoding="utf-8")

FAMILIES = {
    "anthropic": {"model": "claude-opus-5-5", "via": "claude-code-action", "secret": "CLAUDE_CODE_OAUTH_TOKEN"},
    "openai": {"model": "azure/gpt-5", "secret": "AZURE_OPENAI_API_KEY", "api_base_env": "AZURE_OPENAI_ENDPOINT",
               "api_version": "2024-10-21"},
    "xai": {"model": "openai/grok-4.7", "secret": "AZURE_OPENAI_API_KEY", "api_base_env": "AZURE_AI_V1_ENDPOINT",
            "timeout_s": 480},
    "deepseek": {"model": "openai/DeepSeek-V4.1-Flash-1017", "secret": "AZURE_OPENAI_API_KEY",
                 "api_base_env": "AZURE_AI_V1_ENDPOINT", "timeout_s": 180},
}
MODELS = {name: f["model"] for name, f in FAMILIES.items()}
THREE = ["openai", "xai", "deepseek"]
AMBER = {"reviewers": THREE}
RED = {"reviewers": THREE, "human_review": True}
ALL = {"AZURE_OPENAI_API_KEY": "k", "AZURE_OPENAI_ENDPOINT": "https://x",
       "AZURE_AI_V1_ENDPOINT": "https://x/openai/v1", "CLAUDE_CODE_OAUTH_TOKEN": "t"}


def finding(file="A.java", line=10, category="bug", problem="p"):
    return {"file": file, "line_start": line, "line_end": line, "category": category, "severity": "major",
            "problem": problem, "fix": "f", "evidence": "secret_code_line()"}


def answering(fn):
    """Adapt a test double that returns a dict to ask's (data, (tokens_in, tokens_out)) contract."""
    def ask(family, system, user):
        return fn(family, system, user), (100, 20)
    return ask


def down(family):
    raise review.InfraFailure(f"RateLimitError from {MODELS[family]} after 4 attempts")


class Status(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class RateLimitError(Exception):
    pass


class TierOfTest(unittest.TestCase):
    """Audit round 1, P1 (unlabelled must not default to amber) and PR #42's own review,
    #3 (a label alone is never trusted) and #4/#13 (renames and malformed labels)."""

    def files_gh(self, files):
        """files: a list of (filename, previous_filename_or_None), matching what the real
        `--jq ".[] | .filename, (.previous_filename // empty)"` prints: one bare path per line,
        and nothing (not even a blank line) for a missing previous_filename."""
        def gh(*a, check=True):
            self.assertEqual(a[:3], ("api", "repos/o/r/pulls/5/files", "--paginate"))
            lines = [p for f, prev in files for p in (f, prev) if p is not None]
            return "\n".join(lines) + ("\n" if lines else "")
        return gh

    def test_a_green_label_with_no_red_paths_stays_green(self):
        pr = {"number": 5, "labels": [{"name": "tier:green"}]}
        with mock.patch.object(review, "gh", self.files_gh([("docs/index.md", None)])):
            self.assertEqual(review.tier_of(pr, "o/r"), "green")

    def test_a_green_label_on_a_red_floor_path_is_overridden_by_the_computed_tier(self):
        pr = {"number": 5, "labels": [{"name": "tier:green"}]}
        with mock.patch.object(review, "gh", self.files_gh([("tools/review.py", None)])):
            self.assertEqual(review.tier_of(pr, "o/r"), "red")

    def test_an_unlabelled_pr_touching_a_red_floor_path_computes_red(self):
        pr = {"number": 5, "labels": []}
        with mock.patch.object(review, "gh", self.files_gh(
                [("tools/review.py", None), ("app/src/main/Foo.java", None)])):
            self.assertEqual(review.tier_of(pr, "o/r"), "red")

    def test_an_unlabelled_pr_touching_only_app_code_is_not_forced_red(self):
        pr = {"number": 5, "labels": []}
        with mock.patch.object(review, "gh", self.files_gh([("app/src/main/Foo.java", None)])):
            self.assertIn(review.tier_of(pr, "o/r"), ("green", "amber"))

    def test_a_rename_out_of_a_red_floor_path_is_still_scored_red(self):
        pr = {"number": 5, "labels": []}
        with mock.patch.object(review, "gh", self.files_gh([("app/src/main/Foo.java", "tools/Foo.java")])):
            self.assertEqual(review.tier_of(pr, "o/r"), "red")

    def test_a_failure_to_compute_the_tier_fails_closed_to_red_not_amber(self):
        pr = {"number": 5, "labels": []}
        with mock.patch.object(review, "gh", mock.Mock(side_effect=RuntimeError("gh unavailable"))):
            self.assertEqual(review.tier_of(pr, "o/r"), "red")

    def test_an_empty_tier_label_value_is_not_trusted(self):
        pr = {"number": 5, "labels": [{"name": "tier:"}]}
        with mock.patch.object(review, "gh", self.files_gh([("app/src/main/Foo.java", None)])):
            self.assertIn(review.tier_of(pr, "o/r"), ("green", "amber"))

    def test_two_tier_labels_are_not_trusted_either(self):
        pr = {"number": 5, "labels": [{"name": "tier:green"}, {"name": "tier:red"}]}
        with mock.patch.object(review, "gh", self.files_gh([("app/src/main/Foo.java", None)])):
            self.assertIn(review.tier_of(pr, "o/r"), ("green", "amber"))


class PlanTest(unittest.TestCase):
    def test_red_always_needs_a_human_even_with_every_family(self):
        plan = review.plan_review(RED, review.available_families(FAMILIES, ALL))
        self.assertEqual(plan.reviewers, ("openai", "xai", "deepseek"))
        self.assertEqual(review.labels_for(plan), [review.HUMAN_REVIEW])

    def test_amber_with_every_family_needs_no_human(self):
        plan = review.plan_review(AMBER, review.available_families(FAMILIES, ALL))
        self.assertEqual((plan.reviewers, review.labels_for(plan)), (("openai", "xai", "deepseek"), []))

    def test_amber_without_the_v1_endpoint_runs_gpt5_alone_and_hands_the_pr_to_a_human(self):
        plan = review.plan_review(AMBER, review.available_families(FAMILIES, dict(ALL, AZURE_AI_V1_ENDPOINT="")))
        self.assertEqual((plan.reviewers, plan.missing, plan.wanted), (("openai",), ("xai", "deepseek"), 3))
        self.assertEqual(review.labels_for(plan), [review.HUMAN_REVIEW])

    def test_azure_families_need_key_and_their_own_endpoint_and_claude_is_never_called_directly(self):
        self.assertEqual(review.available_families(FAMILIES, {"AZURE_OPENAI_API_KEY": "k"}), set())
        no_v1 = dict(ALL, AZURE_AI_V1_ENDPOINT="")
        self.assertEqual(review.available_families(FAMILIES, no_v1), {"openai"})
        self.assertEqual(review.available_families(FAMILIES, ALL), {"openai", "xai", "deepseek"})

    def test_azure_calls_carry_their_endpoint_and_gpt5_its_pinned_api_version(self):
        self.assertEqual(review.completion_args(FAMILIES["openai"], ALL),
                         {"model": "azure/gpt-5", "api_key": "k", "api_base": "https://x", "api_version": "2024-10-21",
                          "timeout": 180})
        self.assertEqual(review.completion_args(FAMILIES["xai"], ALL),
                         {"model": "openai/grok-4.7", "api_key": "k", "api_base": "https://x/openai/v1", "timeout": 480})
        self.assertEqual(review.completion_args(FAMILIES["deepseek"], ALL),
                         {"model": "openai/DeepSeek-V4.1-Flash-1017", "api_key": "k", "api_base": "https://x/openai/v1",
                          "timeout": 180})

    def test_a_timeout_that_is_not_a_positive_int_up_to_900_seconds_is_refused(self):
        for bad in (0, -1, 901, 180.5, "480", True, None):
            with self.assertRaisesRegex(ValueError, "timeout_s", msg=bad):
                review.completion_args(dict(FAMILIES["deepseek"], timeout_s=bad), ALL)
        self.assertEqual(review.completion_args(dict(FAMILIES["deepseek"], timeout_s=900), ALL)["timeout"], 900)

    def test_placeholder_or_preview_model_is_refused(self):
        for model in ("openai/<pin: x>", "openai/DeepSeek-V4-Flash-preview"):
            with self.assertRaises(ValueError):
                review.completion_args({"model": model, "secret": "G"}, {"G": "g"})

    @unittest.skipIf(yaml is None, "pyyaml not installed")
    def test_the_models_file_routes_three_azure_families_to_amber_and_red_with_one_key(self):
        cfg = yaml.safe_load((ROOT / "factory/models.yaml").read_text(encoding="utf-8"))
        self.assertEqual(set(cfg["families"]), {"anthropic", "openai", "xai", "deepseek"})
        for tier in ("amber", "red"):
            self.assertEqual(cfg["review"][tier]["reviewers"], THREE)
        self.assertTrue(cfg["review"]["red"]["human_review"])
        self.assertEqual(cfg["review"]["merge_model"], "openai")
        self.assertNotIn(cfg["roles"]["builder"], THREE)
        self.assertEqual(review.available_families(cfg["families"], ALL), set(THREE))
        self.assertEqual({cfg["families"][f]["secret"] for f in THREE}, {"AZURE_OPENAI_API_KEY"})
        self.assertEqual({f: review.completion_args(cfg["families"][f], ALL)["timeout"] for f in THREE},
                         {"openai": 180, "xai": 480, "deepseek": 180})
        self.assertEqual(review.completion_args(cfg["families"]["deepseek"], ALL)["api_base"], ALL["AZURE_AI_V1_ENDPOINT"])

    def test_a_verifier_is_never_the_family_that_raised_the_finding(self):
        for source in THREE:
            self.assertNotIn(source, review.verifiers_for(source, THREE))
        self.assertEqual(review.verifiers_for("deepseek", THREE)[0], "openai")
        self.assertEqual(review.verifiers_for("openai", ["openai"]), [])


class FindingsTest(unittest.TestCase):
    def test_dedupe_groups_and_keeps_every_source_without_adding_votes(self):
        fs = [dict(finding(), id=1, sources=["deepseek"], agreement=1, severity="blocker"),
              dict(finding(line=40), id=2, sources=["openai"], agreement=1, verdict="confirmed", verifier="xai",
                   severity="minor"),
              dict(finding("B.java"), id=3, sources=["deepseek"], agreement=1, verdict="rejected")]
        out = review.dedupe(fs, [[0, 1], [2]])
        self.assertEqual([(f["file"], f["sources"], f["also_raised_by"], f["agreement"], f["severity"], f["ids"])
                          for f in out],
                         [("A.java", ["openai"], ["deepseek"], 1, "blocker", [1, 2]),
                          ("B.java", ["deepseek"], [], 1, "major", [3])])
        self.assertEqual([review.section(f) for f in out], ["verified", "low"])
        body = "\n".join(review.render_finding(out[0], 3))
        self.assertIn("**#1, #2 · blocker · `A.java:40`", body)
        self.assertIn("Agreement: 1/3: openai; also raised as a duplicate by deepseek", body)

    def test_dedupe_that_is_not_a_partition_is_an_infra_failure(self):
        fs = [dict(finding(), sources=["deepseek"], agreement=1), dict(finding("B.java"), sources=["openai"], agreement=1)]
        for groups in ([[0]], [[0], [1], [1]], [[0], []], None, {"0": 1}, [["0"], [1]], [[0, 0], [1]], [[0], [1], [2]]):
            with self.assertRaisesRegex(review.InfraFailure, "not a partition", msg=groups):
                review.dedupe(fs, groups)

    def test_dedupe_ignores_a_group_that_spans_files(self):
        fs = [dict(finding(), sources=["deepseek"], agreement=1), dict(finding("B.java"), sources=["openai"], agreement=1)]
        self.assertIs(review.dedupe(fs, [[0, 1]]), fs)


class BackoffTest(unittest.TestCase):
    def test_rate_limit_retries_with_exponential_backoff(self):
        calls, delays = [], []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise Status(429)
            return "ok"
        self.assertEqual(review.with_backoff(flaky, "azure/gpt-5", sleep=delays.append), "ok")
        self.assertEqual(delays, [8.0, 16.0])

    def test_retry_after_is_respected_and_capped(self):
        class Limited(Exception):
            def __init__(self, after):
                super().__init__("429")
                self.status_code = 429
                self.response = type("R", (), {"headers": {"retry-after": after}})()
        for after, expected in (("30", 30.0), ("2", 8.0), ("3600", review.MAX_RETRY_AFTER_S), ("soon", 8.0)):
            calls, delays = [], []

            def flaky(a=after):
                calls.append(1)
                if len(calls) < 2:
                    raise Limited(a)
                return "ok"
            self.assertEqual(review.with_backoff(flaky, "openai/DeepSeek-V4.1-Flash-1017", sleep=delays.append), "ok")
            self.assertEqual(delays, [expected], after)

    def test_exhausted_retries_are_an_infra_failure_not_a_pass(self):
        for exc in (Status(429), Status(503), RateLimitError("quota")):
            delays = []
            with self.assertRaisesRegex(review.InfraFailure, f"^{type(exc).__name__} from openai/DeepSeek-V4.1-Flash-1017 after 4 attempts$"):
                review.with_backoff(lambda e=exc: (_ for _ in ()).throw(e), "openai/DeepSeek-V4.1-Flash-1017", sleep=delays.append)
            self.assertEqual(delays, [8.0, 16.0, 32.0])

    def test_a_timeout_is_retried_once_and_named(self):
        for exc in (TimeoutError(), type("Timeout", (Exception,), {})(), type("APITimeoutError", (Exception,), {})()):
            delays = []
            with self.assertRaisesRegex(review.InfraFailure, f"^{type(exc).__name__} from openai/grok-4.7 after 2 attempts$"):
                review.with_backoff(lambda e=exc: (_ for _ in ()).throw(e), "openai/grok-4.7", sleep=delays.append)
            self.assertEqual(delays, [8.0])

    def test_a_timeout_after_rate_limits_ends_at_the_second_timeout_and_counts_every_attempt(self):
        errors, delays = iter([TimeoutError(), Status(429), TimeoutError()]), []
        with self.assertRaisesRegex(review.InfraFailure, "^TimeoutError from openai/grok-4.7 after 3 attempts$"):
            review.with_backoff(lambda: (_ for _ in ()).throw(next(errors)), "openai/grok-4.7", sleep=delays.append)
        self.assertEqual(delays, [8.0, 16.0])

    def test_non_transient_errors_fail_at_once(self):
        delays = []
        with self.assertRaisesRegex(review.InfraFailure, r"^Status from azure/gpt-5 \(not retryable\)$"):
            review.with_backoff(lambda: (_ for _ in ()).throw(Status(401)), "azure/gpt-5", sleep=delays.append)
        self.assertEqual(delays, [])

    def test_text_without_json_parses_to_none(self):
        self.assertIsNone(review.parse_json_object("I cannot help"))
        self.assertEqual(review.parse_json_object('sure: {"findings": []}'), {"findings": []})


class ConsensusTest(unittest.TestCase):
    """One scenario per brief-018 case: 3/3, 2/3, 1/3 confirmed, 1/3 rejected, one and two reviewers down."""

    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(ROOT)
        self.asked = []

    def tearDown(self):
        os.chdir(self.cwd)

    def run_review(self, raised, verdicts=None, failing=(), tier=AMBER, merger=None, groups=None):
        """raised: family -> findings. verdicts: verifier family -> verdict. failing: families that are down."""
        plan = review.plan_review(tier, set(THREE))

        def ask(family, system, user):
            self.asked.append((family, "verify" if "## Finding" in user else "dedupe" if system == DEDUPE_PROMPT else "review"))
            if family in failing:
                down(family)
            if system == DEDUPE_PROMPT:
                return {"groups": groups}
            if "## Finding" in user:
                return {"verdict": (verdicts or {}).get(family, "confirmed"), "reason": f"{family} read the lines"}
            return {"findings": raised.get(family, [])}
        result = review.review(plan, merger, "diff", "", answering(ask), MODELS)
        return plan, result

    def sections(self, result):
        return [(review.section(f), f["agreement"], f["sources"]) for f in result.findings]

    def test_three_of_three_is_strong_and_needs_no_verifier(self):
        plan, result = self.run_review({f: [finding(line=10 + i)] for i, f in enumerate(THREE)})
        self.assertEqual(self.sections(result), [("strong", 3, sorted(THREE))])
        self.assertNotIn("verify", [kind for _, kind in self.asked])
        body = review.render("amber", plan, result, "a" * 40)
        self.assertIn("Agreement: 3/3: deepseek, openai, xai", body)
        self.assertEqual(review.labels_for(plan, result), [])

    def test_two_of_three_is_strong(self):
        plan, result = self.run_review({"deepseek": [finding()], "xai": [finding(line=12)], "openai": []})
        self.assertEqual(self.sections(result), [("strong", 2, ["deepseek", "xai"])])
        self.assertIn("Agreement: 2/3: deepseek, xai", review.render("amber", plan, result, "a" * 40))

    def test_one_of_three_confirmed_by_another_family_is_kept_as_verified(self):
        plan, result = self.run_review({"deepseek": [finding()]})
        self.assertEqual(self.sections(result), [("verified", 1, ["deepseek"])])
        self.assertEqual([a for a in self.asked if a[1] == "verify"], [("openai", "verify")])
        body = review.render("amber", plan, result, "a" * 40)
        verified = body.split("#### Verified")[1].split("<details>")[0]
        self.assertIn("Verifier: openai confirmed: openai read the lines", verified)

    def test_one_of_three_rejected_is_listed_under_low_confidence_with_its_reason(self):
        plan, result = self.run_review({"openai": [finding(problem="null deref")]}, verdicts={"xai": "rejected"})
        self.assertEqual(self.sections(result), [("low", 1, ["openai"])])
        body = review.render("amber", plan, result, "a" * 40)
        low = body.split("<details>")[1]
        self.assertIn("null deref", low)
        self.assertIn("Agreement: 1/3: openai", low)
        self.assertIn("Verifier: xai rejected: xai read the lines", low)
        self.assertNotIn("null deref", body.split("<details>")[0])

    def test_one_reviewer_down_is_an_infra_failure_for_that_reviewer_only(self):
        plan, result = self.run_review({"deepseek": [finding()], "openai": [finding(line=11)]}, failing={"xai"})
        self.assertEqual(result.answered, ["openai", "deepseek"])
        self.assertTrue(review.is_complete(result))
        self.assertEqual(self.sections(result), [("strong", 2, ["deepseek", "openai"])])
        self.assertEqual(review.labels_for(plan, result), [review.INFRA_FAILURE])
        body = review.render("amber", plan, result, "a" * 40)
        self.assertIn("| reviewer | xai | `openai/grok-4.7` | infra-failure: RateLimitError from openai/grok-4.7 after 4 attempts |",
                      body)
        self.assertNotIn("Review incomplete", body)

    def test_a_verifier_that_is_down_hands_the_finding_to_the_next_family(self):
        plan, result = self.run_review({"deepseek": [finding()]}, failing={"openai"}, verdicts={"xai": "confirmed"})
        self.assertEqual((result.findings[0]["verifier"], review.section(result.findings[0])), ("xai", "verified"))

    def test_two_reviewers_down_is_an_incomplete_review_that_needs_a_human_and_never_passes(self):
        plan, result = self.run_review({"xai": [finding()]}, failing={"deepseek", "openai"})
        self.assertFalse(review.is_complete(result))
        self.assertEqual(review.labels_for(plan, result), [review.HUMAN_REVIEW, review.INFRA_FAILURE])
        self.assertEqual(self.sections(result), [("unverified", 1, ["xai"])])
        body = review.render("amber", plan, result, "a" * 40)
        self.assertIn("**Review incomplete:** 1 of 3 reviewers answered", body)
        self.assertIn("This is not a pass.", body)
        self.assertIn("Verifier: not verified: no other family answered", body.split("<details>")[0])

    def test_a_finding_no_verifier_could_check_stays_visible_and_labels_the_pr(self):
        plan, result = self.run_verifiers_down()
        self.assertEqual(self.sections(result), [("unverified", 1, ["deepseek"])])
        self.assertEqual(review.labels_for(plan, result), [review.HUMAN_REVIEW, review.INFRA_FAILURE])
        body = review.render("amber", plan, result, "a" * 40)
        visible = body.split("<details>")[0]
        self.assertIn("#### Unverified", visible)
        self.assertIn("sql injection", visible)
        self.assertIn("Verifier: not verified: every verifier failed", visible)

    def run_verifiers_down(self):
        """Every reviewer answers; only deepseek raises a finding; every verifier call then fails."""
        plan = review.plan_review(AMBER, set(THREE))

        def ask(family, system, user):
            if "## Finding" in user:
                down(family)
            return {"findings": [finding(problem="sql injection")] if family == "deepseek" else []}
        return plan, review.review(plan, None, "diff", "", answering(ask), MODELS)

    def test_a_verifier_without_a_verdict_leaves_the_finding_unverified_and_visible(self):
        plan, result = self.run_review({"deepseek": [finding()]}, verdicts={"openai": "maybe"})
        self.assertEqual(self.sections(result), [("unverified", 1, ["deepseek"])])
        self.assertEqual(review.labels_for(plan, result), [review.HUMAN_REVIEW])
        self.assertIn("not verified: openai returned no verdict", review.render("amber", plan, result, "a" * 40))

    def test_a_reviewer_with_malformed_findings_is_an_infra_failure_for_that_reviewer_only(self):
        for bad in ([{"file": "A.java", "line_start": "10", "category": "bug"}], [{"line_start": 1}], ["text"], None):
            self.asked = []
            plan, result = self.run_review({"deepseek": bad, "openai": [finding()], "xai": [finding(line=11)]})
            self.assertEqual(result.answered, ["openai", "xai"], msg=bad)
            self.assertEqual(self.sections(result), [("strong", 2, ["openai", "xai"])], msg=bad)
            self.assertIn(review.INFRA_FAILURE, review.labels_for(plan, result))
            row = next(c for c in result.calls if c["family"] == "deepseek")
            self.assertTrue(row["result"].startswith("infra-failure: openai/DeepSeek-V4.1-Flash-1017 returned"), msg=bad)

    def test_red_tier_needs_a_human_even_when_all_three_agree(self):
        plan, result = self.run_review({f: [finding()] for f in THREE}, tier=RED)
        self.assertEqual(review.labels_for(plan, result), [review.HUMAN_REVIEW])

    def test_a_merge_model_that_is_down_leaves_every_finding_and_notes_it(self):
        plan = review.plan_review(AMBER, set(THREE))

        def ask(family, system, user):
            if system == DEDUPE_PROMPT:
                down(family)
            if "## Finding" in user:
                return {"verdict": "confirmed"}
            return {"findings": [finding(family + ".java")]}
        result = review.review(plan, "openai", "diff", "", answering(ask), MODELS)
        self.assertEqual(len(result.findings), 3)
        self.assertIn(f"{review.MECHANICAL}: merge model unavailable (infra-failure: RateLimitError from "
                      "azure/gpt-5 after 4 attempts).", review.render("amber", plan, result, "a" * 40))

    def test_a_dedupe_answer_that_omits_an_index_falls_back_to_mechanical_grouping(self):
        plan, result = self.run_review({"deepseek": [finding("D.java")], "openai": [finding("O.java")]},
                                       merger="openai", groups=[[0]])
        self.assertEqual([f["file"] for f in result.findings], ["O.java", "D.java"])
        self.assertTrue(review.is_complete(result))
        self.assertEqual(result.calls[-1]["result"],
                         "infra-failure: azure/gpt-5 returned groups that are not a partition of 2 findings")
        self.assertIn(review.MECHANICAL, review.render("amber", plan, result, "a" * 40))


class VisibilityTest(unittest.TestCase):
    """What a person sees in the PR comment and the run record (brief 018, Visibility)."""

    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(ROOT)

    def tearDown(self):
        os.chdir(self.cwd)

    def scenario(self):
        plan = review.plan_review(AMBER, {"openai", "xai"})

        def ask(family, system, user):
            if "## Finding" in user:
                return {"verdict": "rejected", "reason": "line 7 | checks null first", "quote": "if (x == null)"}
            return {"findings": [finding("S.java", problem="leaks a token")] if family == "openai" else []}
        return plan, review.review(plan, None, "diff", "", answering(ask), MODELS)

    def test_comment_has_a_row_per_call_with_model_tokens_and_seconds_and_links_the_run(self):
        plan, result = self.scenario()
        body = review.render("amber", plan, result, "a" * 40, run_url="https://github.com/o/r/actions/runs/9")
        self.assertIn("| reviewer | openai | `azure/gpt-5` | ok | 1 | 100/20 |", body)
        self.assertIn("| reviewer | xai | `openai/grok-4.7` | ok | 0 | 100/20 |", body)
        self.assertIn("| verifier | xai | `openai/grok-4.7` | ok | #1: rejected | 100/20 |", body)
        self.assertIn("**#1 · major · `S.java:10`", body)
        self.assertIn("| reviewer | deepseek | | no key | | | |", body)
        self.assertIn("(https://github.com/o/r/actions/runs/9)", body)

    def test_verifier_rows_and_finding_headings_use_the_same_number(self):
        plan = review.plan_review(AMBER, set(THREE))

        def ask(family, system, user):
            if "## Finding" in user:
                return {"verdict": "confirmed", "reason": "seen"}
            if family == "openai":
                return {"findings": [dict(finding("A.java"), severity="minor")]}
            return {"findings": [dict(finding("B.java"), severity="blocker")]}
        result = review.review(plan, None, "diff", "", answering(ask), MODELS)
        body = review.render("amber", plan, result, "a" * 40)
        row = next(c for c in result.calls if c["role"] == "verifier")
        self.assertEqual(row["findings"], "#1: confirmed")
        self.assertIn("**#1 · minor · `A.java:10`", body.split("#### Verified")[1])
        self.assertIn("**#2 · blocker · `B.java:10`", body.split("#### Verified")[0])

    def test_model_text_cannot_open_an_html_comment_or_close_the_details_block(self):
        plan = review.plan_review(AMBER, {"openai", "xai"})

        def ask(family, system, user):
            if "## Finding" in user:
                return {"verdict": "rejected", "reason": "</details> <!-- hidden"}
            return {"findings": [finding(problem="<!-- swallow the rest")] if family == "openai" else []}
        body = review.render("amber", plan, review.review(plan, None, "diff", "", answering(ask), MODELS), "a" * 40)
        self.assertEqual((body.count("<!--"), body.count("</details>")), (1, 1))
        self.assertIn("&lt;!-- swallow the rest", body)

    def test_every_section_is_shown_and_a_rejected_finding_appears_with_who_raised_it_and_why(self):
        plan, result = self.scenario()
        body = review.render("amber", plan, result, "a" * 40)
        for heading in ("#### Strong", "#### Verified", "<summary>Rejected / low confidence (1)</summary>"):
            self.assertIn(heading, body)
        low = body.split("<summary>")[1]
        self.assertIn("leaks a token", low)
        self.assertIn("Agreement: 1/3: openai", low)
        self.assertIn("Verifier: xai rejected: line 7 \\| checks null first", low)

    def test_run_record_has_per_call_and_per_finding_data_but_no_code_or_secrets(self):
        plan, result = self.scenario()
        rec = review.record_of(plan, result)
        self.assertEqual([(c["role"], c["family"], c.get("model"), c["result"]) for c in rec["calls"]],
                         [("reviewer", "openai", "azure/gpt-5", "ok"), ("reviewer", "xai", "openai/grok-4.7", "ok"),
                          ("verifier", "xai", "openai/grok-4.7", "ok"), ("reviewer", "deepseek", None, "no key")])
        self.assertEqual([(f["problem"], f["section"], f["agreement"], f["verifier"], f["verdict"]) for f in rec["findings"]],
                         [("leaks a token", "low", 1, "xai", "rejected")])
        self.assertEqual(rec["agreement"], {"strong": 0, "verified": 0, "unverified": 0, "low": 1,
                                            "answered": 2, "wanted": 3, "raised": 1})
        text = json.dumps(rec)
        self.assertNotIn("secret_code_line", text)
        self.assertNotIn("if (x == null)", text)


class DiffLimitTest(unittest.TestCase):
    def test_an_oversized_diff_is_reviewed_in_part_and_handed_to_a_human(self):
        plan = review.plan_review(AMBER, set(THREE))
        big, reviewed, line = review.clip(plan, "x" * 120_001)
        self.assertEqual(len(reviewed), 120_000)
        self.assertEqual(review.labels_for(big), [review.HUMAN_REVIEW])
        result = review.Result((), [])
        self.assertIn("Diff too large (120001 chars); only the first 120000 were reviewed.",
                      review.render("amber", big, result, "a" * 40, line))

    def test_a_diff_within_the_limit_gets_neither_label_nor_line(self):
        plan = review.plan_review(AMBER, set(THREE))
        small, reviewed, line = review.clip(plan, "x" * 120_000)
        self.assertEqual((len(reviewed), review.labels_for(small)), (120_000, []))
        self.assertNotIn("Diff too large", review.render("amber", small, review.Result((), []), "a" * 40, line))


class Timeout(Exception):
    pass


class OutageTest(unittest.TestCase):
    """Brief 020: DeepSeek is rate-limited or times out on every call; the review completes with gpt-5 and Grok."""

    DEEPSEEK = "openai/DeepSeek-V4.1-Flash-1017"

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        shutil.copytree(ROOT / "factory/prompts", pathlib.Path(self.tmp, "factory/prompts"))
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp)

    def deepseek_down(self, exc):
        tried, posted, labelled, timeouts, merged = [], [], [], {}, []

        def completion(model, messages, timeout, **_):
            system, user = messages[0]["content"], messages[1]["content"]
            tried.append(model)
            timeouts[model] = timeout
            if model == self.DEEPSEEK:
                raise exc
            if system == DEDUPE_PROMPT:
                merged.append(model)
                data = {"groups": [[i] for i in range(len(json.loads(user)))]}
            elif "## Finding" in user:
                data = {"verdict": "confirmed", "reason": "seen"}
            else:
                own = "B.java" if model == "azure/gpt-5" else "C.java"
                data = {"findings": [finding(line=10 if own == "B.java" else 12), finding(own)]}
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(
                content=json.dumps(data)))], usage=types.SimpleNamespace(prompt_tokens=1, completion_tokens=1))

        def gh(*a, check=True):
            if a[:2] == ("pr", "diff"):
                return "diff"
            if a[:2] == ("pr", "comment"):
                posted.append(a[-1])
            if a[-1].endswith("/comments"):
                return "[]"
            if a[-2:-1] == ("-f",) and a[-1].startswith("labels[]="):
                labelled.extend(x.split("=", 1)[1] for x in a if x.startswith("labels[]="))
            return ""

        cfg = {"families": FAMILIES, "review": {"amber": AMBER, "merge_model": "openai"}}
        pr = {"number": 7, "labels": [{"name": "tier:amber"}], "body": "", "headRefOid": "a" * 40}
        out = io.StringIO()
        with mock.patch.dict(sys.modules, {"litellm": types.SimpleNamespace(completion=completion),
                                           "yaml": types.SimpleNamespace(safe_load=lambda _: cfg)}), \
                mock.patch.dict(os.environ, dict(ALL, GITHUB_REPOSITORY="o/r", GITHUB_RUN_ID="9")), \
                mock.patch.object(review, "find_pr", lambda repo: (pr, "a" * 40)), \
                mock.patch.object(review, "tier_of", lambda pr, repo: "amber"), \
                mock.patch.object(review, "gh", gh), \
                mock.patch.object(review, "with_backoff", functools.partial(review.with_backoff, sleep=lambda s: None)), \
                contextlib.redirect_stdout(out):
            pathlib.Path("factory/models.yaml").write_text("stubbed", encoding="utf-8")
            review.main()  # SystemExit here would be a failed job
        (body,) = posted
        record = json.loads(pathlib.Path("run-record.json").read_text())
        return tried, timeouts, merged, body, labelled, out.getvalue(), record

    def assert_completes_with_the_other_two(self, exc, attempts):
        tried, timeouts, merged, body, labelled, out, record = self.deepseek_down(exc)
        error = f"{type(exc).__name__} from {self.DEEPSEEK} after {attempts} attempts"
        self.assertEqual(tried.count(self.DEEPSEEK), attempts)
        self.assertEqual(timeouts, {self.DEEPSEEK: 180, "azure/gpt-5": 180, "openai/grok-4.7": 480})
        self.assertIn(f"| reviewer | deepseek | `{self.DEEPSEEK}` | infra-failure: {error} |", body)
        self.assertIn(f"Label `infra-failure`: reviewer deepseek: infra-failure: {error}", body)
        self.assertEqual(merged, ["azure/gpt-5"])
        self.assertNotIn(review.MECHANICAL, body)
        self.assertNotIn("Review incomplete", body)
        self.assertIn("**#1 · major · `A.java:10` · bug", body)
        self.assertIn("Agreement: 2/3: openai, xai", body)
        self.assertEqual(body.split("#### Verified")[1].split("<details>")[0].count("Verifier: "), 2)
        self.assertEqual(labelled, [review.INFRA_FAILURE])
        self.assertIn(error, out)
        self.assertEqual((record["outcome"], record["agreement"]["answered"]), ("reviewed", 2))
        self.assertIn(error, next(c["result"] for c in record["calls"] if c["family"] == "deepseek"))

    def test_deepseek_rate_limited_on_every_call_still_completes_with_the_other_two(self):
        self.assert_completes_with_the_other_two(RateLimitError("429 too many requests"), review.ATTEMPTS)

    def test_deepseek_timing_out_on_every_call_still_completes_with_the_other_two(self):
        self.assert_completes_with_the_other_two(Timeout("timed out"), review.TIMEOUT_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
