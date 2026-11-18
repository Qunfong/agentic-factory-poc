# Pre-publish scan (brief 009), run before a repository goes public:
#   1. gitleaks over the history of every ref, in the pinned Docker image, repo mounted read-only.
#   2. A deny-list of names (kept outside the repo) over every commit's file contents, file paths,
#      author and committer, and message, plus every ref name and annotated tag.
# Prints counts and commit/file ids only, never a matched name. Exit 0 only when both pass,
# 1 when either finds something, 2 when the scan could not run.
# Keep behaviour and flags in sync with tools/prepublish_check.sh. Runs on Windows PowerShell 5.1 and PowerShell 7.
[CmdletBinding()]
param(
    [string]$DenyList = "",
    [string]$Repo = ".",
    [switch]$Help
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2
$Image = 'zricethezav/gitleaks:v8.24.0@sha256:2bcceac45179b3a91bff11a824d0fb952585b429e54fc928728b1d4d5c3e5176'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }

function Show-Usage {
    @'
Usage: tools/prepublish_check.ps1 -DenyList FILE [-Repo DIR]

  -DenyList FILE  One name per line (blank lines and lines starting with # are ignored).
                  Must live outside the repository. Matching is case-insensitive substring.
  -Repo DIR       A full clone to scan (default: the current directory). Not a linked worktree.
'@
}
function Stop-Scan([string]$msg) { [Console]::Error.WriteLine("ERROR: $msg"); exit 2 }

# Runs a native command; returns its stdout lines and leaves the exit code in $LASTEXITCODE.
function Invoke-Native([string]$exe, [string[]]$argv) {
    $ErrorActionPreference = "Continue"
    $out = & $exe @argv 2>$null
    return @($out | ForEach-Object { "$_" })
}
function Invoke-Git([string[]]$argv, [int[]]$ok = @(0)) {
    $out = Invoke-Native "git" (@("-C", $script:Repo) + $argv)
    if ($ok -notcontains $LASTEXITCODE) { Stop-Scan "git $($argv[0]) failed (exit $LASTEXITCODE)" }
    return $out
}

if ($Help) { Show-Usage; exit 0 }
if (-not $DenyList) { [Console]::Error.WriteLine((Show-Usage)); Stop-Scan "-DenyList is required" }
if (-not (Test-Path -LiteralPath $DenyList -PathType Leaf)) { Stop-Scan "deny-list not found: $DenyList" }
$top = @(Invoke-Native "git" @("-C", $Repo, "rev-parse", "--show-toplevel"))
if ($LASTEXITCODE -ne 0 -or -not $top) { Stop-Scan "not a git repository: $Repo" }
$Repo = (Resolve-Path -LiteralPath $top[0]).ProviderPath.TrimEnd('\', '/')
if (-not (Test-Path -LiteralPath (Join-Path $Repo ".git") -PathType Container)) {
    Stop-Scan "$Repo is a linked worktree or submodule; scan a full clone"
}
$denyDir = (Resolve-Path -LiteralPath (Split-Path -Parent (Resolve-Path -LiteralPath $DenyList).ProviderPath)).ProviderPath.TrimEnd('\', '/')
$sep = [IO.Path]::DirectorySeparatorChar
if (($denyDir + $sep).StartsWith($Repo + $sep, [StringComparison]::OrdinalIgnoreCase)) {
    Stop-Scan "the deny-list must live outside the repository"
}

$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("prepublish-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Tmp | Out-Null
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
try {
    $terms = @([IO.File]::ReadAllLines((Resolve-Path -LiteralPath $DenyList).ProviderPath) |
        ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith("#") })
    if ($terms.Count -eq 0) { Stop-Scan "the deny-list holds no names" }
    $Pat = Join-Path $Tmp "patterns"
    [IO.File]::WriteAllText($Pat, (($terms -join "`n") + "`n"), $Utf8NoBom)
    $lower = @($terms | ForEach-Object { $_.ToLowerInvariant() })
    function Test-Deny([string]$text) {
        $t = $text.ToLowerInvariant()
        foreach ($term in $lower) { if ($t.Contains($term)) { return $true } }
        return $false
    }

    # ---- 1. gitleaks ----
    [IO.File]::WriteAllText((Join-Path $Tmp "ids.tmpl"), '{{range .}}{{.Commit}} {{.File}} {{.RuleID}}{{"\n"}}{{end}}', $Utf8NoBom)
    $dockerArgs = @("run", "--rm", "--network", "none",
        "-e", "GIT_CONFIG_COUNT=1", "-e", "GIT_CONFIG_KEY_0=safe.directory", "-e", "GIT_CONFIG_VALUE_0=*",
        "-v", "${Repo}:/repo:ro", "-v", "${Tmp}:/out",
        $Image, "git", "/repo", "--log-opts=--all", "--redact", "--no-banner", "--exit-code", "3",
        "--report-format", "template", "--report-template", "/out/ids.tmpl", "--report-path", "/out/leaks.txt")
    $ErrorActionPreference = "Continue"
    $log = @(& docker @dockerArgs 2>&1 | ForEach-Object { "$_" })
    $rc = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    $leakFile = Join-Path $Tmp "leaks.txt"
    if ($rc -eq 0) { $leakLines = @() }
    elseif ($rc -eq 3 -and (Test-Path -LiteralPath $leakFile)) { $leakLines = @([IO.File]::ReadAllLines($leakFile) | Where-Object { $_ }) }
    elseif ($rc -eq 3) { $leakLines = @() }
    else { [Console]::Error.WriteLine(($log -join "`n")); Stop-Scan "gitleaks could not run (exit $rc); is Docker running?" }
    if ($rc -eq 3 -and $leakLines.Count -eq 0) { $leakLines = @("(no report written)") }
    Write-Output "gitleaks: $($leakLines.Count) finding(s) over all refs (secrets redacted)"
    foreach ($l in $leakLines) {
        if (Test-Deny $l) { $l = ($l -split " ", 2)[0] + " <path withheld>" }
        Write-Output "  leak: $l"
    }

    # ---- 2. deny-list ----
    $content = 0; $paths = 0; $messages = 0; $tags = 0
    $commits = @(Invoke-Git @("rev-list", "--all") | Where-Object { $_ })
    foreach ($c in $commits) {
        $short = $c.Substring(0, 12)
        foreach ($hit in @(Invoke-Git @("grep", "-i", "-F", "-l", "-f", $Pat, $c, "--") @(0, 1) | Where-Object { $_ })) {
            $content++
            $path = $hit.Substring($c.Length + 1)
            if (Test-Deny $path) { $path = "<path withheld>" }
            Write-Output "  content: $short $path"
        }
        $k = @(Invoke-Git @("ls-tree", "-r", "--name-only", $c) | Where-Object { Test-Deny $_ }).Count
        if ($k -gt 0) { $paths += $k; Write-Output "  path: $short $k file path(s)" }
        $meta = (Invoke-Git @("log", "-1", "--format=%an%n%ae%n%cn%n%ce%n%B", $c)) -join "`n"
        if (Test-Deny $meta) { $messages++; Write-Output "  message or author: $short" }
    }
    $refs = @(Invoke-Git @("for-each-ref", "--format=%(refname)") | Where-Object { Test-Deny $_ }).Count
    if ($refs -gt 0) { Write-Output "  ref names: $refs" }
    foreach ($line in @(Invoke-Git @("for-each-ref", "--format=%(objecttype) %(objectname)", "refs/tags"))) {
        $type, $obj = $line -split " ", 2
        if ($type -eq "tag" -and (Test-Deny ((Invoke-Git @("cat-file", "tag", $obj)) -join "`n"))) {
            $tags++; Write-Output "  annotated tag: $($obj.Substring(0, 12))"
        }
    }
    $denied = $content + $paths + $messages + $refs + $tags
    Write-Output "deny-list: $($terms.Count) name(s), $($commits.Count) commit(s): $content content, $paths path, $messages message or author, $refs ref name, $tags tag hit(s)"

    if ($leakLines.Count -eq 0 -and $denied -eq 0) { Write-Output "PASS"; exit 0 }
    Write-Output "FAIL"; exit 1
}
finally {
    Remove-Item -Recurse -Force -LiteralPath $Tmp -ErrorAction SilentlyContinue
}
