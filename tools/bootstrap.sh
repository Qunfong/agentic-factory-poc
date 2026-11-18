#!/usr/bin/env bash
# One-time GitHub setup for the factory POC (README "One-time setup").
# Creates labels, variables, environments and the two default-branch rulesets with gh.
# Never sets or reads secrets. DRY RUN by default; pass --apply to execute.
# Keep behaviour and flags in sync with tools/bootstrap.ps1.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: tools/bootstrap.sh --org ORG --repo REPO --po-logins LOGIN[,LOGIN...]
                          --release-owner LOGIN|team:SLUG [options]

Required:
  --org ORG                     Repository owner: an organisation or a personal account
  --repo REPO                   Repository name
  --po-logins A,B               Product owner logins -> GATE_ROLES
  --release-owner X             Production approver: a login, or team:<slug> (organisations only)

Owner type:
  --owner-type user|org         What ORG is. Dry run: skips the read-only lookup (no gh call at all).
                                Apply: always looked up, and must match when given.

Code owners. Organisation: team slugs that must exist in ORG.
Personal account: logins (there are no teams), each defaulting to ORG.
  --developers-team X           default: developers
  --tech-leads-team X           default: tech-leads
  --domain-owners-team X        default: domain-owners
  --security-team X             default: security

Approved weakenings (personal account only, off by default; docs/adr/0002-single-maintainer-bypass.md):
  --admin-bypass-via-pr         Repository admins may skip the review rule, through a pull request only
  --allow-self-review           The production reviewer may approve their own deployment

Optional:
  --acceptance-repo OWNER/NAME  default: <org>/meter-acceptance
  --wip-limit N                 default: 3
  --azure-openai-endpoint URL   AZURE_OPENAI_ENDPOINT, such as https://<resource>.openai.azure.com
                                (skipped with a TODO if absent)
  --factory-bot-login LOGIN     FACTORY_BOT_LOGIN, the App's bot login such as my-app[bot]
                                (skipped with a TODO if absent; agents then start only for maintainers)
  --factory-app-client-id ID    FACTORY_APP_CLIENT_ID, the App's public client id such as Iv23li...
                                (skipped with a TODO if absent)
  --no-merge-queue              Drop the merge_queue rule (weakens protection; loud warning)
  --apply                       Execute. Without it, only print what would run.
  -h, --help                    Show this help
EOF
}

die()  { echo "ERROR: $*" >&2; exit 1; }
udie() { echo "ERROR: $*" >&2; echo >&2; usage >&2; exit 2; }

ORG="" REPO="" PO_LOGINS="" RELEASE_OWNER=""
DEV_TEAM="" TL_TEAM="" DOMAIN_TEAM="" SEC_TEAM="" OWNER_TYPE_ARG=""
ACCEPTANCE_REPO="" WIP_LIMIT="3" AZURE_ENDPOINT="" BOT_LOGIN="" CLIENT_ID=""
APPLY=0 NO_MERGE_QUEUE=0 ADMIN_BYPASS=0 SELF_REVIEW=0
ADR="docs/adr/0002-single-maintainer-bypass.md"

