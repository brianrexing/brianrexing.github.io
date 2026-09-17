#!/usr/bin/env python3
"""Fetch college football team records from ESPN and write data/cfb/records.csv.

Uses the ESPN core API (sports.core.api.espn.com), which does not require an API key.
Default group 80 is NCAA Division I (FBS + FCS).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "cfb" / "records.csv"
TEAM_ID_RE = re.compile(r"/teams/(\d+)")


def get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; rexing-cfb-tracker/1.0)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def standings_url(season: int, group: int) -> str:
    return (
        "http://sports.core.api.espn.com/v2/sports/football/leagues/"
        f"college-football/seasons/{season}/types/2/groups/{group}/standings/0"
        "?lang=en&region=us"
    )


def team_url(season: int, team_id: str) -> str:
    return (
        "http://sports.core.api.espn.com/v2/sports/football/leagues/"
        f"college-football/seasons/{season}/teams/{team_id}?lang=en&region=us"
    )


def parse_record(summary: str) -> tuple[int, int, int]:
    parts = (summary or "0-0").replace(" ", "").split("-")
    wins = int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else 0
    losses = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
    ties = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0
    return wins, losses, ties


def fetch_team(season: int, team_id: str) -> dict:
    data = get_json(team_url(season, team_id))
    return {
        "espn_id": team_id,
        "team": data.get("shortDisplayName") or data.get("location") or "",
        "display_name": data.get("displayName") or "",
        "abbreviation": data.get("abbreviation") or "",
        "location": data.get("location") or "",
        "nickname": data.get("name") or "",
    }


def extract_rows(season: int, group: int) -> list[dict]:
    payload = get_json(standings_url(season, group))
    entries = payload.get("standings") or []
    pending: list[tuple[str, str, int, int, int]] = []

    for entry in entries:
        team_ref = (entry.get("team") or {}).get("$ref") or ""
        match = TEAM_ID_RE.search(team_ref)
        if not match:
            continue
        team_id = match.group(1)
        records = entry.get("records") or []
        overall = next(
            (r for r in records if r.get("type") == "total" or r.get("name") == "overall"),
            records[0] if records else {},
        )
        summary = overall.get("summary") or overall.get("displayValue") or "0-0"
        wins, losses, ties = parse_record(summary)
        pending.append((team_id, summary, wins, losses, ties))

    teams: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {
            pool.submit(fetch_team, season, team_id): team_id
            for team_id, *_ in pending
        }
        for fut in as_completed(futures):
            info = fut.result()
            teams[info["espn_id"]] = info

    rows: list[dict] = []
    for team_id, summary, wins, losses, ties in pending:
        info = teams.get(team_id) or {
            "espn_id": team_id,
            "team": team_id,
            "display_name": "",
            "abbreviation": "",
            "location": "",
            "nickname": "",
        }
        rows.append(
            {
                "season": season,
                "team": info["team"],
                "display_name": info["display_name"],
                "abbreviation": info["abbreviation"],
                "location": info["location"],
                "nickname": info["nickname"],
                "conference": "",
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "record": summary,
                "espn_id": team_id,
            }
        )

    rows.sort(key=lambda r: (-r["wins"], r["losses"], r["team"].lower()))
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "season",
        "team",
        "display_name",
        "abbreviation",
        "location",
        "nickname",
        "conference",
        "wins",
        "losses",
        "ties",
        "record",
        "espn_id",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--group", type=int, default=80, help="ESPN group id (80 = D-I)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows = extract_rows(args.season, args.group)
    if not rows:
        raise SystemExit(f"No teams found for season {args.season} group {args.group}")
    write_csv(rows, args.out)
    print(f"Wrote {len(rows)} teams to {args.out}")


if __name__ == "__main__":
    main()
