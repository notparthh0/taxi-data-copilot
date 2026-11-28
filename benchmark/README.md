# Benchmark

- `questions/level1.yml`, `level2.yml`, `level3.yml`: 140 answerable questions (50 / 55 / 35).
- `questions/unanswerable.yml`: 10 questions the data cannot answer (the right reply is to refuse).
- `blind/blind.yml`: 15 extra questions written by a fresh model instance that saw only the
  cleaned table schema (not the cleaning rules, the metric list or the 150 questions). Reported
  separately (RESULTS table 14); not a human blind set.

`copilot/benchmark.py` loads them. The 150 in `questions/` are the frozen experiment set.

## Fields of one question

| Field | Meaning |
|---|---|
| `id` | Stable id: `q001`..., `u001`... (unanswerable), `b001`... (blind). |
| `d` | Difficulty. `1` one table, one number; `2` grouping, ranking, time, a join; `3` shares, comparisons, per-group tops, daily statistics, percentiles. |
| `cat` | Kind of question: `count`, `average`, `revenue`, `ranking`, `time`, `share`, ... |
| `q` | The business question in plain English. |
| `gold` | SQL on the cleaned tables. Its result is the gold answer. |
| `raw` | The obvious SQL on the raw table. Its result is the "naive raw answer". |
| `sem` | The same question as a semantic-layer request, if the layer can express it. |
| `answerable`, `why` | `false` plus the reason, for questions the data cannot answer. |
| `ordered`, `skip`, `percent`, `month_answer`, `also_accept` | Grading hints: row order matters; label columns not compared; a 0-1 fraction is also accepted; other spellings of a month or value. |
| `author`, `written_blind`, `checked_by` | Who wrote it, whether they had seen the data problems, who checked it. |

**Review record:** all 165 questions (150 + 15 blind) were read and approved by the project owner on 22 Nov 2026. No question, gold query or answer was changed in that review, so no result had to be re-run. The `checked_by` fields were left empty on purpose: editing the frozen question files for metadata was not worth the risk.

Gold answers are never typed by hand. `make gold` (and `make blind`) run the gold and raw SQL
and write `results/gold_answers.json` (`results/gold_blind.json`). A question is a **trap** when
the naive raw answer differs from the gold one: measured, not asserted.

## Grading (`copilot/grader.py`, fixed before any model ran)

- **correct**: the same number of rows as the gold answer, and every gold column appears with the
  same values (numbers within 0.1%; extra columns allowed).
- **silent error**: the query ran and returned something, but not the gold answer.
- **error or refusal**: SQL error, blocked by the read-only guard, or the model said it cannot
  answer. For an unanswerable question a refusal is the correct reply.