while [ $# -gt 0 ]; do
  arg="$1"; val=""
  case "$arg" in
    --*=*) val="${arg#*=}"; arg="${arg%%=*}" ;;
  esac
  case "$arg" in
    --apply) APPLY=1; shift; continue ;;
    --no-merge-queue) NO_MERGE_QUEUE=1; shift; continue ;;
    --admin-bypass-via-pr) ADMIN_BYPASS=1; shift; continue ;;
    --allow-self-review) SELF_REVIEW=1; shift; continue ;;
    -h|--help) usage; exit 0 ;;
    --org|--repo|--po-logins|--release-owner|--developers-team|--tech-leads-team|\
    --domain-owners-team|--security-team|--acceptance-repo|--wip-limit|\
    --azure-openai-endpoint|--factory-bot-login|--factory-app-client-id|--owner-type)
      if [ -z "$val" ]; then
        [ $# -ge 2 ] || udie "$arg needs a value"
        val="$2"; shift
      fi
      shift ;;
    *) udie "unknown argument: $arg" ;;
  esac
  case "$arg" in
    --org) ORG="$val" ;;
    --repo) REPO="$val" ;;
    --po-logins) PO_LOGINS="$val" ;;
    --release-owner) RELEASE_OWNER="$val" ;;
    --developers-team) DEV_TEAM="$val" ;;
    --tech-leads-team) TL_TEAM="$val" ;;
    --domain-owners-team) DOMAIN_TEAM="$val" ;;
    --security-team) SEC_TEAM="$val" ;;
    --acceptance-repo) ACCEPTANCE_REPO="$val" ;;
    --wip-limit) WIP_LIMIT="$val" ;;
    --azure-openai-endpoint) AZURE_ENDPOINT="$val" ;;
    --factory-bot-login) BOT_LOGIN="$val" ;;
    --factory-app-client-id) CLIENT_ID="$val" ;;
    --owner-type) OWNER_TYPE_ARG="$val" ;;
  esac
done

# ---- validate input (also keeps values safe inside URL paths and JSON) ----
missing=()
[ -n "$ORG" ] || missing+=(--org)
[ -n "$REPO" ] || missing+=(--repo)
[ -n "$PO_LOGINS" ] || missing+=(--po-logins)
[ -n "$RELEASE_OWNER" ] || missing+=(--release-owner)
[ ${#missing[@]} -eq 0 ] || udie "missing required: ${missing[*]}"

LOGIN_RE='^[A-Za-z0-9]([A-Za-z0-9-]{0,38})$'
SLUG_RE='^[A-Za-z0-9][A-Za-z0-9._-]*$'
NAME_RE='^[A-Za-z0-9._-]+$'

[[ "$ORG" =~ $LOGIN_RE ]] || udie "invalid --org: $ORG"
[[ "$REPO" =~ $NAME_RE ]] || udie "invalid --repo: $REPO"
IFS=',' read -r -a PO_LIST <<<"$PO_LOGINS"
[ ${#PO_LIST[@]} -gt 0 ] || udie "--po-logins is empty"
for l in "${PO_LIST[@]}"; do [[ "$l" =~ $LOGIN_RE ]] || udie "invalid login in --po-logins: '$l'"; done
case "$OWNER_TYPE_ARG" in
  "") ;;
  user) OWNER_TYPE_ARG="User" ;;
  org) OWNER_TYPE_ARG="Organization" ;;
  *) udie "--owner-type must be user or org: $OWNER_TYPE_ARG" ;;
esac
if [[ "$RELEASE_OWNER" == team:* ]]; then
  REL_TYPE="Team"; REL_NAME="${RELEASE_OWNER#team:}"
  [[ "$REL_NAME" =~ $SLUG_RE ]] || udie "invalid team slug in --release-owner: $REL_NAME"
else
  REL_TYPE="User"; REL_NAME="$RELEASE_OWNER"
  [[ "$REL_NAME" =~ $LOGIN_RE ]] || udie "invalid login in --release-owner: $REL_NAME"
