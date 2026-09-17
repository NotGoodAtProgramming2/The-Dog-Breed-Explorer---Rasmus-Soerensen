"""
Dog Breed Explorer dashboard.

Reads directly from the curated DuckDB warehouse (data/warehouse.duckdb),
which the daily pipeline (ingest + dbt) keeps up to date. No extra data
processing happens here -- the dashboard is a thin, read-only view on top
of the marts.breeds / marts.breed_temperaments tables.
"""

from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

# Palette: validated colorblind-safe pair (blue = slot 1, orange = slot 2)
# from the project's dataviz color reference. Orange marks the breeds with
# the longest predicted life span; blue (faded) is everything else.
COLOR_OTHER = "#2a78d6"
COLOR_TOP = "#eb6834"
COLOR_TEXT = "#0b0b0b"

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"

st.set_page_config(page_title="Dog Breed Explorer", page_icon="🐶", layout="wide")
st.title("🐶 Dog Breed Explorer")

con = duckdb.connect(str(DB_PATH), read_only=True)
breeds = con.execute("select * from main.breeds").df()

st.caption(f"{len(breeds)} breeds loaded from the curated warehouse.")

# --- Question 1: which breeds have the longest predicted life span? ---
st.header("Which breeds have the longest predicted life span?")

# One row per breed, sorted so the lowest life span sits at the left (near
# the y-axis) and the highest sits at the right (furthest from it).
life_span = (
    breeds.dropna(subset=["life_span_avg_years"])
    .sort_values("life_span_avg_years")
    .reset_index(drop=True)
)
life_span["rank"] = range(len(life_span))

max_avg = life_span["life_span_avg_years"].max()
life_span["is_top"] = life_span["life_span_avg_years"] == max_avg
top_breeds = life_span[life_span["is_top"]].copy().reset_index(drop=True)

# Extra headroom above the highest span, so the stacked top-breed labels
# (added below) have room to sit inside the chart without overlapping data.
y_domain = [0, life_span["life_span_max_years"].max() + 4]
y_scale = alt.Scale(domain=y_domain)

# A thin line per breed spanning its reported min-to-max life span.
spans = (
    alt.Chart(life_span)
    .mark_rule(strokeWidth=1.5)
    .encode(
        x=alt.X("rank:Q", axis=None, title="Breeds, sorted by predicted life span"),
        y=alt.Y("life_span_min_years:Q", title="Life span (years)", scale=y_scale),
        y2="life_span_max_years:Q",
        color=alt.condition("datum.is_top", alt.value(COLOR_TOP), alt.value(COLOR_OTHER)),
        opacity=alt.condition("datum.is_top", alt.value(0.9), alt.value(0.3)),
        tooltip=["name", "life_span_min_years", "life_span_max_years"],
    )
)

# The min and max endpoints of each span, as points.
endpoints = pd.concat(
    [
        life_span.assign(years=life_span["life_span_min_years"]),
        life_span.assign(years=life_span["life_span_max_years"]),
    ]
)
points = (
    alt.Chart(endpoints)
    .mark_point(filled=True, size=18)
    .encode(
        x=alt.X("rank:Q", axis=None),
        y=alt.Y("years:Q", scale=y_scale),
        color=alt.condition("datum.is_top", alt.value(COLOR_TOP), alt.value(COLOR_OTHER)),
        opacity=alt.condition("datum.is_top", alt.value(0.9), alt.value(0.3)),
        tooltip=["name", "years"],
    )
)

# Name the tied top breeds directly on the chart. They all sit at the same
# value, so a plain label per point would overlap into unreadable text --
# instead, stack them in a vertical list anchored to one x position, using
# the headroom reserved above via y_domain.
top_breeds["label_rank"] = top_breeds["rank"].min()
top_breeds["label_y"] = y_domain[1] - 1.2 * top_breeds.index

labels = (
    alt.Chart(top_breeds)
    .mark_text(align="left", dx=6, fontWeight="bold", color=COLOR_TEXT)
    .encode(x="label_rank:Q", y=alt.Y("label_y:Q", scale=y_scale), text="name")
)

st.altair_chart((spans + points + labels).properties(height=420), use_container_width=True)

top_row = top_breeds.iloc[0]
st.markdown(
    f"**{len(top_breeds)} breeds share the longest predicted life span** "
    f"({top_row['life_span_min_years']:.0f}-{top_row['life_span_max_years']:.0f} years, "
    f"highlighted in orange): {', '.join(top_breeds['name'])}."
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
