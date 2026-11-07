# oryxlib-docs

Source of [docs.oryxflow.dev](https://docs.oryxflow.dev): docs and blog for oryxflow and oryxeval
(Python libraries and Claude Code plugins for trustworthy, accurate AI data analysis), built with [Zensical](https://zensical.org) from `zensical.toml`. Contributor and agent
rules are in `CLAUDE.md`.

## Setup

Clone this repo next to the libraries it documents (the build reads their changelogs):

```
<workspace>/oryxlib-docs   <workspace>/oryxflow   <workspace>/oryxeval
```

```bash
python -m venv ~/venvs/oryxlib-docs && . ~/venvs/oryxlib-docs/bin/activate
pip install ../oryxflow -r docs/requirements-docs.txt
```

## Build and preview

```bash
python scripts/build_docs.py                  # fetch changelogs, run doc tests, build ./site
python scripts/build_docs.py --skip-tests     # fast build
python scripts/build_docs.py --src-root DIR   # siblings elsewhere (or env ORYX_SRC_ROOT)
zensical serve                                # http://127.0.0.1:8000
```

## Deploy

Cloudflare Pages builds this repo on every push to `main`, with no sibling repos:

- Build command: `pip install -r docs/requirements-cloudflare.txt && python scripts/build_docs.py --offline --skip-tests`
- Output directory: `site`; environment variable `PYTHON_VERSION=3.12`

The build uses the committed changelog snapshots in `_external/` and the oryxflow release pinned
in `docs/requirements-cloudflare.txt`. After a library release, run `devops/sync-release.sh`
(or `devops\sync-release.ps1`) to refresh both, run the full build, and commit; add `--push` /
`-Push` to deploy.

### Cutover order (moving the site out of the oryxflow repo)

1. Create the GitHub repo `oryxintel/oryxlib-docs` and push `main`.
2. Create a NEW Cloudflare Pages project, Git-connected to it, with the build command, output
   directory and environment variable above.
3. Check its `*.pages.dev` preview.
4. Move the custom domain `docs.oryxflow.dev` from the old project (Git-connected to `oryxflow`) to
   the new one, and confirm the live site.
5. Disconnect or delete the old project.
6. Only then merge oryxflow's `chore/move-docs-out`: merging earlier breaks the old project's
   builds while it still serves the domain.
