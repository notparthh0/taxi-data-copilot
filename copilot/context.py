"""
Builds the text each setup shows to the model.

  schema_text()      setups 1-3: table and column names with types, nothing else
  docs_text()        setup 3:    written documentation
  semantic_text()    setup 4:    the semantic layer catalogue (metrics + dimensions)

docs_text() and semantic_text() are both rendered from the SAME three sources:
the semantic manifest (dbt/taxi_copilot/models/semantic/trips.yml, compiled by dbt),
the dbt model descriptions, and knowledge/cleaning_rules.yml. That is how setups 3
and 4 carry equal information; tests/test_parity.py checks it.
"""

import json
import re
from dataclasses import dataclass

import yaml

from copilot import config, sqlguard

AGG_SQL = {"sum": "SUM", "average": "AVG", "median": "MEDIAN", "max": "MAX", "min": "MIN",
           "count": "COUNT", "count_distinct": "COUNT(DISTINCT"}
FACT_TABLE = "fct_trips"
ENTITY = "trip"


@dataclass(frozen=True)
class Dimension:
    name: str
    kind: str          # 'time' or 'categorical'
    description: str


@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    definition: str    # the formula in plain SQL terms


@dataclass(frozen=True)
class Knowledge:
    dimensions: tuple
    metrics: tuple
    rules_intro: str
    rules: tuple       # (id, drop_if, why)


# ---------- schema only (setups 1, 2, 3) ----------

def schema_text(db_path, tables) -> str:
    con = sqlguard.connect(db_path)
    try:
        blocks = []
        for table in tables:
            cols = con.execute(f'DESCRIBE "{table}"').fetchall()
            lines = ",\n".join(f"  {c[0]} {c[1]}" for c in cols)
            blocks.append(f"TABLE {table} (\n{lines}\n)")
        return "\n\n".join(blocks)
    finally:
        con.close()


# ---------- shared knowledge (setups 3 and 4) ----------

def _filter_sql(metric: dict) -> str:
    where = (metric.get("filter") or {}).get("where_filters") or []
    parts = [re.sub(r"\{\{\s*Dimension\('\w+__(\w+)'\)\s*\}\}", r"\1", w["where_sql_template"]) for w in where]
    return " AND ".join(parts)


def _metric_definition(metric: dict, measures: dict) -> str:
    params = metric["type_params"]
    if metric["type"] == "simple":
        m = measures[params["measure"]["name"]]
        if m["agg"] == "sum" and m["expr"] == "1":
            text = "COUNT(*)"
        elif m["agg"] == "count_distinct":
            text = f"COUNT(DISTINCT {m['expr']})"
        else:
            text = f"{AGG_SQL[m['agg']]}({m['expr'] or m['name']})"
        text += f" over {FACT_TABLE}"
    elif metric["type"] == "ratio":
        text = f"{params['numerator']['name']} / {params['denominator']['name']}"
    elif metric["type"] == "derived":
        text = params["expr"]
    else:
        raise ValueError(f"metric type not handled yet: {metric['type']}")
    where = _filter_sql(metric)
    return f"{text}, only rows where {where}" if where else text


def load_knowledge() -> Knowledge:
    manifest = json.loads(config.SEMANTIC_MANIFEST.read_text())
    model = next(m for m in manifest["semantic_models"] if m["name"] == "trips")
    measures = {m["name"]: m for m in model["measures"]}
    dimensions = tuple(Dimension(d["name"], d["type"], d["description"]) for d in model["dimensions"])
    metrics = tuple(Metric(m["name"], m["description"], _metric_definition(m, measures))
                    for m in sorted(manifest["metrics"], key=lambda m: m["name"]))
    rules = yaml.safe_load(config.CLEANING_RULES.read_text())
    return Knowledge(dimensions, metrics, " ".join(rules["intro"].split()),
                     tuple((r["id"], r["drop_if"], r["why"]) for r in rules["rules"]))


