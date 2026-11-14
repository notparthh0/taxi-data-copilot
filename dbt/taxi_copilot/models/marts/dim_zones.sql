-- The TLC taxi zone lookup (265 zones), with tidy names.
select
    LocationID      as zone_id,
    Zone            as zone_name,
    Borough         as borough
from {{ ref('taxi_zone_lookup') }}
