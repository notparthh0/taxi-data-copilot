"""
QLoRA step 2: remove every overlap with the benchmark, then write the training files.

The only fine-tuning script that reads the benchmark: all 150 questions plus the 15 blind ones.
A kept candidate is dropped when:
  - its question is close in meaning to any benchmark question (cosine >= 0.85 between
    bge-small-en-v1.5 embeddings; a plain paraphrase scores about 0.93), or
  - its query result matches the gold answer of any answerable benchmark question
    (same frozen comparison as the grader), even when the wording is different.
Then exact duplicates inside the pool are removed, 10% is held out for validation
(seed 0), and each pair is rendered with the exact eval prompt (prompts.build, setup s3_docs).

Writes finetune/data/{train,valid}.jsonl (chat format for mlx_lm.lora) and
results/finetune/overlap_check.json (every count, plus the closest benchmark question per pair).
"""

import json
import random
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config, grader, prompts  # noqa: E402
from copilot.benchmark import BLIND_DIR, BLIND_GOLD_FILE, GOLD_FILE, load_gold, load_questions  # noqa: E402
from copilot.setups import get_setups  # noqa: E402

CANDIDATES = config.RESULTS_DIR / "finetune" / "candidates.jsonl"
REPORT = config.RESULTS_DIR / "finetune" / "overlap_check.json"
DATA = config.REPO / "finetune" / "data"
SIM_MAX = 0.85
VALID_SHARE = 0.10


def embed(texts):
    from fastembed import TextEmbedding
    v = np.array(list(TextEmbedding("BAAI/bge-small-en-v1.5").embed(texts)))
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def main() -> None:
    pool = [r for r in map(json.loads, CANDIDATES.read_text().splitlines()) if r["keep"]]
    bench = load_questions() + load_questions(directory=BLIND_DIR)
    gold = {**load_gold(GOLD_FILE), **load_gold(BLIND_GOLD_FILE)}

    sims = embed([r["q"] for r in pool]) @ embed([q.question for q in bench]).T
    nearest = sims.argmax(axis=1)
    kept, dropped_sim, dropped_answer, dupes, seen = [], [], [], 0, set()
    for i, r in enumerate(pool):
        near = {"benchmark_id": bench[nearest[i]].id, "similarity": round(float(sims[i, nearest[i]]), 3)}
        if near["similarity"] >= SIM_MAX:
            dropped_sim.append({"q": r["q"], **near})
            continue
        if not r["unanswerable"]:
            hit = next((q.id for q in bench if q.answerable and q.id in gold
                        and grader.tables_match(r["rows"], gold[q.id]["rows"])), None)
            if hit:
                dropped_answer.append({"q": r["q"], "same_answer_as": hit})
                continue
        if norm(r["q"]) in seen:
            dupes += 1
            continue
        seen.add(norm(r["q"]))
        kept.append({**r, "nearest": near})

    random.Random(0).shuffle(kept)
    n_valid = max(1, round(len(kept) * VALID_SHARE))
    setup = get_setups()["s3_docs"]
    DATA.mkdir(parents=True, exist_ok=True)
    for name, part in (("valid", kept[:n_valid]), ("train", kept[n_valid:])):
        with (DATA / f"{name}.jsonl").open("w") as f:
            for r in part:
                system, user = prompts.build(setup, r["q"])
                target = r["target"] if r["unanswerable"] else f"```sql\n{r['target']}\n```"
                f.write(json.dumps({"messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": user},
                                                 {"role": "assistant", "content": target}]}) + "\n")

    near_sims = [r["nearest"]["similarity"] for r in kept]
    report = {
        "candidates": sum(1 for _ in CANDIDATES.open()), "passed_second_opinion": len(pool),
        "benchmark_questions_checked": len(bench),
        "dropped_close_in_meaning": len(dropped_sim), "dropped_same_answer": len(dropped_answer),
        "dropped_duplicate_wording": dupes, "kept": len(kept),
        "train": len(kept) - n_valid, "valid": n_valid,
        "kept_unanswerable": sum(r["unanswerable"] for r in kept),
        "similarity_threshold": SIM_MAX,
        "kept_nearest_similarity": {"max": max(near_sims), "median": float(np.median(near_sims))},
        "dropped": {"close_in_meaning": dropped_sim, "same_answer": dropped_answer},
        "kept_pairs": [{"q": r["q"], "judge": r.get("judge", "gemini-3.5-flash-lite"),
                        "gen_model": r.get("gen_model", "gemini-3.5-flash-lite"), **r["nearest"]} for r in kept],
    }
    REPORT.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print({k: v for k, v in report.items() if not isinstance(v, (dict, list))})


if __name__ == "__main__":
    main()
