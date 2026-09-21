# Decisions

## 1 Ingestion — Python script, not dlt/Airbyte
- One small API call, once a day. A full framework is overkill.
- Retries 3 times, checks the response before saving, never overwrites good data with a bad fetch.
- Same script can run twice a day safely — no duplicates.
- The API now needs a key (it didn't when this case was written).

## 2 Warehouse — DuckDB, not BigQuery/Snowflake/Postgres
- Only 631 rows. A cloud database adds cost and setup for no benefit.
- DuckDB is one file (`data/warehouse.duckdb`), no server needed.
- Tradeoff: that file is stored in git — not how I'd do it in production (see below).

## How data flows: raw → staging → marts

1. **Raw** — `ingest/fetch_breeds.py` saves the exact API response, untouched, as JSON.

2. **Staging** (`stg_breeds`) — light cleanup, no parsing:
   - Renamed: `id` → `breed_id`, `weight.metric` → `weight_metric_raw`
   - Kept as-is (still raw text): `name`, `breed_group`, `origin`, `temperament`, `life_span`
   - Dropped (empty or useless for every breed): `bred_for`, `perfect_for`, `species_id`,
     `country_code`, `country_codes`, `description`, `history`, `image`, `height`, `reference_image_id`

3. **Marts** (`breeds`, `breed_temperaments`) — text becomes real data:
   - `life_span` → `life_span_min_years` / `max` / `avg`
   - `weight_metric_raw` → `weight_min_kg` / `max` / `avg`
   - `weight_avg_kg` → derived `size_class`
   - `temperament` → exploded into `breed_temperaments`, one row per trait, lowercased (the
     source capitalizes only the first trait in each breed's list, e.g. "Alert" vs "alert" —
     same trait, not two)
   - This is what the dashboard reads.

## 3 Transformation — dbt
- Hard part: weight/life span are text (`"12-15"` or `"Male: 25-30; Female: 20-25"`).
- Fix: pull every number out, take the smallest as min and largest as max. Works for both formats.
- The `*_avg_*` columns are the midpoint of the reported range, not a measured average. This
  assumes weights (and life spans) within a breed are roughly symmetric, e.g. normally distributed.
- Male and female ranges are merged into one range per breed. Nothing is split by sex.
- `size_class` buckets by average weight (my own thresholds).
- 6 tests: no duplicate IDs, no empty names, valid size classes, min never exceeds max.
- `bred_for`/`perfect_for` are empty for every breed — dropped, not modeled.

## 4 & 5 Version control & CI/CD — GitHub, one GitHub Actions workflow
- One workflow, four triggers: pull request, push to main, daily 02:00 UTC, manual.
- Every run fetches real, live data. Only non-PR runs commit it back.
- API key lives in a GitHub secret and a local `.env` — never in code.

## 6 Orchestration — GitHub Actions' own scheduler, not Airflow/Dagster
- One job, once a day. A scheduler tool would be setup for no real benefit.
- GitHub Actions already shows pass/fail history for free.

## 6 Dashboard — Streamlit, not Power BI/Looker Studio
- Same language as the rest of the project.
- Reads the database file directly, no export step.
- Answers 2 questions: longest life span, and size vs. life span (correlation -0.67).
- A second app, `explore.py`, is a separate consumer-facing browse/search UI (breed photos,
  filters) — kept apart from the analytics dashboard so neither audience gets the other's
  clutter. Breed photos are the API's own `image.url`, hotlinked, not stored.

## What I'd do differently with more time
- Not store the database file in git — use a small hosted database instead.
- Age out old raw snapshots instead of keeping every day forever.
- Host the generated docs (GitHub Pages), not just locally.
- Alert on the 2 breeds with missing weight data.
- Split male/female weight and height instead of merging into one range — could reveal a
  sex-based pattern that's currently hidden.
- Try a bonus idea, e.g. AI-based temperament scoring.
