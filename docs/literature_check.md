# Literature check (15 Nov 2026)

**Question:** has anyone already done what this project plans to do?

**Short answer:** no one has done the whole thing, but each piece has a close neighbour.
The paper cannot claim "first to study data quality and LLMs", "first to compare docs
with a semantic layer", or a new metric. It can claim a narrower and still useful thing
(see "What we can honestly claim").

## How much to trust this file

- Every reference below was opened in a browser tool or shown in a search result with its
  title, authors and URL. Nothing here is from memory.
- **Checked twice** (opened a second time, title, authors and abstract confirmed): the seven
  marked ✔✔.
- **Checked once**: everything else in the tables.
- **Not properly verified**: listed in the last section. Do not cite those until they are opened.
- Numbers were read from abstracts and pages by a tool. **Before any number goes into the
  paper, re-read it in the PDF.**
- Vendor blogs (dbt Labs, MotherDuck, AtScale, Cube, Plexara) sell semantic layers or
  warehouses. Treat their numbers as claims, not as peer-reviewed results.

## 1. The references from the brief

| Reference | What it is | What it found | What it means for us |
|---|---|---|---|
| [arXiv 2408.04691](https://arxiv.org/abs/2408.04691) | Wretblad et al., "Synthetic SQL Column Descriptions and Their Impact on Text-to-SQL Performance", 2024, preprint | Column descriptions on BIRD dev. GPT-4o accuracy: 30.1% with none, 31.3% with BIRD's, 33.3% with gold, 36.8% with generated ones. | Docs help a little on BIRD. Data cleanliness is never varied. |
| [arXiv 2502.20657](https://arxiv.org/abs/2502.20657) | Gao and Luo (Alibaba), "Automatic database description generation for Text-to-SQL", 2025, preprint | A method for generating descriptions. BIRD dev average: 36.25% none, 37.18% generated, 38.59% human-written. | It is a method paper with a +0.93-point effect, not a broad study of descriptions. |
| [arXiv 2311.07509](https://arxiv.org/abs/2311.07509) | Sequeda, Allemang, Jacob (data.world), knowledge graphs vs SQL benchmark, 2023, preprint | 43 questions, insurance schema, GPT-4: 16% on SQL, 54% over a knowledge graph. | The two arms did not get the same information (SQL arm: DDL only). That is the gap our setup 3 vs 4 closes. |
| ✔✔ [dbt Labs blog](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026), [repo](https://github.com/dbt-labs/dbt-llm-sl-bench) | Ganz and Perigaud, "Semantic Layer vs. Text-to-SQL: 2026 Benchmark Update", 7 Apr 2026, vendor blog | 11 questions x 20 runs on Sequeda's insurance data. Original schema: text-to-SQL 64.5%, semantic layer 72.7%. After adding 3 dbt models: text-to-SQL 90.0% / 84.1%, semantic layer 98.2% / 100% (Sonnet 4.6 / GPT-5.3 Codex). | It already compares text-to-SQL before and after modelling. But "modelling" there means fixing joins, not cleaning dirty values, and it is 11 questions. |
| [MotherDuck research page](https://motherduck.com/research/query-log-informed-schema-descriptions-text-to-sql/) | E. Egorova, thesis done at MotherDuck, Aug 2025 | Descriptions mined from query logs: +2-3 points on BIRD dev, +16 points on MotherDuck's own warehouse, with Gemini 2.5 Flash. A Qwen model got worse. | A student thesis on a vendor site, not a paper. |
| [Spider 2.0, arXiv 2411.07763](https://arxiv.org/abs/2411.07763) | Lei et al., ICLR 2025, peer-reviewed | 632 enterprise tasks; best agent solved 21.3% at publication. | **It contains NYC yellow-taxi questions.** See section 4. |
| [BIRD, arXiv 2305.03111](https://arxiv.org/abs/2305.03111) | Li et al., NeurIPS 2023, peer-reviewed | 12,751 questions over 95 databases with "dirty" values. ChatGPT 40.08% vs humans 92.96%. | The dirt is fixed. BIRD never compares against a cleaned copy. |
| [arXiv 2402.12243](https://arxiv.org/abs/2402.12243) | Wretblad et al., noise in BIRD, ACL 2024 short paper | Errors in BIRD's questions and gold SQL are common. | "Noise" here means annotation mistakes, not dirty data. Lesson for us: gold SQL must be hand-checked. |

## 2. The closest work to each of our three ideas

### A. Raw vs cleaned data as the thing being tested

| Reference | Type | What it did | How ours differs |
|---|---|---|---|
| dbt Labs 2026 (above) | Vendor blog | Same questions before and after adding dbt models. | 11 questions; joins, not dirty values; no silent-error count. |
| ✔✔ [RADAR, arXiv 2506.08249](https://arxiv.org/abs/2506.08249) | Gu et al., NeurIPS 2025 Datasets and Benchmarks, peer-reviewed | 2,980 table-question pairs. Each question is asked on a clean table and on copies with missing values, bad values, outliers and inconsistencies. Models do well on clean tables and degrade on dirty ones. | **The paired clean-vs-dirty idea already exists.** But the dirt is injected artificially, the tables are small, and it is not text-to-SQL on a real pipeline. |
| [Data Agent Benchmark, arXiv 2603.20576](https://arxiv.org/abs/2603.20576) | Ma et al., 2026, preprint | 104 queries over 17 datasets with data problems put in on purpose. Best agent 57%. Hints about the problems helped only a few points. | No clean version is run for comparison. |
| [arXiv 2510.01989](https://arxiv.org/abs/2510.01989) | Kohita, 2025, preprint | How normalisation (1NF-3NF) changes SQL generation. | Schema shape is varied, not data cleanliness. |
| [SNAILS](https://dl.acm.org/doi/10.1145/3709727) | Luoma and Kumar, SIGMOD 2025, peer-reviewed | Clearer column names improve accuracy. | Naming only. |

### B. Written docs vs a semantic layer, with equal information

| Reference | Type | What it did | How ours differs |
|---|---|---|---|
| ✔✔ [arXiv 2609.22259](https://arxiv.org/abs/2609.22259) | Qing Ye, Sep 2026, preprint, single author | Four arms on DABStep, four models, separating *what the model is told* from *how it is delivered* and from pre-computed views. Finding: the content does most of the work (hard-task accuracy 13.9% to 55.1%, up to 37.0% to 77.4%). | **The nearest thing to our setup 3 vs 4. Must be cited and distinguished.** It has no arm where the model picks metrics and an engine (MetricFlow) writes the SQL, and no raw-data arm. |
| [AtScale blog, 28 Oct 2026](https://www.atscale.com/blog/semantic-layer-text-to-sql-accuracy/) | Vendor blog | 410 questions, 7 models. "Full documentation" 21.5-36.1% vs AtScale's layer 44.6-62.2%. | Says the docs arm had all the information, but does not show it. We enforce it with a test. |
| ✔✔ [arXiv 2604.25149](https://arxiv.org/abs/2604.25149) | Rumiantsau and Fokeev, Apr 2026, preprint | 100 questions on a retail dataset. Schema only 45.5-50.5%; plus a 4 KB markdown "semantic layer" document 67.7-68.7%. | Their "semantic layer" is a text file. Nothing is compiled. (Reported to be from Cube; the arXiv page lists no affiliation.) |
| [GSK study, JAMIA Open 2025](https://academic.oup.com/jamiaopen/article/8/1/ooaf003/8005804) | Painter et al., peer-reviewed | 60 real questions, GPT-4. Schema only 8.3%; plus a business-context document 78.3%. | Strong peer-reviewed evidence that docs help. One private database, no semantic layer. |
| [Plexara benchmark](https://plexara.io/benchmark/accuracy) | Vendor report | 25 "knowledge-trap" tasks: 42.7% to 98.7% with a knowledge layer. | **Trap questions as a design are not new.** Synthetic data. |

### C. Silent-error rate as the headline number

The idea exists under other names. We must use it, cite it, and not claim it.

| Reference | Type | Name it uses |
|---|---|---|
| ✔✔ [arXiv 2608.09254](https://arxiv.org/abs/2608.09254) | Morris Lee, Aug 2026, preprint | "False success": wrong answers as a share of returned answers (0.754 to 0.351). Uses a local 7B model. |
| ✔✔ [TrustSQL, arXiv 2403.15879](https://arxiv.org/abs/2403.15879) | Lee, Chay, Cho, Choi, 2024, preprint | A "reliability score" that penalises wrong answers and rewards abstaining. |
| arXiv 2604.25149 (above) | Preprint | "Silent hallucination" = SQL that runs but is wrong. |
| [FLEX, NAACL 2025](https://aclanthology.org/2025.naacl-long.228/) | Kim et al., peer-reviewed | False positives and false negatives of execution accuracy. |
| ✔✔ [arXiv 2611.04318](https://arxiv.org/abs/2611.04318) | Xu, Lin, Ma, Nov 2026, preprint | Models silently pick one reading of an ambiguous question. A warning for our grading: some "wrong" answers are a different valid reading. |

## 3. Verdicts

| Idea | Verdict | Confidence |
|---|---|---|
| **A.** Raw vs cleaned data, same questions | **Partly done.** RADAR did paired clean-vs-dirty (artificial dirt, not SQL). dbt did before/after modelling (11 questions, joins not dirt). Nobody found took one real dirty dataset, a real cleaning pipeline, and ran text-to-SQL on both. | about 75% |
| **B.** Docs vs semantic layer, equal information | **Partly done.** Ye (2609.22259) is close. Nobody found puts MetricFlow against a document proven to hold the same information. | about 70% |
| **C.** Silent-error rate | **Already exists** as a concept. What looks unclaimed is reporting the three-way split (correct / silent error / error or refusal) across data-engineering conditions. | about 85% that the metric is not new |

Vendors publish on this topic about once a month. **Re-run this check before submitting.**

## What we can honestly claim

- Safe: "A controlled text-to-SQL comparison of the raw and the dbt-cleaned version of the
  same real 38-million-row dataset, with documentation and a compiled semantic layer holding
  provably equal information, reported as correct / silent error / error."
- Not safe: "first to study data quality for LLM analytics", "first docs-vs-semantic-layer
  comparison", "a new metric".
- The real contribution is the **combination on one real pipeline**, and the equal-information
  control enforced by a test. That is modest, and it is enough for a solid workshop or
  regional-conference paper. It is not a top-venue novelty claim.

## 4. Things the brief got wrong, and risks

1. **Spider 2.0 already has NYC yellow-taxi questions**, and several of them tell the model in
   the question to exclude negative fares. Our trap questions leave that unsaid, which is the
   point, but the paper must cite this. It also means a model may have seen taxi-fare cleaning
   during training.
2. **dbt's benchmark** is not purely "semantic layer vs text-to-SQL". It also has text-to-SQL on
   modelled data, and it reuses Sequeda's dataset.
3. **Trap questions and paired clean/dirty designs both exist** (Plexara, RADAR).
4. **Ambiguity** (2611.04318): a "wrong" answer may be a legitimate other reading. Every benchmark
   question needs one unambiguous reading, or the silent-error rate will be inflated.

## Seen but not verified: do not cite yet

- "Pervasive Annotation Errors Break Text-to-SQL Benchmarks" ([arXiv 2601.08778](https://arxiv.org/abs/2601.08778)): numbers seen only in a search summary.
- Snowflake Cortex Analyst accuracy claims: the page returned an error.
- [Dr.Spider, arXiv 2301.08881](https://arxiv.org/abs/2301.08881): exists; whether its perturbations include dirty values is unconfirmed.
- [KaggleDBQA](https://arxiv.org/abs/2106.11455), [BIRD-Interact](https://arxiv.org/abs/2510.05318), [TrustDABench](https://arxiv.org/abs/2608.24145), [RTS](https://arxiv.org/abs/2501.10858), [CAIT, arXiv 2608.26036](https://arxiv.org/abs/2608.26036), [ETM, arXiv 2407.07313](https://arxiv.org/abs/2407.07313): abstract or snippet level only.
- MotherDuck blogs ([data models](https://motherduck.com/blog/bird-bench-and-data-models/), [semantic layers](https://motherduck.com/blog/oops-maybe-we-do-need-semantic-layers/)) and a [Medium review by Ka Ling Wu](https://medium.com/@kalingwu/text-to-sql-accuracy-semantic-layer-research-f39f62b952ba): opened once; opinion pieces.
