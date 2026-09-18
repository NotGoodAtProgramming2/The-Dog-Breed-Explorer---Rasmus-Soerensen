-- Fails if any breed's parsed min life span exceeds its max.
select breed_id, life_span_min_years, life_span_max_years
from {{ ref('breeds') }}
where life_span_min_years > life_span_max_years
