# CLAUDE.md — working on the oryxlib-docs repo

This repo is the docs.oryxflow.dev site (oryxflow and oryxeval docs, plus the blog), built with
Zensical. Guidance for editing, testing, building, and publishing it. Library internals live in
the sibling repos (`../oryxflow`, `../oryxeval`), which are read-only from here.

**A user-facing change in oryxflow or oryxeval needs a docs update here.**

## What this is

The docs are a **Zensical** site (markdown; Zensical reads `zensical.toml`, bundles the Material
theme, and runs the mkdocstrings / llmstxt / blog plugins). `zensical.toml` at the repo root is the
single source of truth for theme, nav, plugins, and what is published. Edit the `.md` pages in
`docs/` (landing + blog) and `docs/docs/` (the guide + reference).

## Setup: sibling repos and the build env

The default build reads the changelogs of the sibling repos, so clone them next to this repo:

```
<workspace>/oryxlib-docs   <workspace>/oryxflow   <workspace>/oryxeval
```

`--src-root DIR` (or env `ORYX_SRC_ROOT`) points at another location; default is `..`. The build
env is a venv OUTSIDE OneDrive, a non-synced folder such as `~/venvs/oryxlib-docs` (never a venv under a OneDrive path; no
`pip install -e`): `pip install ../oryxflow -r docs/requirements-docs.txt` (non-editable, the API
page introspects the installed oryxflow).

## Parity check

A site-wide refactor is verified by diffing the built `site/` against a saved baseline:
`python scripts/compare_sites.py <baseline-site> site --allow scripts/compare_allow.txt` (0 problems
expected; every accepted difference is a `# reason` entry in `compare_allow.txt`).

## SEO metadata

Every page needs its own `description:` in front matter, 120-160 characters, specific to that
page, key phrase first. `overrides/main.html` turns it into the description meta, Open Graph and
Twitter tags (image: the site logo, so the small `summary` card). The pages the blog plugin
generates (category, archive, pagination) take their text from `[project.extra.seo]` in
`zensical.toml`: add a line there when you add a blog category. After the build,
`scripts/check_seo.py` fails on a missing title, description, canonical or `og:*` tag and on
duplicate titles or descriptions, and warns on length (titles over 65 characters, descriptions
outside 120-160). Family-level wording says "Python libraries and Claude Code plugins for
trustworthy, accurate AI data analysis"; a page about one library speaks about that library.

## Site tabs (top navigation)

`navigation.tabs` is on; the top-level `nav` entries in `zensical.toml` are the tabs. Page paths
(URLs) do not follow the tabs: the tab is only a grouping.

| Tab | Pages |
| --- | --- |
| Home | `index.md` |
| oryxflow | `docs/index.md`, why, installation, quickstart, Guide, Advanced, Example (ML), glossary, supply chain, API reference, changelog |
| Knowledge | `docs/collaborate.md` |
| oryxeval | the five `docs/llm-evals*.md` pages, `docs/claude-plugin/evals.md`, `docs/llm-evals-changelog.md` |
| Claude Code | the plugin pages under `docs/claude-plugin/` (minus `evals.md`), `claude-code-for-data-science.md`, `ai-ready.md` |
| Blog | `blog/index.md` |

The `llmstxt` `sections` mirror the tabs one to one (Blog last): a new page goes in both `nav`
and `sections`.

## Layout

URL layout: `/` = landing (`docs/index.md`), `/docs/*` = the guide + reference (files in
`docs/docs/`), `/blog/*` = the blog. A page's URL mirrors its path under `docs/`, so guide pages
live in the `docs/docs/` subfolder to get the `/docs/` prefix.

