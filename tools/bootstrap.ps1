# One-time GitHub setup for the factory POC (README "One-time setup").
# Creates labels, variables, environments and the two default-branch rulesets with gh.
# Never sets or reads secrets. DRY RUN by default; pass -Apply to execute.
# Keep behaviour and flags in sync with tools/bootstrap.sh.
# Runs on Windows PowerShell 5.1 and PowerShell 7.
[CmdletBinding()]
param(
    [string]$Org = "",
    [string]$Repo = "",
    [string]$PoLogins = "",
    [string]$ReleaseOwner = "",
    [string]$OwnerType = "",
    [string]$DevelopersTeam = "",
    [string]$TechLeadsTeam = "",
    [string]$DomainOwnersTeam = "",
    [string]$SecurityTeam = "",
    [string]$AcceptanceRepo = "",
    [string]$WipLimit = "3",
    [string]$AzureOpenaiEndpoint = "",
    [string]$FactoryBotLogin = "",
    [string]$FactoryAppClientId = "",
    [switch]$NoMergeQueue,
    [switch]$AdminBypassViaPr,
    [switch]$AllowSelfReview,
    [switch]$Apply,
    [switch]$Help
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2

function Show-Usage {
    @'
Usage: tools/bootstrap.ps1 -Org ORG -Repo REPO -PoLogins LOGIN[,LOGIN...]
                           -ReleaseOwner LOGIN|team:SLUG [options]

Required:
  -Org ORG                      Repository owner: an organisation or a personal account
  -Repo REPO                    Repository name
  -PoLogins A,B                 Product owner logins -> GATE_ROLES (quote it: -PoLogins "a,b")
  -ReleaseOwner X               Production approver: a login, or team:<slug> (organisations only)

Owner type:
  -OwnerType user|org           What ORG is. Dry run: skips the read-only lookup (no gh call at all).
                                Apply: always looked up, and must match when given.

Code owners. Organisation: team slugs that must exist in ORG.
Personal account: logins (there are no teams), each defaulting to ORG.
  -DevelopersTeam X             default: developers
  -TechLeadsTeam X              default: tech-leads
  -DomainOwnersTeam X           default: domain-owners
  -SecurityTeam X               default: security

Approved weakenings (personal account only, off by default; docs/adr/0002-single-maintainer-bypass.md):
  -AdminBypassViaPr             Repository admins may skip the review rule, through a pull request only
  -AllowSelfReview              The production reviewer may approve their own deployment

Optional:
  -AcceptanceRepo OWNER/NAME    default: <org>/meter-acceptance
  -WipLimit N                   default: 3
  -AzureOpenaiEndpoint URL      AZURE_OPENAI_ENDPOINT, such as https://<resource>.openai.azure.com
                                (skipped with a TODO if absent)
  -FactoryBotLogin LOGIN        FACTORY_BOT_LOGIN, the App's bot login such as my-app[bot]
                                (skipped with a TODO if absent; agents then start only for maintainers)
  -FactoryAppClientId ID        FACTORY_APP_CLIENT_ID, the App's public client id such as Iv23li...
                                (skipped with a TODO if absent)
  -NoMergeQueue                 Drop the merge_queue rule (weakens protection; loud warning)
  -Apply                        Execute. Without it, only print what would run.
  -Help                         Show this help
'@
}

function Stop-Script([string]$msg) { [Console]::Error.WriteLine("ERROR: $msg"); exit 1 }
function Stop-Usage([string]$msg) {
    [Console]::Error.WriteLine("ERROR: $msg")
    [Console]::Error.WriteLine("")
    [Console]::Error.WriteLine((Show-Usage))
    exit 2
}

if ($Help) { Show-Usage; exit 0 }

# ---- validate input (also keeps values safe inside URL paths and JSON) ----
$missing = @()
if (-not $Org) { $missing += "-Org" }
if (-not $Repo) { $missing += "-Repo" }
if (-not $PoLogins) { $missing += "-PoLogins" }
if (-not $ReleaseOwner) { $missing += "-ReleaseOwner" }
if ($missing.Count -gt 0) { Stop-Usage ("missing required: " + ($missing -join " ")) }

$LoginRe = '^[A-Za-z0-9]([A-Za-z0-9-]{0,38})$'
$SlugRe = '^[A-Za-z0-9][A-Za-z0-9._-]*$'
$NameRe = '^[A-Za-z0-9._-]+$'

if ($Org -notmatch $LoginRe) { Stop-Usage "invalid -Org: $Org" }
if ($Repo -notmatch $NameRe) { Stop-Usage "invalid -Repo: $Repo" }
$PoList = @($PoLogins -split ',')
foreach ($l in $PoList) { if ($l -notmatch $LoginRe) { Stop-Usage "invalid login in -PoLogins: '$l'" } }
switch ($OwnerType) {
    "" { break }
    "user" { $OwnerType = "User"; break }
    "org" { $OwnerType = "Organization"; break }
    default { Stop-Usage "-OwnerType must be user or org: $OwnerType" }
}
if ($ReleaseOwner.StartsWith("team:")) {
    $RelType = "Team"; $RelName = $ReleaseOwner.Substring(5)
    if ($RelName -notmatch $SlugRe) { Stop-Usage "invalid team slug in -ReleaseOwner: $RelName" }
} else {
    $RelType = "User"; $RelName = $ReleaseOwner
    if ($RelName -notmatch $LoginRe) { Stop-Usage "invalid login in -ReleaseOwner: $RelName" }
}
if (-not $AcceptanceRepo) { $AcceptanceRepo = "$Org/meter-acceptance" }
if ($AcceptanceRepo -notmatch '^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$') { Stop-Usage "invalid -AcceptanceRepo: $AcceptanceRepo" }
if ($WipLimit -notmatch '^[1-9][0-9]*$') { Stop-Usage "-WipLimit must be a positive integer: $WipLimit" }
if ($FactoryBotLogin -and $FactoryBotLogin -cnotmatch '^[A-Za-z0-9][A-Za-z0-9-]*\[bot\]$') { Stop-Usage "-FactoryBotLogin must look like <app-slug>[bot]: $FactoryBotLogin" }
if ($AzureOpenaiEndpoint -and $AzureOpenaiEndpoint -cnotmatch '^https://[a-z0-9][a-z0-9-]*\.openai\.azure\.com/?$') { Stop-Usage "-AzureOpenaiEndpoint must look like https://<resource>.openai.azure.com: $AzureOpenaiEndpoint" }
if ($FactoryAppClientId -and $FactoryAppClientId -cnotmatch '^Iv[0-9A-Za-z.]+$') { Stop-Usage "-FactoryAppClientId must look like Iv23...: $FactoryAppClientId" }

$R = "$Org/$Repo"
$Adr = "docs/adr/0002-single-maintainer-bypass.md"
$Done = New-Object System.Collections.Generic.List[string]
$Skipped = New-Object System.Collections.Generic.List[string]
$Todo = New-Object System.Collections.Generic.List[string]
$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("bootstrap-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Tmp | Out-Null
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

# ---- helpers ----
function Format-Arg([string]$a) {  # quote an argument for display only (same style as bootstrap.sh)
    if ($a -match '^[A-Za-z0-9_./:=,@+-]+$') { return $a }
    return "'" + ($a -replace "'", "'\''") + "'"
}
function Show-Cmd([string[]]$cmd) { Write-Output ("+ " + (($cmd | ForEach-Object { Format-Arg $_ }) -join " ")) }
# Windows PowerShell 5.1 (and Legacy argument passing) strips embedded double quotes
# when calling native programs; escape them so gh receives the value intact.
function ConvertTo-NativeArg([string]$a) {
    $legacy = $PSVersionTable.PSVersion -lt [version]"7.3"
    if (-not $legacy) {
        $mode = Get-Variable -Name PSNativeCommandArgumentPassing -ValueOnly -ErrorAction SilentlyContinue
        if ($mode -eq "Legacy") { $legacy = $true }
    }
    if ($legacy) { return ($a -replace '"', '\"') }
    return $a
}
# Run gh; returns stdout as a string; throws on non-zero exit. Output is not echoed.
function Invoke-Gh([string[]]$ghArgs, [switch]$Quiet) {
    $ErrorActionPreference = "Continue"   # native stderr must not become a terminating error in 5.1
    $native = @($ghArgs | ForEach-Object { ConvertTo-NativeArg $_ })
    $out = (& gh @native 2>&1 | ForEach-Object { "$_" }) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw "gh $($ghArgs -join ' ') failed (exit $LASTEXITCODE):`n$out" }
    return $out
}
function Invoke-Step([string[]]$cmd) {
    Show-Cmd $cmd
    if ($Apply) { Invoke-Gh $cmd[1..($cmd.Count - 1)] | Out-Null }
}
function Write-Json([object]$obj, [string]$name) {
    $path = Join-Path $Tmp $name
    $json = ConvertTo-Json -InputObject $obj -Depth 20 -Compress
    [IO.File]::WriteAllText($path, $json, $Utf8NoBom)
    return $path
}
function Invoke-ApiJson([string]$method, [string]$path, [string]$file, [switch]$PlanSensitive) {
    Show-Cmd @("gh", "api", "-X", $method, $path, "--input", (Split-Path $file -Leaf))
    Write-Output ("  payload: " + [IO.File]::ReadAllText($file))
    if ($Apply) {
        try { Invoke-Gh @("api", "-X", $method, $path, "--input", $file) | Out-Null }
        catch { Stop-ApiFail "$method $path" "$_" $PlanSensitive }
    }
}
# A 403/422 on rulesets or environment reviewers usually means the account's plan lacks the feature.
function Stop-ApiFail([string]$what, [string]$out, [bool]$planSensitive) {
    [Console]::Error.WriteLine($out)
    if ($out -match 'upgrade|GitHub Pro|make this repository public|billing|\bplan\b' -or ($planSensitive -and $out -match 'HTTP (403|422)')) {
        Stop-Script "GitHub refused $what, most likely for plan reasons: on a personal account, rulesets and environment required reviewers need a public repo (or GitHub Pro). Branch protection is NOT in place. Make the repo public, then rerun -Apply."
    }
    Stop-Script "$what failed (see above)."
}
function Write-Weakening([string]$what) {  # one loud banner per approved weakening
    Write-Output "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    Write-Output "WARNING: $what"
    Write-Output "WARNING: approved for a single maintainer only; revert trigger in $Adr"
    Write-Output "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
}
function Write-Section([string]$s) { Write-Output ""; Write-Output "== $s ==" }

try {
    if ($Apply) { $Mode = "APPLY" } else { $Mode = "DRY RUN" }
    Write-Output "bootstrap: $R  mode: $Mode"
    if (-not $Apply) { Write-Output "Dry run: nothing is changed; the only gh call is a read-only owner lookup when -OwnerType is absent. Pass -Apply to execute." }

    # ---- owner type: a personal account has no teams and gets the brief 008 adaptations ----
    Write-Section "Owner"
    Show-Cmd @("gh", "api", "users/$Org", "--jq", ".type")
    if ($Apply -or -not $OwnerType) {
        try { $found = (Invoke-Gh @("api", "users/$Org", "--jq", ".type")).Trim() }
        catch { Stop-Script "cannot look up owner '$Org' (pass -OwnerType user|org for an offline dry run). Nothing was changed." }
        if ($OwnerType -and $OwnerType -ne $found) { Stop-Script "-OwnerType says $OwnerType but GitHub says '$Org' is a $found. Nothing was changed." }
        $OwnerType = $found
    } else {
        Write-Output "(dry run: owner type taken from -OwnerType)"
    }
    if ($OwnerType -cne "User" -and $OwnerType -cne "Organization") { Stop-Script "unexpected owner type for '$Org': '$OwnerType'" }
    Write-Output "owner $Org is a $OwnerType"
    if ($OwnerType -eq "User") {
        if ($RelType -ne "User") { Stop-Usage "-ReleaseOwner team:... needs an organisation; '$Org' is a personal account, use a login" }
        $ownerRe = $LoginRe; $ownerKind = "login"
        $defaults = @($Org, $Org, $Org, $Org)
    } else {
        if ($AdminBypassViaPr -or $AllowSelfReview) { Stop-Usage "-AdminBypassViaPr and -AllowSelfReview are for a single-maintainer personal account only ($Adr)" }
        $ownerRe = $SlugRe; $ownerKind = "team slug"
        $defaults = @("developers", "tech-leads", "domain-owners", "security")
    }
    if (-not $DevelopersTeam) { $DevelopersTeam = $defaults[0] }
    if (-not $TechLeadsTeam) { $TechLeadsTeam = $defaults[1] }
    if (-not $DomainOwnersTeam) { $DomainOwnersTeam = $defaults[2] }
    if (-not $SecurityTeam) { $SecurityTeam = $defaults[3] }
    $Teams = @($DevelopersTeam, $TechLeadsTeam, $DomainOwnersTeam, $SecurityTeam)
    foreach ($t in $Teams) { if ($t -notmatch $ownerRe) { Stop-Usage "invalid code owner ${ownerKind}: '$t'" } }

    # ---- preflight (apply only) ----
    Write-Section "Preflight"
    $preflight = New-Object System.Collections.Generic.List[object]
    $preflight.Add(@("auth", "status"))
    $preflight.Add(@("api", "repos/$R"))
    if ($OwnerType -eq "Organization") { foreach ($t in $Teams) { $preflight.Add(@("api", "orgs/$Org/teams/$t")) } }
    else { foreach ($t in $Teams) { $preflight.Add(@("api", "users/$t")) } }
    foreach ($l in $PoList) { $preflight.Add(@("api", "users/$l")) }
    if ($RelType -eq "Team") { $preflight.Add(@("api", "orgs/$Org/teams/$RelName")) } else { $preflight.Add(@("api", "users/$RelName")) }
    $seen = @{}
    foreach ($c in $preflight) {
        $key = $c -join " "
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        Write-Output ("+ gh " + ($c -join " "))
        if ($Apply) {
            try { Invoke-Gh $c | Out-Null } catch { Stop-Script "preflight failed: 'gh $($c -join ' ')'. Nothing was changed." }
        }
    }
    if ($Apply) {
        # Read-only probe before any change: GitHub refuses rulesets on a private personal repo (plan).
        Show-Cmd @("gh", "api", "repos/$R/rulesets")
        try { Invoke-Gh @("api", "repos/$R/rulesets") | Out-Null }
        catch { Stop-ApiFail "reading the rulesets of $R (nothing was changed)" "$_" $true }
        try { Invoke-Gh @("api", "repos/$AcceptanceRepo") | Out-Null }
        catch { Write-Output "WARNING: cannot see $AcceptanceRepo with this token (create it from acceptance-repo-example/)." }
        $Done.Add("preflight passed")
    } else {
        Write-Output "(dry run: preflight not executed)"
    }

    # ---- labels ----
    Write-Section "Labels"
    $labels = @(
        @("feature", "1d76db", "Feature request (issue template)"),
        @("gate:intent-approved", "5319e7", "Gate: product owner approved the intent"),
        @("spec", "0075ca", "Spec PR or spec work"),
        @("work-item", "c5def5", "Work item from the plan breakdown"),
        @("queued", "fbca04", "Work item waiting for a WIP slot"),
        @("blocked", "b60205", "Blocked; needs a human"),
        @("agent", "bfd4f2", "Opened by a factory agent"),
        @("escalated", "d93f0b", "Escalated to a human (limit reached)"),
        @("tier:green", "0e8a16", "Risk tier green"),
        @("tier:amber", "ffa500", "Risk tier amber"),
        @("tier:red", "d73a4a", "Risk tier red"),
        @("round:1", "ededed", "Fix round 1"),
        @("round:2", "cfd3d7", "Fix round 2 (last)"),
        @("factory:builder-failed", "B60205", "Builder failed; branch holds tests only"),
        @("needs-human-review", "d93f0b", "AI review: red tier or a reviewer family missing; a person must review"),
        @("infra-failure", "5a5a5a", "A model or tool stayed unavailable; rerun, never a pass")
    )
    foreach ($lb in $labels) {
        Invoke-Step @("gh", "label", "create", $lb[0], "--repo", $R, "--color", $lb[1], "--description", $lb[2], "--force")
    }
    $Done.Add("$($labels.Count) labels")

    # ---- variables ----
    Write-Section "Variables"
    $gate = [ordered]@{ "gate:intent-approved" = @($PoList) }
    $gateJson = ConvertTo-Json -InputObject $gate -Depth 5 -Compress
    Invoke-Step @("gh", "variable", "set", "GATE_ROLES", "--repo", $R, "--body", $gateJson)
    Invoke-Step @("gh", "variable", "set", "WIP_LIMIT", "--repo", $R, "--body", $WipLimit)
    Invoke-Step @("gh", "variable", "set", "ACCEPTANCE_REPO", "--repo", $R, "--body", $AcceptanceRepo)
    $Done.Add("variables GATE_ROLES, WIP_LIMIT, ACCEPTANCE_REPO")
    if ($AzureOpenaiEndpoint) {
        Invoke-Step @("gh", "variable", "set", "AZURE_OPENAI_ENDPOINT", "--repo", $R, "--body", $AzureOpenaiEndpoint.TrimEnd("/"))
        $Done.Add("variable AZURE_OPENAI_ENDPOINT")
    } else {
        Write-Output "TODO: set variable AZURE_OPENAI_ENDPOINT (the Azure OpenAI resource; rerun with -AzureOpenaiEndpoint)"
        $Skipped.Add("variable AZURE_OPENAI_ENDPOINT"); $Todo.Add("set variable AZURE_OPENAI_ENDPOINT")
    }
    if ($FactoryBotLogin) {
        Invoke-Step @("gh", "variable", "set", "FACTORY_BOT_LOGIN", "--repo", $R, "--body", $FactoryBotLogin)
        $Done.Add("variable FACTORY_BOT_LOGIN")
    } else {
        Write-Output "TODO: set variable FACTORY_BOT_LOGIN (the factory-bot App's login; rerun with -FactoryBotLogin)"
        $Skipped.Add("variable FACTORY_BOT_LOGIN"); $Todo.Add("set variable FACTORY_BOT_LOGIN")
    }
    if ($FactoryAppClientId) {
        Invoke-Step @("gh", "variable", "set", "FACTORY_APP_CLIENT_ID", "--repo", $R, "--body", $FactoryAppClientId)
        $Done.Add("variable FACTORY_APP_CLIENT_ID")
    } else {
        Write-Output "TODO: set variable FACTORY_APP_CLIENT_ID (the App's public client id; rerun with -FactoryAppClientId)"
        $Skipped.Add("variable FACTORY_APP_CLIENT_ID"); $Todo.Add("set variable FACTORY_APP_CLIENT_ID")
    }
    Write-Output "TODO: set variable FACTORY_APP_ID (legacy: publish reads it until it moves to FACTORY_APP_CLIENT_ID, then remove it)"
    $Todo.Add("set variable FACTORY_APP_ID (legacy)")

    # ---- secrets (never set or read here) ----
    Write-Section "Secrets (set these yourself; this script never touches secrets)"
    foreach ($s in @("CLAUDE_CODE_OAUTH_TOKEN", "AZURE_OPENAI_API_KEY", "ACCEPTANCE_REPO_TOKEN", "FACTORY_APP_PRIVATE_KEY")) {
        Write-Output "  gh secret set $s --repo $R      # prompts for the value"
        $Todo.Add("set secret $s")
    }
    Write-Output "  ACCEPTANCE_REPO_TOKEN: fine-grained, read-only, $AcceptanceRepo only."

    # ---- environments ----
    Write-Section "Environments"
    # Deliberate tightening vs README: both environments only accept deployments
    # from protected branches (README only asks for a reviewer on production).
    $branchPolicy = [ordered]@{ protected_branches = $true; custom_branch_policies = $false }
    $f = Write-Json ([ordered]@{ deployment_branch_policy = $branchPolicy }) "env-staging.json"
    Invoke-ApiJson "PUT" "repos/$R/environments/staging" $f

    if ($RelType -eq "Team") { $relPath = "orgs/$Org/teams/$RelName" } else { $relPath = "users/$RelName" }
    if ($Apply) {
        $relId = (Invoke-Gh @("api", $relPath, "--jq", ".id")).Trim()
        if ($relId -notmatch '^[0-9]+$') { Stop-Script "could not resolve release owner '$ReleaseOwner' to a numeric id" }
        $relId = [long]$relId
    } else {
        Show-Cmd @("gh", "api", $relPath, "--jq", ".id")
        $relId = "RESOLVE_AT_APPLY"
    }
    $preventSelfReview = $true
    if ($AllowSelfReview) {
        Write-Weakening "-AllowSelfReview: $ReleaseOwner may approve their own production deployments."
        $preventSelfReview = $false
        $Skipped.Add("production prevent_self_review (-AllowSelfReview, $Adr)")
        $Todo.Add("log every self-approved production deploy under 'Bypass log' in collab/STATUS.md")
    }
    $prod = [ordered]@{
        prevent_self_review      = $preventSelfReview
        reviewers                = @([ordered]@{ type = $RelType; id = $relId })
        deployment_branch_policy = $branchPolicy
    }
    $f = Write-Json $prod "env-production.json"
    Invoke-ApiJson "PUT" "repos/$R/environments/production" $f -PlanSensitive
    $Done.Add("environments staging, production (reviewer: $ReleaseOwner, prevent_self_review: $($preventSelfReview.ToString().ToLower()))")
    if ($RelType -eq "Team") {
        Write-Output "NOTE: team $RelName must have at least read access to $R to be a required reviewer."
    }

    # ---- public-repo hardening (brief 009) ----
    Write-Section "Fork pull requests, vulnerability reports and Discussions"
    # Every outside contributor's fork PR waits for a maintainer's approval before any workflow runs.
    # SECURITY.md sends reporters to private vulnerability reporting.
    $f = Write-Json ([ordered]@{ approval_policy = "all_external_contributors" }) "fork-pr-approval.json"
    Show-Cmd @("gh", "api", "repos/$R", "--jq", ".visibility")
    $visibility = "private"
    if ($Apply) { $visibility = (Invoke-Gh @("api", "repos/$R", "--jq", ".visibility")).Trim() }
    if ($Apply -and $visibility -eq "private") {
        Show-Cmd @("gh", "api", "-X", "PUT", "repos/$R/actions/permissions/fork-pr-contributor-approval", "--input", "fork-pr-approval.json")
        Show-Cmd @("gh", "api", "-X", "PUT", "repos/$R/private-vulnerability-reporting")
        Write-Output "  skipped: GitHub refuses both settings on a private repo. Rerun -Apply right after the flip to public."
        $Skipped.Add("fork PR approval and private vulnerability reporting (repo is private)"); $Todo.Add("rerun bootstrap -Apply right after the repo goes public")
    } else {
        if (-not $Apply) { Write-Output "(dry run: on a private repo -Apply skips the next two calls with a TODO; GitHub accepts them only once the repo is public)" }
        Invoke-ApiJson "PUT" "repos/$R/actions/permissions/fork-pr-contributor-approval" $f
        Invoke-Step @("gh", "api", "-X", "PUT", "repos/$R/private-vulnerability-reporting")
        $Done.Add("fork PR workflows need approval for all outside contributors")
        $Done.Add("private vulnerability reporting on")
    }
    $f = Write-Json ([ordered]@{ has_discussions = $false }) "repo-settings.json"
    Invoke-ApiJson "PATCH" "repos/$R" $f
    $Done.Add("Discussions off")

    # ---- rulesets for the default branch ----
    # Repository rulesets, not classic branch protection: classic protection cannot require a merge queue.
    # A bypass skips every rule of its ruleset, so the one rule a maintainer may skip lives on its own:
    #   factory-default-branch         deletion, force push, required checks, linear history, merge queue.
    #                                  Never bypassable.
    #   factory-default-branch-review  the review rule, squash merges only. Bypassable only with
    #                                  -AdminBypassViaPr ($Adr): the repository admin role
    #                                  (actor_id 5, undocumented) in pull_request mode.
    # Apply reads each ruleset back as one line ($readback) and stops unless it is the expected line:
    # who may bypass, each required check with the app it must come from, linear history, merge methods.
    # Same filter as bootstrap.sh; Invoke-Gh keeps its double quotes intact on Windows PowerShell 5.1.
    $readback = '[.current_user_can_bypass, (.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[] | "check=" + .context + "@" + (.integration_id | tostring)), (.rules[] | select(.type == "required_linear_history") | "linear"), (.rules[] | select(.type == "merge_queue") | "queue=" + .parameters.merge_method), (.rules[] | select(.type == "pull_request") | "merge=" + (.parameters.allowed_merge_methods // [] | join(",")))] | join(" ")'
    # Set-Ruleset: create or replace the repository ruleset $name.
    function Set-Ruleset([string]$name, [object[]]$bypass, [object[]]$rules, [string]$expectReadback) {
        $ruleset = [ordered]@{
            name          = $name
            target        = "branch"
            enforcement   = "active"
            bypass_actors = $bypass
            conditions    = [ordered]@{ ref_name = [ordered]@{ include = @("~DEFAULT_BRANCH"); exclude = @() } }
            rules         = $rules
        }
        $rsFile = Write-Json $ruleset "$name.json"
        # Lookup is parsed in PowerShell (an inline --jq filter would need fragile quoting in 5.1).
        Show-Cmd @("gh", "api", "repos/$R/rulesets", "--paginate", "--slurp")
        if ($Apply) {
            $pages = Invoke-Gh @("api", "repos/$R/rulesets", "--paginate", "--slurp") | ConvertFrom-Json
            $existing = @($pages | ForEach-Object { $_ } | Where-Object { $_.name -eq $name -and $_.source_type -eq "Repository" })
            if ($existing.Count -gt 0) { $method = "PUT"; $rpath = "repos/$R/rulesets/$($existing[0].id)" }
            else { $method = "POST"; $rpath = "repos/$R/rulesets" }
            Show-Cmd @("gh", "api", "-X", $method, $rpath, "--input", "$name.json")
        } else {
            Write-Output "(dry run: POST repos/$R/rulesets if '$name' does not exist, else PUT repos/$R/rulesets/<id>)"
            Show-Cmd @("gh", "api", "-X", "POST", "repos/$R/rulesets", "--input", "$name.json")
        }
        Write-Output ("  payload: " + [IO.File]::ReadAllText($rsFile))
        if (-not $Apply) { return }
        try { $rsId = (Invoke-Gh @("api", "-X", $method, $rpath, "--input", $rsFile, "--jq", ".id")).Trim() }
        catch {
            $err = "$_"
            if ($err -match 'merge.queue') {
                [Console]::Error.WriteLine($err)
                Stop-Script "GitHub rejected the merge_queue rule (merge queue needs an org-owned repo; private repos need Enterprise Cloud). Nothing weakened. Rerun with -NoMergeQueue only if you knowingly accept the default branch without a merge queue."
            }
            Stop-ApiFail "$method $rpath (ruleset '$name')" $err $true
        }
        Show-Cmd @("gh", "api", "repos/$R/rulesets/$rsId", "--jq", $readback)
        $got = (Invoke-Gh @("api", "repos/$R/rulesets/$rsId", "--jq", $readback)).Trim()
        if ($got -cne $expectReadback) { Stop-Script "ruleset '$name' reads back as '$got', expected '$expectReadback'. Check it in the repo settings." }
    }

    Write-Section "Rulesets on the default branch"
    # Only the GitHub Actions app may report the required check (ADR-0013); its id from GET /apps/github-actions.
    $actionsAppId = 15368
    $coreRules = New-Object System.Collections.Generic.List[object]
    $coreRules.Add([ordered]@{ type = "deletion" })
    $coreRules.Add([ordered]@{ type = "non_fast_forward" })
    $coreRules.Add([ordered]@{ type = "required_status_checks"; parameters = [ordered]@{
                strict_required_status_checks_policy = $true
                required_status_checks               = @([ordered]@{ context = "required"; integration_id = $actionsAppId })
            }
        })
    $coreRules.Add([ordered]@{ type = "required_linear_history" })
    $coreExpect = "never check=required@$actionsAppId linear"
    $reviewRules = @([ordered]@{ type = "pull_request"; parameters = [ordered]@{
                required_approving_review_count   = 1
                require_code_owner_review         = $true
                dismiss_stale_reviews_on_push     = $true
                require_last_push_approval        = $true
                required_review_thread_resolution = $false
                allowed_merge_methods             = @("squash")
            }
        })
    if ($NoMergeQueue) {
        Write-Output "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        Write-Output "WARNING: -NoMergeQueue: the default branch will NOT require the merge queue."
        Write-Output "WARNING: README step 4 and stage 6 (merge via queue) are not enforced."
        Write-Output "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        $Skipped.Add("merge_queue rule (-NoMergeQueue)"); $Todo.Add("enable the merge queue on the default branch")
    } else {
        $coreRules.Add([ordered]@{ type = "merge_queue"; parameters = [ordered]@{
                    merge_method                      = "SQUASH"
                    grouping_strategy                 = "ALLGREEN"
                    max_entries_to_build              = 5
                    min_entries_to_merge              = 1
                    max_entries_to_merge              = 5
                    min_entries_to_merge_wait_minutes = 5
                    check_response_timeout_minutes    = 60
                }
            })
        $coreExpect += " queue=SQUASH"
    }
    $reviewBypass = @()
    $reviewExpect = "never"
    if ($AdminBypassViaPr) {
        Write-Weakening "-AdminBypassViaPr: repository admins may merge a pull request without an approving review. Required checks still block."
        $reviewBypass = @([ordered]@{ actor_id = 5; actor_type = "RepositoryRole"; bypass_mode = "pull_request" })
        $reviewExpect = "pull_requests_only"
        $Todo.Add("log every bypassed merge under 'Bypass log' in collab/STATUS.md")
    }
    # Review first: if the second write fails, the branch keeps at least the protection it had before.
    Set-Ruleset "factory-default-branch-review" $reviewBypass $reviewRules "$reviewExpect merge=squash"
    Set-Ruleset "factory-default-branch" @() $coreRules.ToArray() $coreExpect
    $Done.Add("ruleset factory-default-branch on ~DEFAULT_BRANCH (no bypass actors)")
    if ($AdminBypassViaPr) { $Done.Add("ruleset factory-default-branch-review on ~DEFAULT_BRANCH (bypass: repository admin, pull requests only)") }
    else { $Done.Add("ruleset factory-default-branch-review on ~DEFAULT_BRANCH (no bypass actors)") }

    # ---- things this script deliberately does not do ----
    Write-Section "Notes"
    Write-Output "NOTE: Not changed: ""Allow GitHub Actions to create and approve pull requests"". Keep it off:"
    Write-Output "      publish opens PRs with the factory-bot App token, and agents must not approve."
    # GitHub ignores CODEOWNERS owners it cannot resolve, which silently drops code-owner review.
    $codeowners = [IO.File]::ReadAllText((Join-Path $PSScriptRoot "..\.github\CODEOWNERS"))
    if ($OwnerType -eq "User") {
        $unresolved = '@\S+/'; $want = "logins such as @$DevelopersTeam (a personal account has no teams)"
    } else {
        $unresolved = '<org>/'; $want = "@$Org/$DevelopersTeam, @$Org/$TechLeadsTeam, @$Org/$DomainOwnersTeam, @$Org/$SecurityTeam"
    }
    if ($codeowners -match $unresolved) {
        Write-Output "NOTE: .github/CODEOWNERS has owners GitHub cannot resolve here. Replace them with $want."
        $Todo.Add("fix the owners in .github/CODEOWNERS")
    }

    # ---- summary ----
    Write-Section "Summary ($Mode)"
    if ($Apply) { Write-Output "Done:" } else { Write-Output "Would do:" }
    foreach ($x in $Done) { Write-Output "  - $x" }
    Write-Output "Skipped:"
    if ($Skipped.Count -eq 0) { Write-Output "  (none)" } else { foreach ($x in $Skipped) { Write-Output "  - $x" } }
    Write-Output "TODO (by hand):"
    foreach ($x in $Todo) { Write-Output "  - $x" }
}
catch {
    [Console]::Error.WriteLine("ERROR: $_")
    [Console]::Error.WriteLine("Stopping. Rerun is safe: every step is idempotent.")
    exit 1
}
finally {
    Remove-Item -Recurse -Force -LiteralPath $Tmp -ErrorAction SilentlyContinue
}