fi
[ -n "$ACCEPTANCE_REPO" ] || ACCEPTANCE_REPO="$ORG/meter-acceptance"
[[ "$ACCEPTANCE_REPO" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ ]] || udie "invalid --acceptance-repo: $ACCEPTANCE_REPO"
[[ "$WIP_LIMIT" =~ ^[1-9][0-9]*$ ]] || udie "--wip-limit must be a positive integer: $WIP_LIMIT"
[ -z "$BOT_LOGIN" ] || [[ "$BOT_LOGIN" =~ ^[A-Za-z0-9][A-Za-z0-9-]*\[bot\]$ ]] || udie "--factory-bot-login must look like <app-slug>[bot]: $BOT_LOGIN"
[ -z "$AZURE_ENDPOINT" ] || [[ "$AZURE_ENDPOINT" =~ ^https://[a-z0-9][a-z0-9-]*\.openai\.azure\.com/?$ ]] || udie "--azure-openai-endpoint must look like https://<resource>.openai.azure.com: $AZURE_ENDPOINT"
[ -z "$CLIENT_ID" ] || [[ "$CLIENT_ID" =~ ^Iv[0-9A-Za-z.]+$ ]] || udie "--factory-app-client-id must look like Iv23...: $CLIENT_ID"

R="$ORG/$REPO"
DONE=() SKIPPED=() TODO=()
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---- helpers ----
q() {  # quote an argument for display only
  if [[ "$1" =~ ^[A-Za-z0-9_./:=,@+-]+$ ]]; then printf '%s' "$1"
  else printf "'%s'" "${1//\'/\'\\\'\'}"; fi
}
show() { local out="+" a; for a in "$@"; do out+=" $(q "$a")"; done; echo "$out"; }
run() { show "$@"; if [ "$APPLY" -eq 1 ]; then "$@" >/dev/null; fi; }
# api_json METHOD PATH FILE [PLAN_SENSITIVE]: print payload; in apply mode send it with --input.
api_json() {
  show gh api -X "$1" "$2" --input "$(basename "$3")"
  echo "  payload: $(cat "$3")"
  if [ "$APPLY" -eq 1 ]; then
    local out
    out="$(gh api -X "$1" "$2" --input "$3" 2>&1)" || api_fail "$1 $2" "$out" "${4:-0}"
  fi
}
# A 403/422 on rulesets or environment reviewers usually means the account's plan lacks the feature.
api_fail() {  # WHAT OUTPUT PLAN_SENSITIVE(0|1)
  echo "$2" >&2
  if echo "$2" | grep -qiE 'upgrade|GitHub Pro|make this repository public|billing|\bplan\b' \
     || { [ "$3" -eq 1 ] && echo "$2" | grep -qE 'HTTP (403|422)'; }; then
    die "GitHub refused $1, most likely for plan reasons: on a personal account, rulesets and environment required reviewers need a public repo (or GitHub Pro). Branch protection is NOT in place. Make the repo public, then rerun --apply."
  fi
  die "$1 failed (see above)."
}
weakening() {  # one loud banner per approved weakening
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  echo "WARNING: $1"
  echo "WARNING: approved for a single maintainer only; revert trigger in $ADR"
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
}
section() { echo; echo "== $* =="; }

if [ "$APPLY" -eq 1 ]; then MODE="APPLY"; else MODE="DRY RUN"; fi
echo "bootstrap: $R  mode: $MODE"
[ "$APPLY" -eq 1 ] || echo "Dry run: nothing is changed; the only gh call is a read-only owner lookup when --owner-type is absent. Pass --apply to execute."
trap 'echo "ERROR: a command failed (line $LINENO); stopping. Rerun is safe: every step is idempotent." >&2' ERR

# ---- owner type: a personal account has no teams and gets the brief 008 adaptations ----
section "Owner"
show gh api "users/$ORG" --jq .type
if [ "$APPLY" -eq 1 ] || [ -z "$OWNER_TYPE_ARG" ]; then
  OWNER_TYPE="$(gh api "users/$ORG" --jq .type 2>/dev/null)" \
    || die "cannot look up owner '$ORG' (pass --owner-type user|org for an offline dry run). Nothing was changed."
  [ -z "$OWNER_TYPE_ARG" ] || [ "$OWNER_TYPE_ARG" = "$OWNER_TYPE" ] \
    || die "--owner-type says $OWNER_TYPE_ARG but GitHub says '$ORG' is a $OWNER_TYPE. Nothing was changed."
else
  OWNER_TYPE="$OWNER_TYPE_ARG"
  echo "(dry run: owner type taken from --owner-type)"
fi
case "$OWNER_TYPE" in
  User|Organization) ;;
  *) die "unexpected owner type for '$ORG': '$OWNER_TYPE'" ;;
