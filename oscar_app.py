import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from pony.orm import *

DB_PATH = "oscar_awards.db"
DB_URL = "https://github.com/gubin-svg/OscarApp/releases/download/db/oscar_awards.db"

def ensure_db():
    if not os.path.exists(DB_PATH):
        r = requests.get(DB_URL, timeout=60)
        r.raise_for_status()
        with open(DB_PATH, "wb") as f:
            f.write(r.content)

ensure_db()

# =========================================================
# Database setup
# =========================================================
db = Database()


class Ceremony(db.Entity):
    id = PrimaryKey(int, auto=True)
    ceremony_number = Required(int, unique=True)
    year_ceremony = Required(int)
    nominations = Set("Nomination")


class Category(db.Entity):
    id = PrimaryKey(int, auto=True)
    category = Required(str, unique=True)
    canon_category = Required(str)
    nominations = Set("Nomination")


class Film(db.Entity):
    id = PrimaryKey(int, auto=True)
    name = Required(str, unique=True)
    nominations = Set("Nomination")


class Nomination(db.Entity):
    id = PrimaryKey(int, auto=True)
    year_film = Required(int)
    nominee_name = Required(str)
    winner = Required(bool)

    ceremony = Required(Ceremony)
    category = Required(Category)
    film = Optional(Film)


db.bind(provider="sqlite", filename="oscar_awards.db", create_db=False)
db.generate_mapping(create_tables=False)

# =========================================================
# Streamlit page
# =========================================================
st.set_page_config(page_title="Oscar Actor Explorer", layout="wide")
st.title("Oscar Actor Explorer")
st.subheader("Actor / Director Profile App")

