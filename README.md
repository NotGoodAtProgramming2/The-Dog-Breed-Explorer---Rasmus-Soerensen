# Dog Breed Explorer

[![Pipeline](https://github.com/NotGoodAtProgramming2/The-Dog-Breed-Explorer---Rasmus-Soerensen/actions/workflows/pipeline.yml/badge.svg)](https://github.com/NotGoodAtProgramming2/The-Dog-Breed-Explorer---Rasmus-Soerensen/actions/workflows/pipeline.yml)

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

- **Raw**: `ingest/fetch_breeds.py` calls the API, validates the response, writes it untouched.
- **Curated**: dbt parses the messy text into clean tables in `data/warehouse.duckdb`.
- **Dashboard**: `dashboard/app.py` reads that same file directly.
- **Automation**: one GitHub Actions workflow runs daily at 02:00 UTC, on every pull request,
  and on demand. Non-PR runs commit the refreshed data back.

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
- `breeds`: `life_span`/`weight` parsed into numeric min/max/avg, plus a derived `size_class`
  (Small/Medium/Large/Giant).
- `breed_temperaments`: the comma-separated `temperament` list exploded to one row per trait.

10 dbt tests: uniqueness, not-null, valid `size_class`, referential integrity, and a
min-never-exceeds-max sanity check on the parsed numbers.

## What the data says

**Longest life span?** Denmark Feist, Koolie, Miniature Fox Terrier, Rat Terrier, and Silken
Windhound share the top spot, 12-18 years.

**Weight classes?** Most breeds are Medium (250, 40%) or Large (203, 32%); only 59 are Giant.
Peak: 20-25 kg (117 breeds).

**Temperament vs. size?** Most common traits: intelligent (538), loyal (454), alert (377).
Small and Giant breeds deviate most from the overall temperament mix; Medium and Large don't
(see dashboard for which traits and by how much).

**Size vs. life span?** Correlation **-0.67**, slope -0.057 yrs/kg, p ≈ 1.1×10⁻⁷⁸ (589 breeds) —
heavier breeds live shorter, matching known dog biology.

Open the dashboard (`streamlit run dashboard/app.py`) for the charts behind these.

## Secrets

The Dog API requires a free key. Locally: a gitignored `.env` file (see `.env.example`). In CI:
a repository secret named `DOG_API_KEY`.

## What I'd do with more time

See the end of [DECISIONS.md](DECISIONS.md).