esac
echo "owner $ORG is a $OWNER_TYPE"
if [ "$OWNER_TYPE" = "User" ]; then
  [ "$REL_TYPE" = "User" ] || udie "--release-owner team:... needs an organisation; '$ORG' is a personal account, use a login"
  OWNER_RE="$LOGIN_RE"; OWNER_KIND="login"; DEFAULT_OWNER="$ORG"
else
  [ "$ADMIN_BYPASS" -eq 0 ] && [ "$SELF_REVIEW" -eq 0 ] \
    || udie "--admin-bypass-via-pr and --allow-self-review are for a single-maintainer personal account only ($ADR)"
  OWNER_RE="$SLUG_RE"; OWNER_KIND="team slug"; DEFAULT_OWNER=""
fi
DEV_TEAM="${DEV_TEAM:-${DEFAULT_OWNER:-developers}}"
TL_TEAM="${TL_TEAM:-${DEFAULT_OWNER:-tech-leads}}"
DOMAIN_TEAM="${DOMAIN_TEAM:-${DEFAULT_OWNER:-domain-owners}}"
SEC_TEAM="${SEC_TEAM:-${DEFAULT_OWNER:-security}}"
TEAMS=("$DEV_TEAM" "$TL_TEAM" "$DOMAIN_TEAM" "$SEC_TEAM")
for t in "${TEAMS[@]}"; do [[ "$t" =~ $OWNER_RE ]] || udie "invalid code owner $OWNER_KIND: '$t'"; done

# ---- preflight (apply only) ----
section "Preflight"
PREFLIGHT=(
  "gh auth status"
  "gh api repos/$R"
)
if [ "$OWNER_TYPE" = "Organization" ]; then
  for t in "${TEAMS[@]}"; do PREFLIGHT+=("gh api orgs/$ORG/teams/$t"); done
else
  for t in "${TEAMS[@]}"; do PREFLIGHT+=("gh api users/$t"); done
fi
for l in "${PO_LIST[@]}"; do PREFLIGHT+=("gh api users/$l"); done
if [ "$REL_TYPE" = "Team" ]; then PREFLIGHT+=("gh api orgs/$ORG/teams/$REL_NAME"); else PREFLIGHT+=("gh api users/$REL_NAME"); fi
mapfile -t PREFLIGHT < <(printf '%s\n' "${PREFLIGHT[@]}" | awk '!seen[$0]++')
for c in "${PREFLIGHT[@]}"; do
  echo "+ $c"
  if [ "$APPLY" -eq 1 ]; then
    # shellcheck disable=SC2086  # values were validated above; word splitting is intended
    $c >/dev/null 2>&1 || die "preflight failed: '$c'. Nothing was changed."
  fi
done
if [ "$APPLY" -eq 1 ]; then
  # Read-only probe before any change: GitHub refuses rulesets on a private personal repo (plan).
  echo "+ gh api repos/$R/rulesets"
  out="$(gh api "repos/$R/rulesets" 2>&1)" || api_fail "reading the rulesets of $R (nothing was changed)" "$out" 1
  gh api "repos/$ACCEPTANCE_REPO" >/dev/null 2>&1 \
    || echo "WARNING: cannot see $ACCEPTANCE_REPO with this token (create it from acceptance-repo-example/)."
  DONE+=("preflight passed")
else
  echo "(dry run: preflight not executed)"
fi

