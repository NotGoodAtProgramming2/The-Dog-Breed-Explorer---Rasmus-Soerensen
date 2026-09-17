-- The curated, analytics-ready breed table.
--
-- The messy parsing lives here:
-- - life_span and weight arrive as free text ranges (e.g. "12-15", or for
--   many breeds "Male: 25-30; Female: 20-25"). We pull every number out of
--   the text and take the overall min/max, which handles both the simple
--   "N-N" case and the male/female split case correctly in one pass.
-- - size_class is a small derived label (Small/Medium/Large/Giant) based on
--   average weight, so the dashboard can group breeds without everyone
--   having to re-invent the same weight buckets.

with extracted_numbers as (
    select
        breed_id,
        name,
        breed_group,
        origin,
        temperament,
        regexp_extract_all(life_span, '[0-9]+(\.[0-9]+)?') as life_span_numbers,
        regexp_extract_all(weight_metric_raw, '[0-9]+(\.[0-9]+)?') as weight_numbers
    from {{ ref('stg_breeds') }}
),

typed as (
    select
        breed_id,
        name,
        breed_group,
        origin,
        temperament,

        list_min(list_transform(life_span_numbers, x -> try_cast(x as decimal(4, 1))))
            as life_span_min_years,
        list_max(list_transform(life_span_numbers, x -> try_cast(x as decimal(4, 1))))
            as life_span_max_years,

        list_min(list_transform(weight_numbers, x -> try_cast(x as decimal(5, 1))))
            as weight_min_kg,
        list_max(list_transform(weight_numbers, x -> try_cast(x as decimal(5, 1))))
            as weight_max_kg
    from extracted_numbers
)

select
    breed_id,
    name,
    breed_group,
    origin,
    temperament as temperament_raw,

    life_span_min_years,
    life_span_max_years,
    (life_span_min_years + life_span_max_years) / 2 as life_span_avg_years,

    weight_min_kg,
    weight_max_kg,
    (weight_min_kg + weight_max_kg) / 2 as weight_avg_kg,

    case
        when weight_min_kg is null then 'Unknown'
        when (weight_min_kg + weight_max_kg) / 2 < 10 then 'Small'
        when (weight_min_kg + weight_max_kg) / 2 < 25 then 'Medium'
        when (weight_min_kg + weight_max_kg) / 2 < 45 then 'Large'
        else 'Giant'
    end as size_class

from typed
