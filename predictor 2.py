from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from statistics import TeamForm, head_to_head_form, league_position, team_form


@dataclass(frozen=True)
class Scoreline:
    home_goals: int
    away_goals: int
    probability: float

    @property
    def label(self) -> str:
        return f"{self.home_goals}–{self.away_goals}"


@dataclass
class Prediction:
    predicted_home_goals: int
    predicted_away_goals: int
    home_win: float
    draw: float
    away_win: float
    over_25: float
    btts: float
    exact_score_probability: float
    home_xg: float
    away_xg: float
    data_quality: int
    explanation: list[str]
    top_scores: list[Scoreline]

    @property
    def score(self) -> str:
        return f"{self.predicted_home_goals}–{self.predicted_away_goals}"

    @property
    def result_label(self) -> str:
        probabilities = {
            "Home win": self.home_win,
            "Draw": self.draw,
            "Away win": self.away_win,
        }
        return max(probabilities, key=probabilities.get)

    @property
    def result_confidence(self) -> float:
        return max(self.home_win, self.draw, self.away_win)

    @property
    def goals_label(self) -> str:
        return "Over 2.5" if self.over_25 >= 50 else "Under 2.5"

    @property
    def goals_confidence(self) -> float:
        return self.over_25 if self.over_25 >= 50 else 100 - self.over_25

    @property
    def btts_label(self) -> str:
        return "BTTS Yes" if self.btts >= 50 else "BTTS No"

    @property
    def btts_confidence(self) -> float:
        return self.btts if self.btts >= 50 else 100 - self.btts


def _poisson(goals: int, expected_goals: float) -> float:
    return math.exp(-expected_goals) * expected_goals**goals / math.factorial(goals)


def _blend(primary: float, secondary: float, primary_weight: float = 0.65) -> float:
    return primary * primary_weight + secondary * (1.0 - primary_weight)


def _safe_attack(form: TeamForm, fallback: float) -> float:
    return form.goals_for_per_game if form.played >= 2 else fallback


def _safe_defence(form: TeamForm, fallback: float) -> float:
    return form.goals_against_per_game if form.played >= 2 else fallback


def build_prediction(
    fixture: dict[str, Any],
    completed_matches: list[dict[str, Any]],
    standings: list[dict[str, Any]],
) -> Prediction:
    home = fixture.get("homeTeam", {})
    away = fixture.get("awayTeam", {})
    home_id = home.get("id")
    away_id = away.get("id")

    home_recent = team_form(completed_matches, home_id, limit=8)
    away_recent = team_form(completed_matches, away_id, limit=8)
    home_venue = team_form(completed_matches, home_id, limit=6, venue="HOME")
    away_venue = team_form(completed_matches, away_id, limit=6, venue="AWAY")
    h2h = head_to_head_form(completed_matches, home_id, away_id, limit=5)

    league_home_goals = 1.45
    league_away_goals = 1.15

    home_attack = _blend(
        _safe_attack(home_venue, league_home_goals),
        _safe_attack(home_recent, league_home_goals),
    )
    away_defence = _blend(
        _safe_defence(away_venue, league_home_goals),
        _safe_defence(away_recent, league_home_goals),
    )
    away_attack = _blend(
        _safe_attack(away_venue, league_away_goals),
        _safe_attack(away_recent, league_away_goals),
    )
    home_defence = _blend(
        _safe_defence(home_venue, league_away_goals),
        _safe_defence(home_recent, league_away_goals),
    )

    home_xg = (home_attack + away_defence) / 2
    away_xg = (away_attack + home_defence) / 2

    home_position, league_size = league_position(standings, home_id)
    away_position, _ = league_position(standings, away_id)

    explanation: list[str] = []

    if home_recent.played:
        explanation.append(
            f"{home.get('shortName') or home.get('name')} form: "
            f"{home_recent.points} points from {home_recent.played} matches"
        )
    if away_recent.played:
        explanation.append(
            f"{away.get('shortName') or away.get('name')} form: "
            f"{away_recent.points} points from {away_recent.played} matches"
        )

    if home_position and away_position and league_size:
        position_gap = away_position - home_position
        position_adjustment = max(-0.18, min(0.18, position_gap * 0.012))
        home_xg += position_adjustment
        away_xg -= position_adjustment * 0.70
        explanation.append(
            f"League positions: {home_position}th versus {away_position}th"
        )

    if h2h.played >= 2:
        h2h_edge = (h2h.points_per_game - 1.35) * 0.08
        home_xg += h2h_edge
        away_xg -= h2h_edge * 0.5
        explanation.append(f"Head-to-head sample: {h2h.played} matches")

    home_xg = max(0.35, min(3.20, home_xg))
    away_xg = max(0.25, min(3.00, away_xg))

    home_win = draw = away_win = over_25 = btts = 0.0
    scores: list[tuple[float, int, int]] = []

    for home_goals in range(8):
        for away_goals in range(8):
            probability = _poisson(home_goals, home_xg) * _poisson(
                away_goals, away_xg
            )
            scores.append((probability, home_goals, away_goals))

            if home_goals > away_goals:
                home_win += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away_win += probability

            if home_goals + away_goals >= 3:
                over_25 += probability
            if home_goals and away_goals:
                btts += probability

    scores.sort(reverse=True)
    exact_probability, predicted_home, predicted_away = scores[0]
    top_scores = [
        Scoreline(home_goals=h, away_goals=a, probability=p * 100)
        for p, h, a in scores[:3]
    ]

    sample_score = min(
        100,
        round(
            (
                home_recent.played
                + away_recent.played
                + home_venue.played
                + away_venue.played
                + h2h.played
            )
            / 33
            * 100
        ),
    )

    if not explanation:
        explanation.append("Limited historical data; league averages were used.")

    return Prediction(
        predicted_home_goals=predicted_home,
        predicted_away_goals=predicted_away,
        home_win=home_win * 100,
        draw=draw * 100,
        away_win=away_win * 100,
        over_25=over_25 * 100,
        btts=btts * 100,
        exact_score_probability=exact_probability * 100,
        home_xg=home_xg,
        away_xg=away_xg,
        data_quality=sample_score,
        explanation=explanation,
        top_scores=top_scores,
    )
