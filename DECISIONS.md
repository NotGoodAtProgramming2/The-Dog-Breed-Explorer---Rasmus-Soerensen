# Decisions

## Ingestion — Python script, not dlt/Airbyte
- Only one small API call, once a day. A full framework is overkill.
- Retries 3 times if the API fails.
- Checks the data looks right before saving it.
- Never overwrites good data with a bad/broken fetch.
- Same script can run twice a day safely — no duplicates.
- Note: the API now needs a key (it didn't when this case was written).

## Warehouse — DuckDB, not BigQuery/Snowflake/Postgres
- Only 631 rows of data. A big cloud database adds cost and setup for no benefit.
- DuckDB is just one file (`data/warehouse.duckdb`), no server needed.
- Tradeoff: that file is stored in git. Not how you'd do it in a real production system (see "What I'd do differently").

## How data flows: raw → staging → marts

1. **Raw** — `ingest/fetch_breeds.py` fetches data from the API and saves it untouched as a JSON file (`data/raw/...`). Nothing is changed here, this is the exact API response.

2. **Staging** (`stg_breeds`) — dbt reads the raw JSON file and does light cleanup only, no parsing yet:
   - `id` → renamed to `breed_id`
   - `name` → kept as is
   - `breed_group` → kept as is
   - `origin` → kept as is
   - `temperament` → kept as is (still one long comma-separated text)
   - `life_span` → kept as is (still text, e.g. `"12-15"`)
   - `weight.metric` → renamed to `weight_metric_raw` (still text, e.g. `"12-15"` or `"Male: 25-30; Female: 20-25"`)
   - Dropped completely (not carried forward, not useful): `bred_for` and `perfect_for` (empty for every single breed), `species_id` (same value for every breed), `country_code`, `country_codes`, `description`, `history`, `image`, `height`, `reference_image_id`

3. **Marts** (`breeds`, `breed_temperaments`) — dbt turns the text into real, usable data:
   - `life_span` text → split into `life_span_min_years`, `life_span_max_years`, and `life_span_avg_years` (real numbers)
   - `weight_metric_raw` text → split into `weight_min_kg`, `weight_max_kg`, and `weight_avg_kg` (real numbers)
   - `weight_avg_kg` → used to create a new column, `size_class` (Small/Medium/Large/Giant/Unknown)
   - `temperament` text (one long comma list) → exploded into a separate table (`breed_temperaments`), one row per breed per trait, extra spaces trimmed off
   - `breed_id`, `name`, `breed_group`, `origin` → carried through unchanged
   - This is the final, clean data the dashboard reads from.

## Transformation — dbt
- The hard part: weight/life span are text, not numbers (e.g. `"12-15"` or `"Male: 25-30; Female: 20-25"`).
- Fix: pull every number out of the text, use the smallest as min and the largest as max. Works for both formats.
- `size_class` is a size bucket based on average weight (my own threshold choice).
- 6 automated tests check: no duplicate IDs, no empty names, valid size classes, and that min is never bigger than max.
- Two fields from the API (`bred_for`, `perfect_for`) are empty for every single breed — dropped, not modeled.

## Version control & CI/CD — GitHub, one GitHub Actions workflow
- One file (`pipeline.yml`) runs on: every pull request, every push to main, daily at 02:00 UTC, and on manual click.
- Every run fetches real, live data — not fake test data.
- Only non-PR runs save the new data back to the repo.
- The API key is never in the code — it's a GitHub "secret" plus a local `.env` file (both ignored by git).

## Orchestration — GitHub Actions' own scheduler, not Airflow/Dagster
- It's one job, once a day. A full scheduler tool would be extra setup for no real benefit.
- GitHub Actions already shows pass/fail history for free.

## Dashboard — Streamlit, not Power BI/Looker Studio
- Same language (Python) as the rest of the project — one less tool to learn.
- Reads the database file directly, no extra export step.
- Answers 2 questions: longest life span, and size vs. life span (they're linked — bigger breeds live shorter, correlation -0.67).

## What I'd do differently with more time
- Not store the database file in git — use a small hosted database instead.
- Delete old raw data snapshots after a while, instead of keeping every day forever.
- Put the auto-generated docs online (GitHub Pages), not just locally.
- Add an alert for the 2 breeds where weight data is missing/unknown.
- Try one of the bonus ideas — e.g. AI-based temperament scoring.
