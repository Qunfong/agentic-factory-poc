"""A stand-in for `gh` in the bootstrap --apply test (brief 011, Q32). It never touches the network.

Each call is appended to FAKE_GH_LOG as one JSON line: the argv, plus the payload of any --input file.
Answers come from the first matching rule in FAKE_GH_SCENARIO ([[argv prefix, stdout, payload fields?], ...]).
A rule with payload fields matches only a call whose --input payload has those top-level values.
A call no rule matches exits 9, so an unexpected request stops bootstrap.
"""
import json, os, sys


def main(argv):
    if argv == ["__fake_gh_identity"]:
        print(os.environ.get("FAKE_GH_NONCE", ""))
        return 0
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        sys.exit("fake gh: a token is set; the test must unset GH_TOKEN and GITHUB_TOKEN")
    entry = {"argv": argv}
    if "--input" in argv:
        with open(argv[argv.index("--input") + 1], encoding="utf-8") as f:
            entry["payload"] = json.load(f)
    with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as log:
        log.write(json.dumps(entry) + "\n")
    with open(os.environ["FAKE_GH_SCENARIO"], encoding="utf-8") as f:
        rules = json.load(f)
    for prefix, out, *fields in rules:
        wanted = fields[0] if fields else {}
        if argv[:len(prefix)] == prefix and all(entry.get("payload", {}).get(k) == v for k, v in wanted.items()):
            sys.stdout.write(out)
            return 0
    sys.stderr.write(f"fake gh: unexpected call {argv}\n")
    return 9


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
