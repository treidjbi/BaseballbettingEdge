"""Create the PropLine webhook subscription for shadow tracking.

Run this once after the Netlify receiver is deployed. PropLine returns the
webhook secret only once; immediately store it as PROPLINE_WEBHOOK_SECRET in the
receiver environment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import requests

PROPLINE_API_BASE = "https://api.prop-line.com"
DEFAULT_WEBHOOK_URL = "https://baseballbettingedge.netlify.app/api/propline-webhook"


def _api_key() -> str:
    value = os.environ.get("PROPLINE_API_KEY", "").strip()
    if not value:
        raise EnvironmentError("PROPLINE_API_KEY is required")
    return value


def create_subscription(args: argparse.Namespace) -> dict:
    payload = {
        "url": args.url,
        "events": args.events,
        "filter_sport_key": args.sport,
        "filter_market_key": args.market,
        "min_price_change_pct": args.min_price_change_pct,
    }
    payload = {key: value for key, value in payload.items() if value not in (None, "", [])}

    response = requests.post(
        f"{PROPLINE_API_BASE}/v1/webhooks",
        headers={
            "X-API-Key": _api_key(),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    if response.status_code >= 400:
        print(response.text, file=sys.stderr)
    response.raise_for_status()
    return response.json()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a PropLine line-movement webhook subscription."
    )
    parser.add_argument("--url", default=DEFAULT_WEBHOOK_URL)
    parser.add_argument("--sport", default="baseball_mlb")
    parser.add_argument("--market", default="pitcher_strikeouts")
    parser.add_argument(
        "--event",
        dest="events",
        action="append",
        default=["line_movement"],
        help="PropLine webhook event type. Repeat to subscribe to multiple events.",
    )
    parser.add_argument(
        "--min-price-change-pct",
        type=float,
        default=2.0,
        help="Minimum price move for line_movement notifications.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    subscription = create_subscription(args)
    print(json.dumps(subscription, indent=2, sort_keys=True))
    if "secret" in subscription:
        print(
            "\nStore the returned secret immediately as PROPLINE_WEBHOOK_SECRET. "
            "PropLine will not show it again.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
