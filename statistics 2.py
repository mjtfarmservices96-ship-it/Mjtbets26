from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


FINISHED_STATUSES = {"FINISHED", "AWARDED"}


@dataclass
class TeamForm:
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: float = 0.0
    goals_against: float = 0.0
    points: int = 0

    @property
    def goals_for_per_game(self) -> float:
        return self.goals_for / self.played if self.played else 0.0

    @property
    def goals_against_per_game(self) -> float:
        return self.goals_against / self.played if self.played else 0.0

    @property
    def points_per_game(self) -> float:
        return self.points / self.played if self.played else 0.0


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def final_score(match: dict[str, Any]) -> tuple[int, int] | None:
    full_time = match.get("score", {}).get("fullTime", {})
    home = full_time.get("home")
    away = full_time.get("away")

    if home is None or away is None:
        regular = match.get("score", {}).get("regularTime", {})
        home = regular.get("home")
        away = regular.get("away")

    if home is None or away is None:
        return None

    return int(home), int(away)


def completed_before(
    matches: list[dict[str, Any]],
    kickoff: datetime,
) -> list[dict[str, Any]]:
    output = []
    for match in matches:
        if match.get("status") not in FINISHED_STATUSES:
            continue
        score = final_score(match)
        utc_date = match.get("utcDate")
        if score is None or not utc_date:
            continue
        try:
            if parse_utc(utc_date) < kickoff:
                output.append(match)
        except ValueError:
            continue
    return output


def team_form(
    matches: list[dict[str, Any]],
    team_id: int,
    limit: int = 8,
    venue: str | None = None,
) -> TeamForm:
    relevant: list[dict[str, Any]] = []

    for match in matches:
        home_id = match.get("homeTeam", {}).get("id")
        away_id = match.get("awayTeam", {}).get("id")

        if venue == "HOME" and home_id != team_id:
            continue
        if venue == "AWAY" and away_id != team_id:
            continue
        if venue is None and team_id not in {home_id, away_id}:
            continue

        if final_score(match) is not None:
            relevant.append(match)

    relevant.sort(
        key=lambda item: item.get("utcDate", ""),
        reverse=True,
    )
    relevant = relevant[:limit]

    form = TeamForm()
    for match in relevant:
        score = final_score(match)
        if score is None:
            continue

        home_goals, away_goals = score
        is_home = match.get("homeTeam", {}).get("id") == team_id
        goals_for = home_goals if is_home else away_goals
        goals_against = away_goals if is_home else home_goals

        form.played += 1
        form.goals_for += goals_for
        form.goals_against += goals_against

        if goals_for > goals_against:
            form.wins += 1
            form.points += 3
        elif goals_for == goals_against:
            form.draws += 1
            form.points += 1
        else:
            form.losses += 1

    return form


def league_position(
    standings: list[dict[str, Any]],
    team_id: int,
) -> tuple[int | None, int | None]:
    for standing in standings:
        if standing.get("type") != "TOTAL":
            continue
        table = standing.get("table", [])
        for row in table:
            if row.get("team", {}).get("id") == team_id:
                return row.get("position"), len(table)
    return None, None


def head_to_head_form(
    matches: list[dict[str, Any]],
    home_team_id: int,
    away_team_id: int,
    limit: int = 5,
) -> TeamForm:
    meetings = []
    pair = {home_team_id, away_team_id}

    for match in matches:
        teams = {
            match.get("homeTeam", {}).get("id"),
            match.get("awayTeam", {}).get("id"),
        }
        if teams == pair and final_score(match) is not None:
            meetings.append(match)

    meetings.sort(key=lambda item: item.get("utcDate", ""), reverse=True)
    return team_form(meetings[:limit], home_team_id, limit=limit)
