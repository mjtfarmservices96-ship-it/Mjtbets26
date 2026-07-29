from __future__ import annotations

from datetime import date
from typing import Any

import requests


BASE_URL = "https://api.football-data.org/v4"


class FootballDataError(RuntimeError):
    pass


class FootballDataClient:
    def __init__(self, api_key: str, timeout: int = 25) -> None:
        if not api_key:
            raise ValueError("A Football-Data.org API key is required.")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"X-Auth-Token": api_key})

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(
            f"{BASE_URL}{path}",
            params=params or {},
            timeout=self.timeout,
        )

        if response.status_code == 401:
            raise FootballDataError("The Football-Data.org API key is invalid.")
        if response.status_code == 403:
            raise FootballDataError(
                "Your Football-Data.org plan does not include this resource."
            )
        if response.status_code == 429:
            raise FootballDataError(
                "The Football-Data.org request limit has been reached. Try again later."
            )

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise FootballDataError(
                f"Football-Data.org returned HTTP {response.status_code}."
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise FootballDataError("Football-Data.org returned invalid JSON.") from exc

    def matches_for_date(self, selected_date: date) -> list[dict[str, Any]]:
        data = self._get(
            "/matches",
            {
                "dateFrom": selected_date.isoformat(),
                "dateTo": selected_date.isoformat(),
            },
        )
        return data.get("matches", [])

    def competition_matches(
        self,
        competition_code_or_id: str | int,
        season_start_year: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if season_start_year is not None:
            params["season"] = season_start_year

        data = self._get(
            f"/competitions/{competition_code_or_id}/matches",
            params,
        )
        return data.get("matches", [])

    def standings(
        self,
        competition_code_or_id: str | int,
        season_start_year: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if season_start_year is not None:
            params["season"] = season_start_year

        data = self._get(
            f"/competitions/{competition_code_or_id}/standings",
            params,
        )
        return data.get("standings", [])