# ---- labels ----
section "Labels"
LABELS=(
  "feature|1d76db|Feature request (issue template)"
  "gate:intent-approved|5319e7|Gate: product owner approved the intent"
  "spec|0075ca|Spec PR or spec work"
  "work-item|c5def5|Work item from the plan breakdown"
  "queued|fbca04|Work item waiting for a WIP slot"
  "blocked|b60205|Blocked; needs a human"
  "agent|bfd4f2|Opened by a factory agent"
  "escalated|d93f0b|Escalated to a human (limit reached)"
  "tier:green|0e8a16|Risk tier green"
  "tier:amber|ffa500|Risk tier amber"
  "tier:red|d73a4a|Risk tier red"
  "round:1|ededed|Fix round 1"
  "round:2|cfd3d7|Fix round 2 (last)"
  "factory:builder-failed|B60205|Builder failed; branch holds tests only"
  "needs-human-review|d93f0b|AI review: red tier or a reviewer family missing; a person must review"
  "infra-failure|5a5a5a|A model or tool stayed unavailable; rerun, never a pass"
)
for entry in "${LABELS[@]}"; do
  IFS='|' read -r name color desc <<<"$entry"
  run gh label create "$name" --repo "$R" --color "$color" --description "$desc" --force
done
DONE+=("${#LABELS[@]} labels")

# ---- variables ----
section "Variables"
gate_json='{"gate:intent-approved":['
sep=""
for l in "${PO_LIST[@]}"; do gate_json+="$sep\"$l\""; sep=","; done
gate_json+=']}'
run gh variable set GATE_ROLES --repo "$R" --body "$gate_json"
run gh variable set WIP_LIMIT --repo "$R" --body "$WIP_LIMIT"
run gh variable set ACCEPTANCE_REPO --repo "$R" --body "$ACCEPTANCE_REPO"
DONE+=("variables GATE_ROLES, WIP_LIMIT, ACCEPTANCE_REPO")
if [ -n "$AZURE_ENDPOINT" ]; then
  run gh variable set AZURE_OPENAI_ENDPOINT --repo "$R" --body "${AZURE_ENDPOINT%/}"
  DONE+=("variable AZURE_OPENAI_ENDPOINT")
else
  echo "TODO: set variable AZURE_OPENAI_ENDPOINT (the Azure OpenAI resource; rerun with --azure-openai-endpoint)"
  SKIPPED+=("variable AZURE_OPENAI_ENDPOINT"); TODO+=("set variable AZURE_OPENAI_ENDPOINT")
fi
if [ -n "$BOT_LOGIN" ]; then
  run gh variable set FACTORY_BOT_LOGIN --repo "$R" --body "$BOT_LOGIN"
  DONE+=("variable FACTORY_BOT_LOGIN")
else
  echo "TODO: set variable FACTORY_BOT_LOGIN (the factory-bot App's login; rerun with --factory-bot-login)"
  SKIPPED+=("variable FACTORY_BOT_LOGIN"); TODO+=("set variable FACTORY_BOT_LOGIN")
fi
if [ -n "$CLIENT_ID" ]; then
  run gh variable set FACTORY_APP_CLIENT_ID --repo "$R" --body "$CLIENT_ID"
  DONE+=("variable FACTORY_APP_CLIENT_ID")
else
  echo "TODO: set variable FACTORY_APP_CLIENT_ID (the App's public client id; rerun with --factory-app-client-id)"
  SKIPPED+=("variable FACTORY_APP_CLIENT_ID"); TODO+=("set variable FACTORY_APP_CLIENT_ID")
fi
echo "TODO: set variable FACTORY_APP_ID (legacy: publish reads it until it moves to FACTORY_APP_CLIENT_ID, then remove it)"
TODO+=("set variable FACTORY_APP_ID (legacy)")

# ---- secrets (never set or read here) ----
section "Secrets (set these yourself; this script never touches secrets)"
for s in CLAUDE_CODE_OAUTH_TOKEN AZURE_OPENAI_API_KEY ACCEPTANCE_REPO_TOKEN FACTORY_APP_PRIVATE_KEY; do
  echo "  gh secret set $s --repo $R      # prompts for the value"
  TODO+=("set secret $s")
done
echo "  ACCEPTANCE_REPO_TOKEN: fine-grained, read-only, $ACCEPTANCE_REPO only."

