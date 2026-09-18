"""Dog Breed Explorer -- a consumer-facing browse/discover app, separate
from dashboard/app.py (the analytics dashboard). Same warehouse, same data,
different audience: this one is for exploring breeds, not analyzing them."""

import urllib.parse
from pathlib import Path

import altair as alt
import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from scipy import stats

COLOR_ACCENT = "#c96a1f"
COLOR_TEXT = "#1a1a1a"
PAGE_SIZE = 24

# A few common non-ISO origin names, so more of the map actually resolves.
COUNTRY_ALIASES = {
    "England": "United Kingdom",
    "Scotland": "United Kingdom",
    "Wales": "United Kingdom",
    "Northern Ireland": "United Kingdom",
    "Tibet": "China",
}

# Short, plain-language descriptions for the traits shown in the word cloud.
TRAIT_DESCRIPTIONS = {
    "intelligent": "Quick to learn, and good at solving problems on their own.",
    "loyal": "Forms strong, lasting bonds with their family.",
    "alert": "Attentive, and quick to notice changes around them.",
    "energetic": "Needs plenty of exercise and activity to stay happy.",
    "courageous": "Brave, and unafraid to face challenges or danger.",
    "independent": "Comfortable making their own decisions; doesn't need constant guidance.",
    "affectionate": "Enjoys physical closeness and showing love to their people.",
    "friendly": "Warms up easily to people and other animals.",
    "protective": "Watchful over their family and territory.",
    "playful": "Enjoys games, and keeps a fun-loving spirit.",
    "confident": "Self-assured in new situations and surroundings.",
    "gentle": "Calm and mild-mannered, especially around children.",
    "calm": "Relaxed and even-tempered; not easily startled.",
    "work-focused": "Bred for a job, and thrives when given tasks to do.",
    "devoted": "Deeply attached to their owner -- often a \"one-person\" dog.",
    "outgoing": "Sociable, and eager to meet new people or animals.",
    "adaptable": "Adjusts easily to new environments and routines.",
    "eager to please": "Motivated to make their owner happy; often easy to train.",
}


def extract_country(origin: str) -> str:
    """origin is free text, e.g. "Gascony, France" -- take the last part."""
    country = origin.split(",")[-1].strip()
    return COUNTRY_ALIASES.get(country, country)


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"

