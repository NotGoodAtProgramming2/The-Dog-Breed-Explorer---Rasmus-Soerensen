# Decisions

**Extraction & ingestion — plain Python + `requests`, not dlt/Airbyte.** One small REST endpoint,
called once a day, doesn't justify a connector framework. A hand-rolled ~90-line script gives full
control over retries, validation, and idempotency for less complexity than learning a framework's
abstractions. It retries on failure (2s/4s backoff), validates the response shape before writing
anything, and only ever overwrites data with a *good* new fetch — a bad or partial response fails
the run loudly instead of corrupting the raw data. Runs are idempotent: re-running on the same day
overwrites that day's file with the same content, never duplicates it. One real find here: the API
now requires a key (it was fully open when this brief was likely written), and one specific
endpoint (`/v1/breeds`) enforces it strictly while a sibling endpoint doesn't — confirmed by testing
with no key, a fake key, and a real key side by side before concluding it wasn't an IP block.

**Warehouse — DuckDB, not BigQuery/Snowflake/Postgres.** The entire dataset is 631 rows. A
server-based warehouse would add authentication, networking, and (for most options) cost, for zero
benefit at this scale — DuckDB is an embedded file, `data/warehouse.duckdb`, that needs no server
and is trivial to inspect or reset. Layering: raw JSON on disk (bronze) → dbt staging (silver, 1:1
cleanup) → dbt marts (gold, typed and business-ready). The tradeoff: I commit that `.duckdb` file to
git so the dashboard always has fresh data without re-running the pipeline. That's a binary in
version control, which is not something I'd do for a real production system.

**Transformation — dbt Core (dbt-duckdb adapter).** The interesting work was in `models/marts/breeds.sql`:
`life_span` and `weight` arrive as free text, and I initially assumed simple ranges like `"12-15"`.
Inspecting the real data showed 69% of breeds report weight (and height) as
`"Male: 25-30; Female: 20-25"` instead. Extracting every number in the string and taking the overall
min/max handles both formats correctly with one regex, rather than writing a special case for each
pattern. `size_class` (Small/Medium/Large/Giant) is a derived bucket on average weight, thresholds
are a judgement call I made explicit in the SQL comments. `temperament` (comma-separated) is exploded
into a `breed_temperaments` bridge table so it's actually queryable. Two fields the API returns
(`bred_for`, `perfect_for`) are 100% null across all 631 breeds and were dropped rather than modeled.
6 tests cover structure (unique/not-null keys, valid `size_class` values, referential integrity) and
the parsing itself (a singular test asserting min ≤ max on both life span and weight, since a
regex bug there would silently produce nonsense rather than an error). `dev`/`prod` targets are two
DuckDB file paths in `profiles.yml`; PRs build against `dev` so they never touch the file the
dashboard reads.

**Version control & CI/CD — GitHub, one GitHub Actions workflow.** A single workflow file
(`pipeline.yml`) triggers on pull requests, pushes to `main`, a daily 02:00 UTC schedule, and manual
dispatch. Every trigger — including PRs — runs the real ingest + `dbt build` + tests, so a PR is
validated against live data, not a stale fixture. Only non-PR runs commit the refreshed data back
to `main` (tagged `[skip ci]` to avoid re-triggering itself). The only secret involved, `DOG_API_KEY`,
lives in GitHub Actions secrets and a local, gitignored `.env` — never in the repo.

**Orchestration — GitHub Actions' own cron, not Airflow/Dagster.** One daily job doesn't warrant
standing up a scheduler with its own infrastructure to babysit. GitHub Actions' `schedule:` trigger
plus its built-in run history (pass/fail, logs, timestamps) covers "does it run daily" and "did the
last run succeed" with zero extra infrastructure.

**Dashboard — Streamlit, not Metabase/Power BI/Looker Studio.** Keeps the whole stack in one
language (Python), needs no separate server or account to set up, and reads `data/warehouse.duckdb`
directly with no export/sync step. It answers two of the suggested questions: which breeds have the
longest predicted life span, and whether size and life span are related (they are — a -0.67
correlation between average weight and average life span across all 631 breeds).

## What I'd do differently with more time

- Stop committing the `.duckdb` file to git; use a small hosted DuckDB (e.g. MotherDuck) or object
  storage instead, so history isn't stored as binary diffs.
- Age out old raw JSON snapshots instead of keeping every day forever, once the history is actually
  useful for something.
- Host the generated dbt docs (GitHub Pages) instead of only generating them locally/in CI.
- Add a data-quality check on the "unknown" weight bucket (currently 2 breeds fail to parse because
  the API literally returns `"unknown"` for weight — handled gracefully today, but worth alerting on
  if the rate ever grows).
- One of the optional bonus ideas — likely LLM-based temperament enrichment (e.g. an "energy level"
  score), since the temperament bridge table is already in place to build on.