# ---- environments ----
section "Environments"
# Deliberate tightening vs README: both environments only accept deployments
# from protected branches (README only asks for a reviewer on production).
BRANCH_POLICY='{"protected_branches":true,"custom_branch_policies":false}'
printf '{"deployment_branch_policy":%s}' "$BRANCH_POLICY" >"$TMP/env-staging.json"
api_json PUT "repos/$R/environments/staging" "$TMP/env-staging.json"

if [ "$APPLY" -eq 1 ]; then
  if [ "$REL_TYPE" = "Team" ]; then REL_ID="$(gh api "orgs/$ORG/teams/$REL_NAME" --jq .id)"
  else REL_ID="$(gh api "users/$REL_NAME" --jq .id)"; fi
  [[ "$REL_ID" =~ ^[0-9]+$ ]] || die "could not resolve release owner '$RELEASE_OWNER' to a numeric id"
else
  show gh api "$([ "$REL_TYPE" = "Team" ] && echo "orgs/$ORG/teams/$REL_NAME" || echo "users/$REL_NAME")" --jq .id
  REL_ID="\"RESOLVE_AT_APPLY\""
fi
PREVENT_SELF_REVIEW=true
if [ "$SELF_REVIEW" -eq 1 ]; then
  weakening "--allow-self-review: $RELEASE_OWNER may approve their own production deployments."
  PREVENT_SELF_REVIEW=false
  SKIPPED+=("production prevent_self_review (--allow-self-review, $ADR)")
  TODO+=("log every self-approved production deploy under 'Bypass log' in collab/STATUS.md")
fi
printf '{"prevent_self_review":%s,"reviewers":[{"type":"%s","id":%s}],"deployment_branch_policy":%s}' \
  "$PREVENT_SELF_REVIEW" "$REL_TYPE" "$REL_ID" "$BRANCH_POLICY" >"$TMP/env-production.json"
api_json PUT "repos/$R/environments/production" "$TMP/env-production.json" 1
DONE+=("environments staging, production (reviewer: $RELEASE_OWNER, prevent_self_review: $PREVENT_SELF_REVIEW)")
if [ "$REL_TYPE" = "Team" ]; then
  echo "NOTE: team $REL_NAME must have at least read access to $R to be a required reviewer."
fi

# ---- public-repo hardening (brief 009) ----
section "Fork pull requests, vulnerability reports and Discussions"
# Every outside contributor's fork PR waits for a maintainer's approval before any workflow runs.
# SECURITY.md sends reporters to private vulnerability reporting.
printf '{"approval_policy":"all_external_contributors"}' >"$TMP/fork-pr-approval.json"
show gh api "repos/$R" --jq .visibility
VISIBILITY="private"
if [ "$APPLY" -eq 1 ]; then VISIBILITY="$(gh api "repos/$R" --jq .visibility)"; fi
if [ "$APPLY" -eq 1 ] && [ "$VISIBILITY" = "private" ]; then
  show gh api -X PUT "repos/$R/actions/permissions/fork-pr-contributor-approval" --input fork-pr-approval.json
  show gh api -X PUT "repos/$R/private-vulnerability-reporting"
  echo "  skipped: GitHub refuses both settings on a private repo. Rerun --apply right after the flip to public."
  SKIPPED+=("fork PR approval and private vulnerability reporting (repo is private)"); TODO+=("rerun bootstrap --apply right after the repo goes public")
else
  [ "$APPLY" -eq 1 ] || echo "(dry run: on a private repo --apply skips the next two calls with a TODO; GitHub accepts them only once the repo is public)"
  api_json PUT "repos/$R/actions/permissions/fork-pr-contributor-approval" "$TMP/fork-pr-approval.json"
  run gh api -X PUT "repos/$R/private-vulnerability-reporting"
  DONE+=("fork PR workflows need approval for all outside contributors" "private vulnerability reporting on")
fi
printf '{"has_discussions":false}' >"$TMP/repo-settings.json"
api_json PATCH "repos/$R" "$TMP/repo-settings.json"
DONE+=("Discussions off")

