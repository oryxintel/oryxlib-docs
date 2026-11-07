---
title: oryxeval, LLM evals
description: "oryxeval is a Python LLM-eval harness for trustworthy AI data analysis: test if a prompt, schema or model change is better, with cached arms and intervals."
---

# oryxeval

**Cheap, durable LLM evals. Free, local, and you never pay twice for the same answer.**

You changed a prompt, a response schema, a model or what a router reads. Is it better?
`oryxeval` (`import oryxeval as ev`) is a Python harness that answers that with a number you
can trust, not a hunch.

- **Cached arms.** Every arm of an eval matrix (prompt x model x ...) is a cached cell, so a
  re-run pays only for what changed. The cache is keyed on your code, the cases it read and the
  settings, not on the raw API request.
- **Intervals and a verdict.** Paired differences with confidence intervals, a guardrail metric
  that must not get worse, and a last line that says "inside noise" when it is.
- **Baselines from git.** Compare your working tree against the prompt as it was at any commit,
  without copying files around.
- **Re-score for free.** Model outputs and scores are cached separately, so changing a scorer or
  judge rubric re-runs only the scoring.
- **Your production code, as-is.** The function under test is an ordinary async Python function.

It is built on [oryxflow](../index.md) and uses pydantic-evals for scoring. Python 3.10+.

```bash
pip install oryxeval
```

## Where to go next

- [Quickstart](llm-evals-quickstart.md): a complete eval in one file, line by line.
- [Guide](llm-evals.md): run an eval as a cached parameter sweep.
- [Prompt files](llm-evals-prompts.md): keep prompts in files and compare them across commits.
- [Classes and functions](llm-evals-api.md): the API reference.
- [What a plan must contain](llm-evals-checklist.md): the checklist for a change that touches a prompt.
- [Claude Code plugin](claude-plugin/evals.md): four slash commands that plan, scaffold, grow and run an eval.
- [Changelog](llm-evals-changelog.md): what changed in each release.
