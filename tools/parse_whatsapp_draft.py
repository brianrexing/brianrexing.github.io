#!/usr/bin/env python3
"""Parse a WhatsApp chat export and extract college football draft picks.

Supports common export formats:
  [10/15/24, 8:32:15 PM] Brian: 1. Ohio State
  10/15/24, 8:32 PM - Brian: Ohio State
  Brian: Round 1 - Georgia

Also accepts a simple one-pick-per-line paste:
  Brian: Ohio State
  Mike: Georgia

Usage:
  python3 tools/parse_whatsapp_draft.py path/to/WhatsApp Chat.txt
  python3 tools/parse_whatsapp_draft.py path/to/chat.txt -o data/cfb/draft.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "cfb" / "draft.csv"

# WhatsApp Android/iOS export line prefixes
WA_BRACKET = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s+(?P<sender>[^:]+):\s+(?P<body>.*)$"
)
WA_DASH = re.compile(
    r"^(?P<ts>\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s*-\s*"
    r"(?P<sender>[^:]+):\s+(?P<body>.*)$",
    re.IGNORECASE,
)
SIMPLE = re.compile(r"^(?P<sender>[^:]+):\s+(?P<body>.+)$")

# Body patterns that look like a draft pick
PICK_PATTERNS = [
    # "1. Ohio State" / "#1 Ohio State" / "Pick 1: Ohio State"
    re.compile(
        r"^(?:pick\s*)?(?:#\s*)?(?P<pick>\d{1,3})[.):\-\s]+(?P<team>.+)$",
        re.IGNORECASE,
    ),
    # "Round 2 - Alabama" / "R2: Alabama"
    re.compile(
        r"^(?:round|r)\s*(?P<round>\d{1,2})\s*[-:)\s]+(?P<team>.+)$",
        re.IGNORECASE,
    ),
    # "I take Ohio State" / "taking Georgia" / "drafting Alabama"
    re.compile(
        r"^(?:i\s+)?(?:take|taking|drafting|select(?:ing)?|grab(?:bing)?)\s+"
        r"(?P<team>.+)$",
        re.IGNORECASE,
    ),
]

# Bare team names only accepted when they fuzzy-match a known CFB team
BARE_TEAM = re.compile(r"^(?P<team>[A-Za-z0-9 .&'\-]{3,40})$")

SKIP_BODY = re.compile(
    r"^(ok|okay|lol|lmao|haha|yes|no|yep|nah|thanks|thank you|nice|damn|"
    r"ready|fire away|let'?s do this|let'?s go|good luck.*|draft locked.*|"
    r"<media omitted>|image omitted|video omitted|sticker omitted|"
    r"this message was deleted|you deleted this message|"
    r"messages and calls are end-to-end encrypted).*$",
    re.IGNORECASE,
)

SYSTEM_SENDERS = {
    "",
    "system",
    "whatsapp",
}


def clean_team(raw: str) -> str:
    team = raw.strip().strip("\"'`*")
    team = re.sub(r"\s+", " ", team)
    team = re.sub(r"[.!?]+$", "", team)
    # Drop trailing chatter like "Ohio State baby"
    for sep in (" - ", " — ", " (", "!"):
        if sep in team:
            team = team.split(sep, 1)[0].strip()
    return team


def normalize(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9& ]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    for suffix in (
        " fighting irish",
        " buckeyes",
        " bulldogs",
        " crimson tide",
        " tigers",
        " wolves",
        " wolves",
        " longhorns",
        " nittany lions",
        " ducks",
        " wolverines",
        " volunteers",
        " rebels",
        " aggies",
        " hurricanes",
        " mean green",
        " bulls",
        " cyclones",
        " football",
        " university",
    ):
        if name.endswith(suffix.strip()) or f" {suffix.strip()}" in f" {name}":
            name = name.replace(suffix.strip(), "").strip()
    return name


def load_known_teams(records_path: Path) -> list[str]:
    if not records_path.exists():
        return []
    teams: list[str] = []
    with records_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key in ("team", "display_name", "location", "abbreviation"):
                value = (row.get(key) or "").strip()
                if value:
                    teams.append(value)
    return teams


def match_known_team(raw: str, known_teams: list[str]) -> str | None:
    if not known_teams:
        return raw
    needle = normalize(raw)
    if not needle:
        return None

    best: str | None = None
    best_score = 0
    for candidate in known_teams:
        cand = normalize(candidate)
        if not cand:
            continue
        if needle == cand or needle == normalize(candidate.split()[0]):
            return candidate
        if needle in cand or cand in needle:
            score = min(len(needle), len(cand))
            if score > best_score:
                best = candidate
                best_score = score
    # Require a reasonably long overlap so "Texas" doesn't steal "Texas A&M" incorrectly
    # but still allow short unique names like "LSU"
    if best and best_score >= min(4, len(needle)):
        # Prefer exact shortDisplayName-style matches when several contain the needle
        exact = [t for t in known_teams if normalize(t) == needle]
        if exact:
            return exact[0]
        return best
    return None


def parse_body(
    body: str, known_teams: list[str]
) -> tuple[str | None, int | None, int | None]:
    body = body.strip()
    if not body or SKIP_BODY.match(body):
        return None, None, None

    for pattern in PICK_PATTERNS:
        match = pattern.match(body)
        if not match:
            continue
        team = clean_team(match.group("team"))
        if len(team) < 2 or len(team.split()) > 6:
            continue
        resolved = match_known_team(team, known_teams) if known_teams else team
        if known_teams and not resolved:
            continue
        pick = (
            int(match.group("pick"))
            if "pick" in match.groupdict() and match.group("pick")
            else None
        )
        rnd = (
            int(match.group("round"))
            if "round" in match.groupdict() and match.group("round")
            else None
        )
        return resolved or team, pick, rnd

    bare = BARE_TEAM.match(body)
    if bare and known_teams:
        team = clean_team(bare.group("team"))
        resolved = match_known_team(team, known_teams)
        if resolved:
            return resolved, None, None

    return None, None, None


def iter_messages(text: str) -> list[tuple[str, str]]:
    messages: list[tuple[str, str]] = []
    current_sender: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_sender, current_body
        if current_sender is not None:
            messages.append((current_sender.strip(), "\n".join(current_body).strip()))
        current_sender = None
        current_body = []

    for raw_line in text.splitlines():
        line = raw_line.strip("\ufeff").rstrip()
        if not line:
            continue

        matched = None
        for pattern in (WA_BRACKET, WA_DASH, SIMPLE):
            m = pattern.match(line)
            if m and m.group("sender").strip().lower() not in SYSTEM_SENDERS:
                # Avoid treating "http://..." as SIMPLE sender:body
                if pattern is SIMPLE and "/" in m.group("sender"):
                    continue
                matched = m
                break

        if matched:
            flush()
            current_sender = matched.group("sender")
            current_body = [matched.group("body")]
        elif current_sender is not None:
            current_body.append(line)

    flush()
    return messages


def extract_picks(text: str, known_teams: list[str] | None = None) -> list[dict]:
    known_teams = known_teams or []
    picks: list[dict] = []
    auto_pick = 1

    for sender, body in iter_messages(text):
        # Skip WhatsApp system / group notices
        lower = body.lower()
        if "created group" in lower or "added you" in lower:
            continue
        team, pick_num, rnd = parse_body(body, known_teams)
        if not team:
            continue
        if pick_num is None:
            pick_num = auto_pick
        picks.append(
            {
                "pick": pick_num,
                "round": rnd or "",
                "owner": sender,
                "team": team,
                "raw_message": body,
            }
        )
        auto_pick = max(auto_pick, pick_num) + 1

    needs_renumber = len({p["pick"] for p in picks}) != len(picks)
    if needs_renumber:
        for i, p in enumerate(picks, start=1):
            p["pick"] = i

    # Fill rounds if absent (assume equal teams per owner)
    owners = list(dict.fromkeys(p["owner"] for p in picks))
    if owners and all(p["round"] == "" for p in picks):
        n = len(owners)
        for p in picks:
            p["round"] = ((int(p["pick"]) - 1) // n) + 1

    # Drop duplicate owner+team pairs
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for p in picks:
        key = (p["owner"].lower(), p["team"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped


def write_draft(picks: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["pick", "round", "owner", "team", "raw_message"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(picks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chat", type=Path, help="WhatsApp .txt export path")
    parser.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--records",
        type=Path,
        default=ROOT / "data" / "cfb" / "records.csv",
        help="Optional ESPN records CSV used to validate team names",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print picks only")
    args = parser.parse_args()

    text = args.chat.read_text(encoding="utf-8", errors="replace")
    known = load_known_teams(args.records)
    picks = extract_picks(text, known)
    if not picks:
        raise SystemExit(
            "No draft picks found. Try messages like:\n"
            "  Brian: 1. Ohio State\n"
            "  Mike: Georgia\n"
            "Or edit data/cfb/draft.csv by hand."
        )

    if args.dry_run:
        for p in picks:
            print(f"{p['pick']:>3}. R{p['round']}  {p['owner']} -> {p['team']}")
        return

    write_draft(picks, args.out)
    print(f"Wrote {len(picks)} picks ({len({p['owner'] for p in picks})} owners) to {args.out}")


if __name__ == "__main__":
    main()
