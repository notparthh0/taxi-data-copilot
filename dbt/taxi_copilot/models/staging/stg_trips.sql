-- Staging: the cleaned Iceberg trips with tidy names. A view, not exposed to the LLM.
select
    tpep_pickup_datetime                as pickup_at,
    tpep_dropoff_datetime               as dropoff_at,
    cast(passenger_count as integer)    as passenger_count,
    trip_distance                       as trip_distance_miles,
    trip_duration_minutes,
    cast(PULocationID as integer)       as pickup_zone_id,
    cast(DOLocationID as integer)       as dropoff_zone_id,
    cast(RatecodeID as integer)         as rate_code_id,
    cast(payment_type as integer)       as payment_type_id,
    fare_amount,
    tip_amount,
    tolls_amount,
    total_amount
from {{ source('lake', 'trips_cleaned') }}