st.set_page_config(page_title="Dog Breed Explorer", page_icon="🐾", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600;700&display=swap');

    .block-container { padding-left: 5rem; padding-right: 5rem; max-width: 1300px; }
    h1, h2, h3 { font-family: 'Source Serif 4', Georgia, serif !important; }

    .eyebrow {
        font-size: 0.85rem; letter-spacing: 0.14em; text-transform: uppercase;
        color: #a9713a; font-weight: 600; margin-bottom: 0.3rem;
    }
    .subtitle { font-size: 1.15rem; color: #52514e; margin-bottom: 1.2rem; }
    .hero-photo {
        width: 100%; border-radius: 16px; object-fit: cover; height: 320px;
    }
    .stat-badge {
        background: #efe8d8; border-radius: 10px; padding: 0.8rem 1.1rem;
        text-align: center;
    }
    .stat-badge .n { font-size: 1.6rem; font-weight: 700; color: #c96a1f; }
    .stat-badge .label { font-size: 0.85rem; color: #52514e; }

    .group-tile img {
        width: 100%; height: 110px; object-fit: cover; border-radius: 10px 10px 0 0;
    }
    .group-tile .body {
        background: #efe8d8; border-radius: 0 0 10px 10px; padding: 0.5rem 0.8rem;
        font-size: 0.9rem;
    }
    .group-tile .count { color: #7a7263; font-size: 0.78rem; }

    .mini-card {
        border: 1px solid #e1e0d9; border-radius: 12px; background: #fff;
        padding: 1rem; height: 100%;
    }

    .breed-card {
        border: 1px solid #e1e0d9; border-radius: 12px; overflow: hidden;
        margin-bottom: 1.2rem; background: #fff;
    }
    .breed-card img { width: 100%; height: 170px; object-fit: cover; }
    .breed-card .body { padding: 0.8rem 1rem; }
    .breed-card .name { font-weight: 700; font-size: 1.05rem; }
    .breed-card .meta { color: #7a7263; font-size: 0.85rem; margin-bottom: 0.4rem; }
    .chip {
        display: inline-block; background: #efe8d8; color: #7a4a1f;
        border-radius: 999px; padding: 0.15rem 0.6rem; font-size: 0.78rem;
        margin: 0 0.25rem 0.25rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

con = duckdb.connect(str(DB_PATH), read_only=True)
breeds = con.execute("select * from main.breeds").df()
temperaments_all = con.execute("select * from main.breed_temperaments").df()
top_traits = temperaments_all["temperament"].value_counts().head(8)

for key, default in [("view", "home"), ("search", ""), ("group_filter", []), ("filter_key", None)]:
    if key not in st.session_state:
        st.session_state[key] = default


def go_browse(search="", group=None):
    st.session_state.view = "browse"
    st.session_state.search = search
    st.session_state.group_filter = [group] if group else []
    st.session_state.browse_page = 1


# ------------------------------------------------------------ BREED GRID --
def render_breed_grid(df: pd.DataFrame, key_prefix: str):
    """Paginated card grid, shared by the browse view and trait pages."""
    page_key = f"{key_prefix}_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    total_pages = max(1, -(-len(df) // PAGE_SIZE))
    st.session_state[page_key] = min(st.session_state[page_key], total_pages)
    page = st.session_state[page_key]
    shown = df.iloc[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

    cols = st.columns(4)
    for i, (_, breed) in enumerate(shown.iterrows()):
        traits = temperaments_all.loc[temperaments_all["breed_id"] == breed["breed_id"], "temperament"].head(3)
        chips = "".join(f'<span class="chip">{t.capitalize()}</span>' for t in traits)
        life = "?" if pd.isna(breed["life_span_min_years"]) else f'{breed["life_span_min_years"]:.0f}-{breed["life_span_max_years"]:.0f} yrs'
        weight = "?" if pd.isna(breed["weight_min_kg"]) else f'{breed["weight_min_kg"]:.0f}-{breed["weight_max_kg"]:.0f} kg'
        with cols[i % 4]:
            st.markdown(
                f"""
                <div class="breed-card">
                    <img src="{breed['image_url']}">
                    <div class="body">
                        <div class="name">{breed['name']}</div>
                        <div class="meta">{breed['breed_group'] or 'Unknown group'} &middot; {life} &middot; {weight}</div>
                        {chips}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    render_pagination(total_pages, page, page_key)


def render_pagination(total_pages: int, current: int, page_key: str):
    if total_pages <= 1:
        return
    window = 2
    nearby = range(max(1, current - window), min(total_pages, current + window) + 1)
    tokens = sorted(set([1, total_pages, *nearby]))
    n_slots = len(tokens) + 4  # Prev/Next + at most two "…" gaps

    # A narrow, centered block instead of buttons spread across the full width.
    pad, center, _pad = st.columns([1, n_slots * 1.1, 1])
    with center:
        cols = st.columns(n_slots)
        if cols[0].button("‹ Prev", disabled=current == 1, key=f"{page_key}_prev"):
            st.session_state[page_key] = current - 1
            st.rerun()

        col_i = 1
        prev_token = None
        for token in tokens:
            if prev_token is not None and token - prev_token > 1:
                cols[col_i].markdown("…")
                col_i += 1
            is_current = token == current
            if cols[col_i].button(str(token), key=f"{page_key}_{token}",
                                   type="primary" if is_current else "secondary"):
                st.session_state[page_key] = token
                st.rerun()
            col_i += 1
            prev_token = token

        if cols[col_i].button("Next ›", disabled=current == total_pages, key=f"{page_key}_next"):
            st.session_state[page_key] = current + 1
            st.rerun()


# ---------------------------------------------------------------- HOME ----
def render_home():
    left, right = st.columns([3, 2])
    with left:
        st.markdown('<div class="eyebrow">Discover &middot; Learn &middot; Celebrate</div>', unsafe_allow_html=True)
        st.title("Dog Breed Explorer")
        st.markdown(
            f'<div class="subtitle">Explore {len(breeds)} dog breeds with curated data on '
            "temperament, size, life span, origin, and more.</div>",
            unsafe_allow_html=True,
        )
        search = st.text_input("Search for a breed", placeholder="e.g. Golden Retriever, Poodle, Akita...")
        if st.button("Discover", type="primary"):
            go_browse(search=search)
            st.rerun()

        st.write("")
        tags = ["Golden Retriever", "French Bulldog", "German Shepherd",
                "Poodle", "Dachshund", "Labrador Retriever"]
        for row in (tags[:3], tags[3:]):
            row_cols = st.columns(3)
            for col, tag in zip(row_cols, row):
                if col.button(tag, key=f"tag_{tag}"):
                    go_browse(search=tag)
                    st.rerun()

    with right:
        hero_image = breeds.loc[breeds["name"] == "Golden Retriever", "image_url"].iloc[0]
        st.markdown(f'<img class="hero-photo" src="{hero_image}">', unsafe_allow_html=True)

    st.write("")
    n_groups = breeds["breed_group"].nunique()
    n_traits = temperaments_all["temperament"].nunique()
    stat_cols = st.columns(3)
    for col, (n, label) in zip(
        stat_cols,
        [(len(breeds), "Breeds in our dataset"), (n_groups, "Breed groups"), (n_traits, "Temperament traits")],
    ):
        col.markdown(
            f'<div class="stat-badge"><div class="n">{n}</div><div class="label">{label}</div></div>',
            unsafe_allow_html=True,
        )

    st.header("Popular breed groups")
    top_groups = breeds["breed_group"].value_counts().head(8)
    tile_cols = st.columns(4)
    for i, (group, count) in enumerate(top_groups.items()):
        thumb = breeds.loc[breeds["breed_group"] == group, "image_url"].iloc[0]
        with tile_cols[i % 4]:
            st.markdown(
                f'<div class="group-tile"><img src="{thumb}">'
                f'<div class="body">{group}<br><span class="count">{count} breeds</span></div></div>',
                unsafe_allow_html=True,
            )
            if st.button(f"Browse {group}", key=f"group_{group}"):
                go_browse(group=group)
                st.rerun()

    st.header("Explore the data")
    map_col, cloud_col, scatter_col = st.columns(3)
    render_origin_map(map_col)
    render_temperament_cloud(cloud_col)
    render_size_vs_life_span(scatter_col)


def render_origin_map(col):
    with col:
        st.markdown('<div class="mini-card"><b>Where dogs come from</b><br>', unsafe_allow_html=True)
        counts = (
            breeds.assign(country=breeds["origin"].map(extract_country))
            .groupby("country").size().reset_index(name="count")
        )
        # Color by log(count): the raw counts are heavily skewed (a handful of
        # countries with 80+ breeds, most with 1-3), so a linear scale would
        # make almost every country look the same pale color.
        counts["color_value"] = np.log1p(counts["count"])
        fig = px.choropleth(
            counts, locations="country", locationmode="country names", color="color_value",
            color_continuous_scale=["#f7ecd8", "#e0a86a", "#c96a1f", "#8a4413", "#3a2210"],
            hover_name="country", hover_data={"count": True, "color_value": False},
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0), height=260, coloraxis_showscale=False,
            geo=dict(bgcolor="rgba(0,0,0,0)", showframe=False),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)


def render_temperament_cloud(col):
    with col:
        st.markdown('<div class="mini-card"><b>Explore temperaments</b><br><br>', unsafe_allow_html=True)
        counts = temperaments_all["temperament"].value_counts().head(18)
        lo, hi = counts.min(), counts.max()
        palette = ["#c96a1f", "#7a4a1f", "#3a6a5c", "#a03d3d", "#4a3aa7", "#1a1a1a", "#b3691f", "#2a6a4a"]

        # Tier the words by frequency, then place the biggest tier in the
        # middle row and taper outward, so the most common trait reads as
        # the visual center of the cloud, not just the biggest word in a
        # left-to-right list.
        tier_sizes = [1, 2, 3, 4, 4, 4]
        traits_sorted = list(counts.items())
        tiers, idx = [], 0
        for size in tier_sizes:
            tiers.append(traits_sorted[idx : idx + size])
            idx += size
        offsets = [0, -1, 1, -2, 2, -3][: len(tiers)]
        ordered_tiers = [tier for _, tier in sorted(zip(offsets, tiers), key=lambda t: t[0])]

        color_i = 0
        rows_html = []
        for tier in ordered_tiers:
            spans = []
            for trait, count in tier:
                size_px = 13 + 27 * ((count - lo) / max(1, hi - lo))
                color = palette[color_i % len(palette)]
                color_i += 1
                href = f"?trait={urllib.parse.quote(trait)}"
                spans.append(
                    f'<a href="{href}" target="_self" style="font-size:{size_px:.0f}px;color:{color};'
                    f'font-weight:700;text-decoration:none;margin:0 10px;white-space:nowrap;'
                    f'flex-shrink:0;">{trait.capitalize()}</a>'
                )
            rows_html.append(f'<div style="display:flex;flex-wrap:wrap;justify-content:center;">{"".join(spans)}</div>')

        st.markdown("".join(rows_html) + "</div>", unsafe_allow_html=True)


def render_size_vs_life_span(col):
    with col:
        st.markdown(
            '<div class="mini-card"><b>Is there a relationship between size and life span?</b><br>',
            unsafe_allow_html=True,
        )
        sized = breeds.dropna(subset=["weight_avg_kg", "life_span_avg_years"])
        slope, intercept, r, p_value, stderr = stats.linregress(
            sized["weight_avg_kg"], sized["life_span_avg_years"]
        )
        points = alt.Chart(sized).mark_circle(size=25, opacity=0.6, color=COLOR_ACCENT).encode(
            x=alt.X("weight_avg_kg:Q", title="Weight (kg)"),
            y=alt.Y("life_span_avg_years:Q", title="Life span (yrs)"),
        )
        trend = alt.Chart(sized).transform_regression(
            "weight_avg_kg", "life_span_avg_years"
        ).mark_line(color=COLOR_TEXT, strokeDash=[4, 3]).encode(x="weight_avg_kg:Q", y="life_span_avg_years:Q")
        st.altair_chart((points + trend).properties(height=230), use_container_width=True)
        st.caption(
            f"Correlation: {r:.2f} (slope {slope:.3f} yrs/kg) -- bigger dogs tend to live shorter lives. "
            "Full stats on the analytics dashboard."
        )
        st.markdown("</div>", unsafe_allow_html=True)


# -------------------------------------------------------------- BROWSE ----
def render_browse():
    if st.button("← Home"):
        st.session_state.view = "home"
        st.rerun()

    st.title("Discover breeds")

    f1, f2, f3, f4, f5 = st.columns([2, 2, 2, 2, 1])
    search = f1.text_input("Search", value=st.session_state.search)
    groups = f2.multiselect("Breed group", sorted(breeds["breed_group"].dropna().unique()),
                             default=st.session_state.group_filter)
    sizes = f3.multiselect("Size class", ["Small", "Medium", "Large", "Giant"])
    selected_traits = f4.multiselect(
        "Temperament", [f"{t.capitalize()} ({c})" for t, c in top_traits.items()]
    )
    selected_traits = [s.rsplit(" (", 1)[0].lower() for s in selected_traits]
    sort_by = f5.selectbox("Sort by", ["Name", "Longest life span", "Heaviest"])

    filtered = breeds
    if search:
        filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)]
    if groups:
        filtered = filtered[filtered["breed_group"].isin(groups)]
    if sizes:
        filtered = filtered[filtered["size_class"].isin(sizes)]
    if selected_traits:
        matching_ids = temperaments_all.loc[
            temperaments_all["temperament"].isin(selected_traits), "breed_id"
        ].unique()
        filtered = filtered[filtered["breed_id"].isin(matching_ids)]

    if sort_by == "Longest life span":
        filtered = filtered.sort_values("life_span_avg_years", ascending=False)
    elif sort_by == "Heaviest":
        filtered = filtered.sort_values("weight_avg_kg", ascending=False)
    else:
        filtered = filtered.sort_values("name")

    # Reset to page 1 whenever the filters/sort actually change.
    filter_key = (search, tuple(groups), tuple(sizes), tuple(sorted(selected_traits)), sort_by)
    if filter_key != st.session_state.filter_key:
        st.session_state.filter_key = filter_key
        st.session_state.browse_page = 1

    st.caption(f"{len(filtered)} breeds match your filters.")
    render_breed_grid(filtered, key_prefix="browse")


# --------------------------------------------------------- TRAIT DETAIL ----
def render_trait_detail(trait: str):
    if st.button("← Home"):
        st.query_params.clear()
        st.session_state.view = "home"
        st.rerun()

    st.title(trait.capitalize())
    st.markdown(TRAIT_DESCRIPTIONS.get(trait, "No description available yet for this trait."))

    matching_ids = temperaments_all.loc[temperaments_all["temperament"] == trait, "breed_id"].unique()
    matching_breeds = breeds[breeds["breed_id"].isin(matching_ids)].sort_values("name")
    st.caption(f"{len(matching_breeds)} breeds are described as {trait}.")
    render_breed_grid(matching_breeds, key_prefix=f"trait_{trait}")


if "trait" in st.query_params:
    render_trait_detail(st.query_params["trait"].lower())
elif st.session_state.view == "home":
    render_home()
else:
    render_browse()
