<#
.SYNOPSIS
  Sync the docs with the latest oryxflow / oryxeval releases and commit the result (PowerShell 7).
.DESCRIPTION
  Same behaviour as devops/sync-release.sh. Pushing main redeploys the site via Cloudflare,
  so it only happens with -Push. Uses $env:PYTHON if set, else python; -SrcRoot or ORYX_SRC_ROOT
  locate the sibling checkouts.
#>
param([switch]$Push, [string]$SrcRoot)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
$extra = @(); if ($SrcRoot) { $extra = @('--src-root', $SrcRoot) }
function Dirty { @(git status --porcelain | Where-Object { $_ -notmatch '^\?\? docs/todo/' }).Count -gt 0 }
function Run { & @args; if ($LASTEXITCODE -ne 0) { throw "failed: $args" } }

# 1. Clean tree (untracked docs/todo/ is fine), on main, up to date.
if ((git branch --show-current) -ne 'main') { throw 'not on main' }
if (Dirty) { throw 'working tree is dirty; commit or stash first' }
git rev-parse --abbrev-ref '@{u}' 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Run git pull --ff-only }

# 2. Copy changelogs, re-pin oryxflow.  3. Full build with doc tests (aborts on failure).
Run $py scripts/sync_release.py @extra
Run $py scripts/build_docs.py @extra

# 4. Nothing changed (the build may regenerate tests/test_docs_*.py)?
if (-not (Dirty)) { 'docs already in sync'; exit 0 }

# 5. Commit with the newest released versions.
function Ver($repo) {
  (Select-String -Path "_external/$repo/CHANGELOG.md" -Pattern '^## \[(\d+\.\d+\.\d+)\]').Matches |
    ForEach-Object { [version]$_.Groups[1].Value } | Sort-Object | Select-Object -Last 1
}
$msg = "Sync docs with oryxflow $(Ver oryxflow) / oryxeval $(Ver oryxeval)"
Run git add _external docs/requirements-cloudflare.txt 'tests/test_docs_*.py'
Run git commit -m $msg

# 6. Push only on request.
if ($Push) { Run git push origin main } else { 'committed; to deploy: git push origin main' }
