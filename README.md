# Dog Breed Explorer

A curated analytics layer over [The Dog API](https://www.thedogapi.com/), refreshed daily.
See [DECISIONS.md](DECISIONS.md) for the reasoning behind every choice.

## How it fits together

```
ingest/fetch_breeds.py    →  data/raw/<date>/breeds.json   (raw, one snapshot per day)
                              data/raw/latest.json          (always the newest snapshot)
                                        ↓
dbt (staging → marts)     →  data/warehouse.duckdb          (curated tables)
                                        ↓
dashboard/app.py (Streamlit) → charts, read straight from the warehouse
```

- **Raw**: `ingest/fetch_breeds.py` calls the API, checks the response, writes it untouched.
  One dated folder per day, plus a `latest.json` pointer to the newest.
- **Curated**: dbt reads `latest.json`, parses the messy text, writes clean tables into
  `data/warehouse.duckdb`.
- **Dashboard**: a Streamlit app queries that same file directly.
- **Automation**: one GitHub Actions workflow runs the whole chain daily at 02:00 UTC, on
  every pull request, and on demand. Non-PR runs commit the refreshed data back.

## Running it locally

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # paste your key from https://www.thedogapi.com/signup
source .env

python ingest/fetch_breeds.py

cd dbt
DBT_PROFILES_DIR=. dbt build --target prod
cd ..

streamlit run dashboard/app.py
```

## The curated model

- `stg_breeds`: one row per breed, renamed fields, still raw text.
- `breeds`: the main table — `life_span`/`weight` parsed into numeric min/max/avg, plus a
  derived `size_class` (Small/Medium/Large/Giant).
- `breed_temperaments`: the comma-separated `temperament` list exploded to one row per trait.

6 dbt tests: structural correctness (uniqueness, not-null, valid `size_class`, referential
integrity) plus a min-vs-max sanity check on the parsed numbers.

## What the data says

**Longest predicted life span?** Denmark Feist, Koolie, Miniature Fox Terrier, Rat Terrier,
and Silken Windhound share the top spot at 12-18 years.

**Size vs. life span?** A clear negative relationship: correlation **-0.67** across 589 breeds
(slope -0.057 years/kg). A Pearson test rejects "no relationship" decisively (p ≈ 1.1×10⁻⁷⁸) —
larger breeds age faster, matching known dog biology.

Open the dashboard (`streamlit run dashboard/app.py`) to explore both.

## Secrets

The Dog API now requires a free key (it didn't when this brief was written). Locally: a
gitignored `.env` file (see `.env.example`). In CI: a repository secret named `DOG_API_KEY`.

## What I'd do with more time

See the end of [DECISIONS.md](DECISIONS.md).
