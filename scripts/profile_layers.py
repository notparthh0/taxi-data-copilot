"""
Measures how the raw layer differs from the cleaned layer. These numbers are the
raw material for "trap" questions (questions where the raw data quietly gives a
different answer). Writes results/phase1_layer_profile.json.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copilot import config, sqlguard  # noqa: E402

RAW = {
    "rows": "SELECT count(*) FROM yellow_tripdata",
    "fare_negative_rows": "SELECT count(*) FROM yellow_tripdata WHERE fare_amount < 0",
    "fare_zero_rows": "SELECT count(*) FROM yellow_tripdata WHERE fare_amount = 0",
    "distance_zero_or_less_rows": "SELECT count(*) FROM yellow_tripdata WHERE trip_distance <= 0",
    "passenger_count_null_rows": "SELECT count(*) FROM yellow_tripdata WHERE passenger_count IS NULL",
    "passenger_count_zero_rows": "SELECT count(*) FROM yellow_tripdata WHERE passenger_count = 0",
    "dropoff_not_after_pickup_rows": "SELECT count(*) FROM yellow_tripdata WHERE tpep_dropoff_datetime <= tpep_pickup_datetime",
    "longer_than_180_min_rows": "SELECT count(*) FROM yellow_tripdata WHERE date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime) > 180 * 60",
    "pickup_outside_file_month_rows": "SELECT count(*) FROM yellow_tripdata WHERE strftime(tpep_pickup_datetime, '%Y-%m') <> substr(source_file, 17, 7)",
    "pickup_not_in_2023_rows": "SELECT count(*) FROM yellow_tripdata WHERE year(tpep_pickup_datetime) <> 2023",
    "earliest_pickup": "SELECT min(tpep_pickup_datetime)::varchar FROM yellow_tripdata",
    "latest_pickup": "SELECT max(tpep_pickup_datetime)::varchar FROM yellow_tripdata",
    "avg_fare": "SELECT avg(fare_amount) FROM yellow_tripdata",
    "avg_trip_distance_miles": "SELECT avg(trip_distance) FROM yellow_tripdata",
    "max_trip_distance_miles": "SELECT max(trip_distance) FROM yellow_tripdata",
    "avg_passengers": "SELECT avg(passenger_count) FROM yellow_tripdata",
    "total_revenue": "SELECT sum(total_amount) FROM yellow_tripdata",
    "avg_duration_minutes": "SELECT avg(date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)) / 60 FROM yellow_tripdata",
}
CLEAN = {
    "rows": "SELECT count(*) FROM fct_trips",
    "earliest_pickup": "SELECT min(pickup_at)::varchar FROM fct_trips",
    "latest_pickup": "SELECT max(pickup_at)::varchar FROM fct_trips",
    "avg_fare": "SELECT avg(fare_amount) FROM fct_trips",
    "avg_trip_distance_miles": "SELECT avg(trip_distance_miles) FROM fct_trips",
    "max_trip_distance_miles": "SELECT max(trip_distance_miles) FROM fct_trips",
    "avg_passengers": "SELECT avg(passenger_count) FROM fct_trips",
    "total_revenue": "SELECT sum(total_amount) FROM fct_trips",
    "avg_duration_minutes": "SELECT avg(trip_duration_minutes) FROM fct_trips",
}


def run(db, queries):
    con = sqlguard.connect(db)
    try:
        return {name: con.execute(sql).fetchone()[0] for name, sql in queries.items()}
    finally:
        con.close()


def main() -> None:
    raw, clean = run(config.RAW_DB, RAW), run(config.WAREHOUSE_DB, CLEAN)
    shared = [k for k in CLEAN if isinstance(clean[k], (int, float))]
    diff = {k: {"raw": raw[k], "clean": clean[k],
                "raw_vs_clean_percent": round(100 * (raw[k] - clean[k]) / clean[k], 3)} for k in shared}
    out = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "raw": raw, "clean": clean, "same_question_both_layers": diff}
    path = config.RESULTS_DIR / "phase1_layer_profile.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    for k, v in diff.items():
        print(f"{k:26} raw={v['raw']:>18,.4f}  clean={v['clean']:>18,.4f}  diff={v['raw_vs_clean_percent']:+.3f}%")
    print(f"wrote {path.relative_to(config.REPO)}")


if __name__ == "__main__":
    main()
