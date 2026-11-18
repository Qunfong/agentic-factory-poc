"""Q44: no workflow loads a skill whose source is still reviewed: pending."""
import pathlib, sys, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_workflow_policy as policy  # noqa: E402

CLEAN = {"30-build.yml": {"jobs": {"builder": {"steps": [{"run": "python3 tools/load_skills.py builder"}]}}}}


def with_step(step):
    return {"30-build.yml": {"jobs": {"builder": {"steps": [step]}}}}


class AllowPendingRuleTest(unittest.TestCase):
    def test_clean_workflow_passes(self):
        self.assertEqual(policy.no_workflow_loads_pending_skills(CLEAN), [])

    def test_flag_anywhere_in_a_workflow_fails(self):
        for step in ({"run": "python3 tools/load_skills.py builder --allow-pending"},
                     {"run": "python3 tools/skill_eval.py --task G001 --allow-pending"},
                     {"env": {"ARGS": "--ALLOW-PENDING"}, "run": "python3 tools/load_skills.py builder $ARGS"},
                     {"with": {"args": "allow_pending=true"}}):
            self.assertEqual(policy.no_workflow_loads_pending_skills(with_step(step)),
                             ["30-build.yml: passes --allow-pending; unreviewed skill sources load only in the local tools/skill_eval.py"])

    def test_rule_is_registered(self):
        self.assertIn(policy.no_workflow_loads_pending_skills, policy.RULES)


if __name__ == "__main__":
    unittest.main()
