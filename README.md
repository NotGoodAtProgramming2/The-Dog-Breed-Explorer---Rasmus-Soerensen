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
  and on demand.

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

**Longest life span?** 5 breeds: Denmark Feist, Koolie, Miniature Fox Terrier, Rat Terrier, and Silken Windhound share the top spot, 12-18 years.

The data says that almost all breeds are in the range of 10-16 years. This is ignoring differences in sex. If the breeds was divided into male and female, we might see a systematic difference between these, e.g. female breeds live longer than male breeds. 

**Weight classes?** Most breeds are Medium (250, 40%) or Large (203, 32%); only 59 are Giant.
Peak: 20-25 kg (117 breeds).
The distribution has a tail to the right side, which means most breeds has a weight under 30 kg.
This method assumes that the individual breeds has a symmetric distribution, if not the midpoint can't be used as average.
Again the data are missing systematic difference between male and female breeds. 


**Size vs. life span?** The data supports the argument of a decreasing expected life span when moving towards heavier breeds. More precisely a slope of -0.057 yrs/kg says that the life span drops 0.057 years (21 days) per extra kg, on average (N = 589 breeds) - heavier breeds live shorter. This conclusion is tested with a null hypothesis, which is rejected with a p-value of ≈ 0.00, and the conclusion is suggested statistically significant. 
We can't conclude anything about the individual breeds. For instance if a heavy Affenpinscher lifs longer than a non-heavy Affenpinscher, all else equal. 

**Temperament** 
Most of the common temperaments is approximately matching the distribution for all breeds. This suggests that most breeds has the same temperaments across size classes. 
Small and Giant breeds deviate most from the overall temperament mix; Medium and Large don't. This could be because of a correlation between size and temperaments.

(see dashboard for which traits and by how much).



## Secrets

The Dog API requires a free key. Locally: a gitignored `.env` file (see `.env.example`). In CI:
a repository secret named `DOG_API_KEY`.

## What I'd do with more time

See the end of [DECISIONS.md](DECISIONS.md).
