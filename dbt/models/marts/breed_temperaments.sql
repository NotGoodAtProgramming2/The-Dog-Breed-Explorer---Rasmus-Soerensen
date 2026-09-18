-- One row per breed per temperament trait, so it can be filtered/grouped.

with split as (
    select
        breed_id,
        trim(unnest(string_split(temperament_raw, ','))) as temperament
    from {{ ref('breeds') }}
    where temperament_raw is not null
)

select * from split where temperament != ''
