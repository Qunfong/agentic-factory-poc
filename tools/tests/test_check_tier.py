import pathlib, re, sys, unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
RISK_MAP = TOOLS.parent / "factory" / "risk-map.yaml"
sys.path.insert(0, str(TOOLS))
from check_tier import diff_tier, parse_risk_map, path_tier  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None


def read_risk_map():
    """The real risk map, read without pyyaml: it is a default line plus one flow mapping per rule."""
    text = RISK_MAP.read_text(encoding="utf-8")
    rules = [{"pattern": p, "tier": t}
             for p, t in re.findall(r'^\s*-\s*\{pattern:\s*"([^"]+)",\s*tier:\s*(\w+)', text, re.M)]
    default = re.search(r"^default:\s*(\w+)", text, re.M).group(1)
    return {"default": default, "rules": rules}


class RealRiskMapTest(unittest.TestCase):
    def setUp(self):
        self.rules, self.default = parse_risk_map(read_risk_map())

    def tier(self, *paths):
        return diff_tier(list(paths), self.rules, self.default)

    def test_reader_sees_every_rule(self):
        self.assertEqual(len(read_risk_map()["rules"]), RISK_MAP.read_text(encoding="utf-8").count("{pattern:"))

    def test_markdown_under_factory_scores_red_not_green(self):
        self.assertEqual(self.tier("factory/prompts/x.md"), "red")

    def test_tools_scores_red(self):
        self.assertEqual(self.tier("tools/x.py"), "red")
        self.assertEqual(self.tier("tools/README.md"), "red")
        self.assertEqual(self.tier(".github/workflows/README.md"), "red")

    def test_agent_steering_files_score_red(self):
        for path in ("AGENTS.md", "CLAUDE.md", ".claude/settings.json", ".claude/skills/x/SKILL.md"):
            self.assertEqual(self.tier(path), "red", path)

    def test_plain_docs_score_green(self):
        self.assertEqual(self.tier("README.md"), "green")
        self.assertEqual(self.tier("docs/specs/F7/spec.md"), "green")

    def test_the_diff_scores_its_highest_path(self):
        self.assertEqual(self.tier("README.md", "app/src/main/java/X.java"), "amber")
        self.assertEqual(self.tier("README.md", "app/src/main/java/a/billing/X.java", "app/pom.xml"), "red")

    def test_case_and_traversal_tricks_do_not_lower_the_tier(self):
        self.assertEqual(self.tier("Factory/prompts/x.md"), "red")
        self.assertEqual(self.tier("TOOLS/x.py"), "red")
        self.assertEqual(self.tier("app/src/main/java/a/Billing/X.java"), "red")
        self.assertEqual(self.tier("DOCS/x.java"), "amber")
        self.assertEqual(self.tier("docs/../factory/x.md"), "red")

    @unittest.skipIf(yaml is None, "pyyaml is not installed")
    def test_reader_agrees_with_pyyaml(self):
        data = yaml.safe_load(RISK_MAP.read_text(encoding="utf-8"))
        rules = [{"pattern": r["pattern"], "tier": r["tier"]} for r in data["rules"]]
        self.assertEqual(read_risk_map(), {"default": data["default"], "rules": rules})


class MaxTierTest(unittest.TestCase):
    def test_highest_matching_rule_wins_whatever_the_order(self):
        data = {"default": "amber", "rules": [{"pattern": "**/*.md", "tier": "green"},
                                              {"pattern": "app/**", "tier": "red"}]}
        rules, default = parse_risk_map(data)
        self.assertEqual(path_tier("app/notes.md", rules, default), "red")
        rules, default = parse_risk_map({**data, "rules": data["rules"][::-1]})
        self.assertEqual(path_tier("app/notes.md", rules, default), "red")
        self.assertEqual(path_tier("lib/x.java", rules, default), "amber")

    def test_floor_holds_against_a_map_that_says_green(self):
        rules, default = parse_risk_map({"default": "green", "rules": [{"pattern": "**", "tier": "green"}]})
        for path in ("tools/check_paths.py", ".github/workflows/publish.yml", "factory/risk-map.yaml"):
            self.assertEqual(path_tier(path, rules, default), "red", path)

    def test_floor_covers_nested_and_recased_agent_files(self):
        rules, default = parse_risk_map({"default": "green", "rules": [{"pattern": "**", "tier": "green"}]})
        for path in ("AGENTS.md", "app/AGENTS.md", "Agents.md", "CLAUDE.md", "app/claude.md",
                     ".claude/settings.json", "app/.Claude/skills/x/SKILL.md"):
            self.assertEqual(path_tier(path, rules, default), "red", path)
        self.assertEqual(path_tier("README.md", rules, default), "green")

    def test_unknown_tier_is_refused(self):
        with self.assertRaisesRegex(ValueError, "unknown tier"):
            parse_risk_map({"default": "amber", "rules": [{"pattern": "**", "tier": "blue"}]})

    def test_empty_diff_scores_the_default(self):
        self.assertEqual(diff_tier([], *parse_risk_map({"default": "amber", "rules": []})), "amber")


if __name__ == "__main__":
    unittest.main()
