# Decisions

## 1 Ingestion — Python script
- One small automatic API call, once a day.
- Retries 3 times, checks the response (failure in the API key or the server) before saving, never overwrites good data with a bad fetch.
- Same script can run twice a day safely — no duplicates.
- When the pipeline is says "passing" in green in github, new data can be pulled everyday after 02:00.
- The data must be a non-empty list with a minimum of one breed with ID and name. 

Tools:
- A python script for simplicity that uses the library "request"

Tradeoffs:
- More retries = more running time
- Data must be opdated before 02:00, otherwise not included
- Only checking for one breed = a dataset of only one breed can overwrite a more comprehensive dataset.
- A more profound framework is overkill. 

## 2 Warehouse — DuckDB
- The raw data is seperated from the curated data.
- The curated data, stg_breeds, breeds and breed_temperaments is saved in the warehouse file.
- Dropping empty columns. 

Tools:
- Only 631 rows which is why DuckDB is preffered
- DuckDB is one file (`data/warehouse.duckdb`).

Tradeoffs: 
- A small dataset = saving locally in file. 
- A cloud based solution safes local space, but is expensive. This is preffered for a bigger dataset. 


## How data flows: raw → staging → marts

a. **Raw** — `ingest/fetch_breeds.py` saves the exact API response, untouched, as JSON.

b. **Staging** (`stg_breeds`) — light cleanup:
   - Renamed: `id` → `breed_id`, `weight.metric` → `weight_metric_raw`
   - Kept as-is (still raw text): `name`, `breed_group`, `origin`, `temperament`, `life_span`
   - Dropped (empty or useless for every breed): `bred_for`, `perfect_for`, `species_id`,
     `country_code`, `country_codes`, `description`, `history`, `image`, `height`, `reference_image_id`

c. **Marts** (`breeds`, `breed_temperaments`) — text becomes real data:
   - `life_span` → `life_span_min_years` / `max` / `avg`
   - `weight_metric_raw` → `weight_min_kg` / `max` / `avg`
   - `weight_avg_kg` → derived `size_class`
   - `temperament` → exploded into `breed_temperaments`
   - This is what the dashboard reads.

## 3 Transformation — dbt
- weight/life span are text (`"12-15"` or `"Male: 25-30; Female: 20-25"`).
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
- Answers 3 questions: longest life span, weight-class distribution, and size vs. life span
  (correlation -0.67).

## What I'd do differently with more time
- Not store the database file in git — use a small hosted database instead.
- Age out old raw snapshots instead of keeping every day forever.
- Host the generated docs (GitHub Pages), not just locally.
- Alert on the 2 breeds with missing weight data.
- Split male/female weight and height instead of merging into one range — could reveal a
  sex-based pattern that's currently hidden.
- Try a bonus idea, e.g. AI-based temperament scoring.