st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at top left, #1a1f2b 0%, #121722 42%, #0c1018 100%);
        color: #e7ecf3;
    }
    .main .block-container {
        padding-top: 1.5rem;
    }
    .hero-card {
        background: linear-gradient(135deg, rgba(27, 38, 59, 0.95), rgba(65, 90, 119, 0.92));
        color: #f9f2df;
        border-radius: 16px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 10px 30px rgba(27, 38, 59, 0.2);
    }
    .hero-card h3 {
        margin: 0;
        font-size: 1.3rem;
    }
    .hero-card p {
        margin: 0.35rem 0 0 0;
        font-size: 0.95rem;
        color: #fff8e7;
    }
    .stButton > button {
        background: linear-gradient(135deg, #1b263b, #415a77);
        color: #fff8e7;
        border: 1px solid #0d1b2a;
        border-radius: 10px;
        font-weight: 700;
        padding: 0.55rem 1.1rem;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #24344f, #4c6a8e);
        color: #ffffff;
        border-color: #0d1b2a;
    }
    .stButton > button:focus {
        box-shadow: 0 0 0 0.2rem rgba(27, 38, 59, 0.35);
    }
    .stMetric {
        background-color: rgba(235, 241, 252, 0.08);
        border: 1px solid rgba(160, 185, 220, 0.28);
        padding: 0.7rem;
        border-radius: 12px;
    }
    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stMarkdownContainer"] li,
    div[data-testid="stCaptionContainer"] {
        color: #d8e1ef;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #f3f7ff;
    }
    div[data-testid="stDataFrame"] {
        background-color: rgba(235, 241, 252, 0.05);
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero-card">
      <h3>Discover Oscar Career Stories</h3>
      <p>Search for an actor or director to see achievements, category-level performance, and a visual timeline of their Oscar journey.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Helpers
# =========================================================
def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())

def is_relevant_category(category_name: str) -> bool:
    category_upper = category_name.upper()
    return (
        "ACTOR" in category_upper
        or "ACTRESS" in category_upper
        or "DIRECTING" in category_upper
    )


@st.cache_data
def load_all_nominee_names():
    with db_session:
        names = sorted({
            n.nominee_name
            for n in Nomination.select()
            if is_relevant_category(n.category.category)
        })
    return names


def get_name_suggestions(user_text: str, max_results: int = 10):
    if not user_text.strip():
        return []

    query = normalize_text(user_text)
    all_names = load_all_nominee_names()

    startswith_matches = [
        name for name in all_names
        if normalize_text(name).startswith(query)
    ]

    contains_matches = [
        name for name in all_names
        if query in normalize_text(name) and name not in startswith_matches
    ]

    return (startswith_matches + contains_matches)[:max_results]


@db_session
def get_person_profile(person_name: str):
    target = normalize_text(person_name)

    nominations = [
        n for n in Nomination.select()
        if normalize_text(n.nominee_name) == target
        and is_relevant_category(n.category.category)
    ]

    if not nominations:
        return None

    total_nominations = len(nominations)
    total_wins = sum(1 for n in nominations if n.winner)
    win_rate = total_wins / total_nominations if total_nominations else 0

    categories = sorted({n.category.category for n in nominations})
    years_active_list = sorted({n.ceremony.year_ceremony for n in nominations})

    nominated_films = sorted({
        n.film.name for n in nominations if n.film is not None
    })

    winning_films = sorted({
        n.film.name for n in nominations if n.film is not None and n.winner
    })

    first_nomination_year = min(years_active_list) if years_active_list else None
    winning_years = sorted(n.ceremony.year_ceremony for n in nominations if n.winner)
    first_win_year = winning_years[0] if winning_years else None

    years_to_first_win = None
    if first_nomination_year is not None and first_win_year is not None:
        years_to_first_win = first_win_year - first_nomination_year

    year_rows = []
    for year in years_active_list:
        year_noms = [n for n in nominations if n.ceremony.year_ceremony == year]
        year_rows.append({
            "Year": year,
            "Nominations": len(year_noms),
            "Wins": sum(1 for n in year_noms if n.winner),
        })

    # Comparison to average nominee in each category
    comparison_rows = []

    for category_name in categories:
        category_noms = [
            n for n in Nomination.select()
            if n.category.category == category_name
        ]

        nominee_stats = {}
        for n in category_noms:
            nominee = n.nominee_name
            if nominee not in nominee_stats:
                nominee_stats[nominee] = {"noms": 0, "wins": 0}
            nominee_stats[nominee]["noms"] += 1
            nominee_stats[nominee]["wins"] += int(n.winner)

        avg_nominee_win_rate = sum(
            stats["wins"] / stats["noms"] for stats in nominee_stats.values()
        ) / len(nominee_stats)

        person_cat_noms = [n for n in nominations if n.category.category == category_name]
        person_cat_win_rate = sum(1 for n in person_cat_noms if n.winner) / len(person_cat_noms)

        comparison_rows.append({
            "Category": category_name,
            "Person Win Rate": round(person_cat_win_rate * 100, 2),
            "Average Nominee Win Rate": round(avg_nominee_win_rate * 100, 2),
        })

    return {
        "display_name": nominations[0].nominee_name,
        "total_nominations": total_nominations,
        "total_wins": total_wins,
        "win_rate": win_rate,
        "categories": categories,
        "years_active": years_active_list,
        "nominated_films": nominated_films,
        "winning_films": winning_films,
        "years_to_first_win": years_to_first_win,
        "comparison_df": pd.DataFrame(comparison_rows),
        "journey_df": pd.DataFrame(year_rows),
    }


import requests
from urllib.parse import quote

HEADERS = {
    "User-Agent": "OscarActorExplorer/1.0 (student project)"
}

def get_wikipedia_info(person_name: str):
    try:
        base_api = "https://en.wikipedia.org/w/api.php"

        # 1) Search for the best matching page
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": f'intitle:"{person_name}"',
            "format": "json"
        }
        search_resp = requests.get(base_api, params=search_params, headers=HEADERS, timeout=10)
        search_resp.raise_for_status()
        search_data = search_resp.json()

        results = search_data.get("query", {}).get("search", [])
        if not results:
            return {
                "summary": "No Wikipedia page found.",
                "birth_date": None,
                "image_url": None,
                "options": []
            }

        options = [r["title"] for r in results[:5]]
        page_title = options[0]

        # 2) Get summary + image from REST summary endpoint
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(page_title)}"
        summary_resp = requests.get(summary_url, headers=HEADERS, timeout=10)
        summary_resp.raise_for_status()
        summary_data = summary_resp.json()

        summary = summary_data.get("extract", "No biography summary available.")
        image_url = None
        if "originalimage" in summary_data:
            image_url = summary_data["originalimage"].get("source")
        elif "thumbnail" in summary_data:
            image_url = summary_data["thumbnail"].get("source")

        # 3) Get Wikidata ID
        details_params = {
            "action": "query",
            "titles": page_title,
            "prop": "pageprops",
            "ppprop": "wikibase_item",
            "redirects": 1,
            "format": "json"
        }
        details_resp = requests.get(base_api, params=details_params, headers=HEADERS, timeout=10)
        details_resp.raise_for_status()
        details_data = details_resp.json()

        pages = details_data.get("query", {}).get("pages", {})
        page_data = next(iter(pages.values()))
        wikidata_id = page_data.get("pageprops", {}).get("wikibase_item")

        # 4) Get birth date from Wikidata (P569)
        birth_date = None
        if wikidata_id:
            wikidata_api = "https://www.wikidata.org/w/api.php"
            wd_params = {
                "action": "wbgetentities",
                "ids": wikidata_id,
                "props": "claims",
                "format": "json"
            }
            wd_resp = requests.get(wikidata_api, params=wd_params, headers=HEADERS, timeout=10)
            wd_resp.raise_for_status()
            wd_data = wd_resp.json()

            entity = wd_data.get("entities", {}).get(wikidata_id, {})
            claims = entity.get("claims", {})

            if "P569" in claims:
                mainsnak = claims["P569"][0].get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                time_value = datavalue.get("value", {}).get("time")
                if time_value:
                    birth_date = time_value.strip("+").split("T")[0]

        return {
            "summary": summary,
            "birth_date": birth_date,
            "image_url": image_url,
            "options": options
        }

    except Exception as e:
        return {
            "summary": f"Could not fetch Wikipedia information: {e}",
            "birth_date": None,
            "image_url": None,
            "options": []
        }

