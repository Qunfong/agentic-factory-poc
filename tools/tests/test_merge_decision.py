import pathlib, sys, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import review  # noqa: E402

FAMS = ("openai", "xai", "deepseek")
PLAN = review.Plan(FAMS, (), False)


def row(family, ok=True):
    return {"role": "reviewer", "family": family, "result": "ok" if ok else "infra-failure", "findings": 0}


def result(findings=(), failed=()):
    return review.Result(calls=tuple(row(f, f not in failed) for f in FAMS), findings=list(findings))


def finding(severity="major", agreement=2, verdict=None):
    return {"id": 1, "severity": severity, "agreement": agreement, "verdict": verdict}


class MergeDecisionTest(unittest.TestCase):
    def decide(self, labels=("agent",), plan=PLAN, res=None):
        return review.merge_decision(set(labels), plan, res or result())

    def test_clean_complete_review_of_a_work_item_merges(self):
        self.assertTrue(self.decide()[0])

    def test_non_agent_pr_never_merges(self):
        self.assertFalse(self.decide(labels=("spec",))[0])

    def test_red_tier_needs_a_person(self):
        self.assertFalse(self.decide(plan=review.Plan(FAMS, (), True))[0])

    def test_one_reviewer_failing_blocks_even_with_quorum(self):
        self.assertFalse(self.decide(res=result(failed=("deepseek",)))[0])

    def test_agreed_major_blocks(self):
        self.assertFalse(self.decide(res=result([finding("major", 2)]))[0])

    def test_verified_blocker_blocks(self):
        self.assertFalse(self.decide(res=result([finding("blocker", 1, "confirmed")]))[0])

    def test_rejected_or_minor_findings_do_not_block(self):
        self.assertTrue(self.decide(res=result([finding("major", 1, "rejected"), finding("minor", 2)]))[0])

    def test_unverified_single_source_finding_needs_a_person(self):
        self.assertFalse(self.decide(res=result([finding("minor", 1, None)]))[0])


if __name__ == "__main__":
    unittest.main()
