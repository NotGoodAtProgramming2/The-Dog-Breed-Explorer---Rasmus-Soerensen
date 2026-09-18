-- One row per breed per temperament trait, so it can be filtered/grouped.
-- Lowercased: the source only capitalizes the first trait in each breed's
-- list (it's the start of a sentence), so "Alert" and "alert" are the same
-- trait, not two.

with split as (
    select
        breed_id,
        lower(trim(unnest(string_split(temperament_raw, ',')))) as temperament
    from {{ ref('breeds') }}
    where temperament_raw is not null
)

select * from split where temperament != ''