@db_session
def generate_fun_fact(profile):
    name = profile["display_name"]
    nominations = profile["total_nominations"]
    wins = profile["total_wins"]
    years_active = profile["years_active"]
    categories = profile["categories"]
    years_to_first_win = profile["years_to_first_win"]

    if wins == 0 and nominations >= 3:
        return f"{name} received {nominations} Oscar nominations but has never won."

    if wins > 0 and years_to_first_win == 0:
        return f"{name} won an Oscar on their very first nomination."

    if wins > 0 and years_to_first_win is not None and years_to_first_win >= 10:
        return f"It took {name} {years_to_first_win} years to go from first nomination to first Oscar win."

    if len(categories) > 1:
        return f"{name} was nominated in {len(categories)} different Oscar categories."

    if years_active:
        span = max(years_active) - min(years_active)
        if span >= 20:
            return f"{name}'s Oscar career spans {span} years."

    return f"{name} has {nominations} nominations and {wins} wins at the Oscars."

# =========================================================
# UI
# =========================================================
user_input = st.text_input(
    "Enter an actor or director name:",
    placeholder="e.g., Meryl Streep, Brad Pitt, Steven Spielberg"
)

suggestions = get_name_suggestions(user_input) if user_input else []

selected_name = None

if user_input:
    if len(user_input.strip().split()) < 2:
        st.info("Please enter a full name. Here are matching names from the dataset:")
        if suggestions:
            selected_name = st.selectbox(
                "Choose a full name:",
                options=suggestions,
                index=None,
                placeholder="Select a matching full name"
            )
        else:
            st.warning("No close matches found in the dataset yet.")
    else:
        exact_match_exists = any(
            normalize_text(name) == normalize_text(user_input)
            for name in load_all_nominee_names()
        )

        if exact_match_exists:
            selected_name = user_input
        elif suggestions:
            st.warning("Exact name not found. Did you mean one of these?")
            selected_name = st.selectbox(
                "Choose a matching name:",
                options=suggestions,
                index=None,
                placeholder="Select a suggested name"
            )
        else:
            st.error("This person was not found in the Oscar dataset.")

