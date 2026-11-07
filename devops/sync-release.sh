#!/usr/bin/env bash
# Sync the docs with the latest oryxflow / oryxeval releases and commit the result.
# Usage: devops/sync-release.sh [--push] [--src-root DIR]   (ORYX_SRC_ROOT also works)
# Pushing main is what redeploys the site via Cloudflare, so it only happens with --push.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
PUSH=0; ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --push) PUSH=1 ;;
    --src-root) ARGS+=(--src-root "$2"); shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

# 1. Clean tree (untracked docs/todo/ is fine), on main, up to date.
[[ "$(git branch --show-current)" == "main" ]] || { echo "not on main" >&2; exit 1; }
if [[ -n "$(git status --porcelain | grep -v '^?? docs/todo/' || true)" ]]; then
  echo "working tree is dirty; commit or stash first" >&2; exit 1
fi
if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then git pull --ff-only; fi

# 2. Copy changelogs, re-pin oryxflow.  3. Full build with doc tests (aborts on failure).
"$PY" scripts/sync_release.py "${ARGS[@]+"${ARGS[@]}"}"
"$PY" scripts/build_docs.py ${ARGS[@]+"${ARGS[@]}"}

# 4. Nothing changed (the build may regenerate tests/test_docs_*.py)?
if [[ -z "$(git status --porcelain | grep -v '^?? docs/todo/' || true)" ]]; then
  echo "docs already in sync"; exit 0
fi

# 5. Commit with the newest released versions.
ver() { sed -n 's/^## \[\([0-9][0-9.]*\)\].*/\1/p' "_external/$1/CHANGELOG.md" | sort -t. -k1,1n -k2,2n -k3,3n | tail -1; }
MSG="Sync docs with oryxflow $(ver oryxflow) / oryxeval $(ver oryxeval)"
git add _external docs/requirements-cloudflare.txt tests/test_docs_*.py
git commit -m "$MSG"

# 6. Push only on request.
if [[ $PUSH -eq 1 ]]; then git push origin main; else echo "committed; to deploy: git push origin main"; fi
