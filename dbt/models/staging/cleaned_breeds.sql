-- Reads the latest raw snapshot straight off disk and gives fields sane
-- names. No parsing/typing yet, that happens in marts/breeds.sql -- this
-- model is a 1:1 cleanup of the source JSON.
--
-- We drop a few fields from the source that carry no information for every
-- single breed in the current dataset (bred_for, perfect_for) or that are
-- constant across all rows (species_id is always "2", i.e. dogs).

select
    id::varchar as breed_id,
    name,
    breed_group,
    origin,
    temperament,
    life_span,
    weight.metric as weight_metric_raw
from read_json_auto('../data/raw/latest.json')
