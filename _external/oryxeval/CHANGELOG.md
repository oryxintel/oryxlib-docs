# Changelog

All notable changes to **oryxeval** are recorded here. This file is read by humans *and* by AI
coding agents diagnosing regressions after an upgrade, so the format is load-bearing:

- Newest first. One `## [version] - YYYY-MM-DD` heading per release; version is calver `YY.M.D`
  matching `pyproject.toml` / `oryxeval.__version__`. Unreleased work goes under `## [Unreleased]`.
- Group bullets under `### Added` / `### Changed` / `### Deprecated` / `### Removed` /
  `### Fixed` / `### Security` (Keep a Changelog: https://keepachangelog.com/).
- **Every breaking change is a bullet that STARTS with the literal token `BREAKING:`** and carries
  a same-bullet `Migration:` clause with the old->new fix.
- **Name the actual symbol in backticks** (`` `sweep` ``, `` `EvalResult.verdict()` ``), never
  prose. Agents grep this file for the symbol in their traceback.

## [26.11.6] - 2026-11-06
### Added
- `oryxeval`: first release as a standalone package. The code is `oryxflow.evals` as of oryxflow
  26.10.22, unchanged apart from the import name. Requires `oryxflow>=26.11.6`. Migration: change
  only the import lines, `import oryxflow.evals as ev` -> `import oryxeval as ev` and `from
  oryxflow.evals.<module> import X` -> `from oryxeval.<module> import X`; existing eval caches then
  stay valid (no cache key contains the module path). Keep `import oryxflow` and leave every
  function body as it is: `code_version()`, `case()` and their helpers are hashed into the cache
  key, so any edit there (even `oryxflow.hash_files` -> `ev.hash_files`) re-runs every arm. The next
  run reuses the cache but prints StalenessWarnings; clear them once, from `evals/`: `python -c
  "import oryxflow; oryxflow.accept_code()"` (the `accept_code(<Eval>)` the warning names covers
  only the scoring stage). New evals use `ev.hash_files`.
- `oryxeval` re-exports oryxflow's `Parameter`, `IntParameter`, `FloatParameter`, `BoolParameter`,
  `ChoiceParameter`, `ListParameter`, `DictParameter`, `DateParameter`, `EnumParameter` and
  `hash_files` (the same objects).
### Fixed
- `pyyaml` is a declared dependency (`load_cases` reads `.yaml` files).
- `oryxeval.cli` and `oryxeval.build_app` import and resolve on first use as documented.

## Before the split (shipped as oryxflow.evals)

The entries below are from oryxflow's changelog, verbatim, under their original versions.

## [26.10.5] - 2026-10-05
### Added
- `oryxflow.evals`: **a cell is now two cached stages -- the model calls, then the scoring.**
  `TaskEval` generates an `<Eval>Outputs` task (`TaskJson`, one record per case x repeat: output,
  inputs, timing, metrics, attributes) that the scoring task requires. Editing an evaluator,
  changing a judge rubric or swapping the judge model re-scores the stored outputs with ZERO calls
  to the model under test; editing what the arm reads re-runs both. Before, one `code_version()`
  keyed both, so a scorer change either re-billed every call or served stale scores. A subclass's
  `code_version()` keeps its meaning (what the ARM reads) and now keys the model-call stage only;
  the new `TaskEval.scorer_version()` keys the scoring stage and defaults to every evaluator's code
  and configuration (`as_spec()`). A typed output is rebuilt with `model_validate`, so
  `ctx.output.attr` scorers are unchanged. Evaluators that read the run's span tree
  (`HasMatchingSpan`, `ToolCorrectness`, `TrajectoryMatch`, `ArgumentCorrectness`, `MaxToolCalls`,
  `MaxModelRequests`, or any with `needs_trace = True`) score in the model-call stage, because spans
  are not stored.
- `oryxflow.evals`: `sweep(rescore=True)` / `ev.cli --rescore` -- re-run only the scorers over the
  stored outputs (after a transient judge failure, say). The bill prints `re-scoring N arms from
  stored outputs: no model calls` and counts an LLM judge's calls separately.
- `oryxflow.evals`: `baseline=` on `sweep()` (or a `baseline` attribute on a `TaskEval`; default:
  an arm named `baseline`). The verdict then reports every arm's paired difference from it with its
  interval, and names no winner -- mixed results need a written judgement, not a pass/fail.
- `oryxflow.evals`: `EvalResult.side_by_side(path=None, all=False, template=None)` -- every arm's
  output per case as markdown, by default only the cases where the arms disagree on a column the
  verdict reads, plus failures. Rendered with Jinja from the stored outputs (no model call);
  `template=` takes a path or a string.
- `oryxflow.evals`: `load_cases()` also takes a list of row dicts, routed exactly like a file's
  rows -- for a probe that keeps a handful of cases inline.
- `oryxflow.evals`: `ev.cli --side-by-side` writes `EvalResult.side_by_side()` to the eval module's
  own `results/<date>-<arms>-side-by-side.md`, wherever the run was launched from.
- `oryxflow.evals`: `ev.cli` warns when launched from a directory other than the eval script's own
  -- the cache and relative paths resolve against the working directory, so such a run reads and
  writes a different cache.
- `oryxflow.evals` — an LLM-eval harness over
  [pydantic-evals](https://pydantic.dev/docs/ai/evals/), installed with the new `evals` extra
  (`pip install oryxflow[evals]`; pydantic-evals, scipy, typer). Nothing in it is imported by
  `oryxflow/__init__.py`, so a user without the extra is unaffected; import it explicitly as
  `import oryxflow.evals as ev`. pydantic-evals keeps scoring — cases, evaluators, repeats,
  concurrency, retries, the success/failure split — and oryxflow adds the matrix and the cache:
  one parquet per arm, so a re-run of an unchanged arm makes zero calls and editing the target
  function or the case file re-runs only the cells that read it.
  - `ev.sweep(target, cases=..., metric=..., **arms)` runs the grid and returns an
    `ev.EvalResult` (`.df`, `.verdict()`, `.report()`, `.best()`). `target` may be a plain async
    function — no class and no scaffold for a first eval — or an `ev.TaskEval` subclass. Any
    keyword holding a list is an axis. The projected call count, the cached/new split and a cost
    estimate print **before** anything is billed, and a swept parameter the function cannot
    accept raises rather than running N identical cells labelled as branches. `watch=`
    (glob patterns, or a callable) folds files the target **reads** — a prompt template, a
    `.sql` file — into the cache key, so editing one re-runs the arms that read it; without it
    a prompt sits outside the key entirely and an edit re-runs nothing.
  - `ev.TaskEval` is the class form (a `TaskPqPandas` with `persists = ['cases']`): declare
    `dataset`, `metric`, `guardrail`, `slices` and one `case()` coroutine. `preflight()` makes
    one real call before the sweep, so a credential failure costs one call instead of a matrix;
    above `max_failure_rate` (default 20%) the run raises `ev.EvalFailureRateError` and **saves
    nothing**, because a parquet of exceptions is indistinguishable from a measurement.
    `concurrency` is `significant=False`, so it cannot fragment the cache.
  - `ev.load_cases(path, inputs=..., expected=...)` reads cases from `.csv` / `.yaml` / `.jsonl`,
    routing columns by name; a `@path/to/file.md` value is replaced by that file's text.
    `synthetic` cases are reported beside the headline and never in it, and `holdout` cases are
    withheld from every arm with the count stated.
  - `ev.Metric(label, column, where=, higher_is_better=, budget=, coverage=)` is the number a
    sweep is judged on. `ev.rate_ci` / `ev.delta_ci` (scipy, clustered by case) put a confidence
    interval on it. The verdict names **no winner** when the delta interval spans zero, never
    says "wins" unqualified when a guardrail budget broke, flags a metric that is identically 0%
    or 100% in every arm, and flags a denominator that moved between arms.
  - `ev.git_tree(ref, paths, dest=, expect_absent=)` materializes a baseline arm from a git ref
    (byte-exact, and the only mechanism that can restore a *deleted* file); `ev.git_sha(ref)` is
    the resolved SHA to use as that arm's `code_version()`. `ev.Variant(old, new)` is the
    anchored-replacement probe for a rewrite that has not shipped, and raises when its anchor is
    gone rather than silently becoming a no-op.
  - `ev.cli(TaskEvalSubclass)` builds a Typer command line whose flags are **derived** from the
    task's Parameters, so adding a parameter adds a repeatable flag and the two cannot drift.
    Built-ins: `--repeats --concurrency --reset --check --csv --yes`; `--check` runs `preflight()`
    only and exits. `ev.cli` / `ev.build_app` resolve on first use, so `import oryxflow.evals`
    does not pay for Typer.
### Changed
- `oryxflow.evals`: the `evals` extra now requires `pydantic-evals>=2` (for the tool-call
  evaluators, `CaseLifecycle` and Windows-safe report output) and adds `jinja2` (for
  `side_by_side()`).
- `oryxflow.evals`: `reset=True` / `--reset` discards BOTH stages, model calls included. Use
  `rescore` to re-run only the scorers.
- `oryxflow.evals`: the function form's arm identity now also follows what the target CALLS
  (`codehash.callable_code_hash`), not only the target's own body -- editing a project-local helper
  or prompt loader re-runs the arms that use it.
- `oryxflow.evals`: `rep` is read from pydantic-evals' own `"<name> [i/N]"` naming when outputs
  are stored, instead of being re-derived from row order (`TaskEval._assign_reps` is now a no-op
  kept as an override point).
- `oryxflow.evals`: **judge validation.** `ev.judge_alignment(df, judge, human)` reports a
  judge's TPR, TNR and Cohen's kappa against human labels, and `ev.corrected_rate(observed,
  alignment)` applies the Rogan-Gladen correction -- the standard estimator for a
  proportion measured with an imperfect test, which is what an LLM judge is. Declare it on
  the metric (`ev.Metric('pairing', 'pairing_holds', human='pairing_human')`) and the
  verdict prints the alignment and the corrected rate per arm. Kappa is reported *and
  labelled* as the one to read, because raw agreement inflates under class imbalance: on a
  90%-pass set a judge that passes everything scores 90% agreement and has learned nothing
  (kappa 0). The correction is REFUSED when `TPR + TNR <= 1`, where the estimator's
  denominator collapses and the "correction" is amplified noise. This matters beyond
  tidiness: an imperfect judge pulls every rate toward its own error floor, so it shrinks
  the very difference a sweep exists to detect -- a true 85% vs 55% reads as 78% vs 60%
  through a judge that is 88% accurate.
- `oryxflow.evals`: a **guardrail inside budget on the point estimate but not on its
  interval** now says so (`the interval for prod reaches 25% -- at this sample size the
  guardrail is not demonstrated, only not yet violated`). At n=12, `0% (0/12)` is entirely
  consistent with a true rate above a 5% budget, and the bound is the thing to act on.
- `oryxflow.evals`: a **lone arm scoring 100%** is flagged as saturated rather than
  reported as a win -- a case set that never fails cannot show a regression or an
  improvement, so the response is harder cases. (Multi-arm saturation was already caught
  by the dead-metric check.)
- `oryxflow.evals`: `ev.PromptArm` -- where one arm READS its prompt files and the cache
  key that MATCHES them, in one object (`.dir()` and `.code_version()`). Written by hand
  those are two places that must agree, and when they drift the failure is silent: a
  baseline arm reading a checked-out tree but keyed on a hash of the LIVE files re-runs
  when a live prompt is edited, and does *not* re-run when it is pointed at a different
  ref. A working-tree arm is keyed on the content of its `globs`, a `ref` arm on the
  resolved sha; both hand back the same layout via `subdir=`, so a loader never has to
  know which arm it got. An arm with no key at all is refused at construction.
- `oryxflow.evals`: the cost confirmation now offers the one-call preflight **at the
  prompt** -- `Run 56 new calls for X? (y/n/c=check one call first)`. `c` spends one call,
  reports whether the wiring works, and asks again. A `--check` flag only helps someone who
  already knows it exists, and the person who needs it most is running the eval for the
  first time. Deliberately still *offered* rather than run automatically before the bill: a
  tool that bills money should not make its first call unasked, however cheap.
- `oryxflow.evals`: `sweep()` accepts `evaluators=` and passes them to the dataset it generates.
  The target function is handed only `inputs`, so scoring against a case's `expected_output` — the
  shape every classifier eval has — previously required building a `Dataset` by hand and passing
  both `cases=` and `dataset=`.
- `oryxflow.evals`: a sweep axis with a **single value** no longer appears in the arm name. It is
  identical in every arm, so it added width to every row of every table and distinguished nothing:
  `model_id=['gemini-3.5-flash'], prompt_version=['prod','preship']` now names the arms `prod` and
  `preship` rather than `model_id_gemini-3.5-flash_prompt_version_prod`. When *no* axis varies the
  full name is kept, since a lone cell called `default` says less.
- `oryxflow.evals`: `verdict()` no longer reprints the call-count header that `sweep()` already
  emitted as the bill, and "Weakest slices" lists only slices actually **below** the arm's own
  rate — a 100% slice under that heading reads as a warning about something that is fine.
### Fixed
- `oryxflow.evals`: a `TaskEval` subclass now re-runs when its case set changes. Only the
  function form folded the cases into its cache key, so editing `cases.csv` under the class form
  served the previous cases' results.
- `oryxflow.evals`: under pandas 3 the `<field>_preview` columns were never written, because text
  columns get a `str` dtype instead of `object`.
- `oryxflow.evals`: the per-case frame was discarding most of what the report carried.
  `_to_frame()` read only assertions, scores, metadata and the output, so **six** things
  went on the floor. Now columns: `case.metrics` (what `increment_eval_metric` recorded --
  token counts, retries, anything a task measures about its own call), `case.attributes`
  (`set_eval_attribute` -- a resolved model snapshot, say), `case.expected_output`
  (flattened to `expected` / `expected_*`), `case.labels`, `case.total_duration`, and
  `report.report_evaluator_failures`. The `expected_*` recovery is the one that changes
  how code reads: a confusion matrix or a per-label breakdown is now a crosstab of two
  frame columns instead of joining the answer key back on by case name.
- `oryxflow.evals`: `EvalResult.verdict()` reports **measured usage** when the task
  recorded it -- `measured usage: input tokens 9,612, output tokens 2,720` -- read from
  the conventional `input_tokens` / `output_tokens` / `total_tokens` / `cost` columns.
  Before this, cost could only ever be the pre-run estimate, because the real numbers
  pydantic-evals collected were being thrown away. Reported by name rather than inferred
  from any numeric column: guessing which column is a token count eventually sums
  something that is not one.
- `oryxflow.evals`: an evaluator that **raised** is no longer indistinguishable from one
  that declined to score. `ReportCase.evaluator_failures` was read by nothing, so a judge
  crashing on every case (a missing API key, say) left its column absent and the metric
  reported `n/a` with no hint that anything was wrong. The frame now carries
  `evaluator_errors` / `evaluator_error` and the verdict prints them above the rate.
  `case.labels` was likewise dropped and is now a column like assertions and scores.
- `oryxflow.evals`: a sync `case()` (or a sync `sweep()` target) no longer silently
  serializes the run. `concurrency` is scheduled as coroutines by pydantic-evals, so a
  blocking case holds the event loop and the cases run one at a time while the setting
  still reads as honored -- same numbers, ~5x the wall clock (8 half-second cases at
  `concurrency=4`: 1.0s async, 4.9s sync). It now emits a `RuntimeWarning` naming the
  task and the ignored concurrency. Nothing about oryxflow itself is async; the
  requirement comes from the eval runner, and `concurrency=1` is the quiet way to opt out.
- `oryxflow.evals`: the dead-metric flag no longer fires on a **guardrail sitting inside
  its budget in every arm**. `0%` false-positives on both sides is the outcome a guardrail
  exists to confirm, and reporting it as "this usually measures the harness" teaches the
  reader to ignore the one line that matters when it is real. A guardrail identically
  *over* budget is still flagged.
- `oryxflow.evals`: declining the cost confirmation on the `ev.cli` path exits 0 with a
  one-line message instead of raising through to a traceback. Choosing not to spend is the
  outcome the confirmation exists to make easy.
- `oryxflow.evals`: a `Metric` no longer counts an **unmeasured** row as a failed one. A row whose
  metric column is null (an LLM judge that grades only some cases, or one switched off with
  `--judge-model none`) is now excluded from the rate exactly as an errored row is, instead of
  being coerced to `False`. Previously that both deflated the numerator and padded the
  denominator: a prompt passing 2 of 2 judged rows out of 6 reported `33%`, and a metric with no
  verdicts at all reported a confident `0%` with a confidence interval. `Metric.compute()` now
  counts only measured rows, a wholly unmeasured metric returns `NaN` and renders `n/a`, and
  `Metric.unmeasured()` / the verdict state how many rows carried no verdict. New
  `Metric.eligible()` is the denominator before that filter.
- `oryxflow.evals`: `sweep()` no longer silently overwrites a case metadata column named `arm` (or
  one named after a sweep axis) with its own cell label. `arm` is the natural word for a dataset
  that compares, say, an `outline` arm with a `guidelines` arm, and the tag destroyed it: any
  `slices=('arm',)` then reported the arm label back with no error and a plausible-looking table.
  The clash is knowable from the cases alone, so it now raises **before any call is made**, naming
  the key and the fix. `arm` joins `RESERVED_METADATA`.
