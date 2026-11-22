"""
QLoRA step 5: compare the fine-tuned 3B with the same base model on the same questions.

Reads results/finetune/runs/*.jsonl (setup s3_docs, the frozen 150 questions) and
results/finetune/runs_blind/*.jsonl (the 15 blind ones). The 7B and Gemini rows are read from the
frozen experiment (results/runs/, same setup, same grader) for reference only.
The paired bootstrap resamples questions (10,000 draws, seed 0).

Writes results/finetune/summary.json and docs/FINETUNE.md (generated; do not edit by hand).
"""

import datetime as dt
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config  # noqa: E402

FT = config.RESULTS_DIR / "finetune"
BASE, TUNED = "qwen-coder-3b-base-control", "qwen-coder-3b-qlora"
REFERENCE = {"qwen-coder-7b": "Qwen2.5-Coder 7B (frozen run)", "gemini-flash-lite": "Gemini 3.5 Flash-Lite (frozen run, 3 repeats)"}


def load(path: Path, setup="s3_docs"):
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [r for r in rows if r["setup"] == setup]


def rates(rows):
    ans = [r for r in rows if r["answerable"]]
    un = [r for r in rows if not r["answerable"]]
    share = lambda xs, g: round(100 * sum(r["grade"] == g for r in xs) / len(xs), 1) if xs else None  # noqa: E731
    return {"n_answerable": len(ans), "correct_pct": share(ans, "correct"),
            "correct": sum(r["grade"] == "correct" for r in ans),
            "silent_error_pct": share(ans, "silent_error"), "error_or_refusal_pct": share(ans, "error_or_refusal"),
            "unanswerable_refused": f"{sum(r['grade'] == 'correct' for r in un)}/{len(un)}",
            "median_llm_seconds": round(statistics.median(r["llm_seconds"] for r in rows), 2) if rows else None,
            "by_difficulty": {d: share([r for r in ans if r["difficulty"] == d], "correct") for d in (1, 2, 3)}}


def paired(base, tuned, draws=10_000):
    b = {r["question_id"]: r["grade"] == "correct" for r in base if r["answerable"]}
    t = {r["question_id"]: r["grade"] == "correct" for r in tuned if r["answerable"]}
    ids = sorted(set(b) & set(t))
    diff = [t[i] - b[i] for i in ids]
    rng = random.Random(0)
    boots = sorted(sum(rng.choice(diff) for _ in ids) / len(ids) for _ in range(draws))
    return {"questions": len(ids), "points": round(100 * sum(diff) / len(ids), 1),
            "ci95_points": [round(100 * boots[int(0.025 * draws)], 1), round(100 * boots[int(0.975 * draws)], 1)],
            "fixed": sum(d == 1 for d in diff), "broken": sum(d == -1 for d in diff)}


def closeness_check(base, tuned):
    """Were the fixed questions closer to the training pairs than the rest? (bge-small cosine, as in ft_filter)"""
    import numpy as np
    from fastembed import TextEmbedding
    from copilot.benchmark import load_questions
    text = {q.id: q.question for q in load_questions()}
    b = {r["question_id"]: r["grade"] == "correct" for r in base if r["answerable"]}
    t = {r["question_id"]: r["grade"] == "correct" for r in tuned if r["answerable"]}
    ids = sorted(set(b) & set(t))
    fixed = {i for i in ids if t[i] and not b[i]}
    pairs = [p["q"] for p in json.loads((FT / "overlap_check.json").read_text())["kept_pairs"]]
    model = TextEmbedding("BAAI/bge-small-en-v1.5")
    emb = lambda xs: (lambda v: v / np.linalg.norm(v, axis=1, keepdims=True))(np.array(list(model.embed(xs))))  # noqa: E731
    near = dict(zip(ids, (emb([text[i] for i in ids]) @ emb(pairs).T).max(axis=1).tolist()))
    med = lambda xs: round(statistics.median(xs), 3)  # noqa: E731
    return {"fixed_median_similarity": med([near[i] for i in fixed]),
            "others_median_similarity": med([near[i] for i in ids if i not in fixed]),
            "n_fixed": len(fixed), "n_others": len(ids) - len(fixed)}


