<#
.SYNOPSIS
    Pull the latest digests and publish them into the Obsidian vault.

.DESCRIPTION
    Runs on a Windows scheduled task shortly after the GitHub Action that
    generates the daily digest. Steps:
      1. git pull the news-digest repo
      2. regenerate the Obsidian notes from digests/ (idempotent)
      3. copy the notes into the vault's "10_情報/AI News" folder
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
$target = Join-Path $VaultPath "10_情報/AI News"
New-Item -ItemType Directory -Force $target | Out-Null

# Copy only when content actually differs, so unchanged notes keep their
# original mtime and the vault's git history stays readable. Notes live in
# category subfolders, so walk recursively and mirror the relative layout.
$copied = 0
$expected = @{}
foreach ($file in Get-ChildItem $source -Recurse -Filter *.md) {
    $rel = $file.FullName.Substring($source.Length).TrimStart('\', '/')
    $expected[$rel] = $true
    $dest = Join-Path $target $rel
    New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
    $isNew = -not (Test-Path $dest)
    if ($isNew -or
        (Get-FileHash $file.FullName).Hash -ne (Get-FileHash $dest).Hash) {
        Copy-Item $file.FullName $dest -Force
        $copied++
    }
}
# Prune vault notes that no longer exist in the generated set (e.g. the old
# one-file-per-day layout). The generator is the single source of truth here.
$pruned = 0
foreach ($file in Get-ChildItem $target -Recurse -Filter *.md) {
    $rel = $file.FullName.Substring((Join-Path $VaultPath "10_情報/AI News").Length).TrimStart('\', '/')
    if (-not $expected.ContainsKey($rel)) {
        Remove-Item $file.FullName -Force
        $pruned++
    }
}
Write-Step "$copied note(s) updated, $pruned stale note(s) removed in the vault"

# --- 4. commit and push the vault -------------------------------------------
# git writes progress and CRLF warnings to stderr; under ErrorAction=Stop
# PowerShell 5.1 would promote those to terminating errors. Exit codes are
# checked explicitly below, so plain Continue is the correct mode here.
$ErrorActionPreference = "Continue"
# The vault is shared with other collectors (ai-collect, dev-collect, cc-cases)
# that may leave unrelated working-tree changes behind; stage only our folder
# so this sync can never sweep someone else's files into an "AI news" commit.
$status = git -C $VaultPath status --porcelain -- "10_情報/AI News"
if (-not $status) {
    Write-Step "Vault already up to date - nothing to commit."
    exit 0
}

git -C $VaultPath add -- "10_情報/AI News"
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
