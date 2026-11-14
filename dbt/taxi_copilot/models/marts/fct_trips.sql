-- Fact table: one row per cleaned trip, with zone names and code labels joined in,
-- so questions do not need joins or code lookups.
-- Code labels come from the official TLC yellow taxi data dictionary.
select
    t.pickup_at,
    t.dropoff_at,
    cast(t.pickup_at as date)                       as pickup_date,
    hour(t.pickup_at)                               as pickup_hour,
    isodow(t.pickup_at)                             as pickup_day_of_week,
    dayname(t.pickup_at)                            as pickup_day_name,
    isodow(t.pickup_at) >= 6                        as is_weekend,
    strftime(t.pickup_at, '%Y-%m')                  as month_key,

    t.pickup_zone_id,
    pz.zone_name                                    as pickup_zone,
    pz.borough                                      as pickup_borough,
    t.dropoff_zone_id,
    dz.zone_name                                    as dropoff_zone,
    dz.borough                                      as dropoff_borough,

    case t.payment_type_id
        when 0 then 'Flex Fare trip'
        when 1 then 'Credit card'
        when 2 then 'Cash'
        when 3 then 'No charge'
        when 4 then 'Dispute'
        when 5 then 'Unknown'
        when 6 then 'Voided trip'
        else 'Unknown'
    end                                             as payment_type,
    case t.rate_code_id
        when 1 then 'Standard rate'
        when 2 then 'JFK'
        when 3 then 'Newark'
        when 4 then 'Nassau or Westchester'
        when 5 then 'Negotiated fare'
        when 6 then 'Group ride'
        else 'Unknown'
    end                                             as rate_code,

    t.passenger_count,
    t.trip_distance_miles,
    t.trip_duration_minutes,
    t.fare_amount,
    t.tip_amount,
    t.tolls_amount,
    t.total_amount
from {{ ref('stg_trips') }} t
left join {{ ref('dim_zones') }} pz on t.pickup_zone_id = pz.zone_id
left join {{ ref('dim_zones') }} dz on t.dropoff_zone_id = dz.zone_id
