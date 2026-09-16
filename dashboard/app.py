"""
Dog Breed Explorer dashboard.

Reads directly from the curated DuckDB warehouse (data/warehouse.duckdb),
which the daily pipeline (ingest + dbt) keeps up to date. No extra data
processing happens here -- the dashboard is a thin, read-only view on top
of the marts.breeds / marts.breed_temperaments tables.
"""

from pathlib import Path

import duckdb
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"

st.set_page_config(page_title="Dog Breed Explorer", page_icon="🐶", layout="wide")
st.title("🐶 Dog Breed Explorer")

con = duckdb.connect(str(DB_PATH), read_only=True)
breeds = con.execute("select * from main.breeds").df()

st.caption(f"{len(breeds)} breeds loaded from the curated warehouse.")

# --- Question 1: which breeds have the longest predicted life span? ---
st.header("Which breeds have the longest predicted life span?")

top_n = st.slider("Number of breeds to show", 5, 30, 15)
longest_lived = (
    breeds.dropna(subset=["life_span_avg_years"])
    .sort_values("life_span_avg_years", ascending=False)
    .head(top_n)
    .set_index("name")
)
st.bar_chart(longest_lived["life_span_avg_years"])

top_breed = longest_lived.iloc[0]
st.markdown(
    f"**{longest_lived.index[0]}** tops the list with a predicted life span of "
    f"**{top_breed['life_span_min_years']:.0f}-{top_breed['life_span_max_years']:.0f} years**. "
    "Several breeds share the same reported range, so ties at the top are common."
)

# --- Question 2: relationship between size and life span ---
st.header("Is there a relationship between size and life span?")

sized = breeds.dropna(subset=["weight_avg_kg", "life_span_avg_years"])
correlation = sized["weight_avg_kg"].corr(sized["life_span_avg_years"])

st.scatter_chart(sized, x="weight_avg_kg", y="life_span_avg_years", color="size_class")

direction = "negative" if correlation < 0 else "positive"
st.markdown(
    f"Correlation between average weight and average life span: **{correlation:.2f}** "
    f"({direction}). Heavier breeds tend to live shorter lives, in line with the well "
    "known pattern that larger dogs age faster than small ones."
)

avg_by_size = (
    sized.groupby("size_class")["life_span_avg_years"]
    .mean()
    .round(1)
    .sort_values(ascending=False)
)
st.bar_chart(avg_by_size)