if st.button("Show Profile"):
    if not selected_name:
        st.warning("Please enter or choose a valid full name.")
    else:
        profile = get_person_profile(selected_name)
        fact = generate_fun_fact(profile)
        st.info("💡 Did You Know? " + fact)
        if profile is None:
            st.error("This person was not found in the Oscar dataset.")
        else:
            wiki = get_wikipedia_info(profile["display_name"])
    
            col1, col2 = st.columns([1, 2.4], vertical_alignment="top")

            with col1:
                if wiki["image_url"]:
                    st.image(wiki["image_url"], width=240)
                else:
                    st.info("No photo available.")

            with col2:
                st.markdown(f"## {profile['display_name']}")
                st.caption("Oscar profile snapshot")

                metric_col1, metric_col2, metric_col3 = st.columns(3)
                metric_col1.metric("Nominations", profile["total_nominations"])
                metric_col2.metric("Wins", profile["total_wins"])
                metric_col3.metric("Win Rate", f"{profile['win_rate']:.1%}")

                metric_col4, metric_col5 = st.columns(2)
                years_active_text = (
                    f"{min(profile['years_active'])}–{max(profile['years_active'])}"
                    if profile["years_active"] else "N/A"
                )
                metric_col4.metric("Years Active at Oscars", years_active_text)

                years_to_first_win_text = (
                    str(profile["years_to_first_win"])
                    if profile["years_to_first_win"] is not None
                    else "No win"
                )
                metric_col5.metric("Years to First Win", years_to_first_win_text)

            tab1, tab2 = st.tabs(["Overview", "Visual Insights"])

            with tab1:
                st.markdown("### Biography")
                st.write(wiki["summary"] if wiki["summary"] else "No biography summary available.")

                bio_col1, bio_col2 = st.columns([1, 2])
                with bio_col1:
                    st.markdown("### Birth Date")
                    st.write(wiki["birth_date"] if wiki["birth_date"] else "Not available")
                with bio_col2:
                    st.markdown("### Categories Nominated In")
                    st.write(", ".join(profile["categories"]) if profile["categories"] else "Not available")

                st.markdown("### Nominated Films")
                if profile["nominated_films"]:
                    st.write(", ".join(profile["nominated_films"]))
                else:
                    st.write("No nominated film data available.")

                st.markdown("### Winning Films")
                if profile["winning_films"]:
                    st.write(", ".join(profile["winning_films"]))
                else:
                    st.write("No winning films.")

            with tab2:
                st.markdown("### Category Performance")
                st.caption(
                    "Person Win Rate = this person's win percentage in that category. "
                    "Average Nominee Win Rate = average of all nominees' personal win percentages in that category."
                )

                comparison_df = profile["comparison_df"]

                if not comparison_df.empty:
                    st.dataframe(comparison_df, width="stretch")

                    comparison_long = comparison_df.melt(
                        id_vars="Category",
                        value_vars=["Person Win Rate", "Average Nominee Win Rate"],
                        var_name="Metric",
                        value_name="Percent"
                    )

                    fig_compare = px.bar(
                        comparison_long,
                        x="Category",
                        y="Percent",
                        color="Metric",
                        barmode="group",
                        title="Win Rate Compared to Average Nominee",
                        color_discrete_sequence=["#1f5aa6", "#e09f3e"],
                    )
                    fig_compare.update_layout(
                        xaxis_title="Category",
                        yaxis_title="Win Rate (%)",
                        legend_title="",
                    )
                    st.plotly_chart(fig_compare, width="stretch")
                else:
                    st.write("No category comparison available.")

                st.markdown("### Oscar Journey Over Time")
                journey_df = profile["journey_df"]
                if not journey_df.empty:
                    journey_long = journey_df.melt(
                        id_vars="Year",
                        value_vars=["Nominations", "Wins"],
                        var_name="Metric",
                        value_name="Count"
                    )
                    fig_journey = px.line(
                        journey_long,
                        x="Year",
                        y="Count",
                        color="Metric",
                        markers=True,
                        title="Nominations and Wins by Ceremony Year",
                        color_discrete_sequence=["#264653", "#d62828"],
                    )
                    fig_journey.update_layout(legend_title="")
                    st.plotly_chart(fig_journey, width="stretch")
                else:
                    st.write("No timeline data available.")


# @db_session
# def actors_with_most_nominations_zero_wins(limit=10):
#     stats = {}

#     for n in Nomination.select():
#         if not is_relevant_category(n.category.category):
#             continue

#         name = n.nominee_name
#         if name not in stats:
#             stats[name] = {"noms": 0, "wins": 0}

#         stats[name]["noms"] += 1
#         stats[name]["wins"] += int(n.winner)

#     result = [
#         (name, values["noms"])
#         for name, values in stats.items()
#         if values["wins"] == 0
#     ]

#     result.sort(key=lambda x: x[1], reverse=True)
#     return result[:limit]

# print("Actors/Directors with Most Nominations but No Wins:")
# with db_session:
#     print(actors_with_most_nominations_zero_wins())



# @db_session
# def longest_gap(limit=5):
#     stats = {}

#     for n in Nomination.select():
#         if not is_relevant_category(n.category.category):
#             continue

#         name = n.nominee_name
#         year = n.ceremony.year_ceremony

#         if name not in stats:
#             stats[name] = {"years": [], "wins": []}

#         stats[name]["years"].append(year)
#         if n.winner:
#             stats[name]["wins"].append(year)

#     result = []

#     for name, data in stats.items():
#         if data["wins"]:
#             first_nom = min(data["years"])
#             first_win = min(data["wins"])
#             gap = first_win - first_nom

#             if gap > 0:
#                 result.append((name, gap))

#     result.sort(key=lambda x: x[1], reverse=True)
#     return result[:limit]

# print("Longest Time from First Nomination to First Win:")
# print(longest_gap())


# @db_session
# def actor_director_overlap():
#     stats = {}

#     for n in Nomination.select():
#         cat = n.category.category.upper()
#         name = n.nominee_name

#         if name not in stats:
#             stats[name] = {"actor": False, "director": False}

#         if "ACTOR" in cat or "ACTRESS" in cat:
#             stats[name]["actor"] = True
#         if "DIRECTING" in cat:
#             stats[name]["director"] = True

#     result = [
#         name for name, v in stats.items()
#         if v["actor"] and v["director"]
#     ]

#     return result[:10]

# print("Individuals Nominated as Both Actor and Director:")
# print(actor_director_overlap())

