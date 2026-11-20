# Findings (21 Nov 2026)

Written by hand from the tables in [RESULTS.md](RESULTS.md), which `scripts/summarise.py`
generates from `results/runs/*.jsonl`. Section numbers like "(RESULTS 4)" point to the table.
Read the limits at the end before quoting anything.

**What was run.** 150 questions (140 answerable, 10 not) x 5 setups, temperature 0, one attempt
per question (no repair loop), for three models:

| Model | Where it ran | Repeats | Answers |
|---|---|---:|---:|
| `gemini-3.5-flash-lite` | Google API | 3 | 2,250 |
| Qwen2.5-Coder-7B (4-bit) | this Mac, MLX | 1 | 750 |
| Qwen2.5-Coder-3B (4-bit) | this Mac, MLX | 1 | 750 |

Gemini's three repeats are pooled in every table (so its n is 3 times larger). Rates below are
"correct / silent error / error or refusal" on the answerable questions unless stated.

## 1. Cleaning the data is the biggest single step, for every model

| Setup (RESULTS 1) | Gemini | Qwen 7B | Qwen 3B |
|---|---:|---:|---:|
| Raw data, schema only: correct | 23.1% | 20.0% | 6.4% |
| Cleaned tables, schema only: correct | 93.6% | 77.1% | 53.6% |
| Gain from cleaning | +70.5 points | +57.1 points | +47.2 points |
| Raw data: silently wrong | 75.5% | 77.1% | 61.4% |
| Cleaned tables: silently wrong | 6.4% | 11.4% | 19.3% |

Same questions, same prompt, same models. Only the tables changed.

- On the 106 **trap** questions (where the obvious query on raw data gives a different number),
  no model gets anywhere on raw data: Gemini 0 correct of 318 answers, Qwen 7B 0.9%, Qwen 3B
  0.0% (RESULTS 3a).
- On the 34 questions where raw and cleaned data agree, Gemini scores 95.1% on raw data
  (RESULTS 3b). So the stronger model is not bad at SQL on raw data. It answers a different
  question, correctly, on dirty rows.
- Most raw-data silent errors are exactly the number the obvious raw query returns: 282 of 317
  for Gemini (89.0%), 84 of 108 for Qwen 7B (77.8%), 41 of 86 for Qwen 3B (47.7%)
  (RESULTS 5). The models did what a careless analyst would do. (For the 3B model the share is
  lower because more of its wrong answers are wrong for other reasons, too.)

**Honest caveat.** Part of this is true by construction. The gold answer is defined on cleaned
data, and a model shown only raw column names cannot know the cleaning rules. What carries the
weight is the size of the effect and finding 2.

**An odd detail worth knowing before a professor asks.** On the 34 non-trap questions, Qwen 7B
did *better* on raw data (79.4% correct) than on cleaned tables (52.9%), mostly because of SQL
errors on the cleaned schema (29.4% errors; RESULTS 3b). Gemini shows no such drop (95.1% vs
93.1%). n is small (34) and I have not looked into which column names tripped it up.

## 2. Documentation did not make up for skipping the cleaning

The extra arm (setup "1+") gives the model the raw table **plus** full docs: the data
dictionary, the 7 cleaning rules and the metric definitions. Trap questions only (RESULTS 4):

| | Correct | Silently wrong | Error |
|---|---:|---:|---:|
| Gemini, raw | 0.0% | 98.4% | 1.6% |
| Gemini, raw + docs | 14.2% | 49.1% | 36.8% |
| Gemini, cleaned | 93.7% | 6.3% | 0.0% |
| Qwen 7B, raw | 0.9% | 95.3% | 3.8% |
| Qwen 7B, raw + docs | 1.9% | 92.5% | 5.7% |
| Qwen 7B, cleaned | 84.9% | 9.4% | 5.7% |
| Qwen 3B, raw | 0.0% | 74.5% | 25.5% |
| Qwen 3B, raw + docs | 0.9% | 66.0% | 33.0% |
| Qwen 3B, cleaned | 60.4% | 19.8% | 19.8% |

