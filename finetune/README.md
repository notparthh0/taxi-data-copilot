# QLoRA follow-up: can a small local model close the gap?

The experiment found that Qwen2.5-Coder 3B, run locally, answers 55.0% of the 140 answerable
questions correctly on cleaned tables + docs (setup s3_docs), against 82.9% for the 7B and 98.3%
for Gemini. This follow-up asks whether a LoRA adapter, trained on this Mac, closes part of that gap.

It is **product-side and separate from the frozen experiment**: it never writes `results/runs/`,
`results/runs_blind/` or `docs/RESULTS.md`. Results: [`docs/FINETUNE.md`](../docs/FINETUNE.md).

## How the training data was made (and kept apart from the benchmark)

1. **`make ft-pairs`** (`scripts/ft_generate.py`): Gemini writes new questions on 16 topics, each with
   one DuckDB query, plus questions the data cannot answer. It sees the schema and docs, never
   the benchmark. Each query runs through the read-only guard.
2. **Second opinion:** the question alone goes through the exact eval prompt to another Gemini
   call. A pair is kept only when both queries return the same table (the grader's comparison), or,
   for an unanswerable question, when the second opinion refuses.
3. **`make ft-filter`** (`scripts/ft_filter.py`), the only step that reads the benchmark: drops any
   pair close in meaning to one of the 165 benchmark questions (bge-small embeddings, cosine >= 0.85)
   or whose result equals a benchmark gold answer. Counts and every dropped pair:
   `results/finetune/overlap_check.json`.
4. Training prompts are rendered with `prompts.build` for s3_docs, so the model is trained on the
   exact text it sees at test time; answers are a fenced SQL block or `CANNOT_ANSWER: <reason>`.

## Training and evaluation

- **`make ft-train`**: QLoRA (a LoRA adapter on the 4-bit model) with `mlx_lm`; settings in
  `lora_config.yaml`. The checkpoint is chosen by validation loss on the held-out 10% only.
- **`make ft-eval`**: the base and the tuned model, same harness, same frozen grader, one attempt per
  question at temperature 0, on the 150 questions and the 15 blind ones. Run once, after the
  data, settings and adapter were committed.
- **`make ft-summary`**: `results/finetune/summary.json` and `docs/FINETUNE.md`, with a paired
  bootstrap interval over questions.

The model is available to the agent as `COPILOT_MODEL=qwen-coder-3b-qlora`.
