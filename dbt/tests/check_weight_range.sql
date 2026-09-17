-- Same idea as assert_life_span_min_lte_max.sql, but for weight.
select breed_id, weight_min_kg, weight_max_kg
from {{ ref('parsed_breeds') }}
where weight_min_kg > weight_max_kg