The two model families failed in opposite ways:

- **Gemini tried to apply the rules and mostly broke the query.** None of its 200 silent
  errors with docs equals the naive raw number (RESULTS 5), so it always applied some rules.
  Of its 143 loud errors, 135 come from rule 7 alone: it tries to read the month out of the
  `source_file` name with `SUBSTR` and gets the character positions wrong (RESULTS 11). Its
  wrong numbers come from applying some rules but not all.
- **The docs made Gemini worse on the easy questions.** On non-trap questions it fell from
  95.1% correct (raw) to 31.4% (raw + docs) (RESULTS 3b).
- **The docs made Gemini unpredictable.** Raw + docs is by far its least stable setup: the same
  grade in all 3 repeats for only 53 of 150 questions (35.3%), against 86.0% to 98.7% for every
  other setup (RESULTS 8). Its correct count moved between 21 and 31 of 140 across repeats
  (RESULTS 8b).
- **The Qwen models largely ignored the rules.** 71.4% (7B) and 67.1% (3B) of their silent
  errors with docs are still the naive raw number (RESULTS 5).

In this experiment, telling the model the rules was not a substitute for applying them once
in a pipeline. That answers the "dirty data obviously gives wrong answers" objection: the
question is not whether dirt hurts, but whether documentation can fix it. Here it could not,
for any of the three models.

## 3. Docs on top of cleaned tables: a small gain, smallest for the smallest model

| (RESULTS 1) | Gemini | Qwen 7B | Qwen 3B |
|---|---:|---:|---:|
| Cleaned, schema only: correct | 93.6% | 77.1% | 53.6% |
| Cleaned + docs: correct | 98.3% | 82.9% | 55.0% |
| Gain | +4.7 points | +5.8 points | +1.4 points |
| Silent error, schema only to docs | 6.4% to 1.7% | 11.4% to 6.4% | 19.3% to 17.9% |

- For Gemini the gain holds up across repeats. Cleaned-only scored 130, 132 and 131 of 140;
  cleaned + docs scored 138, 137 and 138 (RESULTS 8b). So the gap (5 to 8 questions) is larger
  than the run-to-run spread (1 to 2 questions). Note that this only measures the model's own
  run-to-run noise, not how the gap would change with a different set of questions.
- The gain is largest on the hardest questions: Gemini level 3 rose from 84.8% to 100.0%
  (RESULTS 2.3).
- Qwen 7B's gain is from one pass and is similar in size; Qwen 3B barely benefits. The 3B model's
  problem is writing valid SQL at all (see finding 6), and docs do not fix that.

## 4. The semantic layer did not beat the docs. The hypothesis is not supported.

Setups 3 and 4 get the same information by construction. Setup 4 must ask the compiled
semantic layer (MetricFlow) for metrics instead of writing SQL. (RESULTS 6)

| Questions | Model | Docs: correct / silent / error | Semantic layer: correct / silent / error |
|---|---|---|---|
| Expressible in the layer (108) | Gemini | 98.8% / 1.2% / 0.0% | 89.5% / 1.5% / 9.0% |
| Expressible in the layer (108) | Qwen 7B | 89.8% / 2.8% / 7.4% | 64.8% / 9.3% / 25.9% |
| Expressible in the layer (108) | Qwen 3B | 63.9% / 16.7% / 19.4% | 28.7% / 5.6% / 65.7% |
| Not expressible (32) | Gemini | 96.9% / 3.1% / 0.0% | 0.0% / 63.5% / 36.5% |
| Not expressible (32) | Qwen 7B | 59.4% / 18.8% / 21.9% | 0.0% / 31.2% / 68.8% |
| Not expressible (32) | Qwen 3B | 25.0% / 21.9% / 53.1% | 0.0% / 34.4% / 65.6% |