```
zensical.toml                 # site config: theme (black header, blue links, logo), nav, plugins
overrides/                     # theme overrides (main.html: titles, descriptions, Open Graph, JSON-LD, FAQ)
_external/                     # COMMITTED changelog snapshots of oryxflow/oryxeval (see Releasing)
devops/sync-release.sh / .ps1  # sync + build + commit after a library release
docs/                          # docs_dir
  index.md                     # ROOT landing page  ->  /
  assets/                      # logo-oryx.png, extra.css (link-color override)
  docs/                        # the guide + reference  ->  /docs/*
    index.md                   #   /docs/ home (section index; navigation.indexes)
    why-oryxflow.md            #   positioning / overview page (trust-led, GEO-shaped)
    installation.md quickstart.md tasks.md workflow.md run.md targets.md logging.md
    collaborate.md managing-workflows.md advtasksdyn.md advparam.md functional_tasks.md
    example-ml.md llm-evals*.md   #   llm-evals-changelog.md includes _external/oryxeval/CHANGELOG.md
    claude-plugin/             #   "Claude Code" tab
      index.md commands.md why.md   #   plugin section landing + commands + matched-pair rationale
    reference.md               #   API reference, generated from docstrings via mkdocstrings
    changelog.md               #   includes _external/oryxflow/CHANGELOG.md via a pymdownx snippet
    requirements-docs.txt / requirements-cloudflare.txt   # toolchain deps; Cloudflare adds the oryxflow pin
  blog/
    index.md                   # blog landing (Material "blog" plugin)  ->  /blog/
    posts/*.md                 # one file per post; front-matter: date, slug, categories
                               #   permalinks are /blog/<category>/<slug> (no date; see zensical.toml)
  todo/                        # design/plan notes — excluded from build (internal)
tests/
  conftest.py                  # isolates test_docs_*.py in a throwaway cwd (module-scoped)
  test_docs_*.py               # GENERATED by phmdoctest from the pages below — do not hand-edit
scripts/
  build_docs.py                # fetch changelogs, regenerate doc tests, run them, `zensical build`, stamp dates
  sync_release.py              # copy changelogs into _external/, re-pin oryxflow for Cloudflare
  compare_sites.py             # parity diff of two built sites (+ compare_allow.txt)
  check_seo.py                 # build-time SEO check: required tags, duplicate titles/descriptions
.github/workflows/docs.yml     # CI: build + test only (no deploy)
```

## Local preview

```bash
python scripts/build_docs.py --skip-tests   # build into ./site (fast)
zensical serve                              # http://127.0.0.1:8000
```

## Working on the docs from another oryx repo

Agents in a library or plugin repo: read `MAINTAINING.md` (page map, when to update, how to verify,
release sync). It is self-contained.

## Testing the examples in the docs

Code examples are unit-tested so they can't silently rot. We use **phmdoctest** to *compile*
runnable Markdown pages into real pytest files (`tests/test_docs_*.py`), which pytest then runs.

**Assertions live outside the docs.** The pages contain only clean, runnable example code — no
`assert` lines. phmdoctest generates a test per code block that fails if the code raises; that
implicit check *is* the assertion, and it lives in the generated test file, not the prose. (If a
block is followed by an expected-output fenced block, phmdoctest also asserts stdout matches it —
still generated, still outside the page.)

Three invisible HTML-comment directives control generation (they render as nothing):

