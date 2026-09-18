-- Curated breed table. life_span and weight arrive as free text (e.g.
-- "12-15", or "Male: 25-30; Female: 20-25"). We pull every number out and
-- take the overall min/max, which handles both formats in one pass.

with extracted_numbers as (
    select
        breed_id,
        name,
        breed_group,
        origin,
        temperament,
        image_url,
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
        temperament as temperament_raw,
        image_url,
        list_min(list_transform(life_span_numbers, x -> try_cast(x as decimal(4, 1))))
            as life_span_min_years,
        list_max(list_transform(life_span_numbers, x -> try_cast(x as decimal(4, 1))))
            as life_span_max_years,
        list_min(list_transform(weight_numbers, x -> try_cast(x as decimal(5, 1))))
            as weight_min_kg,
        list_max(list_transform(weight_numbers, x -> try_cast(x as decimal(5, 1))))
            as weight_max_kg
    from extracted_numbers
),

averaged as (
    select
        *,
        (life_span_min_years + life_span_max_years) / 2 as life_span_avg_years,
        (weight_min_kg + weight_max_kg) / 2 as weight_avg_kg
    from typed
)

select
    *,
    case
        when weight_avg_kg is null then 'Unknown'
        when weight_avg_kg < 10 then 'Small'
        when weight_avg_kg < 25 then 'Medium'
        when weight_avg_kg < 45 then 'Large'
        else 'Giant'
    end as size_class
from averaged
