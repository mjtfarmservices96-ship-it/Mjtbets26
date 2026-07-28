import hashlib
import math
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="MJ Bets 26",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ MJ Bets 26")
st.caption("Daily football score predictions and match analysis")


def get_api_key():
    try:
        return st.secrets["FOOTBALL_DATA_API_KEY"]
    except Exception:
        return ""


def fetch_matches(api_key, selected_date):
    url = "https://api.football-data.org/v4/matches"

    headers = {
        "X-Auth-Token": api_key
    }

    params = {
        "dateFrom": selected_date.isoformat(),
        "dateTo": selected_date.isoformat(),
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=20,
    )

    if response.status_code == 401:
        raise ValueError("The Football-Data.org API key is incorrect.")

    if response.status_code == 429:
        raise ValueError("API request limit reached. Try again later.")

    response.raise_for_status()

    return response.json().get("matches", [])


def poisson_probability(goals, expected_goals):
    return (
        math.exp(-expected_goals)
        * expected_goals**goals
        / math.factorial(goals)
    )


def expected_goals(home_team, away_team):
    seed_text = f"{home_team}-{away_team}"
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:8], 16)

    home_adjustment = ((seed % 41) - 20) / 100
    away_adjustment = (((seed // 41) % 41) - 20) / 100

    home_xg = max(0.65, min(2.40, 1.45 + home_adjustment))
    away_xg = max(0.55, min(2.20, 1.15 + away_adjustment))

    return home_xg, away_xg


def predict_match(home_team, away_team):
    home_xg, away_xg = expected_goals(home_team, away_team)

    score_probabilities = []
    home_win = 0
    draw = 0
    away_win = 0
    over_25 = 0
    btts = 0

    for home_goals in range(7):
        for away_goals in range(7):
            probability = (
                poisson_probability(home_goals, home_xg)
                * poisson_probability(away_goals, away_xg)
            )

            score_probabilities.append(
                (probability, home_goals, away_goals)
            )

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

    score_probabilities.sort(reverse=True)

    best_probability, predicted_home, predicted_away = score_probabilities[0]

    result_probabilities = {
        "Home win": home_win,
        "Draw": draw,
        "Away win": away_win,
    }

    predicted_result = max(
        result_probabilities,
        key=result_probabilities.get,
    )

    confidence = result_probabilities[predicted_result]

    return {
        "prediction": f"{predicted_home}-{predicted_away}",
        "result": predicted_result,
        "confidence": confidence,
        "home_xg": home_xg,
        "away_xg": away_xg,
        "over_25": over_25,
        "btts": btts,
        "score_probability": best_probability,
    }


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
        "Minimum confidence",
        min_value=25,
        max_value=80,
        value=40,
        step=1,
    )

    st.warning(
        "Predictions are estimates, not guaranteed betting outcomes. "
        "Only gamble what you can afford to lose."
    )


if not api_key:
    st.error("Football-Data.org API key has not been added.")
    st.info(
        "Open your Streamlit app settings, select Secrets, and add:\n\n"
        'FOOTBALL_DATA_API_KEY = "your-api-key"'
    )
    st.stop()


try:
    with st.spinner("Loading fixtures..."):
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


rows = []

for match in matches:
    home_team = match.get("homeTeam", {}).get("name", "Home team")
    away_team = match.get("awayTeam", {}).get("name", "Away team")
    competition = match.get("competition", {}).get("name", "Competition")
    kickoff = match.get("utcDate", "")
    status = match.get("status", "")

    prediction = predict_match(home_team, away_team)

    if prediction["confidence"] * 100 < minimum_confidence:
        continue

    rows.append(
        {
            "Competition": competition,
            "Kick-off": kickoff[11:16] if len(kickoff) >= 16 else "",
            "Home": home_team,
            "Away": away_team,
            "Correct score": prediction["prediction"],
            "Main prediction": prediction["result"],
            "Confidence": round(prediction["confidence"] * 100, 1),
            "Home xG": round(prediction["home_xg"], 2),
            "Away xG": round(prediction["away_xg"], 2),
            "Over 2.5": round(prediction["over_25"] * 100, 1),
            "BTTS": round(prediction["btts"] * 100, 1),
            "Status": status,
        }
    )


if not rows:
    st.info("No fixtures meet your selected confidence level.")
    st.stop()


results = pd.DataFrame(rows)
results = results.sort_values("Confidence", ascending=False)

col1, col2, col3 = st.columns(3)

col1.metric("Fixtures analysed", len(results))
col2.metric(
    "Highest confidence",
    f"{results['Confidence'].max():.1f}%",
)
col3.metric(
    "Average confidence",
    f"{results['Confidence'].mean():.1f}%",
)

st.subheader("Today's predictions")

st.dataframe(
    results,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Confidence": st.column_config.ProgressColumn(
            "Confidence",
            min_value=0,
            max_value=100,
            format="%.1f%%",
        ),
        "Over 2.5": st.column_config.NumberColumn(
            "Over 2.5",
            format="%.1f%%",
        ),
        "BTTS": st.column_config.NumberColumn(
            "BTTS",
            format="%.1f%%",
        ),
    },
)

st.subheader("Strongest selections")

strongest = results.head(5)

for _, row in strongest.iterrows():
    with st.expander(
        f"{row['Home']} v {row['Away']} — {row['Correct score']}"
    ):
        st.write(f"**Competition:** {row['Competition']}")
        st.write(f"**Main prediction:** {row['Main prediction']}")
        st.write(f"**Correct-score estimate:** {row['Correct score']}")
        st.write(f"**Confidence:** {row['Confidence']}%")
        st.write(f"**Expected goals:** {row['Home xG']}–{row['Away xG']}")
        st.write(f"**Over 2.5 probability:** {row['Over 2.5']}%")
        st.write(f"**Both teams to score:** {row['BTTS']}%")

st.caption(
    "This first version uses a Poisson probability model. "
    "It does not guarantee profit or identify bookmaker value without odds data."
)