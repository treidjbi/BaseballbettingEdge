from __future__ import annotations

import json
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

    def select_rows(
        self,
        table: str,
        params: dict[str, str],
        *,
        timeout_seconds: float = 20,
        attempts: int = 3,
    ) -> list[dict]:
        response = self._select_response_with_retries(
            table,
            params,
            timeout_seconds=timeout_seconds,
            attempts=attempts,
        )
        return response.json()

    def count_rows(self, table: str, params: dict[str, str] | None = None) -> int:
        query = dict(params or {})
        query.setdefault("select", "*")
        query["limit"] = "1"
        response = requests.get(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("count=exact"),
            params=query,
            timeout=20,
        )
        response.raise_for_status()
        return _count_from_content_range(response.headers.get("Content-Range", ""))

    def delete_rows(self, table: str, params: dict[str, str]) -> int:
        if not params:
            raise ValueError("delete params are required")
        response = requests.delete(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("return=minimal,count=exact"),
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return _count_from_content_range(response.headers.get("Content-Range", ""))

    def update_rows(self, table: str, params: dict[str, str], values: dict) -> int:
        if not params:
            raise ValueError("update params are required")
        if not values:
            return 0
        response = requests.patch(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("return=minimal,count=exact"),
            params=params,
            json=values,
            timeout=20,
        )
        response.raise_for_status()
        return _count_from_content_range(response.headers.get("Content-Range", ""))

    def _select_response_with_retries(
        self,
        table: str,
        params: dict[str, str],
        *,
        attempts: int = 3,
        base_delay_seconds: float = 0.5,
        timeout_seconds: float = 20,
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            response = None
            try:
                response = requests.get(
                    f"{self.supabase_url}/rest/v1/{table}",
                    headers=self._headers("return=representation"),
                    params=params,
                    timeout=timeout_seconds,
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

    def upsert_rows(
        self,
        table: str,
        rows: list[dict],
        on_conflict: str,
        *,
        timeout_seconds: float = 20,
        return_representation: bool = True,
        attempts: int = 1,
        retry_database_codes: set[str] | None = None,
    ) -> list[dict]:
        if not rows:
            return []
        if attempts < 1:
            raise ValueError("upsert attempts must be at least 1")
        selected_database_codes = {str(code) for code in (retry_database_codes or set())}
        return_preference = "representation" if return_representation else "minimal"

        for attempt in range(1, attempts + 1):
            response = requests.post(
                f"{self.supabase_url}/rest/v1/{table}",
                headers=self._headers(f"resolution=merge-duplicates,return={return_preference}"),
                params={"on_conflict": on_conflict},
                json=rows,
                timeout=timeout_seconds,
            )
            try:
                _raise_for_status_with_context(
                    response,
                    table=table,
                    operation="upsert_rows",
                    row_count=len(rows),
                    on_conflict=on_conflict,
                )
            except requests.HTTPError as error:
                status_code = _status_code_from_error(error, response)
                database_code = _database_code_from_response(response)
                retry_selected = (
                    attempt < attempts
                    and status_code in TRANSIENT_STATUS_CODES
                    and database_code in selected_database_codes
                )
                if not retry_selected:
                    raise
                delay = 0.5 * attempt
                print(
                    "Warning: Supabase upsert_rows selected transient failure "
                    f"table={table} status={status_code} database_code={database_code}; "
                    f"retrying attempt {attempt + 1}/{attempts}",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue

            if return_representation:
                return response.json()
            return []

        raise RuntimeError(f"Supabase upsert_rows failed after {attempts} attempts")

    def insert_ignore_rows(
        self,
        table: str,
        rows: list[dict],
        on_conflict: str,
        *,
        timeout_seconds: float = 20,
    ) -> list[dict]:
        if not rows:
            return []
        response = requests.post(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("resolution=ignore-duplicates,return=representation"),
            params={"on_conflict": on_conflict},
            json=rows,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def _count_from_content_range(content_range: str) -> int:
    if "/" not in content_range:
        return 0
    total = content_range.rsplit("/", 1)[-1]
    if not total or total == "*":
        return 0
    return int(total)


def _raise_for_status_with_context(
    response: requests.Response,
    *,
    table: str,
    operation: str,
    row_count: int,
    on_conflict: str | None = None,
) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        body = (getattr(response, "text", "") or "").strip()
        if len(body) > 1000:
            body = f"{body[:1000]}..."
        parts = [
            str(error),
            f"table={table}",
            f"operation={operation}",
            f"rows={row_count}",
        ]
        if on_conflict:
            parts.append(f"on_conflict={on_conflict}")
        if body:
            parts.append(f"response_body={body}")
        raise requests.HTTPError("; ".join(parts), response=response) from error


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


def _database_code_from_response(response: requests.Response) -> str | None:
    body = (getattr(response, "text", "") or "").strip()
    if not body:
        return None
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("code") is None:
        return None
    return str(payload["code"])
