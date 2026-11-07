# _external

Committed snapshots of the `CHANGELOG.md` files of the sibling repos (`oryxflow/`,
`oryxeval/`). The changelog pages include them by snippet, and the Cloudflare build
(`python scripts/build_docs.py --offline`) reads only these copies, because it checks out this
repo alone. This folder is outside `docs/`, so it is never published.

Refresh it with `python scripts/sync_release.py` (or `devops/sync-release.sh`) after a release;
do not edit the copies by hand.
