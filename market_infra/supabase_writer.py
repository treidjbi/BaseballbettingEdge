from __future__ import annotations

import sys
import time

import requests


TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class SupabaseMarketWriter:
    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key

    def _headers(self, prefer: str) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    def insert_rows(self, table: str, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        response = requests.post(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("return=representation"),
            json=rows,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def select_rows(self, table: str, params: dict[str, str]) -> list[dict]:
        response = self._select_response_with_retries(table, params)
        return response.json()

    def _select_response_with_retries(
        self,
        table: str,
        params: dict[str, str],
        *,
        attempts: int = 3,
        base_delay_seconds: float = 0.5,
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            response = None
            try:
                response = requests.get(
                    f"{self.supabase_url}/rest/v1/{table}",
                    headers=self._headers("return=representation"),
                    params=params,
                    timeout=20,
                )
                response.raise_for_status()
                return response
            except requests.RequestException as error:
                last_error = error
                status_code = _status_code_from_error(error, response)
                if attempt >= attempts or status_code not in TRANSIENT_STATUS_CODES:
                    raise
                delay = base_delay_seconds * attempt
                print(
                    "Warning: Supabase select_rows transient failure "
                    f"table={table} status={status_code}; retrying attempt {attempt + 1}/{attempts}",
                    file=sys.stderr,
                )
                time.sleep(delay)

        raise RuntimeError(f"Supabase select_rows failed after {attempts} attempts") from last_error

    def upsert_rows(self, table: str, rows: list[dict], on_conflict: str) -> list[dict]:
        if not rows:
            return []
        response = requests.post(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("resolution=merge-duplicates,return=representation"),
            params={"on_conflict": on_conflict},
            json=rows,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def insert_ignore_rows(self, table: str, rows: list[dict], on_conflict: str) -> list[dict]:
        if not rows:
            return []
        response = requests.post(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("resolution=ignore-duplicates,return=representation"),
            params={"on_conflict": on_conflict},
            json=rows,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()


def _status_code_from_error(
    error: requests.RequestException,
    response: requests.Response | None,
) -> int | None:
    if response is not None and response.status_code:
        return int(response.status_code)
    error_response = getattr(error, "response", None)
    if error_response is not None and error_response.status_code:
        return int(error_response.status_code)
    return None
