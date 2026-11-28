"""
QLoRA step 3: train a LoRA adapter on the 4-bit Qwen2.5-Coder 3B (QLoRA: LoRA on a quantized base),
on this Mac with MLX. Settings live in finetune/lora_config.yaml.

The checkpoint is chosen by validation loss on the held-out 10% of the training pool, never by
the benchmark. The chosen weights are copied to finetune/adapters/qwen3b-qlora/adapters.safetensors.

Writes results/finetune/training.json (every validation loss, the chosen step, minutes) and
logs/ft_train.log (the raw mlx_lm output).
"""

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "finetune" / "lora_config.yaml"
ADAPTER = REPO / "finetune" / "adapters" / "qwen3b-qlora"
LOG = REPO / "logs" / "ft_train.log"
OUT = REPO / "results" / "finetune" / "training.json"
VAL_LINE = re.compile(r"Iter (\d+): Val loss ([\d.]+)")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def main() -> None:
    LOG.parent.mkdir(exist_ok=True)
    start = time.time()
    with LOG.open("w") as log:
        proc = subprocess.Popen([sys.executable, "-m", "mlx_lm", "lora", "-c", str(CONFIG)], cwd=REPO,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            log.write(line)
            log.flush()
        if proc.wait():
            raise SystemExit(f"training failed, see {LOG}")
    minutes = round((time.time() - start) / 60, 1)

    text = ANSI.sub("", LOG.read_text())
    vals = [(int(i), float(v)) for i, v in VAL_LINE.findall(text)]
    if not vals:                       # newer mlx_lm prints a table: "  100    val 0.150   40.96s"
        vals = [(int(i), float(v)) for i, v in re.findall(r"^\s*(\d+)\s+val\s+([\d.]+)", text, re.M)]
    saved = {int(p.name.split("_")[0]): p for p in ADAPTER.glob("*_adapters.safetensors")}
    candidates = [(loss, step) for step, loss in vals if step in saved]
    best_loss, best_step = min(candidates)
    shutil.copy(saved[best_step], ADAPTER / "adapters.safetensors")
    for p in saved.values():           # keep only the chosen weights
        p.unlink()
    OUT.write_text(json.dumps({"config": CONFIG.read_text(), "minutes": minutes,
                               "val_loss_by_step": dict(vals), "chosen_step": best_step,
                               "chosen_val_loss": best_loss}, indent=2) + "\n")
    print(f"done in {minutes} min; chose step {best_step} (val loss {best_loss})")


if __name__ == "__main__":
    main()