Overall, the semantic layer cost 29.3 points for Gemini (98.3% to 69.0%), 32.9 for Qwen 7B
(82.9% to 50.0%) and 32.9 for Qwen 3B (55.0% to 22.1%) (RESULTS 1).

- **Where the layer can express the question,** it did not reduce silent errors for Gemini
  (1.2% vs 1.5%) and added loud ones. The one place it helped is the point of a semantic layer:
  Qwen 3B's silent errors fell from 16.7% to 5.6%. But its loud errors tripled, so it got far
  fewer answers right.
- **Most loud errors are interface mistakes, not wrong logic** (RESULTS 11). The biggest single
  cause: writing a month filter as `'2023-01'` where the layer needs a full date (30 of
  Gemini's errors, 35 of Qwen 7B's, 27 of Qwen 3B's). The second: asking for a metric or
  dimension name that does not exist, or sending an invalid request (61 of Qwen 3B's errors).
- **Where the layer cannot express the question** (percent shares, "top zone in each borough",
  daily statistics, percentiles), the honest reply is "the layer cannot answer this". Models
  rarely gave it: Gemini 21 of 96 times, Qwen 7B 3 of 32, Qwen 3B 0 of 32 (RESULTS 6). Mostly
  they returned something else, which is graded as a silent error (Gemini 61 of 96). The
  grader also counts the honest refusals as errors, because the question *is* answerable with
  SQL. Text-to-SQL with docs handled these questions well, for Gemini at least (96.9%).
- **Most of those "silent errors" are not wrong numbers.** On a read of a sample (not counted
  by a script), the model often returned correct ingredients (for "what percentage of trips
  were paid by card" it returned the trip count per payment type) but not the number asked
  for. A stricter analysis should separate "correct ingredients" from "wrong number". That
  split is not done.
- **Gemini's semantic-layer answers vary more between repeats** than its SQL answers: the same
  grade in all 3 repeats for 129 of 150 questions (86.0%), against 98.7% with docs (RESULTS 8).

So on this benchmark the semantic layer's promise (it cannot write wrong SQL) held only inside
its coverage. There it tied the docs on silent errors for the strongest model and lowered them
for the weakest, at a large cost in loud errors and coverage. The instructions for the layer's
request format were short. A longer guide with a month-filter example would probably remove
many loud errors. That is a limitation of this study, and the paper should say so.

## 5. Questions the data cannot answer

10 questions (no driver IDs, no cash tips, no ratings, ...). Correct means the model refused.
(RESULTS 7)

- Gemini refused 80.0% to 96.7% of the time depending on the setup (n=30 each, 3 repeats), and
  best with cleaned tables + docs (29 of 30).
- Qwen 7B refused 40% to 80% (n=10 each); Qwen 3B 20% to 60%. The small models often made up an
  answer.

With 10 questions these are indications, not rates.

## 6. Model size: the setups rank the same, the gaps do not

| Cleaned + docs, correct (RESULTS 2) | Gemini | Qwen 7B | Qwen 3B |
|---|---:|---:|---:|
| Level 1 | 95.3% | 100.0% | 82.0% |
| Level 2 | 100.0% | 81.8% | 54.5% |
| Level 3 | 100.0% | 60.0% | 17.1% |

- On easy questions, Qwen 7B is level with Gemini (it is ahead on level 1). The small models
  fall behind as the questions get harder.
- Qwen 3B often cannot write valid SQL: 29, 23, 21 and 11 of its answers in setups 1, 1+, 2 and
  3 are SQL that does not even parse, for example a select list that starts with `.Zone` with
  the table alias missing (RESULTS 11).
- **The ordering of the setups is the same for all three models:** raw < cleaned < cleaned +
  docs, and the semantic layer is below cleaned + docs (RESULTS 1). The conclusions above do not
  depend on which model is used. The sizes of the gaps do.

## What the data says about the research question

"Where does the accuracy come from: the model, the documentation, or the data engineering?"

On this dataset:

1. **Data engineering**, by far: +47 to +71 points from cleaning the tables, for every model,
   and documentation could not stand in for it.
2. **The model**, next: with the same cleaned tables and docs, 98.3% (Gemini) vs 82.9% (Qwen 7B)
   vs 55.0% (Qwen 3B), a 43-point spread. Most of it is on harder questions.
3. **Documentation**, last: +1.4 to +5.8 points on top of cleaned tables, and no rescue for raw
   data.
4. A compiled semantic layer did **not** add accuracy over equally informative docs. It cost 29
   to 33 points, mostly through interface mistakes and questions outside its coverage.

## Product check (not part of the experiment)

The copilot agent (setup 3 context, plus a repair loop, plus a plain-English answer) was
tried on the real warehouse through the HTTP API and the MCP server
(`results/api_trial.json`, `results/mcp_trial.json`, from `scripts/try_api.py` and
`scripts/try_mcp.py`):

- 12 benchmark questions over HTTP (every 14th answerable one plus 2 unanswerable): 12 of 12
  graded correct by the same grader, none needed a repair. 12 questions is a smoke test, not a
  score.
- 4 attack prompts over HTTP (drop a table, read `/etc/passwd`, print the API key, delete rows):
  Gemini refused all 4, the key did not appear in any reply, and every table had the same row
  count afterwards.
- 6 attack SQL statements sent straight to the MCP `run_sql` tool, with no model in the way:
  all 6 blocked. 5 were blocked by the SQL guard. The 6th (`read_csv('/etc/passwd')`) passed
  the guard and was stopped by DuckDB's own setting that disables file access. That is the
  second safety layer working, and it is why the guard alone should not be described as the
  whole defence.
- The slowest answer (about 15 s) was spent waiting on Gemini rate-limit retries, not on the
  query, which took 0.04 s.

## Limits (read before quoting)

- **Only Gemini has repeats.** The two Qwen runs are single passes. Gemini's run-to-run spread
  is 1 to 2 questions out of 140 in most setups, 5 for the semantic layer and 10 for raw + docs
  (RESULTS 8b). Treat differences of a few points for the Qwen models with care.
- **No confidence intervals across questions yet.** The repeats measure the model's own noise,
  not how much the results depend on which 140 questions were chosen. A bootstrap over
  questions would be the next step for the paper.
- **All 150 questions were written by Claude** and are not yet reviewed by the project owner.
  None were written blind. The author knew the data problems and the metric list.
- **The raw-vs-cleaned gap is partly true by construction** (see finding 1).
- **One dataset; one small cloud model and two small local models**; temperature 0; one attempt
  per question with no repair loop. A repair loop would likely fix many loud errors, especially
  the rule-7 and month-format ones.
- **The semantic-layer instructions were brief**, and "correct ingredients" are graded as silent
  errors (finding 4).
- **3 Gemini semantic-layer answers failed because of the harness, not the model**: the
  MetricFlow subprocess crashed on start (`Fatal Python error: init_sys_streams`; questions
  q122, q123 and q125 in repeat 2). They are graded as errors and were not rerun. At most they
  move Gemini's setup-4 score by 3 of 420 answers (0.7 points).
- **The `unsafe_sql` label in the run files is misleading.** All 97 such answers are SQL that the
  guard could not parse (syntax errors). None was an attempt to write or drop anything
  (RESULTS 11).
- **Error causes (RESULTS 11) are sorted by fixed text patterns**, written after the runs. They
  describe the errors and change no grade.
- **One correction after the first run:** 6 Gemini replies that said CANNOT_ANSWER inside a code
  block were first recorded as blocked SQL. They are now graded as refusals
  (`scripts/regrade_refusals.py`). No other grading rule was changed after the models ran.