# ---- rulesets for the default branch ----
# Repository rulesets, not classic branch protection: classic protection cannot require a merge queue.
# A bypass skips every rule of its ruleset, so the one rule a maintainer may skip lives on its own:
#   factory-default-branch         deletion, force push, required checks, linear history, merge queue.
#                                  Never bypassable.
#   factory-default-branch-review  the review rule, squash merges only. Bypassable only with
#                                  --admin-bypass-via-pr ($ADR): the repository admin role
#                                  (actor_id 5, undocumented) in pull_request mode.
# Apply reads each ruleset back as one line (READBACK) and stops unless it is the expected line:
# who may bypass, each required check with the app it must come from, linear history, merge methods.
READBACK='[.current_user_can_bypass, (.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[] | "check=" + .context + "@" + (.integration_id | tostring)), (.rules[] | select(.type == "required_linear_history") | "linear"), (.rules[] | select(.type == "merge_queue") | "queue=" + .parameters.merge_method), (.rules[] | select(.type == "pull_request") | "merge=" + (.parameters.allowed_merge_methods // [] | join(",")))] | join(" ")'
# put_ruleset NAME BYPASS RULES EXPECTED_READBACK: create or replace the repository ruleset NAME.
put_ruleset() {
  local name="$1" file="$TMP/$1.json" id method rpath out got
  printf '{"name":"%s","target":"branch","enforcement":"active","bypass_actors":[%s],"conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}},"rules":[%s]}' \
    "$name" "$2" "$3" >"$file"
  show gh api "repos/$R/rulesets" --paginate --jq ".[] | select(.name==\"$name\" and .source_type==\"Repository\") | .id"
  if [ "$APPLY" -eq 1 ]; then
    id="$(gh api "repos/$R/rulesets" --paginate \
      --jq ".[] | select(.name==\"$name\" and .source_type==\"Repository\") | .id" | head -n1)"
    if [ -n "$id" ]; then method=PUT; rpath="repos/$R/rulesets/$id"; else method=POST; rpath="repos/$R/rulesets"; fi
    show gh api -X "$method" "$rpath" --input "$name.json"
  else
    echo "(dry run: POST repos/$R/rulesets if '$name' does not exist, else PUT repos/$R/rulesets/<id>)"
    show gh api -X POST "repos/$R/rulesets" --input "$name.json"
  fi
  echo "  payload: $(cat "$file")"
  [ "$APPLY" -eq 1 ] || return 0
  if ! out="$(gh api -X "$method" "$rpath" --input "$file" --jq .id 2>&1)"; then
    if echo "$out" | grep -qi 'merge.queue\|merge_queue'; then
      echo "$out" >&2
      die "GitHub rejected the merge_queue rule (merge queue needs an org-owned repo; private repos need Enterprise Cloud). Nothing weakened. Rerun with --no-merge-queue only if you knowingly accept the default branch without a merge queue."
    fi
    api_fail "$method $rpath (ruleset '$name')" "$out" 1
  fi
  show gh api "repos/$R/rulesets/$out" --jq "$READBACK"
  got="$(gh api "repos/$R/rulesets/$out" --jq "$READBACK")"
  [ "$got" = "$4" ] \
    || die "ruleset '$name' reads back as '$got', expected '$4'. Check it in the repo settings."
}

