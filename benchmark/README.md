# Benchmark

`questions.yml` will hold about 150 questions. Parth reviews every question before it
goes in; nothing is added without his sign-off.

## Fields of one question

| Field | Meaning |
|---|---|
| `id` | Stable id, e.g. `q001`. |
| `dataset` | `nyc_taxi` for now. A second dataset gets its own value. |
| `question` | The business question in plain English, as a manager would ask it. |
| `difficulty` | `1` one table, one aggregate. `2` grouping, filters, top-N. `3` multi-step: ratios, comparisons, window logic. |
| `category` | What it measures: `count`, `average`, `revenue`, `ranking`, `time`, `ratio`, ... |
| `trap` | `true` if the raw data gives a different answer when queried the obvious way. |
| `trap_reason` | Which data problem causes it, e.g. `negative_fares`, `stray_months`. Empty if `trap: false`. |
| `author` | Who wrote it: `parth`, `claude`, or a classmate's name. Used to report results by author. |
| `written_blind` | `true` if the author had not seen the data problems or the docs. |
| `gold_sql` | Hand-checked SQL on the cleaned tables. Its result is the gold answer. |
| `naive_raw_sql` | The obvious SQL on the raw table. Its result is the "naive raw answer", used to recognise *why* a wrong answer is wrong. |
| `answer_shape` | `scalar`, `row`, or `table`; and whether row order matters. |
| `checked_by` | Who verified the gold SQL by hand, and the date. |

Gold answers are never typed in by hand. A script runs `gold_sql` and writes them to
`results/`, so the answers can always be regenerated from the data.

## Grading (decided up front, applied by a script)

- **correct**: the returned values match the gold answer (numbers within a small
  relative tolerance, to be fixed before any model is run; extra columns are allowed).
- **wrong but plausible (silent error)**: the query ran and returned an answer of the
  right shape, but the values do not match. Nothing tells the user it is wrong.
- **error or refusal**: SQL error, timeout, blocked by the read-only guard, or the
  model said it cannot answer.

The silent-error rate is the headline metric. Trap and normal questions are always
reported separately.