def _rules_block(k: Knowledge) -> str:
    lines = [f"{rid}. Dropped if {drop_if}. {why}" for rid, drop_if, why in k.rules]
    return "## Cleaning rules\n" + k.rules_intro + "\n" + "\n".join(lines)


def _metrics_block(k: Knowledge) -> str:
    return "\n".join(f"- {m.name}: {m.description} Formula: {m.definition}." for m in k.metrics)


def _other_tables_block() -> str:
    """Descriptions of the modelled tables other than the fact table (from dbt)."""
    nodes = json.loads(config.DBT_MANIFEST.read_text())["nodes"]
    out = []
    for name in ("dim_zones", "trips_hourly_demand"):
        node = nodes[f"model.taxi_copilot.{name}"]
        out.append(f"### {name}\n{' '.join(node['description'].split())}")
        out += [f"- {c}: {meta['description']}" for c, meta in node["columns"].items()]
    return "\n".join(out)


# ---------- setup 3: written docs ----------

def docs_text() -> str:
    k = load_knowledge()
    cols = "\n".join(f"- {d.name}: {d.description}" for d in k.dimensions)
    return "\n\n".join([
        "# Documentation",
        f"## Columns of {FACT_TABLE} (one row per trip)\n{cols}",
        f"## Other tables\n{_other_tables_block()}",
        "## Metric definitions (how the business defines each number)\n" + _metrics_block(k),
        _rules_block(k),
    ])


# ---------- extra arm: raw data + docs ----------

def raw_docs_text() -> str:
    """Docs for the RAW table: the TLC data dictionary, the same metric definitions,
    and the 7 cleaning rules written as filters the analyst must apply by hand."""
    k = load_knowledge()
    d = yaml.safe_load((config.REPO / "knowledge" / "raw_dictionary.yml").read_text())
    cols = "\n".join(f"- {name}: {text}" for name, text in d["columns"].items())
    lookup = "\n".join(f"- {name}: {text}" for name, text in d["lookup_columns"].items())
    rules = "\n".join(f"{rid}. Drop the trip if {drop_if}. {why}" for rid, drop_if, why in k.rules)
    return "\n\n".join([
        "# Documentation",
        f"## Columns of {d['table']} (one row per trip, NOT cleaned)\n{cols}",
        f"## Columns of {d['lookup_table']}\n{lookup}",
        "## Cleaning rules (NOT applied to this table - apply them in your query)\n"
        "This table is raw. Business numbers are defined on valid trips only. A trip is valid "
        "only if it passes all 7 rules:\n" + rules,
        "## Metric definitions (how the business defines each number)\n"
        + " ".join(d["name_map"].split()) + "\n" + _metrics_block(k),
    ])


# ---------- setup 4: semantic layer catalogue ----------

SEMANTIC_HOWTO = f"""## How to ask
Do not write SQL. Reply with one JSON object:
{{"metrics": [...], "group_by": [...], "where": [...], "order_by": [...], "limit": N}}
- metrics: one or more metric names from the list below (required).
- group_by: dimension names written as {ENTITY}__<dimension>, e.g. {ENTITY}__pickup_borough.
  For time use metric_time__day, metric_time__week, metric_time__month, metric_time__quarter
  or metric_time__year (metric_time is the pickup date).
- where: filters such as "{{{{ Dimension('{ENTITY}__payment_type') }}}} = 'Cash'" or
  "{{{{ TimeDimension('metric_time', 'day') }}}} >= '2023-03-01'".
- order_by: names from metrics or group_by; prefix with - for descending.
- limit: optional row limit.
If the question cannot be answered with these metrics and dimensions, reply {{"cannot_answer": "<reason>"}}."""


def semantic_text() -> str:
    k = load_knowledge()
    dims = "\n".join(f"- {ENTITY}__{d.name}: {d.description}" for d in k.dimensions)
    return "\n\n".join([
        "# Semantic layer",
        SEMANTIC_HOWTO,
        "## Metrics\n" + _metrics_block(k),
        f"## Dimensions (each describes one trip)\n{dims}",
        _rules_block(k),
    ])
