import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
OLD_BRANCH = re.compile(r"origin/main\b|refs/heads/main\b|branches:\s*\[\s*main\s*\]")


class DefaultBranchTest(unittest.TestCase):
    def test_tools_and_workflows_never_name_the_old_main_branch(self):
        files = [p for p in (ROOT / "tools").glob("*.py")] + list((ROOT / ".github" / "workflows").glob("*.yml"))
        hits = [f"{p.relative_to(ROOT)}:{n}" for p in files
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if OLD_BRANCH.search(line)]
        self.assertEqual(hits, [], "the default branch is master; publish failed on origin/main (factory run #16)")


if __name__ == "__main__":
    unittest.main()
