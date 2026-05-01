from __future__ import annotations

import requests


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
