"""Dawarich API client service"""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytz


class DawarichService:
    """Service for interacting with Dawarich API"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

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
