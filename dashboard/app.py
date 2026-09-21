"""Dog Breed Explorer dashboard. Reads data/warehouse.duckdb directly; no
processing happens here beyond display."""

from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st
from scipy import stats

# Editorial palette (heyra.ai style): amber highlights what matters, gray recedes.
COLOR_OTHER = "#a9a08c"
COLOR_TOP = "#c96a1f"
COLOR_TEXT = "#1a1a1a"

# size_class is ordinal (Small < ... < Giant), so it gets one hue, light to dark.
SIZE_CLASS_COLORS = {
    "Small": "#f1ddb8",
    "Medium": "#dba24f",
    "Large": "#b3691f",
    "Giant": "#5c3a1e",
    "Unknown": "#c7c2b4",
}

# Legend text with each class's weight range. Must match the thresholds in
# dbt/models/marts/breeds.sql (<10, <25, <45, else Giant).
SIZE_CLASS_LABELS = {
    "Small": "Small (under 10 kg)",
    "Medium": "Medium (10-25 kg)",
    "Large": "Large (25-45 kg)",
    "Giant": "Giant (over 45 kg)",
}
SIZE_LABEL_COLORS = {SIZE_CLASS_LABELS[c]: SIZE_CLASS_COLORS[c] for c in SIZE_CLASS_LABELS}
WEIGHT_BIN_KG = 5  # divides every class threshold, so no bar spans two classes

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"

