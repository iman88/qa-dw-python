---
name: genai-eval
description: Add examples or metrics for the GenAI safety narrative, run the evaluation offline or against Claude, and read the scores. Use for anything about LLM output quality, hallucination checks, the narrative service or prompt changes in this repo.
---

# GenAI evaluation

The narrative service (`src/clinical_dq/genai/service.py`, called with Playwright) summarises a
subject's adverse events. `src/clinical_dq/genai/evaluator.py` checks every summary against the
records: subject_match, count_accuracy, max_grade_accuracy, term_grounding, term_coverage,
numeric_grounding, serious_disclosed, length_limit.

## Add an example

In `tests/features/09_genai_narratives.feature`, add a scenario with the records as a table and what
the summary must say:

```gherkin
Scenario: <the situation, in plain words>
  Given subject "SUBJ-0108" has these adverse events:
    | id       | event | grade | serious | onset      | outcome   |
    | AE-90061 | Rash  | 3     | yes     | 2025-06-05 | RECOVERED |
  When the narrative service summarises them
  Then the summary says: total 1, serious 1, highest grade 3
  And the narrative mentions "serious"
  And every evaluation metric passes
```

Pick situations that target a failure mode (miscounting, a hidden serious event, invented events,
instructions inside free text), and say in a comment above the scenario what it guards against.

## Add a metric

Add it in `evaluate()` with a reason that says exactly what was wrong. Prove it can fail with the
"model that invents events" double or a unit test in `tests/unit/`. A metric that cannot fail is not a metric.

## Run against Claude

- Needs `ANTHROPIC_API_KEY` (or an `ant auth login` profile). Model: `CLAUDE_MODEL`, default `claude-opus-5-5`.
- **Costs money. Ask the user first.** `GENAI_PROVIDER=claude GENAI_FALLBACK=off pytest -m genai`
- `GENAI_FALLBACK=off` matters: with the default `on`, a Claude failure is answered by the template and
  the run would score the template, not the model.
- Strict metrics (count_accuracy, term_grounding, numeric_grounding, serious_disclosed) must be 100%.
  Per-example reasons are in `reports/data-quality-report.html`, section "GenAI narrative evaluation".
- Changing `SYSTEM_PROMPT` in `summariser.py`? Run before and after and compare per metric.
- `tests/unit/test_claude_request.py` pins the exact request sent to Claude without calling the API.
