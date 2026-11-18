"""skill_eval's pure parts and its hidden-test workspace, without running claude or mvn."""
import json, pathlib, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import skill_eval  # noqa: E402


class SkillEvalTest(unittest.TestCase):
    def test_setups_grow_from_none_to_all_skills(self):
        self.assertEqual(skill_eval.SETUPS, {"A": (), "B": ("always",), "C": ("always", "on_trigger")})

    def setup_in_copy(self, setup):
        with tempfile.TemporaryDirectory() as d:
            repo = pathlib.Path(d)
            skill_eval.shutil.copytree(ROOT / "factory", repo / "factory", ignore=skill_eval.shutil.ignore_patterns("golden"))
            stale = repo / ".claude/skills/stale"
            stale.mkdir(parents=True)
            skills, prompt = skill_eval.load_setup("builder", repo, skill_eval.SETUPS[setup], False)
            installed = sorted(p.name for p in (repo / ".claude/skills").glob("*"))
            return skills, prompt, installed

    def test_setup_a_loads_nothing(self):
        skills, prompt, installed = self.setup_in_copy("A")
        self.assertEqual((skills, installed), ("-", []))
        self.assertEqual(prompt, (ROOT / "factory/prompts/builder.md").read_text(encoding="utf-8"))

    def test_setup_b_inlines_always_on_skills_and_installs_none(self):
        skills, prompt, installed = self.setup_in_copy("B")
        self.assertEqual((skills, installed), ("inline:minimal-change inline:meter-conventions", []))
        self.assertIn("### Skill: minimal-change", prompt)
        self.assertIn("### Skill: meter-conventions", prompt)

    def test_setup_c_installs_exactly_the_charters_on_trigger_skills(self):
        skills, prompt, installed = self.setup_in_copy("C")
        self.assertEqual(installed, ["impact-check"])
        self.assertEqual(skills, "inline:minimal-change inline:meter-conventions impact-check")
        self.assertIn("### Skill: minimal-change", prompt)

    def test_prompt_hides_the_evaluator_section(self):
        task = (ROOT / "factory/golden/G001/task.md").read_text(encoding="utf-8")
        prompt = skill_eval.task_prompt("You are the builder.", task)
        self.assertIn("AC-4: A valid newer reading", prompt)
        self.assertNotIn("Expected outcome", prompt)
        self.assertNotIn("AcceptanceTest", prompt)
        self.assertTrue(prompt.startswith("You are the builder."))

    def test_numstat_counts_lines_under_a_prefix_and_skips_binaries(self):
        numstat = "3\t1\tapp/src/main/A.java\n10\t0\tapp/src/test/T.java\n-\t-\tapp/src/main/x.png\n"
        self.assertEqual(skill_eval.numstat_lines(numstat, "app/src/main/"), 4)
        self.assertEqual(skill_eval.numstat_lines(numstat), 14)

    def test_surefire_reads_one_class_and_reports_zero_when_it_never_ran(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(skill_eval.surefire(d, "AcceptanceTest"), (0, 0))
            pathlib.Path(d, "TEST-com.example.meter.AcceptanceTest.xml").write_text(
                '<testsuite tests="4" failures="1" errors="1" skipped="0"/>')
            pathlib.Path(d, "TEST-com.example.meter.ArchitectureTest.xml").write_text(
                '<testsuite tests="3" failures="3" errors="0"/>')
            self.assertEqual(skill_eval.surefire(d, "AcceptanceTest"), (4, 2))

    def test_agent_metrics_from_claude_json_and_from_failures(self):
        ok = {"subtype": "success", "is_error": False, "num_turns": 7, "total_cost_usd": 0.5,
              "usage": {"input_tokens": 10, "cache_creation_input_tokens": 20, "cache_read_input_tokens": 30, "output_tokens": 40}}
        m = skill_eval.agent_metrics(json.dumps(ok))
        self.assertEqual((m["agent_status"], m["turns"], m["input_tokens"], m["output_tokens"]), ("success", 7, 10, 40))
        err = skill_eval.agent_metrics(json.dumps({"is_error": True, "result": "Failed to authenticate"}))
        self.assertEqual(err["agent_status"], "error: Failed to authenticate")
        self.assertEqual(skill_eval.agent_metrics("not json"), {"agent_status": "no json output"})

    def test_workspace_holds_no_golden_task_in_files_or_history(self):
        commit = skill_eval.git(ROOT, "rev-parse", "HEAD").strip()
        with tempfile.TemporaryDirectory() as d:
            repo = pathlib.Path(d, "repo")
            skill_eval.workspace_without_golden(commit, repo, pathlib.Path(d, "src.tar"))
            self.assertTrue((repo / "app/pom.xml").is_file())
            self.assertFalse((repo / skill_eval.GOLDEN).exists())
            self.assertNotIn("golden", skill_eval.git(repo, "log", "--all", "--name-only", "--format="))
            self.assertEqual(skill_eval.git(repo, "rev-list", "--count", "HEAD").strip(), "1")
            skill_eval.shutil.rmtree(repo, onerror=skill_eval.writable)


if __name__ == "__main__":
    unittest.main()