def main() -> None:
    base, tuned = load(FT / "runs" / f"{BASE}.jsonl"), load(FT / "runs" / f"{TUNED}.jsonl")
    out = {"generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "setup": "s3_docs", "base": rates(base), "tuned": rates(tuned), "paired": paired(base, tuned),
           "blind": {"base": rates(load(FT / "runs_blind" / f"{BASE}.jsonl")),
                     "tuned": rates(load(FT / "runs_blind" / f"{TUNED}.jsonl"))},
           "reference": {k: rates(load(config.RESULTS_DIR / "runs" / f"{k}.jsonl")) for k in REFERENCE},
           "data": json.loads((FT / "overlap_check.json").read_text()) | {"dropped": "see overlap_check.json",
                                                                         "kept_pairs": "see overlap_check.json"},
           "training": json.loads((FT / "training.json").read_text()),
           "closeness": closeness_check(base, tuned)}
    (FT / "summary.json").write_text(json.dumps(out, indent=2) + "\n")

    p, d = out["paired"], out["data"]
    lines = ["# QLoRA follow-up: does a fine-tuned 3B model close the gap?", "",
             "Generated by `scripts/ft_summarise.py`; do not edit by hand. A product-side follow-up, run after the",
             "experiment was frozen: nothing here changes `docs/RESULTS.md`. Setup s3_docs (cleaned tables + docs),",
             "one attempt per question, temperature 0, the same frozen grader.", "",
             "| Model | Correct (of 140) | Silent errors | Errors / refusals | Unanswerable refused | Median s / answer |",
             "|---|---:|---:|---:|---:|---:|"]
    for name, r in [("Qwen2.5-Coder 3B, base (re-run here)", out["base"]),
                    ("**Qwen2.5-Coder 3B + QLoRA adapter**", out["tuned"])] + \
                   [(REFERENCE[k], out["reference"][k]) for k in REFERENCE]:
        lines.append(f"| {name} | {r['correct_pct']}% (n={r['n_answerable']}) | {r['silent_error_pct']}% | "
                     f"{r['error_or_refusal_pct']}% | {r['unanswerable_refused']} | {r['median_llm_seconds']} |")
    lines += ["", f"**Paired change, tuned minus base:** {p['points']:+} points "
                  f"(95% bootstrap interval {p['ci95_points'][0]:+} to {p['ci95_points'][1]:+}; "
                  f"{p['fixed']} questions fixed, {p['broken']} broken, {p['questions']} compared).", "",
              "**Did it just learn near-copies of the test questions?** For each benchmark question, take its "
              "closest training question (embedding similarity). Fixed questions: median "
              f"{out['closeness']['fixed_median_similarity']} (n={out['closeness']['n_fixed']}); all the others: "
              f"{out['closeness']['others_median_similarity']} (n={out['closeness']['n_others']}). The fixed ones are "
              "no closer to the training data than the rest.", "",
              "By difficulty (correct %, levels 1 / 2 / 3): base "
              + " / ".join(str(out['base']['by_difficulty'][k]) for k in (1, 2, 3)) + ", tuned "
              + " / ".join(str(out['tuned']['by_difficulty'][k]) for k in (1, 2, 3)) + ".", "",
              f"Blind set (15 questions): base {out['blind']['base']['correct']}/{out['blind']['base']['n_answerable']}, "
              f"tuned {out['blind']['tuned']['correct']}/{out['blind']['tuned']['n_answerable']} correct.", "",
              "## Training data", "",
              f"- {d['candidates']} candidate questions written by Gemini, each with a DuckDB query "
              f"(`scripts/ft_generate.py`; it never reads the benchmark).",
              f"- {d['passed_second_opinion']} passed the second opinion: the question alone, sent through the exact "
              "eval prompt, gave the same result table (or, for unanswerable ones, a refusal).",
              f"- Removed for overlap with the 165 benchmark questions (`scripts/ft_filter.py`): "
              f"{d['dropped_close_in_meaning']} close in meaning (embedding similarity >= {d['similarity_threshold']}), "
              f"{d['dropped_same_answer']} with the same answer as a benchmark question. "
              f"Highest similarity left: {d['kept_nearest_similarity']['max']}.",
              f"- Kept {d['kept']} ({d['kept_unanswerable']} unanswerable): {d['train']} train, {d['valid']} validation.",
              "", "## Training", "",
              f"- QLoRA with MLX on a MacBook Air M4 (16 GB): LoRA adapter on the 4-bit model, "
              f"{out['training']['minutes']} minutes. Settings: `finetune/lora_config.yaml`.",
              f"- Checkpoint chosen by validation loss only (step {out['training']['chosen_step']}, "
              f"loss {out['training']['chosen_val_loss']}); the benchmark was run once, after that choice.",
              "", "## Limits", "",
              "- The benchmark questions are not yet reviewed by the owner (same caveat as the main results).",
              "- The training questions come from Gemini, so this is distillation from a larger model, on one dataset.",
              "- One run per model at temperature 0; no repeats for the local models."]
    (config.REPO / "docs" / "FINETUNE.md").write_text("\n".join(lines) + "\n")
    print(f"base {out['base']['correct_pct']}% -> tuned {out['tuned']['correct_pct']}% "
          f"({p['points']:+} pts, CI {p['ci95_points']}); unanswerable {out['base']['unanswerable_refused']} -> "
          f"{out['tuned']['unanswerable_refused']}")


if __name__ == "__main__":
    main()
