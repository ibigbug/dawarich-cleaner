"""
Dawarich API client for fetching and managing location points
"""

import json
from js import fetch, Object, JSON
from datetime import datetime
import json
import pytz


class DawarichClient:
    """Client for interacting with Dawarich API"""

    def __init__(self, base_url, api_key):
        """
        Initialize Dawarich API client

        Args:
            base_url: Base URL of Dawarich instance (e.g., https://dawarich.example.com)
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def fetch_points(self, start_date, end_date, timezone="UTC"):
        """
        Fetch location points for a date range

        Args:
            start_date: Start date in local time (ISO format: YYYY-MM-DD)
            end_date: End date in local time (ISO format: YYYY-MM-DD)
            timezone: IANA timezone name (e.g., "America/Los_Angeles")

        Returns:
            List of point dictionaries
        """

        # Get timezone object
        tz = pytz.timezone(timezone)

        # Parse dates and localize to timezone
        start_dt = datetime.strptime(f"{start_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
        start_dt = tz.localize(start_dt)

        end_dt = datetime.strptime(f"{end_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
        end_dt = tz.localize(end_dt)

        # Convert to ISO format strings
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()

        # Fetch all pages of points
        all_points = []
        page = 1
        per_page = 1000  # Max per page

        while True:
            url = f"{self.base_url}/api/v1/points"
            params = f"?start_at={start_iso}&end_at={end_iso}&page={page}&per_page={per_page}&api_key={self.api_key}"

            options = Object.fromEntries(
                [
                    ["method", "GET"],
                    ["headers", Object.fromEntries(list(self.headers.items()))],
                ]
            )

            full_url = f"{url}{params}"
            print(f"Fetching page {page} from: {full_url}")

            response = await fetch(full_url, options)

            print(f"Response status: {response.status}")

            if not response.ok:
                error_text = await response.text()
                raise Exception(
                    f"Failed to fetch points: {response.status} - {error_text}"
                )

            data = await response.json()

            try:
                data_str = JSON.stringify(data)
                data_python = json.loads(data_str)

                if isinstance(data_python, list):
                    points = data_python
                elif isinstance(data_python, dict):
                    points = data_python.get("points", [])
                else:
                    points = []
            except Exception as e:
                print(f"Error converting response: {e}")
                if hasattr(data, "points"):
                    points = list(data.points)
                else:
                    points = []

            if not points:
                break

            all_points.extend(points)
            print(f"Fetched {len(points)} points (total so far: {len(all_points)})")

            # If we got fewer points than per_page, we've reached the end
            if len(points) < per_page:
                break

            page += 1

        print(f"Total points fetched: {len(all_points)}")
        return all_points

    async def delete_points(self, point_ids):
        """
        Delete multiple points by ID

        Args:
            point_ids: List of point IDs to delete

        Returns:
            Response data with count of deleted points
        """

        url = f"{self.base_url}/api/v1/points/bulk_destroy?api_key={self.api_key}"

        options = Object.fromEntries(
            [
                ["method", "DELETE"],
                ["headers", Object.fromEntries(list(self.headers.items()))],
                ["body", json.dumps({"point_ids": point_ids})],
            ]
        )

        response = await fetch(url, options)

        if not response.ok:
            error_text = await response.text()
            raise Exception(
                f"Failed to delete points: {response.status} - {error_text}"
            )

        return await response.json()

    async def get_point(self, point_id):
        """
        Get a single point by ID

        Args:
            point_id: Point ID

        Returns:
            Point dictionary
        """

        url = f"{self.base_url}/api/v1/points/{point_id}?api_key={self.api_key}"

        options = Object.fromEntries(
            [
                ["method", "GET"],
                ["headers", Object.fromEntries(list(self.headers.items()))],
            ]
        )

        response = await fetch(url, options)

        if not response.ok:
            error_text = await response.text()
            raise Exception(f"Failed to fetch point: {response.status} - {error_text}")

        data = await response.json()
        return data.get("point", {})

    async def restore_points(self, points_data):
        """
        Restore (re-create) points in Dawarich

        Args:
            points_data: List of point dictionaries with lat, lon, timestamp, etc.

        Returns:
            Response data
        """

        url = f"{self.base_url}/api/v1/points/bulk_create?api_key={self.api_key}"

        # Format points for Dawarich API
        formatted_points = []
        for point in points_data:
            formatted_points.append(
                {
                    "latitude": point["latitude"],
                    "longitude": point["longitude"],
                    "timestamp": point["timestamp"],
                    "battery": point.get("battery", 100),
                    "accuracy": point.get("accuracy", 10),
                }
            )

        options = Object.fromEntries(
            [
                ["method", "POST"],
                ["headers", Object.fromEntries(list(self.headers.items()))],
                ["body", json.dumps({"points": formatted_points})],
            ]
        )

        response = await fetch(url, options)

        if not response.ok:
            error_text = await response.text()
            raise Exception(
                f"Failed to restore points: {response.status} - {error_text}"
            )

        return await response.json()
