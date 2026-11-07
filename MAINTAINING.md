# Maintaining the docs from another oryx repo

For coding agents whose working directory is a library or plugin repo (siblings
`../oryxflow`, `../oryxeval`, `../oryxflow-claude-plugin`, `../oryxeval-claude-plugin`) and who
must update pages here. This repo is separate: work in `../oryxlib-docs`, using its build env.

| Source repo | Docs pages to update (paths from this repo's root) |
| --- | --- |
| `oryxflow` | the oryxflow tab: `docs/index.md`, `docs/docs/index.md`, `why-oryxflow.md`, `installation.md`, `quickstart.md`, the guide and advanced pages in `docs/docs/` (`tasks.md`, `workflow.md`, `run.md`, `targets.md`, `advparam.md`, ...), `docs/docs/collaborate.md`; the API page `docs/docs/reference.md` is generated from the installed package's docstrings; changelog page `docs/docs/changelog.md` (snapshot, see below) |
| `oryxeval` | `docs/docs/llm-evals-quickstart.md`, `llm-evals.md`, `llm-evals-prompts.md`, `llm-evals-api.md`, `llm-evals-checklist.md`, `docs/docs/claude-plugin/evals.md`, changelog page `docs/docs/llm-evals-changelog.md` |
| `oryxflow-claude-plugin` | the Claude Code tab: `docs/docs/claude-plugin/index.md`, `trust.md`, `commands.md`, `project-structure.md`, `coding-standards.md`, `why.md`, plus `docs/docs/claude-code-for-data-science.md`, `docs/docs/ai-ready.md` |
| `oryxeval-claude-plugin` | `docs/docs/claude-plugin/evals.md` and the eval pages that mention its slash commands (`docs/docs/llm-evals-quickstart.md`, `llm-evals.md`) |

- **When an update is required:** any user-facing change: a new, renamed or removed API, parameter,
  command or behaviour, or a changed install step. Internal refactors need nothing.
- **Edit and preview:** edit the `.md` pages, then `zensical serve` (http://127.0.0.1:8000) from
  this repo with the build env active.
- **Verify:** `python scripts/build_docs.py --src-root ..` (doc tests plus site build, from this
  repo). Pages need valid YAML front matter (quote values containing a colon) and every blog post
  needs a `<!-- more -->` excerpt marker; the build fails otherwise. A new page goes in both `nav`
  and the llmstxt `sections` of `zensical.toml`.
- **Separate git repo:** commit here on its own, with this repo's conventions; never push without
  asking (a push to `main` redeploys the site).
- **Changelogs are not edited here.** `_external/*/CHANGELOG.md` are snapshots, synced from the
  sibling repos by `devops/sync-release.sh` (or `.ps1`) after a release. Change the changelog in
  the library repo.
- **Release sync (after an oryxflow or oryxeval release lands on PyPI):** from this repo run
  `devops/sync-release.sh --push` (or `devops\sync-release.ps1 -Push`). It copies both changelogs
  into `_external/`, re-pins oryxflow for Cloudflare, runs the full build with doc tests, commits
  `Sync docs with oryxflow X / oryxeval Y` and pushes `main`, which redeploys the site. Without
  `--push` it only commits. Ask the human before pushing.
- **Not published:** this file sits outside `docs/`, so it is not part of the site.

## Cutover from the oryxflow repo (one-time, in this order)

The site used to build from the `oryxflow` repo; it now builds from this one. Do not reorder:

1. Create the GitHub repo `oryxintel/oryxlib-docs` and push `main`.
2. Create a NEW Cloudflare Pages project, Git-connected to it, with the build command, output
   directory and environment variable (see README.md, Deploy).
3. Check its `*.pages.dev` preview.
4. Move the custom domain `docs.oryxflow.dev` from the old project (Git-connected to `oryxflow`) to
   the new one, and confirm the live site.
5. Disconnect or delete the old project.
6. Only then merge oryxflow's `chore/move-docs-out`: merging earlier breaks the old project's
   builds while it still serves the domain.
