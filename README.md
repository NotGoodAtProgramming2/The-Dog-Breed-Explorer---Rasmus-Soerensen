# Dog Breed Explorer

A small, curated analytics layer on top of [The Dog API](https://www.thedogapi.com/), refreshed
daily. See [DECISIONS.md](DECISIONS.md) for the reasoning behind every tool choice and tradeoff.

## How it fits together

```
ingest/fetch_breeds.py    →  data/raw/<date>/breeds.json   (raw, one snapshot per day)
                              data/raw/latest.json          (always the newest snapshot)
                                        ↓
dbt (staging → marts)     →  data/warehouse.duckdb          (curated tables)
                                        ↓
dashboard/app.py (Streamlit) → charts, read straight from the warehouse
```

- **Raw layer**: `ingest/fetch_breeds.py` calls the API, checks the response looks sane, and
  writes it to disk untouched. Every day gets its own dated folder (a permanent history), plus a
  `latest.json` pointer that always has the newest data.
- **Curated layer**: dbt reads `latest.json`, parses the messy text fields, and writes clean
  tables into `data/warehouse.duckdb` (a single-file DuckDB database).
- **Dashboard**: a Streamlit app queries that same DuckDB file directly.
- **Automation**: one GitHub Actions workflow (`.github/workflows/pipeline.yml`) runs the whole
  chain daily at 02:00 UTC, on every pull request (to catch breakages before merge), and on
  demand. On non-PR runs it commits the refreshed data back to the repo.

## Running it locally

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then paste your key from https://www.thedogapi.com/signup
source .env

python ingest/fetch_breeds.py          # fetches today's data

cd dbt
DBT_PROFILES_DIR=. dbt build --target prod   # builds + tests the curated tables
DBT_PROFILES_DIR=. dbt docs serve            # optional: browse the generated docs
cd ..

streamlit run dashboard/app.py         # opens the dashboard in your browser
```

## The curated model

- `stg_breeds`: one row per breed, straight from the API, renamed/cleaned.
- `breeds`: the main curated table — `life_span` and `weight` are parsed out of free text
  (e.g. `"12-15"` or `"Male: 25-30; Female: 20-25"`) into numeric min/max/avg columns, plus a
  derived `size_class` (Small/Medium/Large/Giant) based on average weight.
- `breed_temperaments`: the comma-separated `temperament` list exploded into one row per
  breed per trait, so it can actually be filtered and grouped.

6 dbt tests cover both structural correctness (uniqueness, not-null, valid `size_class` values,
referential integrity to `breeds`) and the parsing logic itself (a min-vs-max sanity check on
both life span and weight).

## What the data says

Answering two of the suggested questions, using the dataset as fetched:

**Which breeds have the longest predicted life span?** The Denmark Feist, Koolie, Miniature
Fox Terrier, Rat Terrier and Silken Windhound share the top spot at 12-18 years.

**Is there a relationship between size and life span?** Yes — a clear negative one. The
correlation between average weight and average life span across 589 breeds with both values
is **-0.67** (slope: -0.057 years per extra kg). A Pearson correlation test rejects the null
hypothesis of no relationship decisively (p ≈ 1.1×10⁻⁷⁸). This matches a well-documented pattern
in dog biology: larger breeds tend to age faster and live shorter lives than small ones.

Open the dashboard (`streamlit run dashboard/app.py`) to explore both interactively.

## Secrets

The Dog API now requires a free API key (it didn't when this project brief was written). Locally
it's read from a `.env` file (gitignored, never committed — see `.env.example`). In CI it must be
added as a repository secret named `DOG_API_KEY` (Settings → Secrets and variables → Actions).

## What I'd do with more time

See the closing section of [DECISIONS.md](DECISIONS.md).