- `<!--phmdoctest-share-names-->` before a ```python block → its names are visible to later
  blocks on the page (so a tutorial that builds up state across blocks works).
- `<!--phmdoctest-skip-->` before a block → not compiled into a test (use for illustrative
  fragments that don't run standalone).
- `<!--phmdoctest-setup-->` / `<!--phmdoctest-teardown-->` before a block → run once per module.
  We generally avoid these because the block would be *visible* in the rendered page; per-page
  working-directory isolation is handled in `tests/conftest.py` instead.

Which pages are tested is the `TESTED_PAGES` dict in `scripts/build_docs.py`. To add a page:
mark its runnable blocks with `<!--phmdoctest-share-names-->`, add it to `TESTED_PAGES`, then:

```bash
python scripts/build_docs.py         # regenerate tests/test_docs_*.py, run them, build the site
```

Commit the regenerated `tests/test_docs_*.py`. CI does NOT gate on staleness (it does not run
`build_docs.py --check`, deliberately): phmdoctest names tests by source line, so a stale file is
bookkeeping churn, not a behaviour change; the pre-commit hook below regenerates them. `--check`
still exists for a manual look.

**A pre-commit hook does this for you — install it once per clone:**

```bash
pip install pre-commit && pre-commit install
```

Why it exists: phmdoctest names each generated test after its code block's **source line**
(`test_code_66`), so editing **prose above a code block** renames the test and leaves the
committed file stale — no behavior change, pure churn (CI does not gate on it). The `docs-regen` hook (`.pre-commit-config.yaml`) runs `build_docs.py --regen` — front-matter
validation plus regeneration only, no pytest and no site build, so it stays ~1s. When it
rewrites a file, pre-commit reports *"files were modified by this hook"* and aborts; `git add` the
regenerated tests and commit again. Without `pre-commit install` the config does nothing and
you're back to remembering, and the generated files drift until the next regeneration.

Isolation gotcha: doc examples use the default output directory, the relative path `data/` —
don't add `oryxflow.set_dir('data/')` to an example, it's a no-op that contradicts the "nothing to
configure" pitch (only show `set_dir` where the point *is* a non-default directory). The
`conftest.py` fixture runs each `test_docs_*` module in a throwaway working directory (module
scope, so blocks on one page share the same cache dir). Because a whole page runs in one shared
namespace + cache dir, **two tasks with the same family name and no distinguishing parameters
collide** (the second reuses the first's cached output). Give distinct example tasks distinct
class names — this is why the quickstart's ML loader is `GetDiabetes`, not a second `GetData`.

## Claims about AI-readiness live on one page — keep them true

`docs/docs/ai-ready.md` is the single place the docs claim oryxflow is "AI-coding ready" (README and
the two index pages only link to it). It asserts three things that can silently rot, so if you touch
them, update that page in the same commit:

- **"The examples an agent reads first are executed by the test suite"** — deliberately scoped to
  the three `TESTED_PAGES` (home, quickstart, targets) and paired with an explicit admission that
  the deeper guides and blog aren't all executed. Only ~13 of ~214 python blocks in `docs/` run, so
  do **not** upgrade this to "every example"; if you add a page to `TESTED_PAGES`, name it there.
- **"100% of the public API carries a docstring"** — verify before restating it:

  ```bash
  python -c "import inspect,oryxflow,oryxflow.core,oryxflow.parameter,oryxflow.tasks,oryxflow.targets as t; \
  m={'oryxflow':oryxflow,'core':oryxflow.core,'parameter':oryxflow.parameter,'tasks':oryxflow.tasks,'targets':t}; \
  o=[f'{k}.{n}' for k,v in m.items() for n,x in vars(v).items() if not n.startswith('_') \
  and (inspect.isfunction(x) or inspect.isclass(x)) and getattr(x,'__module__','').startswith('oryxflow') \
  and not (inspect.getdoc(x) or '').strip()]; print('undocumented:', o or 'none')"
  ```

- **`llms.txt` / `llms-full.txt` exist and are complete** — they come from the `llmstxt` plugin's
  `sections` in `zensical.toml`. A new page added to `nav` but not to `sections` is missing from both
  files, so agents never see it. Add every new page to both.

## Building & AI-crawler outputs

`python scripts/build_docs.py` writes `./site`, including:

- `sitemap.xml` — `<lastmod>` and the JSON-LD `dateModified` are stamped from git commit dates by
  `scripts/stamp_lastmod.py` after the build. Needs real git history: CI uses `fetch-depth: 0`,
  and Cloudflare Pages clones shallowly, so the stamping step runs `git fetch --unshallow` first
  (it prints that it did). If the repo is still shallow after that, stamping is skipped with a loud
  WARNING (never HEAD's date on every page). Uncommitted files are skipped (no lastmod).
- `llms.txt` — the sectioned index for AI agents (sections defined under the `llmstxt` plugin in
  `zensical.toml`).
- `llms-full.txt` — the entire docs concatenated into one file for single-request ingestion.

The build checks that the installed oryxflow is not older than the newest CHANGELOG release, and
that every blog post has a `<!-- more -->` marker. Link and anchor problems are warnings (see
`[project.validation]`); `--strict` is not used (mkdocstrings/griffe warn about docstrings in the
oryxflow source).

## Publishing and the Cloudflare build

Cloudflare Pages builds THIS repo alone from GitHub (Git integration) on every push to `main`; CI
never deploys and holds no Cloudflare secrets. With no sibling repos available, the build runs
offline from committed inputs:

- Build command: `pip install -r docs/requirements-cloudflare.txt && python scripts/build_docs.py --offline --skip-tests`
- Output directory: `site`. Environment variable: `PYTHON_VERSION=3.12`.
- `--offline` reads the committed `_external/<repo>/CHANGELOG.md` snapshots, never the siblings.
- `docs/requirements-cloudflare.txt` = `-r requirements-docs.txt` + `oryxflow==<newest release>` from
  PyPI (the API page documents that package).

## Releasing / keeping the docs current

After an oryxflow or oryxeval release lands on PyPI: `devops/sync-release.sh --push` (or
`devops\sync-release.ps1 -Push`). It refuses a dirty tree or a non-`main` branch, then runs
`python scripts/sync_release.py` (copies both changelogs into `_external/`, rewrites the oryxflow
pin), `python scripts/build_docs.py` (full build with doc tests), commits
`Sync docs with oryxflow X / oryxeval Y`, and pushes only with `--push`. Done by hand: the same
three scripts, run the parity check, commit, push `main`. The push is what redeploys the site via
Cloudflare. Pushing is the human's step; agents ask first.

CI (`.github/workflows/docs.yml`) builds against oryxflow main with `--use-snapshot oryxeval`
(oryxeval has no GitHub remote yet; once it does, check it out as a sibling and drop the flag).

## Writing a blog post

Posts are the main content channel and get written often — this is the whole recipe, so you don't
have to re-derive it by reading five existing posts.

**1. File + front-matter.** One file per post at `docs/blog/posts/<name>.md`. No `zensical.toml` nav
entry is needed (the blog plugin picks up `posts/*.md`, and `llmstxt` globs it).

```yaml
---
date: 2026-07-25          # required by the blog plugin
slug: keyword-first-slug  # required: the URL is /blog/<first-category-slug>/<slug>
categories:               # first one becomes the URL segment (post_url_max_categories: 1)
  - AI agents
description: One or two keyword-bearing sentences. Used as the meta description and the social
  card, so write it for a search result, not as a summary for yourself.
faq:                      # optional but standard — see 4
  - q: "A question phrased the way someone would type it"
    a: "A self-contained answer, 2-4 sentences, that names oryxflow at least once."
---
```

Categories in use (reuse rather than inventing — each new one mints a new URL prefix):
`Comparisons`, `AI agents`, `Caching`, `Reproducibility`, `Machine learning`, `MLOps`, `Guides`.

**2. Body shape.** Every post follows the same skeleton:

```markdown
# Title (H1, matching the intent of the slug)

*One-line italic subtitle — the thesis, or the promise.*

<!-- more -->            <-- REQUIRED. post_excerpt: required; the build fails without it.

## Sections...

## Takeaway              <-- or a titled conclusion; always land the argument

    pip install oryxflow

## Frequently asked questions
### <the q: from front-matter, verbatim>
<the a: from front-matter, verbatim>

Then keep going:
- <3-6 links: sibling posts first, then guide pages, then GitHub>
```

**3. Links.** Plain relative Markdown, and `[project.validation]` in `zensical.toml` reports a bad
target as a build warning. From a post: a sibling post is `other-post.md`; a guide page is `../../docs/page.md`; the
blog index is `../index.md`.

**4. The FAQ is duplicated on purpose.** `overrides/main.html` reads the `faq:` front-matter and
emits a JSON-LD `FAQPage` block for search/AI crawlers; the visible "Frequently asked questions"
section at the bottom is the human copy. **Keep the two byte-identical** — write the answer once
and paste it into both. Answers must stand alone (no "as described above") because they get
extracted out of context.

**5. Code in posts is NOT tested.** Only the pages in `TESTED_PAGES` (`scripts/build_docs.py`) are
compiled by phmdoctest, and blog posts aren't among them. So examples may reference undefined
helpers (`build_classifier(...)`) — but it also means nothing checks the API surface for you.
**Verify every API you show against the source** before publishing: grep the signature in
`oryxflow/`, and for third-party libraries fetch the current docs rather than writing from memory.
Same for any vendor pricing/retention claim — cite the vendor's own page, quote it, and date-stamp
it ("as of July 2026"). A wrong number about a named competitor is the one error that costs
credibility outright.

**6. Register the post** in `docs/blog/index.md` under the right themed heading. The plugin
generates the chronological list; the curated lists at the top are hand-maintained.

**7. Check it.** `zensical serve` and open `/blog/`, or build and confirm no
link warnings for the new file.

## Conventions

- User docs speak to data scientists in terms of benefits, never library internals or jargon
  (same rule as the repo-root `CLAUDE.md`). Internals belong in code comments and `docs/todo/`.
- Cross-page links are plain relative Markdown: `[text](other-page.md#anchor)`. Anchors are the
  auto-generated slug of the target heading.
- Don't hand-edit `tests/test_docs_*.py` — regenerate via `scripts/build_docs.py`.
- Blog posts need YAML front-matter with at least `date:`; put them in `docs/blog/posts/`.
