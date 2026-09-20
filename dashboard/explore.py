"""Dog Breed Explorer -- a consumer-facing browse/discover app, separate
from dashboard/app.py (the analytics dashboard). Same warehouse, same data,
different audience: this one is for exploring breeds, not analyzing them."""

import math
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

# Longer, plain-language descriptions for the traits shown in the word cloud
# -- what the trait tends to look like day to day, not just a one-liner.
TRAIT_DESCRIPTIONS = {
    "intelligent": (
        "Intelligent dogs pick up new commands and routines quickly, often after just a few "
        "repetitions. They tend to problem-solve on their own -- figuring out how to open doors, "
        "find hidden treats, or work around obstacles. This same sharpness means they need mental "
        "stimulation, not just exercise; a bored intelligent dog will often invent its own games, "
        "which aren't always the games you'd choose. Puzzle toys, scent work, and ongoing training "
        "keep them satisfied."
    ),
    "loyal": (
        "A loyal dog forms deep, lasting attachments to their family and stays devoted through "
        "the years. They tend to check in often, follow their owner from room to room, and settle "
        "best when their people are nearby. This bond can make them excellent watchdogs and "
        "companions, but it also means they can struggle with long absences or being rehomed. "
        "Loyal breeds usually reward consistent, patient handling with unwavering trust."
    ),
    "alert": (
        "An alert dog notices sounds, movement, and changes in their environment before most "
        "people do. They're quick to raise their head, prick their ears, or bark at something "
        "unusual, which makes them naturally good at signaling visitors or potential issues. This "
        "watchfulness is useful for a family that wants a heads-up, but it can also mean more "
        "barking than some households want. Alert dogs generally settle down once they've "
        "confirmed there's no real threat."
    ),
    "energetic": (
        "Energetic dogs have a high drive to move, play, and explore, and they don't tire out "
        "easily. Without enough daily exercise, that energy tends to come out as restlessness, "
        "chewing, or excessive barking. They do best with owners who enjoy long walks, runs, or "
        "active play sessions, and they often thrive in dog sports like agility or fetch-based "
        "games. A tired energetic dog is usually a calm, happy one."
    ),
    "courageous": (
        "Courageous dogs face new situations, unfamiliar animals, or potential threats without "
        "backing down. This bravery historically made many of these breeds effective at guarding, "
        "hunting, or working alongside people in demanding conditions. At home, it can translate "
        "into confidence around strangers or other animals, though it sometimes means they don't "
        "back away from confrontations they should avoid. Consistent socialization channels this "
        "courage constructively."
    ),
    "independent": (
        "Independent dogs are comfortable making their own decisions and don't need constant "
        "direction or reassurance from their owner. They can happily entertain themselves and "
        "often approach training on their own terms rather than eagerly seeking approval. This "
        "self-reliance was often bred for specific jobs, like hunting or herding at a distance, "
        "where a dog had to think for itself. Patient, respect-based training usually works "
        "better than repetition-heavy methods."
    ),
    "affectionate": (
        "Affectionate dogs actively seek out physical closeness -- leaning against legs, climbing "
        "into laps, or wanting to be touched and petted often. They tend to form warm bonds "
        "quickly and enjoy being included in everyday family life rather than kept at a distance. "
        "This makes them wonderful companions for people who want a dog that's demonstrative with "
        "its love. The flip side is that affectionate breeds can be prone to separation anxiety if "
        "left alone too often."
    ),
    "friendly": (
        "A friendly dog warms up quickly to new people, children, and often other animals, with "
        "little of the wariness some breeds show toward strangers. They tend to greet visitors "
        "with enthusiasm rather than suspicion, making them popular family pets. This openness "
        "usually extends to other dogs at the park or in group settings, though it doesn't replace "
        "proper introductions. Friendly breeds are generally easygoing about changes in their "
        "social circle."
    ),
    "protective": (
        "Protective dogs are naturally watchful over their family, home, and territory, and they'll "
        "position themselves between their people and anything they see as a threat. This instinct "
        "made many of these breeds valuable as guardians historically, and it still shows up today "
        "as alertness toward strangers or unfamiliar situations. With good socialization, "
        "protectiveness stays measured rather than aggressive. Owners should still supervise "
        "interactions with unfamiliar visitors."
    ),
    "playful": (
        "Playful dogs keep a fun-loving, youthful attitude well into adulthood, always ready for a "
        "game of fetch, tug, or chase. They tend to initiate play with people and other dogs, and "
        "they often use toys or invented games to burn off energy. This trait makes them "
        "entertaining, engaging companions, especially for active households or families with "
        "children. A playful dog that isn't given enough outlets can get creative in less welcome "
        "ways, like turning shoes into toys."
    ),
    "confident": (
        "Confident dogs walk into new environments, meet new people, and handle unexpected "
        "situations without much hesitation. They rarely seem intimidated, and they recover "
        "quickly from startling moments rather than staying anxious. This makes them well-suited "
        "to busy households, travel, or public outings where a nervous dog might struggle. "
        "Confidence should be nurtured with positive experiences early on so it doesn't tip into "
        "pushiness."
    ),
    "gentle": (
        "Gentle dogs are soft and careful in how they interact, especially with children, the "
        "elderly, or smaller animals. They tend to have a naturally calm way of engaging physically "
        "-- leaning in slowly rather than jumping or barreling forward. This makes them popular "
        "choices for families or first-time owners who want a low-drama companion. Gentle "
        "temperaments often respond better to a soft training approach than a firm one."
    ),
    "calm": (
        "Calm dogs have an even-tempered, relaxed default state, and they aren't easily rattled by "
        "noise, chaos, or new situations. They tend to settle quickly after excitement rather than "
        "staying wound up, and they're comfortable with quieter households. This makes them a good "
        "fit for apartment living or owners who prefer a low-key companion. Calm doesn't mean "
        "lazy, though -- many calm breeds are still happy to be active when asked."
    ),
    "work-focused": (
        "Work-focused dogs were bred for a specific job -- herding, guarding, hunting, or pulling "
        "-- and they still carry that drive to have a task. They tend to thrive when given "
        "structure, a routine, or something purposeful to do each day, rather than being left "
        "without direction. Without an outlet, that drive can turn into restlessness or the dog "
        "inventing its own \"job,\" which isn't always convenient for the household. Training, "
        "sport, or simple daily chores can satisfy this need."
    ),
    "devoted": (
        "Devoted dogs attach strongly to one person or their close family, often more intensely "
        "than the average dog. They tend to shadow their favorite person around the house and seek "
        "them out specifically, sometimes at the expense of bonding evenly with everyone. This "
        "deep attachment makes them incredibly rewarding companions for that person, but it can "
        "mean more difficulty adjusting to a new owner or household. Devoted breeds usually settle "
        "in for life once that bond is formed."
    ),
    "outgoing": (
        "Outgoing dogs actively seek out new people, animals, and experiences rather than waiting "
        "to be approached. They tend to greet strangers with enthusiasm and adapt easily to busy, "
        "social environments like parks, cafes, or gatherings. This makes them great companions "
        "for people who like to bring their dog everywhere. An outgoing dog still benefits from "
        "basic manners training, since their eagerness to meet everyone can come across as overly "
        "forward without it."
    ),
    "adaptable": (
        "Adaptable dogs adjust easily to new homes, routines, schedules, or environments without "
        "much stress. They tend to cope well with change -- a move, a new baby, a different "
        "walking schedule -- better than more rigid breeds. This flexibility makes them a solid "
        "choice for owners whose lives don't always follow the same pattern, like frequent "
        "travelers or growing families. Adaptable dogs still appreciate some consistency, but they "
        "don't fall apart without it."
    ),
    "eager to please": (
        "Dogs that are eager to please are highly motivated by their owner's approval, which makes "
        "them attentive during training and quick to respond to feedback. They tend to watch their "
        "person closely for cues and adjust their behavior based on praise or correction. This "
        "makes them some of the easier breeds to train, especially with positive reinforcement. "
        "The downside is they can be sensitive to a harsh tone or repeated correction, so a gentle, "
        "encouraging approach gets the best results."
    ),
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

    .section-title {
        font-family: 'Source Serif 4', Georgia, serif;
        font-size: 1.35rem; font-weight: 700; color: #1a1a1a;
        margin-bottom: 0.6rem;
    }
    .trait-description {
        font-size: 0.92rem; color: #52514e; line-height: 1.5; margin-top: 0.5rem;
    }

    .breed-card {
        border: 1px solid #e1e0d9; border-radius: 12px; overflow: hidden;
        margin-bottom: 1.2rem; background: #fff;
    }
    .breed-card img { width: 100%; height: 170px; object-fit: cover; }
    .breed-card .body { padding: 0.8rem 1rem; }
    .breed-card .name, .breed-card .meta, .breed-card .chips {
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .breed-card .name { font-weight: 700; font-size: 1.05rem; }
    .breed-card .meta { color: #7a7263; font-size: 0.85rem; margin-bottom: 0.4rem; }
    .breed-card .chips { min-height: 1.9rem; }
    .chip {
        display: inline-block; background: #efe8d8; color: #7a4a1f;
        border-radius: 999px; padding: 0.15rem 0.6rem; font-size: 0.78rem;
        margin: 0 0.25rem 0.25rem 0;
    }

    /* Pagination: shrink each column to its button and center the row. */
    [class*="st-key-pager_"] [data-testid="stHorizontalBlock"] {
        justify-content: center; gap: 0.4rem; flex-wrap: nowrap;
    }
    [class*="st-key-pager_"] [data-testid="stColumn"] {
        flex: 0 0 auto !important; width: auto !important; min-width: 0 !important;
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
CHIP_BUDGET = 42  # character budget for one line of chips (measured across all 27 pages)
CHIP_OVERHEAD = 4.7  # each chip's padding/margin, in character widths


def fit_chips(traits) -> list:
    """Chips that fit on one line, so every card has the same height. A trait
    that doesn't fully fit is shortened and ends in "-" (e.g. "Work-fo-")."""
    fitted, used = [], 0.0
    for trait in traits:
        word = trait.capitalize()
        if used + len(word) + CHIP_OVERHEAD <= CHIP_BUDGET:
            fitted.append(word)
            used += len(word) + CHIP_OVERHEAD
            continue
        room = int(CHIP_BUDGET - used - CHIP_OVERHEAD)
        if room >= 4:
            cut = word[: room - 1]
            fitted.append(cut if cut.endswith("-") else cut + "-")
        break
    return fitted


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
        chips = "".join(f'<span class="chip">{t}</span>' for t in fit_chips(traits))
        life = "?" if pd.isna(breed["life_span_min_years"]) else f'{breed["life_span_min_years"]:.0f}-{breed["life_span_max_years"]:.0f} yrs'
        weight = "?" if pd.isna(breed["weight_min_kg"]) else f'{breed["weight_min_kg"]:.0f}-{breed["weight_max_kg"]:.0f} kg'
        with cols[i % 4]:
            st.markdown(
                f"""
                <div class="breed-card">
                    <img src="{breed['image_url']}">
                    <div class="body">
                        <div class="name" title="{breed['name']}">{breed['name']}</div>
                        <div class="meta">{breed['breed_group'] or 'Unknown group'} &middot; {life} &middot; {weight}</div>
                        <div class="chips">{chips}</div>
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

    items = [("prev", None)]
    prev_token = None
    for token in tokens:
        if prev_token is not None and token - prev_token > 1:
            items.append(("gap", None))
        items.append(("page", token))
        prev_token = token
    items.append(("next", None))

    # The st-key-pager_* container is styled in the CSS above to pack the
    # columns tightly together and center them.
    with st.container(key=f"pager_{page_key}"):
        for col, (kind, value) in zip(st.columns(len(items)), items):
            with col:
                if kind == "gap":
                    st.markdown("…")
                elif kind == "prev":
                    if st.button("‹ Prev", disabled=current == 1, key=f"{page_key}_prev"):
                        st.session_state[page_key] = current - 1
                        st.rerun()
                elif kind == "next":
                    if st.button("Next ›", disabled=current == total_pages, key=f"{page_key}_next"):
                        st.session_state[page_key] = current + 1
                        st.rerun()
                elif st.button(str(value), key=f"{page_key}_{value}",
                               type="primary" if value == current else "secondary"):
                    st.session_state[page_key] = value
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
        st.markdown('<div class="section-title">Where dogs come from</div>', unsafe_allow_html=True)
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


def render_temperament_cloud(col):
    with col:
        st.markdown('<div class="section-title">Explore temperaments</div>', unsafe_allow_html=True)
        counts = temperaments_all["temperament"].value_counts().head(13)
        lo, hi = counts.min(), counts.max()
        palette = ["#c96a1f", "#7a4a1f", "#3a6a5c", "#a03d3d", "#4a3aa7", "#1a1a1a", "#b3691f", "#2a6a4a"]
        traits_sorted = list(counts.items())

        # Radial layout: the single most common trait sits dead center, and
        # each ring further out holds more (smaller) words, evenly spaced
        # around the circle -- a real word-cloud shape, not a left-to-right list.
        # Ring 1's angles skip the band directly left/right of center (0/180
        # degrees), since the center word is wide and words placed there would
        # collide with it even at a fairly generous radius.
        ring_sizes = [1, 5, 7]
        radii = [0, 118, 178]
        ring_angles = {1: [-90, -145, -35, 145, 35]}
        canvas_height = 400

        spans = []
        idx = 0
        for ring_i, (ring_size, radius) in enumerate(zip(ring_sizes, radii)):
            ring_traits = traits_sorted[idx : idx + ring_size]
            idx += ring_size
            angles = ring_angles.get(ring_i) or [
                -90 + ring_i * 15 + j * (360 / max(1, ring_size)) for j in range(ring_size)
            ]
            for j, (trait, count) in enumerate(ring_traits):
                angle = math.radians(angles[j])
                dx = radius * math.cos(angle)
                dy = radius * math.sin(angle)
                size_px = 13 + 21 * ((count - lo) / max(1, hi - lo))
                color = palette[idx % len(palette)]
                href = f"?trait={urllib.parse.quote(trait)}"
                spans.append(
                    f'<a href="{href}" target="_self" style="position:absolute; '
                    f'left:calc(50% + {dx:.0f}px); top:calc({canvas_height / 2:.0f}px + {dy:.0f}px); '
                    f'transform:translate(-50%,-50%); font-size:{size_px:.0f}px; color:{color}; '
                    f'font-weight:700; text-decoration:none; white-space:nowrap;">{trait.capitalize()}</a>'
                )

        st.markdown(
            f'<div style="position:relative; width:100%; height:{canvas_height}px;">{"".join(spans)}</div>',
            unsafe_allow_html=True,
        )


def render_size_vs_life_span(col):
    with col:
        st.markdown(
            '<div class="section-title">Is there a relationship between size and life span?</div>',
            unsafe_allow_html=True,
        )
        sized = breeds.dropna(subset=["weight_avg_kg", "life_span_avg_years"])
        slope, intercept, r, p_value, stderr = stats.linregress(
            sized["weight_avg_kg"], sized["life_span_avg_years"]
        )
        y_scale = alt.Scale(domain=[5, 16])  # pulled toward 0 instead of auto-cropping to the data
        points = alt.Chart(sized).mark_circle(size=25, opacity=0.6, color=COLOR_ACCENT).encode(
            x=alt.X("weight_avg_kg:Q", title="Weight (kg)"),
            y=alt.Y("life_span_avg_years:Q", title="Life span (yrs)", scale=y_scale),
        )
        trend = alt.Chart(sized).transform_regression(
            "weight_avg_kg", "life_span_avg_years"
        ).mark_line(color=COLOR_TEXT, strokeDash=[4, 3]).encode(
            x="weight_avg_kg:Q", y=alt.Y("life_span_avg_years:Q", scale=y_scale)
        )
        st.altair_chart((points + trend).properties(height=230), use_container_width=True)
        st.markdown(
            '<div class="trait-description">'
            "Each dot is one breed: its weight (left-right) and how long it's expected to live "
            "(up-down). The dashed line is the general trend -- it slopes down, meaning heavier "
            "breeds tend to live shorter lives on average. "
            f"<b>Correlation</b> ({r:.2f}) says how <i>strongly</i> the two are linked, on a scale "
            "from -1 (perfectly opposite) to +1 (perfectly together) -- it doesn't use any units. "
            f"<b>Slope</b> ({slope:.3f} yrs/kg) says <i>how much</i> life span actually drops for "
            "every extra kg of weight, in real years. Correlation tells you how tight the pattern "
            "is; slope tells you the actual rate. Full statistical test on the analytics dashboard."
            "</div>",
            unsafe_allow_html=True,
        )


# -------------------------------------------------------------- BROWSE ----
def render_browse():
    if st.button("← Home"):
        st.session_state.view = "home"
        st.rerun()

    st.title("Discover breeds")

    f1, f2, f3, f4, f5 = st.columns([2, 2, 2, 2, 2.2])
    search = f1.text_input("Search", value=st.session_state.search)
    groups = f2.multiselect("Breed group", sorted(breeds["breed_group"].dropna().unique()),
                             default=st.session_state.group_filter)
    sizes = f3.multiselect("Size class", ["Small", "Medium", "Large", "Giant"])
    selected_traits = f4.multiselect(
        "Temperament", [f"{t.capitalize()} ({c})" for t, c in top_traits.items()]
    )
    selected_traits = [s.rsplit(" (", 1)[0].lower() for s in selected_traits]
    sort_by = f5.selectbox(
        "Sort by",
        [
            "Alphabetical",
            "Life span: high → low",
            "Life span: low → high",
            "Weight: high → low",
            "Weight: low → high",
        ],
    )

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

    if sort_by == "Life span: high → low":
        filtered = filtered.sort_values("life_span_avg_years", ascending=False)
    elif sort_by == "Life span: low → high":
        filtered = filtered.sort_values("life_span_avg_years", ascending=True)
    elif sort_by == "Weight: high → low":
        filtered = filtered.sort_values("weight_avg_kg", ascending=False)
    elif sort_by == "Weight: low → high":
        filtered = filtered.sort_values("weight_avg_kg", ascending=True)
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