st.set_page_config(page_title="Dog Breed Explorer", page_icon="🐶", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600;700&display=swap');

    .block-container { padding-left: 5rem; padding-right: 5rem; max-width: 1300px; }

    h1, h2, h3 { font-family: 'Source Serif 4', Georgia, serif !important; }
    h1 { font-size: 2.75rem !important; }
    h2 { font-size: 1.7rem !important; }
    .stMarkdown p, .stMarkdown li, .stCaption { font-size: 1.08rem !important; }

    .eyebrow {
        font-family: system-ui, sans-serif;
        font-size: 0.85rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #7a7263;
        margin-bottom: 0.3rem;
    }
    .callout {
        border-left: 3px solid #c96a1f;
        background: #efe8d8;
        padding: 1rem 1.2rem;
        font-size: 1.15rem;
        color: #1a1a1a;
        margin-bottom: 1.3rem;
    }
    .stats-table-wrap { display: inline-block; margin: 0.5rem 0 1.4rem 0; }
    .stats-table { border-collapse: collapse; font-size: 1.05rem; }
    .stats-table th, .stats-table td {
        padding: 0.6rem 1.4rem;
        text-align: left;
        white-space: nowrap;
        border-bottom: 1px solid #e1e0d9;
    }
    .stats-table th {
        color: #7a7263;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        border-bottom: 2px solid #c96a1f;
    }
    .stats-table td:first-child { color: #52514e; }
    .stats-table td:last-child { font-family: system-ui, sans-serif; color: #1a1a1a; }
    .stats-table tr:last-child td {
        border-bottom: none;
        font-weight: 600;
        white-space: normal;
    }
    .data-table-wrap { margin: 0.5rem 0 1.4rem 0; overflow-x: auto; }
    .data-table { border-collapse: collapse; width: 100%; font-size: 1rem; }
    .data-table th, .data-table td {
        padding: 0.4rem 0.7rem;
        text-align: left;
        vertical-align: top;
        line-height: 1.35;
        border-bottom: 1px solid #e1e0d9;
    }
    .data-table th {
        color: #7a7263;
        font-weight: 600;
        font-size: 0.8rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        white-space: nowrap;
        border-bottom: 2px solid #c96a1f;
    }
    .data-table tr:last-child td { border-bottom: none; }
    .data-table td.ellipsis {
        text-align: center;
        color: #c96a1f;
        font-weight: 700;
        font-size: 1.2rem;
        letter-spacing: 0.4em;
        padding: 0.15rem 0.6rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="eyebrow">Heyra Data Platform &middot; Daily Refresh</div>', unsafe_allow_html=True)
st.title("Dog Breed Explorer")
st.markdown(
    '<div class="callout">A curated analytics layer over the Dog API, rebuilt daily.</div>',
    unsafe_allow_html=True,
)

con = duckdb.connect(str(DB_PATH), read_only=True)
breeds = con.execute("select * from main.breeds").df()
breeds["size_label"] = breeds["size_class"].map(SIZE_CLASS_LABELS)

# --- What the raw data looks like, before any parsing ---
st.header("The raw data")

# Read the raw JSON directly (an absolute path, so it works from any folder)
# instead of dbt's stg_breeds view, which only resolves its file path when
# run from the dbt/ folder. life_span and weight stay as free text here.
RAW_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "latest.json"
raw_breeds = duckdb.connect().execute(
    f"""
    select
        id::varchar as breed_id,
        name,
        breed_group,
        origin,
        temperament,
        life_span,
        weight.metric as weight_kg_raw
    from read_json_auto('{RAW_JSON_PATH.as_posix()}')
    """
).df()

preview_source = raw_breeds.assign(_id_num=raw_breeds["breed_id"].astype(int)).sort_values("_id_num")
top5 = preview_source.head(5).drop(columns="_id_num")
bottom1 = preview_source.tail(1).drop(columns="_id_num")

# Human-readable column headers instead of the raw snake_case field names.
column_titles = {
    "breed_id": "ID",
    "name": "Name",
    "breed_group": "Breed group",
    "origin": "Origin",
    "temperament": "Temperament",
    "life_span": "Life span, raw (years)",
    "weight_kg_raw": "Weight, raw (kg)",
}


def render_row(row):
    return "".join(f"<td>{row[col]}</td>" for col in preview_source.columns if col != "_id_num")


header_html = "".join(f"<th>{title}</th>" for title in column_titles.values())
body_html = "".join(f"<tr>{render_row(row)}</tr>" for _, row in top5.iterrows())
body_html += f'<tr><td class="ellipsis" colspan="{len(column_titles)}">⋯</td></tr>'
body_html += "".join(f"<tr>{render_row(row)}</tr>" for _, row in bottom1.iterrows())

st.markdown(
    f"""
    <div class="data-table-wrap">
    <table class="data-table">
        <thead><tr>{header_html}</tr></thead>
        <tbody>{body_html}</tbody>
    </table>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    f"{len(breeds)} breeds, as returned by the API (empty columns removed). Life span "
    "and weight are still free text. Shown: the lowest 5 IDs, then the highest."
)

# Some breeds miss life span and/or weight. Show what that excludes, but
# only if it excludes anything -- clean future data should hide this table.
sized = breeds.dropna(subset=["weight_avg_kg", "life_span_avg_years"])
excluded_either = len(breeds) - len(sized)
if excluded_either > 0:
    missing_life = int(breeds["life_span_avg_years"].isna().sum())
    missing_weight = int(breeds["weight_avg_kg"].isna().sum())
    exclusion_rows = [
        ("Total breeds", f"{len(breeds)}"),
        ("Excluded — missing life span", f"{missing_life}"),
        ("Excluded — missing weight", f"{missing_weight}"),
        ("Remaining sample", f"{len(sized)}"),
    ]
    exclusion_html = "".join(
        f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in exclusion_rows
    )
    st.markdown("Not every breed has both values, so a few are excluded below:")
    st.markdown(
        f"""
        <div class="stats-table-wrap">
        <table class="stats-table">
            <thead><tr><th>Sample size</th><th>Count</th></tr></thead>
            <tbody>{exclusion_html}</tbody>
        </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- Question 1: which breeds have the longest predicted life span? ---
st.header("Which breeds have the longest predicted life span?")

# Sorted so lowest life span is near the y-axis, highest is furthest away.
life_span = (
    breeds.dropna(subset=["life_span_avg_years"])
    .sort_values("life_span_avg_years")
    .reset_index(drop=True)
)
life_span["rank"] = range(len(life_span))

max_avg = life_span["life_span_avg_years"].max()
life_span["is_top"] = life_span["life_span_avg_years"] == max_avg
top_breeds = life_span[life_span["is_top"]].copy().reset_index(drop=True)

# Headroom above the highest span, for the stacked labels added below.
y_domain = [0, life_span["life_span_max_years"].max() + 5.5]
y_scale = alt.Scale(domain=y_domain)

# A thin line per breed spanning its reported min-to-max life span.
spans = (
    alt.Chart(life_span)
    .mark_rule(strokeWidth=1.5)
    .encode(
        x=alt.X("rank:Q", axis=None, title="Breeds, sorted by predicted life span"),
        y=alt.Y("life_span_min_years:Q", title="Expected life span (years)", scale=y_scale),
        y2="life_span_max_years:Q",
        color=alt.condition("datum.is_top", alt.value(COLOR_TOP), alt.value(COLOR_OTHER)),
        opacity=alt.condition("datum.is_top", alt.value(0.9), alt.value(0.3)),
        tooltip=[
            alt.Tooltip("name:N", title="Breed"),
            alt.Tooltip("life_span_min_years:Q", title="Min. expected life span (years)"),
            alt.Tooltip("life_span_max_years:Q", title="Max. expected life span (years)"),
        ],
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
        tooltip=[
            alt.Tooltip("name:N", title="Breed"),
            alt.Tooltip("years:Q", title="Expected life span (years)"),
        ],
    )
)

# Tied breeds share a value, so their labels are stacked, not overlapped.
top_breeds["label_rank"] = top_breeds["rank"].min()
top_breeds["label_y"] = y_domain[1] - 1.5 * top_breeds.index

labels = (
    alt.Chart(top_breeds)
    .mark_text(align="left", dx=8, fontSize=14, fontWeight="bold", color=COLOR_TEXT)
    .encode(x="label_rank:Q", y=alt.Y("label_y:Q", scale=y_scale), text="name")
)

chart1 = (spans + points + labels).properties(height=460).configure_axis(
    labelFontSize=13, titleFontSize=15
)
st.altair_chart(chart1, use_container_width=True)

top_row = top_breeds.iloc[0]
st.markdown(
    f"**{len(top_breeds)} breeds share the longest predicted life span** "
    f"({top_row['life_span_min_years']:.0f}-{top_row['life_span_max_years']:.0f} years, "
    f"highlighted in orange): {', '.join(top_breeds['name'])}."
)

# --- Question 3: how are breeds distributed across weight classes? ---
st.header("How are breeds distributed across weight classes?")

# One bar per 5 kg of average weight, colored by the size class it falls in.
weighed = breeds.dropna(subset=["weight_avg_kg"]).copy()
weighed["bin_start"] = (weighed["weight_avg_kg"].astype(float) // WEIGHT_BIN_KG) * WEIGHT_BIN_KG
weighed["bin_end"] = weighed["bin_start"] + WEIGHT_BIN_KG
bins = (
    weighed.groupby(["bin_start", "bin_end", "size_label"]).size().reset_index(name="breeds")
)
bins["range"] = bins.apply(lambda b: f"{b.bin_start:.0f}-{b.bin_end:.0f} kg", axis=1)

bars = (
    alt.Chart(bins)
    .mark_bar(stroke="#f9f6ef", strokeWidth=1.5)
    .encode(
        x=alt.X("bin_start:Q", title="Avg. weight (kg)", scale=alt.Scale(nice=False)),
        x2="bin_end:Q",
        y=alt.Y("breeds:Q", title="Number of breeds"),
        y2=alt.datum(0),
        color=alt.Color(
            "size_label:N",
            title="Size class",
            scale=alt.Scale(
                domain=list(SIZE_LABEL_COLORS.keys()), range=list(SIZE_LABEL_COLORS.values())
            ),
        ),
        tooltip=[
            alt.Tooltip("range:N", title="Weight"),
            alt.Tooltip("breeds:Q", title="Breeds"),
            alt.Tooltip("size_label:N", title="Size class"),
        ],
    )
)
counts_text = (
    alt.Chart(bins)
    .mark_text(dy=-8, fontSize=13, color=COLOR_TEXT)
    .encode(x=alt.X("mid:Q"), y="breeds:Q", text="breeds:Q")
    .transform_calculate(mid="(datum.bin_start + datum.bin_end) / 2")
)
st.altair_chart(
    (bars + counts_text).properties(height=420).configure_axis(labelFontSize=13, titleFontSize=15)
    .configure_legend(labelFontSize=13, titleFontSize=14),
    use_container_width=True,
)

per_class = weighed["size_label"].value_counts()
most = per_class.idxmax()
st.markdown(
    f"**{len(weighed)} breeds** have a known weight. Most are **{most.split(' (')[0]}** "
    f"({per_class.max()} breeds, {per_class.max() / len(weighed):.0%}); only "
    f"{per_class.get(SIZE_CLASS_LABELS['Giant'], 0)} are Giant. "
    "Each bar is 5 kg wide and uses the breed's average weight (the middle of its "
    "reported range, so a breed listed at 20-30 kg counts as 25 kg)."
)

# --- Question 2: relationship between size and life span ---
st.header("Is there a relationship between size and life span?")

# `sized` is computed above, with the exclusion table.

# Linear regression: slope, intercept, correlation (r), and the p-value
# for H0: slope = 0 (same test as asking if the correlation is nonzero).
slope, intercept, r, p_value, stderr = stats.linregress(
    sized["weight_avg_kg"], sized["life_span_avg_years"]
)
n = len(sized)
t_stat = slope / stderr

points = (
    alt.Chart(sized)
    .mark_circle(size=55, opacity=0.75)
    .encode(
        x=alt.X("weight_avg_kg:Q", title="Avg. weight (kg)"),
        y=alt.Y("life_span_avg_years:Q", title="Avg. expected life span (years)"),
        color=alt.Color(
            "size_label:N",
            title="Size class",
            scale=alt.Scale(
                domain=list(SIZE_LABEL_COLORS.keys()), range=list(SIZE_LABEL_COLORS.values())
            ),
        ),
        tooltip=[
            alt.Tooltip("name:N", title="Breed"),
            alt.Tooltip("weight_avg_kg:Q", title="Avg. weight (kg)"),
            alt.Tooltip("life_span_avg_years:Q", title="Avg. expected life span (years)"),
            alt.Tooltip("size_class:N", title="Size class"),
        ],
    )
)

trend = (
    alt.Chart(sized)
    .transform_regression("weight_avg_kg", "life_span_avg_years")
    .mark_line(color=COLOR_TEXT, strokeDash=[6, 3], strokeWidth=2)
    .encode(x="weight_avg_kg:Q", y="life_span_avg_years:Q")
)

# Slope as a callout box + pointer, not a plain label (which overlapped the line).
x_min, x_max = sized["weight_avg_kg"].min(), sized["weight_avg_kg"].max()
x_anchor = x_min + 0.55 * (x_max - x_min)  # mid-line, away from crowded edges
y_on_line = slope * x_anchor + intercept
label_y = y_on_line + 2.6
box_half_width = 0.13 * (x_max - x_min)

connector = (
    alt.Chart(pd.DataFrame([{"x": x_anchor, "y0": y_on_line, "y1": label_y - 0.65}]))
    .mark_rule(color=COLOR_TOP, strokeWidth=1.5)
    .encode(x="x:Q", y="y0:Q", y2="y1:Q")
)
pin = (
    alt.Chart(pd.DataFrame([{"x": x_anchor, "y": y_on_line}]))
    .mark_point(filled=True, size=55, color=COLOR_TOP)
    .encode(x="x:Q", y="y:Q")
)
callout_box = (
    alt.Chart(
        pd.DataFrame(
            [
                {
                    "x0": x_anchor - box_half_width,
                    "x1": x_anchor + box_half_width,
                    "y0": label_y - 0.65,
                    "y1": label_y + 0.65,
                }
            ]
        )
    )
    .mark_rect(color="#efe8d8", stroke=COLOR_TOP, strokeWidth=1.2, cornerRadius=4)
    .encode(x="x0:Q", x2="x1:Q", y="y0:Q", y2="y1:Q")
)
slope_label = (
    alt.Chart(pd.DataFrame([{"x": x_anchor, "y": label_y, "text": f"slope: {slope:.3f} years/kg"}]))
    .mark_text(fontWeight="bold", fontSize=16, color=COLOR_TEXT)
    .encode(x="x:Q", y="y:Q", text="text")
)

chart2 = (
    (points + trend + connector + pin + callout_box + slope_label)
    .properties(height=460)
    .configure_axis(labelFontSize=13, titleFontSize=15)
    .configure_legend(labelFontSize=13, titleFontSize=14)
)
st.altair_chart(chart2, use_container_width=True)

direction = "negative" if r < 0 else "positive"
slope_days = abs(slope) * 365
st.markdown(
    f"A clear {direction} relationship: life span drops **{abs(slope):.3f} years "
    f"({slope_days:.0f} days) per extra kg**, on average."
)

st.markdown("**Is this real, or random chance?**")
st.markdown(
    "A Pearson correlation test. H0: no relationship (correlation = 0). "
    "H1: there is one. We reject H0 if p < 0.05."
)

p_mantissa, p_exponent = f"{p_value:.2e}".split("e")
p_display = f"{p_mantissa} × 10<sup>{int(p_exponent)}</sup> ≈ 0.00"

stats_rows = [
    ("Correlation (r)", f"{r:.3f}"),
    ("Sample size (n)", f"{n}"),
    ("Slope (years/kg)", f"{slope:.4f}"),
    ("t-statistic", f"{t_stat:.2f}"),
    ("p-value", p_display),
    (
        "Conclusion (α = 0.05)",
        "Reject H0 — significant" if p_value < 0.05 else "Fail to reject H0",
    ),
]
rows_html = "".join(f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in stats_rows)
st.markdown(
    f"""
    <div class="stats-table-wrap">
    <table class="stats-table">
        <thead><tr><th>Statistic</th><th>Value</th></tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>
    """,
    unsafe_allow_html=True,
)
