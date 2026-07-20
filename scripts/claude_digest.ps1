<#
.SYNOPSIS
    Mechanical stages of the digest run, with summarization left to Claude Code.

.DESCRIPTION
    generate_digest.py can do the whole job in one pass using Groq. This script
    is the alternative wiring: it runs the deterministic parts and leaves the
    one step that actually needs a language model to Claude Code, which is
    driven by the `ai-news-digest` skill.

        collect  ->  Claude reads the topics and writes summaries  ->  publish

    Keeping the mechanics in two allowlistable commands means the whole run
    works unattended, without Claude needing broad shell permissions.

.PARAMETER Stage
    'collect' gathers and ranks topics into -StatePath.
    'publish' renders every output, then commits and syncs.

.PARAMETER StatePath
    Collection hand-off file. Defaults to data/pending_topics.json.

.PARAMETER SummariesPath
    JSON array of {index, title_ja, summary_ja}. Optional: without it, publish
    still runs and falls back to original headlines.

.PARAMETER SkipVaultSync
    Publish to the repo but do not touch the Obsidian vault.

.PARAMETER Force
    Replace today's digest if one already exists. Off by default: a same-day
    rerun finds the *next* set of stories rather than the same ones, so an
    accidental second run would otherwise swap out the published digest.

.EXAMPLE
    .\claude_digest.ps1 -Stage collect
    .\claude_digest.ps1 -Stage publish -SummariesPath data\pending_summaries.json
#>
param(
    [Parameter(Mandatory)][ValidateSet('collect', 'publish')][string]$Stage,
    [string]$RepoPath = "C:\dev\news-digest",
    [string]$StatePath,
    [string]$SummariesPath,
    [switch]$SkipVaultSync,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "[digest] $msg" }

if (-not $StatePath) { $StatePath = Join-Path $RepoPath "data\pending_topics.json" }
$script = Join-Path $RepoPath "scripts\generate_digest.py"

if ($Stage -eq 'collect') {
    # Pull first so the dedup history is current; otherwise a run can re-publish
    # topics that another run already covered.
    Write-Step "Refreshing repo"
    if (Test-Path (Join-Path $RepoPath "obsidian")) {
        git -C $RepoPath clean -fdq -- obsidian
        if (git -C $RepoPath ls-files -- obsidian) {
            git -C $RepoPath checkout -q -- obsidian
        }
    }
    git -C $RepoPath pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw "git pull failed in $RepoPath" }

    Write-Step "Collecting topics"
    python $script --collect $StatePath
    if ($LASTEXITCODE -ne 0) { throw "collection failed" }

    # The count is already reported by the Python step above. Re-parsing here
    # would mean reading UTF-8 through Windows PowerShell's ANSI default, which
    # mangles the multibyte characters and breaks ConvertFrom-Json.
    Write-Step "Topics ready for summarization at $StatePath"
    exit 0
}

# --- publish -----------------------------------------------------------------
if (-not (Test-Path $StatePath)) { throw "No collected state at $StatePath. Run -Stage collect first." }

$renderArgs = @($script, "--render", $StatePath)
if ($Force) { $renderArgs += "--force" }
if ($SummariesPath) {
    if (-not (Test-Path $SummariesPath)) { throw "Summaries file not found: $SummariesPath" }
    $renderArgs += @("--summaries", $SummariesPath)
} else {
    Write-Warning "No -SummariesPath given; the digest will fall back to original headlines."
}

Write-Step "Rendering digest"
python @renderArgs
if ($LASTEXITCODE -ne 0) { throw "render failed" }

Write-Step "Exporting Obsidian notes"
python (Join-Path $RepoPath "scripts\export_obsidian.py")
if ($LASTEXITCODE -ne 0) { throw "export_obsidian.py failed" }

Write-Step "Committing digest"
git -C $RepoPath add digests archive index.html data/published_topics.json obsidian
# `diff --cached --quiet` exits 1 when something is staged. It prints nothing,
# so the non-zero exit does not trip $ErrorActionPreference.
git -C $RepoPath diff --cached --quiet
$hasStagedChanges = ($LASTEXITCODE -ne 0)
if ($hasStagedChanges) {
    $today = Get-Date -Format "yyyy-MM-dd"
    git -C $RepoPath commit -q -m "digest: $today"
    git -C $RepoPath push -q origin main
    if ($LASTEXITCODE -ne 0) { throw "push failed" }
    Write-Step "Pushed."
} else {
    Write-Step "Nothing new to commit."
}

if ($SkipVaultSync) {
    Write-Step "Skipping vault sync (-SkipVaultSync)."
    exit 0
}

Write-Step "Syncing vault"
& (Join-Path $RepoPath "scripts\sync_to_vault.ps1")
