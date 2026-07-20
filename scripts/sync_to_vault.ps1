<#
.SYNOPSIS
    Pull the latest digests and publish them into the Obsidian vault.

.DESCRIPTION
    Runs on a Windows scheduled task shortly after the GitHub Action that
    generates the daily digest. Steps:
      1. git pull the news-digest repo
      2. regenerate the Obsidian notes from digests/ (idempotent)
      3. copy the notes into the vault's "10_AI News" folder
      4. commit and push the vault so the Android client picks it up

    Safe to run by hand at any time; it is a no-op when nothing changed.

.PARAMETER RepoPath
    Working clone of the news-digest repository.

.PARAMETER VaultPath
    Root of the Obsidian vault (must already be a git repo with a remote).

.PARAMETER NoPush
    Do everything except pushing the vault. Useful for a dry check.
#>
param(
    [string]$RepoPath  = "C:\dev\news-digest",
    [string]$VaultPath = "C:\Users\PC_User\ObsidianVault",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "[sync] $msg" }

if (-not (Test-Path $RepoPath))  { throw "Repo not found: $RepoPath" }
if (-not (Test-Path $VaultPath)) { throw "Vault not found: $VaultPath" }

# --- 1. refresh the repo -----------------------------------------------------
# Everything under obsidian/ is generated output that the CI job also commits.
# A local run leaves copies behind, and git then refuses to pull ("untracked
# working tree files would be overwritten"). Discarding them first is safe
# precisely because step 2 regenerates the whole directory from digests/.
$generated = Join-Path $RepoPath "obsidian"
if (Test-Path $generated) {
    Write-Step "Discarding locally generated notes before pull"
    git -C $RepoPath clean -fdq -- obsidian
    # Only restore tracked files; before the first CI run nothing under
    # obsidian/ is in HEAD and checkout would fail on an unmatched pathspec.
    if (git -C $RepoPath ls-files -- obsidian) {
        git -C $RepoPath checkout -q -- obsidian
    }
}

Write-Step "Pulling $RepoPath"
git -C $RepoPath pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "git pull failed in $RepoPath" }

# --- 2. rebuild Obsidian notes ----------------------------------------------
Write-Step "Exporting Obsidian notes"
python (Join-Path $RepoPath "scripts\export_obsidian.py")
if ($LASTEXITCODE -ne 0) { throw "export_obsidian.py failed" }

$source = Join-Path $RepoPath "obsidian\AI News"
if (-not (Test-Path $source)) {
    Write-Step "No notes generated yet — nothing to sync."
    exit 0
}

# --- 3. copy into the vault --------------------------------------------------
$target = Join-Path $VaultPath "10_AI News"
New-Item -ItemType Directory -Force $target | Out-Null

# Copy only when content actually differs, so unchanged notes keep their
# original mtime and the vault's git history stays readable.
$copied = 0
foreach ($file in Get-ChildItem $source -Filter *.md) {
    $dest = Join-Path $target $file.Name
    $isNew = -not (Test-Path $dest)
    if ($isNew -or
        (Get-FileHash $file.FullName).Hash -ne (Get-FileHash $dest).Hash) {
        Copy-Item $file.FullName $dest -Force
        $copied++
    }
}
Write-Step "$copied note(s) updated in the vault"

# --- 4. commit and push the vault -------------------------------------------
$status = git -C $VaultPath status --porcelain
if (-not $status) {
    Write-Step "Vault already up to date — nothing to commit."
    exit 0
}

git -C $VaultPath add -A
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git -C $VaultPath commit -m "AI news sync: $stamp"
if ($LASTEXITCODE -ne 0) { throw "vault commit failed" }

if ($NoPush) {
    Write-Step "Committed. Skipping push (-NoPush)."
    exit 0
}

git -C $VaultPath push
if ($LASTEXITCODE -ne 0) { throw "vault push failed" }
Write-Step "Vault pushed. Android will pick it up on next pull."
