from __future__ import annotations

from datetime import date, timedelta
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

from football_api import FootballDataClient, FootballDataError
from predictor import Prediction, build_prediction
from statistics import completed_before, parse_utc


st.set_page_config(
    page_title="MJ Bets 26 Pro",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container{max-width:820px;padding-top:.8rem;padding-bottom:4rem}
    h1{letter-spacing:-1px}.app-subtitle{opacity:.72;margin-top:-10px;margin-bottom:18px}
    .hero{padding:20px;border-radius:22px;margin:10px 0 20px;
      background:linear-gradient(135deg,rgba(21,138,76,.28),rgba(15,23,42,.55));
      border:1px solid rgba(83,224,139,.28)}
    .hero-kicker{font-size:.78rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;opacity:.8}
    .hero-fixture{font-size:1.35rem;font-weight:850;line-height:1.3;margin:7px 0}
    .hero-pick{font-size:1.05rem;font-weight:750}.hero-note{font-size:.8rem;opacity:.72;margin-top:8px}
    .match-card{border:1px solid rgba(128,128,128,.28);border-radius:20px;
      padding:18px;margin:14px 0;background:rgba(128,128,128,.055)}
    .competition{font-size:.8rem;opacity:.68;margin-bottom:8px}.fixture{font-size:1.15rem;font-weight:800;line-height:1.35}
    .kickoff{font-size:.86rem;opacity:.7;margin-top:4px}.score{font-size:2.25rem;font-weight:900;margin:13px 0 1px}
    .pick{font-size:1rem;font-weight:760;margin-bottom:8px}.confidence-wrap{margin:10px 0 14px}
    .confidence-track{height:9px;background:rgba(128,128,128,.2);border-radius:99px;overflow:hidden}
    .confidence-fill{height:100%;background:linear-gradient(90deg,#ffb020,#32d583);border-radius:99px}
    .stat-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
    .stat{padding:11px;border-radius:12px;background:rgba(128,128,128,.10)}
    .stat-label{font-size:.72rem;opacity:.66}.stat-value{font-size:.98rem;font-weight:760;margin-top:2px}
    .scores{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:9px}
    .score-chip{text-align:center;padding:9px;border-radius:11px;background:rgba(50,213,131,.09);border:1px solid rgba(50,213,131,.18)}
    .score-chip strong{display:block;font-size:1.02rem}.score-chip span{font-size:.72rem;opacity:.68}
    .quality{font-size:.76rem;opacity:.67;margin:11px 0 0}.badge{display:inline-block;padding:4px 9px;border-radius:99px;
      font-size:.72rem;font-weight:800;background:rgba(50,213,131,.12);border:1px solid rgba(50,213,131,.22)}
    @media(max-width:520px){.block-container{padding-left:1rem;padding-right:1rem}.stat-grid{grid-template-columns:1fr 1fr}.hero{padding:17px}}
    </style>
    """,
    unsafe_allow_html=True,
)


def secret(name: str) -> str:
    try:
        return str(st.secrets[name]).strip()
    except Exception:
        return ""


@st.cache_data(ttl=900, show_spinner=False)
def get_fixtures(api_key: str, selected_date: date):
    return FootballDataClient(api_key).matches_for_date(selected_date)


@st.cache_data(ttl=3600, show_spinner=False)
def get_competition_data(api_key: str, identifier: str, season_year: int | None):
    client = FootballDataClient(api_key)
    matches = client.competition_matches(identifier, season_year)
    try:
        standings = client.standings(identifier, season_year)
    except FootballDataError:
        standings = []
    return matches, standings


def uk_time(utc_value: str) -> str:
    try:
        return parse_utc(utc_value).astimezone(ZoneInfo("Europe/London")).strftime("%H:%M UK")
    except (ValueError, TypeError):
        return "Time unavailable"


def competition_identifier(fixture: dict) -> str:
    competition = fixture.get("competition", {})
    return str(competition.get("code") or competition.get("id"))


def season_year(fixture: dict) -> int | None:
    start_date = fixture.get("season", {}).get("startDate")
    try:
        return int(start_date[:4]) if start_date else None
    except (TypeError, ValueError):
        return None


def accumulator_pick(prediction: Prediction) -> tuple[str, float]:
    options = [
        (prediction.result_label, prediction.result_confidence),
        (prediction.goals_label, prediction.goals_confidence),
        (prediction.btts_label, prediction.btts_confidence),
    ]
    return max(options, key=lambda item: item[1])


def fixture_name(fixture: dict) -> str:
    home = fixture.get("homeTeam", {}).get("name", "Home team")
    away = fixture.get("awayTeam", {}).get("name", "Away team")
    return f"{home} v {away}"


st.title("⚽ MJ Bets 26 Pro")
st.markdown('<div class="app-subtitle">Daily football score predictions and match analysis</div>', unsafe_allow_html=True)

api_key = secret("FOOTBALL_DATA_API_KEY")

with st.sidebar:
    st.header("Settings")
    selected_date = st.date_input(
        "Fixture date", value=date.today(),
        min_value=date.today() - timedelta(days=3),
        max_value=date.today() + timedelta(days=10),
    )
    minimum_confidence = st.slider("Minimum result confidence", 30, 75, 40, 1)
    minimum_data_quality = st.slider("Minimum data quality", 0, 100, 20, 5)
    maximum_fixtures = st.slider("Maximum fixtures analysed", 3, 20, 10, 1)
    include_postponed = st.toggle("Include postponed fixtures", value=False)
    show_accumulator = st.toggle("Show accumulator builder", value=True)

    if st.button("Refresh data", use_container_width=True):
        get_fixtures.clear(); get_competition_data.clear(); st.rerun()

    st.warning("Predictions are statistical estimates, not guaranteed outcomes. Never chase losses and only gamble what you can afford to lose.")

if not api_key:
    st.error("Add your Football-Data.org key in Streamlit Secrets.")
    st.code('FOOTBALL_DATA_API_KEY = "your-api-key"', language="toml")
    st.stop()

try:
    fixtures = get_fixtures(api_key, selected_date)
except FootballDataError as exc:
    st.error(str(exc)); st.stop()

if not include_postponed:
    fixtures = [f for f in fixtures if f.get("status") not in {"POSTPONED", "CANCELLED", "SUSPENDED"}]
fixtures = fixtures[:maximum_fixtures]

if not fixtures:
    st.info(f"No supported fixtures found for {selected_date:%d %B %Y}."); st.stop()

competition_cache: dict[tuple[str, int | None], tuple[list, list]] = {}
predictions: list[tuple[dict, Prediction]] = []
errors: list[str] = []

with st.spinner("Analysing form, venue performance and league data…"):
    for fixture in fixtures:
        identifier = competition_identifier(fixture)
        season = season_year(fixture)
        cache_key = (identifier, season)
        try:
            if cache_key not in competition_cache:
                competition_cache[cache_key] = get_competition_data(api_key, identifier, season)
            season_matches, standings = competition_cache[cache_key]
            kickoff = parse_utc(fixture.get("utcDate", ""))
            history = completed_before(season_matches, kickoff)
            prediction = build_prediction(fixture, history, standings)
            if prediction.result_confidence >= minimum_confidence and prediction.data_quality >= minimum_data_quality:
                predictions.append((fixture, prediction))
        except (FootballDataError, ValueError) as exc:
            errors.append(f"{identifier}: {exc}")

if not predictions:
    st.info("No fixtures meet your filters. Lower the confidence or data-quality sliders in Settings.")
    if errors:
        with st.expander("Data-source messages"):
            for message in sorted(set(errors)): st.write(message)
    st.stop()

predictions.sort(key=lambda item: (item[1].result_confidence, item[1].data_quality), reverse=True)

m1, m2, m3 = st.columns(3)
m1.metric("Fixtures", len(predictions))
m2.metric("Best", f"{predictions[0][1].result_confidence:.1f}%")
m3.metric("Average", f"{sum(p.result_confidence for _, p in predictions)/len(predictions):.1f}%")

best_fixture, best_prediction = predictions[0]
st.markdown(
    f'''<div class="hero"><div class="hero-kicker">⭐ Bet of the day</div>
    <div class="hero-fixture">{escape(fixture_name(best_fixture))}</div>
    <div class="hero-pick">{escape(best_prediction.result_label)} · {best_prediction.result_confidence:.1f}% model probability</div>
    <div class="hero-note">Correct-score lean: {best_prediction.score} · Data quality {best_prediction.data_quality}%</div></div>''',
    unsafe_allow_html=True,
)

if show_accumulator:
    acca = []
    combined = 1.0
    for fixture, prediction in predictions[:4]:
        pick, confidence = accumulator_pick(prediction)
        if confidence >= 55:
            acca.append((fixture_name(fixture), pick, confidence))
            combined *= confidence / 100
    if len(acca) >= 2:
        with st.expander("🔥 Model accumulator builder", expanded=False):
            for name, pick, confidence in acca:
                st.write(f"**{name}** — {pick} ({confidence:.1f}%)")
            st.caption(f"Combined model probability: {combined*100:.1f}%. This is not bookmaker value and is not a guarantee.")

st.subheader(f"Predictions for {selected_date:%d %B}")

for fixture, prediction in predictions:
    home = fixture.get("homeTeam", {}).get("name", "Home team")
    away = fixture.get("awayTeam", {}).get("name", "Away team")
    competition = fixture.get("competition", {}).get("name", "Competition")
    status = fixture.get("status", "").replace("_", " ").title()
    chips = "".join(
        f'<div class="score-chip"><strong>{score.label}</strong><span>{score.probability:.1f}%</span></div>'
        for score in prediction.top_scores
    )
    st.markdown(
        f'''<div class="match-card">
        <div class="competition">{escape(competition)}</div><div class="fixture">{escape(home)} v {escape(away)}</div>
        <div class="kickoff">{uk_time(fixture.get('utcDate',''))} · {escape(status)}</div>
        <div class="score">{prediction.score}</div><div class="pick">{prediction.result_label} · {prediction.result_confidence:.1f}%</div>
        <div class="confidence-wrap"><div class="confidence-track"><div class="confidence-fill" style="width:{min(prediction.result_confidence,100):.1f}%"></div></div></div>
        <div class="stat-grid">
          <div class="stat"><div class="stat-label">Home / Draw / Away</div><div class="stat-value">{prediction.home_win:.0f}% / {prediction.draw:.0f}% / {prediction.away_win:.0f}%</div></div>
          <div class="stat"><div class="stat-label">Expected goals</div><div class="stat-value">{prediction.home_xg:.2f}–{prediction.away_xg:.2f}</div></div>
          <div class="stat"><div class="stat-label">Goals market</div><div class="stat-value">{prediction.goals_label} · {prediction.goals_confidence:.1f}%</div></div>
          <div class="stat"><div class="stat-label">Both teams score</div><div class="stat-value">{prediction.btts_label} · {prediction.btts_confidence:.1f}%</div></div>
        </div><div class="quality"><span class="badge">Data quality {prediction.data_quality}%</span></div>
        <div class="quality">Top three correct scores</div><div class="scores">{chips}</div></div>''',
        unsafe_allow_html=True,
    )
    with st.expander(f"Why the model chose {prediction.result_label.lower()}"):
        for reason in prediction.explanation: st.write(f"• {reason}")

if errors:
    with st.expander("Some competitions could not be fully analysed"):
        for message in sorted(set(errors)): st.write(message)

st.caption("MJ Bets 26 Pro v4 uses recent completed matches, home/away form, standings, available head-to-head data and a Poisson score model. Coverage depends on your Football-Data.org plan.")
