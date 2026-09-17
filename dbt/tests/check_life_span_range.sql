-- A singular test: fails (returns rows) if any breed's parsed minimum life
-- span ended up greater than its maximum, which would mean the regex/parsing
-- logic misread the source text.
select breed_id, life_span_min_years, life_span_max_years
from {{ ref('parsed_breeds') }}
where life_span_min_years > life_span_max_years
