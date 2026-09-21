-- 1:1 cleanup of the raw JSON: sane field names, no parsing yet (that's
-- marts/breeds.sql). Drops bred_for/perfect_for (always empty) and
-- species_id (always "2", i.e. dogs).

select
    id::varchar as breed_id,
    name,
    breed_group,
    origin,
    temperament,
    life_span,
    weight.metric as weight_metric_raw
from read_json_auto('../data/raw/latest.json')
