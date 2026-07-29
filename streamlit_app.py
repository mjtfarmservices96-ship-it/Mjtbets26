import hashlib
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
import streamlit as st


st.set_page_config(
    page_title="MJ Bets 26",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 760px;
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }
    .match-card {
        border: 1px solid rgba(128,128,128,.28);
        border-radius: 16px;
        padding: 16px;
        margin: 12px 0;
        background: rgba(128,128,128,.06);
    }
    .competition {
        font-size: .82rem;
        opacity: .72;
        margin-bottom: 8px;
    }
    .fixture {
        font-size: 1.18rem;
        font-weight: 700;
        line-height: 1.35;
    }
    .kickoff {
        font-size: .9rem;
        opacity: .75;
        margin-top: 3px;
    }
    .score {
        font-size: 2rem;
        font-weight: 800;
        margin: 12px 0 4px 0;
    }
    .pick {
        font-size: 1rem;
        font-weight: 650;
        margin-bottom: 12px;
    }
    .stat-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
    }
    .stat {
        padding: 10px;
        border-radius: 11px;
        background: rgba(128,128,128,.10);
    }
    .stat-label {
        font-size: .76rem;
        opacity: .7;
    }
    .stat-value {
        font-size: 1.02rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚽ MJ Bets 26")
st.caption("Daily football score predictions and match analysis")


def get_api_key() -> str:
    try:
        return str(st.secrets["FOOTBALL_DATA_API_KEY"]).strip()
    except Exception:
        return ""


@st.cache_data(ttl=900, show_spinner=False)
def fetch_matches(api_key: str, selected_date: date) -> list[dict]:
    response = requests.get(
        "https://api.football-data.org/v4/matches",
        headers={"X-Auth-Token": api_key},
        params={
            "dateFrom": selected_date.isoformat(),
            "dateTo": selected_date.isoformat(),
        },
        timeout=20,
    )

    if response.status_code == 401:
        raise ValueError("The Football-Data.org API key is incorrect.")
    if response.status_code == 429:
        raise ValueError("The Football-Data.org request limit has been reached. Try again later.")

    response.raise_for_status()
    return response.json().get("matches", [])


def poisson_probability(goals: int, expected_goals: float) -> float:
    return (
        math.exp(-expected_goals)
        * expected_goals**goals
        / math.factorial(goals)
    )


def expected_goals(home_team: str, away_team: str) -> tuple[float, float]:
    # Stable placeholder estimate. This is not trained on form, injuries or bookmaker odds.
    seed_text = f"{home_team}-{away_team}"
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:8], 16)

    home_adjustment = ((seed % 41) - 20) / 100
    away_adjustment = (((seed // 41) % 41) - 20) / 100

    home_xg = max(0.65, min(2.40, 1.45 + home_adjustment))
    away_xg = max(0.55, min(2.20, 1.15 + away_adjustment))
    return home_xg, away_xg


def predict_match(home_team: str, away_team: str) -> dict:
    home_xg, away_xg = expected_goals(home_team, away_team)
    score_probabilities = []

    home_win = draw = away_win = over_25 = btts = 0.0

    for home_goals in range(8):
        for away_goals in range(8):
            probability = (
                poisson_probability(home_goals, home_xg)
                * poisson_probability(away_goals, away_xg)
            )
            score_probabilities.append((probability, home_goals, away_goals))

            if home_goals > away_goals:
                home_win += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away_win += probability

            if home_goals + away_goals >= 3:
                over_25 += probability
            if home_goals > 0 and away_goals > 0:
                btts += probability

    best_probability, predicted_home, predicted_away = max(score_probabilities)

    result_probabilities = {
        "Home win": home_win,
        "Draw": draw,
        "Away win": away_win,
    }
    predicted_result = max(result_probabilities, key=result_probabilities.get)

    return {
        "score": f"{predicted_home}–{predicted_away}",
        "result": predicted_result,
        "confidence": result_probabilities[predicted_result] * 100,
        "home_xg": home_xg,
        "away_xg": away_xg,
        "over_25": over_25 * 100,
        "btts": btts * 100,
        "score_probability": best_probability * 100,
    }


def uk_kickoff(utc_text: str) -> str:
    if not utc_text:
        return "Time unavailable"

    try:
        parsed = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local = parsed.astimezone(ZoneInfo("Europe/London"))
        return local.strftime("%H:%M UK")
    except (TypeError, ValueError):
        return "Time unavailable"


api_key = get_api_key()

with st.sidebar:
    st.header("Settings")
    selected_date = st.date_input(
        "Fixture date",
        value=date.today(),
        min_value=date.today() - timedelta(days=7),
        max_value=date.today() + timedelta(days=10),
    )
    minimum_confidence = st.slider(
        "Minimum result confidence",
        min_value=25,
        max_value=80,
        value=40,
        step=1,
    )
    show_all = st.toggle("Show every fixture", value=False)

    if st.button("Refresh fixtures", use_container_width=True):
        fetch_matches.clear()
        st.rerun()

    st.warning(
        "Predictions are estimates, not guaranteed outcomes. "
        "Only gamble what you can afford to lose."
    )

if not api_key:
    st.error("Football-Data.org API key has not been added.")
    st.code('FOOTBALL_DATA_API_KEY = "your-api-key"', language="toml")
    st.stop()

try:
    with st.spinner("Loading fixtures…"):
        matches = fetch_matches(api_key, selected_date)
except requests.RequestException as error:
    st.error(f"Could not load fixtures: {error}")
    st.stop()
except ValueError as error:
    st.error(str(error))
    st.stop()

if not matches:
    st.info(f"No supported fixtures found for {selected_date:%d %B %Y}.")
    st.stop()

predictions = []
for match in matches:
    home_team = match.get("homeTeam", {}).get("name", "Home team")
    away_team = match.get("awayTeam", {}).get("name", "Away team")
    prediction = predict_match(home_team, away_team)

    if not show_all and prediction["confidence"] < minimum_confidence:
        continue

    predictions.append(
        {
            "competition": match.get("competition", {}).get("name", "Competition"),
            "home": home_team,
            "away": away_team,
            "kickoff": uk_kickoff(match.get("utcDate", "")),
            "status": match.get("status", ""),
            **prediction,
        }
    )

if not predictions:
    st.info("No fixtures meet the selected confidence level. Lower the slider or turn on “Show every fixture”.")
    st.stop()

predictions.sort(key=lambda item: item["confidence"], reverse=True)

m1, m2, m3 = st.columns(3)
m1.metric("Fixtures", len(predictions))
m2.metric("Best", f"{predictions[0]['confidence']:.1f}%")
m3.metric(
    "Average",
    f"{sum(item['confidence'] for item in predictions) / len(predictions):.1f}%",
)

st.subheader(f"Predictions for {selected_date:%d %B}")

for item in predictions:
    st.markdown(
        f"""
        <div class="match-card">
            <div class="competition">{item['competition']}</div>
            <div class="fixture">{item['home']} v {item['away']}</div>
            <div class="kickoff">{item['kickoff']} · {item['status'].replace('_', ' ').title()}</div>
            <div class="score">{item['score']}</div>
            <div class="pick">{item['result']} · {item['confidence']:.1f}% confidence</div>
            <div class="stat-grid">
                <div class="stat">
                    <div class="stat-label">Expected goals</div>
                    <div class="stat-value">{item['home_xg']:.2f}–{item['away_xg']:.2f}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Exact-score chance</div>
                    <div class="stat-value">{item['score_probability']:.1f}%</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Over 2.5 goals</div>
                    <div class="stat-value">{item['over_25']:.1f}%</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Both teams score</div>
                    <div class="stat-value">{item['btts']:.1f}%</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.caption(
    "Current model: Poisson score estimates using placeholder expected-goal values. "
    "It does not yet use recent team form, injuries or bookmaker odds, so it should not be treated as a value-betting system."
)