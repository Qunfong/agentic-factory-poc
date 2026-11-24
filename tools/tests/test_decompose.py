import pathlib, sys, unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import decompose  # noqa: E402


class ParseFeaturesTest(unittest.TestCase):
    def test_one_feature_with_two_acs(self):
        text = (
            "# Design\n\n## Proposed features\n"
            "- Meter summary endpoint\n"
            "  AC-1: GET /meters/summary returns totals per type\n"
            "  AC-2: an empty registry returns zero totals, not 404\n"
        )
        self.assertEqual(decompose.parse_features(text),
                         [("Meter summary endpoint",
                           ["AC-1: GET /meters/summary returns totals per type",
                            "AC-2: an empty registry returns zero totals, not 404"])])

    def test_two_features_stop_at_next_heading(self):
        text = (
            "## Proposed features\n"
            "- First\n  AC-1: a\n"
            "- Second\n  AC-1: b\n  AC-2: c\n"
            "## Open questions\n"
            "- Second\n  AC-1: should not be parsed\n"
        )
        features = decompose.parse_features(text)
        self.assertEqual([t for t, _ in features], ["First", "Second"])
        self.assertEqual(features[1][1], ["AC-1: b", "AC-2: c"])

    def test_no_heading_returns_empty(self):
        self.assertEqual(decompose.parse_features("# Design\n\nno such section\n"), [])

    def test_bullet_with_no_ac_lines_is_dropped(self):
        text = "## Proposed features\n- Not ready yet, no ACs\n- Ready\n  AC-1: x\n"
        self.assertEqual(decompose.parse_features(text), [("Ready", ["AC-1: x"])])

    def test_issue_body_links_back_to_the_design_idea(self):
        body = decompose.issue_body("42", ["AC-1: a", "AC-2: b"])
        self.assertIn("design idea #42", body)
        self.assertIn("AC-1: a", body)
        self.assertIn("AC-2: b", body)


if __name__ == "__main__":
    unittest.main()
