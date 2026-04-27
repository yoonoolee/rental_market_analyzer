"""
Build eval datasets from real session logs.

The app doesn't write session logs to disk by default — to use this script you
first need to capture a few real sessions by running the app with LOG_SESSIONS=true:

    LOG_SESSIONS=true uvicorn server:app --reload --port 8000

Each session will be written to logs/sessions/<session_id>.json as the graph
completes. Then run this script to convert those logs into eval dataset files:

    python -m scripts.build_eval_dataset
    python -m scripts.build_eval_dataset --sessions logs/sessions/abc123.json logs/sessions/def456.json
    python -m scripts.build_eval_dataset --out evals/datasets/real_listings.json

What this produces:
  - static_listings.json-compatible file: one entry per listing profile, with the
    same field schema the production listing_agent_node returns (commute_times as
    strings, nearby_places as dicts, photo-analysis booleans, disqualified flag).
  - preferences.json-compatible file: one entry per session with extracted preferences.

These files can be passed to the eval runner instead of the hand-crafted fixtures:
    python -m evals.run_evals --experiments end_to_end --dataset logs/sessions/

NOTE: session logs may contain real user queries and real listing URLs. Do not
commit them to the repo. logs/ is in .gitignore.
"""
import json
import argparse
import uuid
from pathlib import Path
from datetime import datetime, timezone


LOGS_DIR = Path(__file__).parent.parent / "logs" / "sessions"
EVALS_DIR = Path(__file__).parent.parent / "evals" / "datasets"


def load_session(path: Path) -> dict:
    return json.loads(path.read_text())


def extract_listings(session: dict) -> list[dict]:
    """
    Pull listing profiles out of a session log.
    Each profile is the direct output of listing_agent_node — the real schema,
    not the hand-crafted fixture schema.
    """
    profiles = session.get("listing_profiles", [])
    city = (session.get("preferences", {}) or {}).get("city", "")
    out = []
    for p in profiles:
        if not p.get("url"):
            continue
        entry = dict(p)
        # Attach city so the end-to-end eval can filter by city (same as static_listings.json)
        if city and "city" not in entry:
            entry["city"] = city
        # Generate a stable ID from the URL so repeated runs don't duplicate entries
        entry["id"] = "RL" + str(abs(hash(p["url"])))[:6]
        out.append(entry)
    return out


def extract_preference(session: dict, session_id: str) -> dict | None:
    """
    Pull the final extracted preferences out of a session log.
    Returns a preferences.json-compatible row.
    """
    prefs = session.get("preferences")
    if not prefs:
        return None
    conversation = session.get("conversation", [])
    return {
        "id": session_id,
        "split": "real",
        "description": f"Real session — {prefs.get('city', 'unknown city')}",
        "conversation": conversation,
        "expected_preferences": prefs,
    }


def build_datasets(session_paths: list[Path], out_listings: Path, out_preferences: Path):
    all_listings: list[dict] = []
    all_preferences: list[dict] = []
    seen_urls: set[str] = set()

    for path in session_paths:
        try:
            session = load_session(path)
        except Exception as e:
            print(f"  skip {path.name}: {e}")
            continue

        session_id = path.stem

        listings = extract_listings(session)
        for l in listings:
            if l["url"] not in seen_urls:
                seen_urls.add(l["url"])
                all_listings.append(l)

        pref = extract_preference(session, session_id)
        if pref:
            all_preferences.append(pref)

        print(f"  {path.name}: {len(listings)} listings, preferences={'yes' if pref else 'no'}")

    out_listings.write_text(json.dumps(all_listings, indent=2))
    print(f"\nWrote {len(all_listings)} listings → {out_listings}")

    out_preferences.write_text(json.dumps(all_preferences, indent=2))
    print(f"Wrote {len(all_preferences)} preferences → {out_preferences}")


def main():
    parser = argparse.ArgumentParser(description="Build eval datasets from real session logs")
    parser.add_argument(
        "--sessions", nargs="+", type=Path, default=None,
        help="Specific session log files to use. Defaults to all files in logs/sessions/."
    )
    parser.add_argument(
        "--out-listings", type=Path,
        default=EVALS_DIR / "real_static_listings.json",
        help="Output path for the listings dataset (default: evals/datasets/real_static_listings.json)"
    )
    parser.add_argument(
        "--out-preferences", type=Path,
        default=EVALS_DIR / "real_preferences.json",
        help="Output path for the preferences dataset (default: evals/datasets/real_preferences.json)"
    )
    args = parser.parse_args()

    if args.sessions:
        session_paths = args.sessions
    elif LOGS_DIR.exists():
        session_paths = sorted(LOGS_DIR.glob("*.json"))
    else:
        print(f"No session logs found at {LOGS_DIR}.")
        print("Run the app with LOG_SESSIONS=true to capture sessions, then re-run this script.")
        return

    if not session_paths:
        print("No session log files found.")
        return

    print(f"Processing {len(session_paths)} session(s)...\n")
    build_datasets(session_paths, args.out_listings, args.out_preferences)


if __name__ == "__main__":
    main()
