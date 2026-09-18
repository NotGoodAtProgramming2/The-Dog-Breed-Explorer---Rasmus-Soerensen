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
from scipy import stats

# Editorial theme (matching heyra.ai): warm neutrals + one amber accent,
# used instead of a blue/orange tech palette. "Other" data recedes in a
# muted warm gray; the amber accent is reserved for what the chart is
# actually pointing at (the top breeds, the trend line).
COLOR_OTHER = "#a9a08c"
COLOR_TOP = "#c96a1f"
COLOR_TEXT = "#1a1a1a"

# size_class is ordinal (Small < Medium < Large < Giant), so it gets a
# single-hue amber ramp light-to-dark rather than arbitrary categorical
# hues -- the ramp itself encodes the ordering.
SIZE_CLASS_COLORS = {
    "Small": "#f1ddb8",
    "Medium": "#dba24f",
    "Large": "#b3691f",
    "Giant": "#5c3a1e",
    "Unknown": "#c7c2b4",
}

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"

st.set_page_config(page_title="Dog Breed Explorer", page_icon="🐶", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600;700&display=swap');

    h1, h2, h3 { font-family: 'Source Serif 4', Georgia, serif !important; }

    .eyebrow {
        font-family: system-ui, sans-serif;
        font-size: 0.78rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #7a7263;
        margin-bottom: 0.2rem;
    }
    .callout {
        border-left: 3px solid #c96a1f;
        background: #efe8d8;
        padding: 0.9rem 1.1rem;
        font-size: 1.05rem;
        color: #1a1a1a;
        margin-bottom: 1.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="eyebrow">Heyra Data Platform &middot; Daily Refresh</div>', unsafe_allow_html=True)
st.title("Dog Breed Explorer")
st.markdown(
    '<div class="callout">A curated analytics layer over the Dog API, rebuilt daily: '
    "raw breed data is cleaned, typed, and parsed into the numbers below.</div>",
    unsafe_allow_html=True,
)

con = duckdb.connect(str(DB_PATH), read_only=True)
breeds = con.execute("select * from main.breeds").df()

# --- What the curated data looks like ---
st.header("The curated data")

preview_source = breeds.assign(_id_num=breeds["breed_id"].astype(int)).sort_values("_id_num")
top5 = preview_source.head(5).drop(columns="_id_num")
bottom1 = preview_source.tail(1).drop(columns="_id_num")
ellipsis_row = pd.DataFrame([{col: "…" for col in top5.columns}])
preview_table = pd.concat([top5, ellipsis_row, bottom1], ignore_index=True)

st.dataframe(preview_table, use_container_width=True, hide_index=True)
st.caption(
    f"{len(breeds)} breeds, one row each, after cleaning and parsing. Every breed has an "
    "identity (name, breed_group, origin, raw temperament text) plus numeric life span "
    "(years) and weight (kg) ranges parsed out of the source API's free text, and a "
    "derived size_class. Rows shown: the 5 lowest breed_id values, then the single "
    "highest, to give a sense of the full range without printing all "
    f"{len(breeds)} rows."
)

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

# Classic linear regression: slope, intercept, correlation (r), and the
# p-value for the t-test on the slope -- which is the same test as asking
# "is the correlation significantly different from zero?"
slope, intercept, r, p_value, stderr = stats.linregress(
    sized["weight_avg_kg"], sized["life_span_avg_years"]
)
n = len(sized)
dof = n - 2
t_stat = slope / stderr

points = (
    alt.Chart(sized)
    .mark_circle(size=40, opacity=0.75)
    .encode(
        x=alt.X("weight_avg_kg:Q", title="Average weight (kg)"),
        y=alt.Y("life_span_avg_years:Q", title="Average life span (years)"),
        color=alt.Color(
            "size_class:N",
            title="Size class",
            scale=alt.Scale(
                domain=list(SIZE_CLASS_COLORS.keys()),
                range=list(SIZE_CLASS_COLORS.values()),
            ),
        ),
        tooltip=["name", "weight_avg_kg", "life_span_avg_years", "size_class"],
    )
)

trend = (
    alt.Chart(sized)
    .transform_regression("weight_avg_kg", "life_span_avg_years")
    .mark_line(color=COLOR_TEXT, strokeDash=[6, 3], strokeWidth=2)
    .encode(x="weight_avg_kg:Q", y="life_span_avg_years:Q")
)

# Label the trend line with its slope, placed at its right-hand end.
x_max = sized["weight_avg_kg"].max()
slope_label = pd.DataFrame(
    [{"x": x_max, "y": slope * x_max + intercept, "text": f"slope: {slope:.3f} years/kg"}]
)
trend_label = (
    alt.Chart(slope_label)
    .mark_text(align="right", dy=-8, fontWeight="bold", color=COLOR_TEXT)
    .encode(x="x:Q", y="y:Q", text="text")
)

st.altair_chart((points + trend + trend_label).properties(height=420), use_container_width=True)

direction = "negative" if r < 0 else "positive"
st.markdown(
    f"There's a clear {direction} relationship: on average, life span drops by "
    f"**{abs(slope):.3f} years for every extra kg** of body weight."
)

st.markdown("**Hypothesis test: is this relationship real, or could it be random chance?**")
st.markdown(
    "This is a classic Pearson correlation test. The null hypothesis (H0) says there is "
    "*no* linear relationship between weight and life span (correlation = 0) -- i.e. any "
    "pattern we see is just random noise in this sample. We test that against the "
    "alternative (H1: correlation ≠ 0) using a t-test on the slope. If the p-value is "
    "below 0.05, we reject H0."
)

stats_table = pd.DataFrame(
    {
        "Statistic": [
            "Correlation (r)",
            "Sample size (n)",
            "Slope (years/kg)",
            "t-statistic",
            "Degrees of freedom",
            "p-value",
            "Conclusion (α = 0.05)",
        ],
        "Value": [
            f"{r:.3f}",
            f"{n}",
            f"{slope:.4f}",
            f"{t_stat:.2f}",
            f"{dof}",
            f"{p_value:.2e}",
            "Reject H0 -- the relationship is statistically significant"
            if p_value < 0.05
            else "Fail to reject H0",
        ],
    }
)
st.table(stats_table.set_index("Statistic"))
