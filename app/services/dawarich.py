"""Dawarich API client service"""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytz


class DawarichService:
    """Service for interacting with Dawarich API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def fetch_points_range(
        self,
        start_ts: int,
        end_ts: int,
        *,
        anomalies_only: bool = False,
        per_page: int = 1000,
    ) -> list[dict[str, Any]]:
        """Fetch points using Unix timestamp range.

        Dawarich accepts either Unix timestamps or ISO8601 strings for `start_at`/`end_at`.

        Notes:
        - The API can only return either "anomaly" or "not_anomaly" points per request.
          To get both, call twice (anomalies_only=True/False) and merge by id.
        """
        all_points: list[dict[str, Any]] = []
        page = 1

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                url = f"{self.base_url}/api/v1/points"
                params = {
                    "start_at": int(start_ts),
                    "end_at": int(end_ts),
                    "page": page,
                    "per_page": per_page,
                    "api_key": self.api_key,
                }
                if anomalies_only:
                    params["anomalies_only"] = "true"

                response = await client.get(url, params=params, headers=self.headers)

                if response.status_code != 200:
                    raise Exception(
                        f"Failed to fetch points: {response.status_code} - {response.text}"
                    )

                data = response.json()

                if isinstance(data, list):
                    points = data
                elif isinstance(data, dict):
                    points = data.get("points", [])
                else:
                    points = []

                if not points:
                    break

                all_points.extend(points)

                if len(points) < per_page:
                    break

                page += 1

        return all_points

    async def fetch_points_range_all(
        self,
        start_ts: int,
        end_ts: int,
        *,
        per_page: int = 1000,
    ) -> list[dict[str, Any]]:
        """Fetch points (both anomaly and non-anomaly) for a Unix timestamp range."""
        non_anomaly = await self.fetch_points_range(
            start_ts,
            end_ts,
            anomalies_only=False,
            per_page=per_page,
        )
        anomaly = await self.fetch_points_range(
            start_ts,
            end_ts,
            anomalies_only=True,
            per_page=per_page,
        )

        merged: dict[int, dict[str, Any]] = {}
        for p in non_anomaly + anomaly:
            try:
                merged[int(p.get("id"))] = p
            except Exception:
                continue

        return list(merged.values())

    async def fetch_track_points(
        self,
        track_id: int,
        *,
        page: int | None = None,
        per_page: int = 1000,
    ) -> list[dict[str, Any]]:
        """Fetch points for a given track."""
        url = f"{self.base_url}/api/v1/tracks/{int(track_id)}/points"
        params: dict[str, Any] = {"api_key": self.api_key}
        if page is not None:
            params["page"] = int(page)
            params["per_page"] = int(per_page)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=self.headers)

            if response.status_code != 200:
                raise Exception(
                    f"Failed to fetch track points: {response.status_code} - {response.text}"
                )

            data = response.json()
            if not isinstance(data, list):
                return []
            return data

    async def update_point_location(self, point_id: int, latitude: float, longitude: float) -> dict[str, Any]:
        """Update a point's location.

        Dawarich enqueues track recalculation on point update when the point has track_id.
        We use this as a best-effort way to force track recalculation after bulk deletes.
        """
        url = f"{self.base_url}/api/v1/points/{int(point_id)}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.patch(
                url,
                params={"api_key": self.api_key},
                headers=self.headers,
                json={"point": {"latitude": latitude, "longitude": longitude}},
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to update point: {response.status_code} - {response.text}"
                )

            return response.json()

    def _parse_datetime(self, date_str: str, timezone: str, is_end: bool = False) -> datetime:
        """Parse datetime string in various formats.

        Args:
            date_str: Date/datetime string in various formats
            timezone: Timezone for naive datetimes
            is_end: If True and date-only, use 23:59:59; otherwise 00:00:00

        Returns:
            Timezone-aware datetime
        """
        # Try ISO format with timezone first (e.g., "2024-01-15T14:30:00+00:00" or "Z")
        if "T" in date_str and ("+" in date_str or "-" in date_str[11:] or date_str.endswith("Z")):
            # Already has timezone info - parse as ISO
            dt_str = date_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)

        tz = pytz.timezone(timezone)

        # Date only: "YYYY-MM-DD"
        if len(date_str) == 10:
            time_suffix = "23:59:59" if is_end else "00:00:00"
            dt = datetime.strptime(f"{date_str} {time_suffix}", "%Y-%m-%d %H:%M:%S")
            return tz.localize(dt)

        # Datetime without timezone: "YYYY-MM-DD HH:MM:SS"
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return tz.localize(dt)

    async def fetch_points(
        self, start_date: str, end_date: str, timezone: str = "UTC"
    ) -> list[dict[str, Any]]:
        """Fetch location points for a date range.

        Args:
            start_date: One of:
                - "YYYY-MM-DD" (date only, uses 00:00:00 in given timezone)
                - "YYYY-MM-DD HH:MM:SS" (datetime, interpreted in given timezone)
                - ISO format with timezone (e.g., "2024-01-15T00:00:00+00:00")
            end_date: Same formats as start_date (date only uses 23:59:59)
            timezone: Timezone name for interpreting naive dates (ignored if ISO format with tz)
        """
        start_dt = self._parse_datetime(start_date, timezone, is_end=False)
        end_dt = self._parse_datetime(end_date, timezone, is_end=True)

        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()

        all_points = []
        page = 1
        per_page = 1000

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                url = f"{self.base_url}/api/v1/points"
                params = {
                    "start_at": start_iso,
                    "end_at": end_iso,
                    "page": page,
                    "per_page": per_page,
                    "api_key": self.api_key,
                }

                response = await client.get(url, params=params, headers=self.headers)

                if response.status_code != 200:
                    raise Exception(
                        f"Failed to fetch points: {response.status_code} - {response.text}"
                    )

                data = response.json()

                if isinstance(data, list):
                    points = data
                elif isinstance(data, dict):
                    points = data.get("points", [])
                else:
                    points = []

                if not points:
                    break

                all_points.extend(points)

                if len(points) < per_page:
                    break

                page += 1

        return all_points

    async def delete_points(self, point_ids: list[int]) -> dict[str, Any]:
        """Delete multiple points by ID"""
        url = f"{self.base_url}/api/v1/points/bulk_destroy"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                "DELETE",
                url,
                params={"api_key": self.api_key},
                headers=self.headers,
                json={"point_ids": point_ids},
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to delete points: {response.status_code} - {response.text}"
                )

            return response.json()

    async def reimport_points(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        """Re-import points by creating them via POST /api/v1/points

        Args:
            points: List of point dicts with latitude, longitude, timestamp

        Returns:
            Dict with created point data
        """
        # Convert to GeoJSON format expected by Dawarich
        locations = [
            {
                "geometry": {
                    "type": "Point",
                    "coordinates": [point["longitude"], point["latitude"]],
                },
                "properties": {
                    # Convert Unix timestamp to ISO8601 string
                    # Handle both seconds and milliseconds timestamps
                    "timestamp": (
                        datetime.fromtimestamp(
                            (
                                point["timestamp"] / 1000
                                if point["timestamp"] > 100_000_000_000
                                else point["timestamp"]
                            ),
                            tz=UTC,
                        ).isoformat()
                    )
                },
            }
            for point in points
        ]

        url = f"{self.base_url}/api/v1/points"
        params = {"api_key": self.api_key}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                params=params,
                headers=self.headers,
                json={"locations": locations},
            )

            if response.status_code not in [200, 201]:
                raise Exception(
                    f"Failed to reimport points: {response.status_code} - {response.text}"
                )

            return response.json()
