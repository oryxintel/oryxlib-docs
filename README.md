# oryxlib-docs

Source of [docs.oryxflow.dev](https://docs.oryxflow.dev): the oryxflow and oryxeval docs and the
blog, built with [Zensical](https://zensical.org) from `zensical.toml`. Contributor and agent
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
