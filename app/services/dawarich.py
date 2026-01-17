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

    async def fetch_points(
        self, start_date: str, end_date: str, timezone: str = "UTC"
    ) -> list[dict[str, Any]]:
        """Fetch location points for a date range"""
        tz = pytz.timezone(timezone)

        start_dt = datetime.strptime(f"{start_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
        start_dt = tz.localize(start_dt)

        end_dt = datetime.strptime(f"{end_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
        end_dt = tz.localize(end_dt)

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
