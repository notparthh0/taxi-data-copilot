"""Loads the benchmark questions (benchmark/questions/*.yml) and their gold answers."""

import calendar
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from copilot import config

QUESTIONS_DIR = config.REPO / "benchmark" / "questions"
GOLD_FILE = config.RESULTS_DIR / "gold_answers.json"


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    difficulty: int
    category: str
    dataset: str = "nyc_taxi"
    answerable: bool = True
    gold_sql: str = ""
    naive_raw_sql: str = ""
    semantic: dict = None            # the same question as a semantic-layer request, if expressible
    ordered: bool = False            # row order is part of the answer
    skip: tuple = ()                 # label columns of the gold result that are not compared
    also_accept: tuple = ()          # other spellings of a single-value answer
    percent: bool = False            # answer is a percentage; the 0-1 fraction is accepted too
    month_answer: bool = False       # answer is a month number; '2023-05', 'May', ... accepted too
    why: str = ""                    # for unanswerable questions: why the data cannot answer it
    author: str = "claude"
    written_blind: bool = False
    checked_by: str = ""


BLIND_DIR = config.REPO / "benchmark" / "blind"
BLIND_GOLD_FILE = config.RESULTS_DIR / "gold_blind.json"


def load_questions(dataset: str = "nyc_taxi", directory: Path = QUESTIONS_DIR) -> list:
    """The frozen 150-question set by default. load_questions(directory=BLIND_DIR) loads the blind set."""
    out = []
    for path in sorted(directory.glob("*.yml")):
        for raw in yaml.safe_load(path.read_text()) or []:
            q = Question(
                id=raw["id"], question=raw["q"], difficulty=raw["d"], category=raw["cat"],
                dataset=raw.get("dataset", "nyc_taxi"), answerable=raw.get("answerable", True),
                gold_sql=raw.get("gold", ""), naive_raw_sql=raw.get("raw", ""), semantic=raw.get("sem"),
                ordered=raw.get("ordered", False), skip=tuple(raw.get("skip", ())),
                also_accept=tuple(str(a) for a in raw.get("also_accept", ())),
                percent=raw.get("percent", False), month_answer=raw.get("month_answer", False),
                why=raw.get("why", ""), author=raw.get("author", "claude"),
                written_blind=raw.get("written_blind", False), checked_by=raw.get("checked_by", ""))
            if q.dataset == dataset:
                out.append(q)
    ids = [q.id for q in out]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    return out


def month_spellings(month_number: int) -> tuple:
    m = int(month_number)
    return (f"2023-{m:02d}", f"2023-{m:02d}-01", calendar.month_name[m], calendar.month_abbr[m])


def load_gold() -> dict:
    """question id -> {'columns', 'rows', 'raw_rows', 'raw_diverges', ...} written by scripts/build_gold.py."""
    return json.loads(GOLD_FILE.read_text())["questions"]
