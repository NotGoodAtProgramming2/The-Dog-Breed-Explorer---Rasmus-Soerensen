"""Dog Breed Explorer -- a consumer-facing browse/discover app, separate
from dashboard/app.py (the analytics dashboard). Same warehouse, same data,
different audience: this one is for exploring breeds, not analyzing them."""

from pathlib import Path

import duckdb
import streamlit as st

COLOR_ACCENT = "#c96a1f"
COLOR_TEXT = "#1a1a1a"

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

if "view" not in st.session_state:
    st.session_state.view = "home"
if "search" not in st.session_state:
    st.session_state.search = ""
if "group_filter" not in st.session_state:
    st.session_state.group_filter = []


def go_browse(search="", group=None):
    st.session_state.view = "browse"
    st.session_state.search = search
    st.session_state.group_filter = [group] if group else []


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
    n_traits = con.execute("select count(distinct temperament) from main.breed_temperaments").fetchone()[0]
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


# -------------------------------------------------------------- BROWSE ----
def render_browse():
    if st.button("← Home"):
        st.session_state.view = "home"
        st.rerun()

    st.title("Discover breeds")

    f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
    search = f1.text_input("Search", value=st.session_state.search)
    groups = f2.multiselect("Breed group", sorted(breeds["breed_group"].dropna().unique()),
                             default=st.session_state.group_filter)
    sizes = f3.multiselect("Size class", ["Small", "Medium", "Large", "Giant"])
    sort_by = f4.selectbox("Sort by", ["Name", "Longest life span", "Heaviest"])

    filtered = breeds
    if search:
        filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)]
    if groups:
        filtered = filtered[filtered["breed_group"].isin(groups)]
    if sizes:
        filtered = filtered[filtered["size_class"].isin(sizes)]

    if sort_by == "Longest life span":
        filtered = filtered.sort_values("life_span_avg_years", ascending=False)
    elif sort_by == "Heaviest":
        filtered = filtered.sort_values("weight_avg_kg", ascending=False)
    else:
        filtered = filtered.sort_values("name")

    st.caption(f"{len(filtered)} breeds match your filters.")

    limit = st.slider("Breeds to show", 8, 96, 24, step=8)
    shown = filtered.head(limit)

    temperaments = con.execute("select * from main.breed_temperaments").df()

    cols = st.columns(4)
    for i, (_, breed) in enumerate(shown.iterrows()):
        traits = temperaments.loc[temperaments["breed_id"] == breed["breed_id"], "temperament"].head(3)
        chips = "".join(f'<span class="chip">{t}</span>' for t in traits)
        life = "?" if pd_isna(breed["life_span_min_years"]) else f'{breed["life_span_min_years"]:.0f}-{breed["life_span_max_years"]:.0f} yrs'
        weight = "?" if pd_isna(breed["weight_min_kg"]) else f'{breed["weight_min_kg"]:.0f}-{breed["weight_max_kg"]:.0f} kg'
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


def pd_isna(value):
    return value is None or value != value  # NaN check without importing pandas here


if st.session_state.view == "home":
    render_home()
else:
    render_browse()
