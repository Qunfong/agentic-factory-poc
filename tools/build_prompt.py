"""Build a role's prompt: the role prompt with its always-on skills inlined and hash-checked (brief 010),
then, given an issue JSON, the work item and its spec.
Usage: python tools/build_prompt.py <role> [issue.json]"""
import json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import load_skills  # noqa: E402

role = sys.argv[1]
try:
    parts = [pathlib.Path(f"factory/prompts/{role}.md").read_text(encoding="utf-8") + load_skills.prompt_section(role)]
except load_skills.SkillError as e:
    sys.exit(f"build_prompt: {e}")
if len(sys.argv) > 2:
    issue = json.load(open(sys.argv[2], encoding="utf-8"))
    parts += [f"\n## Work item: {issue['title']}", "<untrusted-issue-text>", issue.get("body", ""), "</untrusted-issue-text>"]
    spec_ref = re.search(r"docs/specs/F\d+", issue.get("body", ""))
    if spec_ref:
        for name in ("spec.md", "plan.md"):
            f = pathlib.Path(spec_ref.group(0)) / name
            if f.exists():
                parts += [f"\n## {f}", f.read_text(encoding="utf-8")]
print("\n".join(parts))
