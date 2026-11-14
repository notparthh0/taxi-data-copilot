"""
Phase 1 check: proves the four setups exist, are read-only, and answer one fixed
question each. Writes results/phase1_setups.json. No LLM is involved here: the
"answers" below are hand-written, only to exercise each setup's plumbing.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config, sqlguard  # noqa: E402
from copilot.setups import get_setups  # noqa: E402

# "What was the average fare in 2023?" answered the obvious way in each setup.
PROBE = {
    "s1_raw": "SELECT avg(fare_amount) AS avg_fare FROM yellow_tripdata",
    "s2_modelled": "SELECT avg(fare_amount) AS avg_fare FROM fct_trips",
    "s3_docs": "SELECT avg(fare_amount) AS avg_fare FROM fct_trips",
    "s4_semantic": {"metrics": ["avg_fare"]},
}

# Things a read-only copilot must refuse.
ATTACKS = {
    "drop_table": "DROP TABLE {t}",
    "delete_rows": "DELETE FROM {t}",
    "two_statements": "SELECT 1; DROP TABLE {t}",
    "read_local_file": "SELECT * FROM read_csv('/etc/passwd')",
    "copy_to_file": "COPY {t} TO '/tmp/leak.csv'",
    "attach_other_db": "ATTACH '/tmp/x.duckdb' AS x",
}


def main() -> None:
    out = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "setups": {}}
    for key, setup in get_setups().items():
        con = sqlguard.connect(setup.db_path)
        counts = {t: con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in setup.tables}
        con.close()
        probe = setup.execute(PROBE[key])
        refused = {}
        if setup.mode == "sql":
            for name, sql in ATTACKS.items():
                r = setup.execute(sql.format(t=setup.tables[0]))
                refused[name] = {"refused": r.status == "error", "how": r.error_type}
        ctx = setup.context()
        out["setups"][key] = {
            "title": setup.title,
            "database": setup.db_path.name,
            "mode": setup.mode,
            "tables_and_rows": counts,
            "context_characters": len(ctx),
            "probe_question": "What was the average fare in 2023?",
            "probe_status": probe.status,
            "probe_answer": probe.rows[0][0] if probe.rows else None,
            "probe_error": probe.error,
            "probe_seconds": probe.seconds,
            "attacks_refused": refused,
        }
        print(f"{key:12} {probe.status:5} avg_fare={probe.rows[0][0] if probe.rows else None} "
              f"context={len(ctx):,} chars  attacks refused={sum(v['refused'] for v in refused.values())}/{len(refused)}")
    config.RESULTS_DIR.mkdir(exist_ok=True)
    path = config.RESULTS_DIR / "phase1_setups.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {path.relative_to(config.REPO)}")


if __name__ == "__main__":
    main()
