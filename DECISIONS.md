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



## 3 Transformation — dbt
- weight/life span are text (`"12-15"` or `"Male: 25-30; Female: 20-25"`).
- Fix: pull every number out, take the smallest as min and largest as max. Nothing is split by sex. 
- `*_avg_*` columns are computed as the midpoint of the reported range by assuming a symmetric distribution within the breeds. 
- `size_class` buckets by average weight (my own thresholds).
- `bred_for`/`perfect_for` are empty for every breed — dropped, not modeled.
- 10 tests: 
    stg_breeds:
      Unique breed_id
      breed_id not empty
      Name not empty
    Breeds:
      no duplicate IDs
      breed_id not empty
      name not empty
      valid size classes
      min never exceeds max in weight
      min never exceeds max in life span
      Temerament not empty

      

Tradeoffs:
- Not dividing the breeds in sex = more simple, but maybe missing some insights
- Assuming a symmetric distribution within the breeds to calculate `*_avg_*`. More data on the distributions gives more insight.
- Same test in stg_breeds and breeds to check if potential errors comes from model og data. 


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



## 4 & 5 Version control & CI/CD
- One workflow, four triggers: pull request, push to main, daily 02:00 UTC, manual.
- Every run fetches real, live data.
- API key lives in a GitHub secret and a local `.env` — never in code.
- A passing badge in the README file. 

## 6 Orchestration — GitHub Actions
- One job, once a day.
- GitHub Actions already shows pass/fail history for free.
- The passing badge shows whether the last run passed or failed

## 7 Dashboard — Streamlit
- Reads the data and creates streamlit file directly.
- Answers 3 questions: longest life span, weight-class distribution, and size vs. life span



## What I'd do differently with more time
- Not store the database file in git — use a small hosted database instead. The repo keeps growing.
- Age out old raw snapshots instead of keeping every day forever.
- Alert on the 2 breeds with missing weight data instead of excluding.
- Split male/female weight and height instead of merging into one range — could reveal another insight
- Estimating the actual distribution within the breeds to get a more precise `*_avg_*`. 
- Prepare my pipeline for a dataset with different conclusions. For instance making sure conclusions are automatically genrerated if the correlation between lifespan and weight was positive instead of negative. 
- Investigate the individual breeds and test if conclusions about the relationsship between life span and weight stands. 
- Try a bonus idea, e.g. AI-based temperament scoring. 

