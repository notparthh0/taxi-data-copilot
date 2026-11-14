-- Mart: trips per pickup zone per hour (same grain as the mart in nyc-taxi-elt-pipeline).
-- One row per (pickup_date, pickup_hour, pickup_zone_id) that had at least one trip.
select
    pickup_date,
    pickup_hour,
    pickup_zone_id,
    count(*)                    as trip_count,
    avg(fare_amount)            as avg_fare,
    avg(trip_distance_miles)    as avg_trip_distance,
    sum(total_amount)           as total_revenue
from {{ ref('fct_trips') }}
group by 1, 2, 3
