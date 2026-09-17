-- Turns the comma-separated temperament string on breeds into one row per
-- breed per trait, so temperament can actually be filtered/grouped/counted
-- instead of pattern-matched inside a text blob.

with split as (
    select
        breed_id,
        trim(unnest(string_split(temperament_raw, ','))) as temperament
    from {{ ref('breeds') }}
    where temperament_raw is not null
)

select * from split where temperament != ''
