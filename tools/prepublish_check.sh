#!/usr/bin/env bash
# Pre-publish scan (brief 009), run before a repository goes public:
#   1. gitleaks over the history of every ref, in the pinned Docker image, repo mounted read-only.
#   2. A deny-list of names (kept outside the repo) over every commit's file contents, file paths,
#      author and committer, and message, plus every ref name and annotated tag.
# Prints counts and commit/file ids only, never a matched name. Exit 0 only when both pass,
# 1 when either finds something, 2 when the scan could not run.
# Keep behaviour and flags in sync with tools/prepublish_check.ps1.
set -euo pipefail

IMAGE='zricethezav/gitleaks:v8.24.0@sha256:2bcceac45179b3a91bff11a824d0fb952585b429e54fc928728b1d4d5c3e5176'

usage() {
  cat <<'EOF'
Usage: tools/prepublish_check.sh --deny-list FILE [--repo DIR]

  --deny-list FILE  One name per line (blank lines and lines starting with # are ignored).
                    Must live outside the repository. Matching is case-insensitive substring.
  --repo DIR        A full clone to scan (default: the current directory). Not a linked worktree.
EOF
}
stop() { echo "ERROR: $*" >&2; exit 2; }

DENY="" REPO="."
while [ $# -gt 0 ]; do
  case "$1" in
    --deny-list) [ $# -ge 2 ] || stop "--deny-list needs a value"; DENY="$2"; shift 2 ;;
    --repo) [ $# -ge 2 ] || stop "--repo needs a value"; REPO="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; stop "unknown argument: $1" ;;
  esac
done
[ -n "$DENY" ] || { usage >&2; stop "--deny-list is required"; }
[ -f "$DENY" ] || stop "deny-list not found: $DENY"
top="$(git -C "$REPO" rev-parse --show-toplevel 2>/dev/null)" || stop "not a git repository: $REPO"
REPO="$(cd "$top" && pwd -P)"
[ -d "$REPO/.git" ] || stop "$REPO is a linked worktree or submodule; scan a full clone"
deny_dir="$(cd "$(dirname "$DENY")" && pwd -P)"
case "${deny_dir,,}/" in "${REPO,,}/"*) stop "the deny-list must live outside the repository" ;; esac

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PAT="$TMP/patterns"
tr -d '\r' <"$DENY" | grep -v -e '^[[:space:]]*$' -e '^[[:space:]]*#' >"$PAT" || true
terms=$(wc -l <"$PAT" | tr -d ' ')
[ "$terms" -gt 0 ] || stop "the deny-list holds no names"

# Lines of $1 that hold a name, case-insensitive. awk, not grep -iF: Git for Windows' grep 3.0 aborts on -i -F -f.
# Always call it as a plain assignment, so a failure stops the scan instead of reading as "no match".
count() {
  awk 'NR == FNR { if (length($0)) t[++n] = tolower($0); next }
       { l = tolower($0); for (i = 1; i <= n; i++) if (index(l, t[i])) { c++; break } }
       END { print c + 0 }' "$PAT" - <<<"$1"
}
host_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }

# ---- 1. gitleaks ----
printf '%s' '{{range .}}{{.Commit}} {{.File}} {{.RuleID}}{{"\n"}}{{end}}' >"$TMP/ids.tmpl"
set +e
MSYS_NO_PATHCONV=1 docker run --rm --network none \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
  -v "$(host_path "$REPO"):/repo:ro" -v "$(host_path "$TMP"):/out" \
  "$IMAGE" git /repo --log-opts=--all --redact --no-banner --exit-code 3 \
  --report-format template --report-template /out/ids.tmpl --report-path /out/leaks.txt >/dev/null 2>"$TMP/gitleaks.err"
rc=$?
set -e
case "$rc" in
  0) leaks=0 ;;
  3) leaks=$(grep -c . "$TMP/leaks.txt" 2>/dev/null || true); [ "${leaks:-0}" -gt 0 ] || leaks=1 ;;
  *) cat "$TMP/gitleaks.err" >&2; stop "gitleaks could not run (exit $rc); is Docker running?" ;;
esac
echo "gitleaks: $leaks finding(s) over all refs (secrets redacted)"
if [ "$leaks" -gt 0 ] && [ -f "$TMP/leaks.txt" ]; then
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    k=$(count "$line")
    [ "$k" -eq 0 ] || line="${line%% *} <path withheld>"
    echo "  leak: $line"
  done <"$TMP/leaks.txt"
fi

# ---- 2. deny-list ----
content=0 paths=0 messages=0 refs=0 tags=0
commits=$(git -C "$REPO" rev-list --all)
n=0
for c in $commits; do
  n=$((n + 1))
  set +e
  hits=$(git -C "$REPO" grep -i -F -l -f "$PAT" "$c" --)
  grc=$?
  set -e
  [ "$grc" -le 1 ] || stop "git grep failed on ${c:0:12}"
  while IFS= read -r hit; do
    [ -n "$hit" ] || continue
    content=$((content + 1))
    path="${hit#*:}"
    k=$(count "$path")
    [ "$k" -eq 0 ] || path="<path withheld>"
    echo "  content: ${c:0:12} $path"
  done <<<"$hits"
  text=$(git -C "$REPO" ls-tree -r --name-only "$c")
  k=$(count "$text")
  if [ "$k" -gt 0 ]; then paths=$((paths + k)); echo "  path: ${c:0:12} $k file path(s)"; fi
  text=$(git -C "$REPO" log -1 --format='%an%n%ae%n%cn%n%ce%n%B' "$c")
  k=$(count "$text")
  if [ "$k" -gt 0 ]; then messages=$((messages + 1)); echo "  message or author: ${c:0:12}"; fi
done
text=$(git -C "$REPO" for-each-ref --format='%(refname)')
refs=$(count "$text")
[ "$refs" -eq 0 ] || echo "  ref names: $refs"
objects=$(git -C "$REPO" for-each-ref --format='%(objecttype) %(objectname)' refs/tags)
for t in $(awk '$1 == "tag" { print $2 }' <<<"$objects"); do
  text=$(git -C "$REPO" cat-file tag "$t")
  k=$(count "$text")
  if [ "$k" -gt 0 ]; then tags=$((tags + 1)); echo "  annotated tag: ${t:0:12}"; fi
done
denied=$((content + paths + messages + refs + tags))
echo "deny-list: $terms name(s), $n commit(s): $content content, $paths path, $messages message or author, $refs ref name, $tags tag hit(s)"

if [ "$leaks" -eq 0 ] && [ "$denied" -eq 0 ]; then echo "PASS"; exit 0; fi
echo "FAIL"; exit 1