section "Rulesets on the default branch"
# Only the GitHub Actions app may report the required check (ADR-0013); its id from GET /apps/github-actions.
ACTIONS_APP_ID=15368
MQ_RULE='{"type":"merge_queue","parameters":{"merge_method":"SQUASH","grouping_strategy":"ALLGREEN","max_entries_to_build":5,"min_entries_to_merge":1,"max_entries_to_merge":5,"min_entries_to_merge_wait_minutes":5,"check_response_timeout_minutes":60}}'
CORE_RULES='{"type":"deletion"},{"type":"non_fast_forward"}'
CORE_RULES+=',{"type":"required_status_checks","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"required","integration_id":'"$ACTIONS_APP_ID"'}]}}'
CORE_RULES+=',{"type":"required_linear_history"}'
CORE_EXPECT="never check=required@$ACTIONS_APP_ID linear"
REVIEW_RULES='{"type":"pull_request","parameters":{"required_approving_review_count":1,"require_code_owner_review":true,"dismiss_stale_reviews_on_push":true,"require_last_push_approval":true,"required_review_thread_resolution":false,"allowed_merge_methods":["squash"]}}'
if [ "$NO_MERGE_QUEUE" -eq 1 ]; then
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  echo "WARNING: --no-merge-queue: the default branch will NOT require the merge queue."
  echo "WARNING: README step 4 and stage 6 (merge via queue) are not enforced."
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  SKIPPED+=("merge_queue rule (--no-merge-queue)"); TODO+=("enable the merge queue on the default branch")
else
  CORE_RULES+=",$MQ_RULE"
  CORE_EXPECT+=" queue=SQUASH"
fi
REVIEW_BYPASS="" REVIEW_EXPECT="never"
if [ "$ADMIN_BYPASS" -eq 1 ]; then
  weakening "--admin-bypass-via-pr: repository admins may merge a pull request without an approving review. Required checks still block."
  REVIEW_BYPASS='{"actor_id":5,"actor_type":"RepositoryRole","bypass_mode":"pull_request"}'
  REVIEW_EXPECT="pull_requests_only"
  TODO+=("log every bypassed merge under 'Bypass log' in collab/STATUS.md")
fi
# Review first: if the second write fails, the branch keeps at least the protection it had before.
put_ruleset factory-default-branch-review "$REVIEW_BYPASS" "$REVIEW_RULES" "$REVIEW_EXPECT merge=squash"
put_ruleset factory-default-branch "" "$CORE_RULES" "$CORE_EXPECT"
DONE+=("ruleset factory-default-branch on ~DEFAULT_BRANCH (no bypass actors)")
if [ "$ADMIN_BYPASS" -eq 1 ]; then
  DONE+=("ruleset factory-default-branch-review on ~DEFAULT_BRANCH (bypass: repository admin, pull requests only)")
else
  DONE+=("ruleset factory-default-branch-review on ~DEFAULT_BRANCH (no bypass actors)")
fi

# ---- things this script deliberately does not do ----
section "Notes"
echo "NOTE: Not changed: \"Allow GitHub Actions to create and approve pull requests\". Keep it off:"
echo "      publish opens PRs with the factory-bot App token, and agents must not approve."
# GitHub ignores CODEOWNERS owners it cannot resolve, which silently drops code-owner review.
CODEOWNERS="$(dirname "$0")/../.github/CODEOWNERS"
if [ "$OWNER_TYPE" = "User" ]; then
  UNRESOLVED='@[^[:space:]]+/'; WANT="logins such as @$DEV_TEAM (a personal account has no teams)"
else
  UNRESOLVED='<org>/'; WANT="@$ORG/$DEV_TEAM, @$ORG/$TL_TEAM, @$ORG/$DOMAIN_TEAM, @$ORG/$SEC_TEAM"
fi
if grep -qE "$UNRESOLVED" "$CODEOWNERS"; then
  echo "NOTE: .github/CODEOWNERS has owners GitHub cannot resolve here. Replace them with $WANT."
  TODO+=("fix the owners in .github/CODEOWNERS")
fi

# ---- summary ----
section "Summary ($MODE)"
if [ "$APPLY" -eq 1 ]; then echo "Done:"; else echo "Would do:"; fi
for x in "${DONE[@]}"; do echo "  - $x"; done
echo "Skipped:"
if [ ${#SKIPPED[@]} -eq 0 ]; then echo "  (none)"; else for x in "${SKIPPED[@]}"; do echo "  - $x"; done; fi
echo "TODO (by hand):"
for x in "${TODO[@]}"; do echo "  - $x"; done
