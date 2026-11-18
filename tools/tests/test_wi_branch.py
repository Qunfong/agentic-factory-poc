"""The work-item branch regex in 45-fix-round.yml, run in bash: one canonical branch per issue (brief 011, Q15)."""
import pathlib, re, shutil, subprocess, unittest

FIX_ROUND = pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows" / "45-fix-round.yml"
BASH = shutil.which("bash")


def fix_round_issue(branch):
    """The issue number 45-fix-round parses from branch, or None when its check rejects it."""
    test = re.search(r'\[\[ "\$BRANCH" =~ (\S+) \]\]', FIX_ROUND.read_text(encoding="utf-8")).group(1)
    script = f'[[ "$BRANCH" =~ {test} ]] || exit 3; echo "${{BASH_REMATCH[1]}}"'
    r = subprocess.run([BASH, "-c", script], env={"BRANCH": branch}, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


@unittest.skipIf(BASH is None, "bash is not installed")
class FixRoundBranchTest(unittest.TestCase):
    def test_canonical_branch_gives_its_issue(self):
        self.assertEqual(fix_round_issue("wi-7"), "7")
        self.assertEqual(fix_round_issue("wi-120"), "120")

    def test_leading_zero_and_zero_are_rejected(self):
        for branch in ("wi-007", "wi-0", "wi-", "wi-7x", "xwi-7"):
            self.assertIsNone(fix_round_issue(branch), branch)


if __name__ == "__main__":
    unittest.main()
