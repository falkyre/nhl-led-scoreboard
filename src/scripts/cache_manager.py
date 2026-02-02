#!/usr/bin/env python3
"""
NHL LED Scoreboard Cache Manager CLI

A command-line tool to view, inspect, and manage the scoreboard cache.

Usage:
    python src/scripts/cache_manager.py [command] [options]

Commands:
    list        List all cache entries with summary info
    inspect     Show detailed info for a specific cache key
    delete      Delete a specific cache key
    clear       Clear all cache entries
    stats       Show cache statistics
    workers     Show worker-specific cache info

Examples:
    python src/scripts/cache_manager.py list
    python src/scripts/cache_manager.py inspect nhl_standings
    python src/scripts/cache_manager.py delete nhl_games_today
    python src/scripts/cache_manager.py clear --confirm
    python src/scripts/cache_manager.py workers
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import diskcache as dc

# Cache location
CACHE_PATH = "/tmp/sb_cache"

# Known cache keys and their descriptions
KNOWN_KEYS = {
    "nhl_games_today": {
        "worker": "GamesWorker",
        "description": "Today's NHL games (raw and structured formats)",
        "refresh": "Adaptive (1-30 minutes based on game state)",
    },
    "nhl_standings": {
        "worker": "StandingsWorker",
        "description": "NHL standings by conference, division, and wildcard",
        "refresh": "60 minutes",
    },
    "nhl_stats_leaders": {
        "worker": "StatsLeadersWorker",
        "description": "Stats leaders (goals, assists, points, etc.)",
        "refresh": "30 minutes",
    },
    "team_schedule_data": {
        "worker": "TeamScheduleWorker",
        "description": "Previous/next game data for preferred teams",
        "refresh": "30 minutes",
    },
    "weather": {
        "worker": "WeatherAPI",
        "description": "Current weather data from configured provider",
        "refresh": "Configurable",
    },
    "location": {
        "worker": "GeoLocation",
        "description": "Cached location (lat/lng) for weather lookups",
        "refresh": "7 days",
    },
}


def get_cache() -> Optional[dc.Cache]:
    """Open and return the cache, or None if it doesn't exist."""
    if not os.path.exists(CACHE_PATH):
        return None
    return dc.Cache(CACHE_PATH)


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_timedelta(td: timedelta) -> str:
    """Format timedelta as human-readable string."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "expired"

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


def get_cache_entry_info(cache: dc.Cache, key: str) -> Dict[str, Any]:
    """Get detailed info about a cache entry."""
    try:
        value, expire_time = cache.get(key, expire_time=True)
        if value is None:
            return {"exists": False}

        info = {
            "exists": True,
            "key": key,
            "value": value,
            "expire_time": expire_time,
        }

        # Calculate TTL
        if expire_time:
            now = datetime.now().timestamp()
            ttl_seconds = expire_time - now
            info["ttl_seconds"] = ttl_seconds
            info["ttl_human"] = format_timedelta(timedelta(seconds=ttl_seconds))
            info["expires_at"] = datetime.fromtimestamp(expire_time).strftime("%Y-%m-%d %H:%M:%S")

        # Get value type and size estimate
        info["value_type"] = type(value).__name__
        try:
            info["value_size"] = len(json.dumps(value, default=str))
        except:
            info["value_size"] = sys.getsizeof(value)

        # Add known key metadata
        if key in KNOWN_KEYS:
            info["metadata"] = KNOWN_KEYS[key]
        elif key.startswith("live_game_overview_"):
            game_id = key.replace("live_game_overview_", "")
            info["metadata"] = {
                "worker": "LiveGameWorker",
                "description": f"Live game overview for game {game_id}",
                "refresh": "5-30 seconds (adaptive)",
            }

        return info
    except Exception as e:
        return {"exists": False, "error": str(e)}


def format_value_summary(value: Any, max_length: int = 100) -> str:
    """Format a cache value as a short summary."""
    if value is None:
        return "None"

    if isinstance(value, dict):
        keys = list(value.keys())
        if len(keys) > 5:
            return f"dict with {len(keys)} keys: {keys[:5]}..."
        return f"dict with keys: {keys}"

    if isinstance(value, list):
        return f"list with {len(value)} items"

    if isinstance(value, str):
        if len(value) > max_length:
            return f'"{value[:max_length]}..."'
        return f'"{value}"'

    # Check for dataclass
    if hasattr(value, "__dataclass_fields__"):
        fields = list(value.__dataclass_fields__.keys())
        return f"{type(value).__name__}({', '.join(fields[:5])}{'...' if len(fields) > 5 else ''})"

    return str(value)[:max_length]


def cmd_list(args):
    """List all cache entries."""
    cache = get_cache()
    if not cache:
        print(f"Cache not found at {CACHE_PATH}")
        return 1

    print(f"\n{'='*80}")
    print(f"NHL LED Scoreboard Cache - {CACHE_PATH}")
    print(f"{'='*80}\n")

    # Get all keys
    keys = list(cache)

    if not keys:
        print("Cache is empty.\n")
        cache.close()
        return 0

    # Sort keys: known keys first, then live game keys, then others
    def key_sort(k):
        if k in KNOWN_KEYS:
            return (0, k)
        if k.startswith("live_game_overview_"):
            return (1, k)
        return (2, k)

    keys.sort(key=key_sort)

    print(f"{'Key':<35} {'Type':<15} {'Size':<10} {'TTL':<15} {'Worker':<20}")
    print(f"{'-'*35} {'-'*15} {'-'*10} {'-'*15} {'-'*20}")

    for key in keys:
        info = get_cache_entry_info(cache, key)
        if info["exists"]:
            worker = info.get("metadata", {}).get("worker", "-")
            ttl = info.get("ttl_human", "no expiry")
            size = format_size(info.get("value_size", 0))
            value_type = info.get("value_type", "unknown")
            print(f"{key:<35} {value_type:<15} {size:<10} {ttl:<15} {worker:<20}")

    print(f"\nTotal entries: {len(keys)}")
    cache.close()
    return 0


def cmd_inspect(args):
    """Inspect a specific cache entry."""
    cache = get_cache()
    if not cache:
        print(f"Cache not found at {CACHE_PATH}")
        return 1

    key = args.key
    info = get_cache_entry_info(cache, key)

    if not info["exists"]:
        print(f"Key '{key}' not found in cache.")
        if "error" in info:
            print(f"Error: {info['error']}")
        cache.close()
        return 1

    print(f"\n{'='*80}")
    print(f"Cache Entry: {key}")
    print(f"{'='*80}\n")

    # Metadata
    if "metadata" in info:
        meta = info["metadata"]
        print(f"Worker:      {meta.get('worker', 'Unknown')}")
        print(f"Description: {meta.get('description', 'N/A')}")
        print(f"Refresh:     {meta.get('refresh', 'N/A')}")
        print()

    # Entry info
    print(f"Type:        {info['value_type']}")
    print(f"Size:        {format_size(info['value_size'])}")

    if "expires_at" in info:
        print(f"Expires at:  {info['expires_at']}")
        print(f"TTL:         {info['ttl_human']}")
    else:
        print(f"Expires:     Never")

    print()

    # Value inspection
    value = info["value"]

    if args.full:
        print("Full Value:")
        print("-" * 40)
        try:
            print(json.dumps(value, indent=2, default=str))
        except:
            print(value)
    else:
        print("Value Summary:")
        print("-" * 40)

        if isinstance(value, dict):
            # Show dict structure
            for k, v in value.items():
                print(f"  {k}: {format_value_summary(v)}")

                # Special handling for known structures
                if k == "raw" and isinstance(v, list):
                    print(f"    └─ {len(v)} games")
                elif k == "structured" and isinstance(v, list):
                    print(f"    └─ {len(v)} Game objects")
                elif k == "fetched_at" and isinstance(v, datetime):
                    age = datetime.now() - v
                    print(f"    └─ {format_timedelta(age)} ago")

        elif hasattr(value, "__dataclass_fields__"):
            # Dataclass - show fields
            for field_name in value.__dataclass_fields__:
                field_value = getattr(value, field_name)
                print(f"  {field_name}: {format_value_summary(field_value)}")

        else:
            print(f"  {format_value_summary(value, 500)}")

    print()
    cache.close()
    return 0


def cmd_delete(args):
    """Delete a specific cache entry."""
    cache = get_cache()
    if not cache:
        print(f"Cache not found at {CACHE_PATH}")
        return 1

    key = args.key

    if key not in cache:
        print(f"Key '{key}' not found in cache.")
        cache.close()
        return 1

    if not args.confirm:
        print(f"This will delete cache entry '{key}'.")
        response = input("Are you sure? [y/N]: ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            cache.close()
            return 0

    del cache[key]
    print(f"Deleted '{key}' from cache.")
    cache.close()
    return 0


def cmd_clear(args):
    """Clear all cache entries."""
    cache = get_cache()
    if not cache:
        print(f"Cache not found at {CACHE_PATH}")
        return 1

    count = len(list(cache))

    if count == 0:
        print("Cache is already empty.")
        cache.close()
        return 0

    if not args.confirm:
        print(f"This will delete ALL {count} cache entries.")
        response = input("Are you sure? [y/N]: ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            cache.close()
            return 0

    cache.clear()
    print(f"Cleared {count} entries from cache.")
    cache.close()
    return 0


def cmd_stats(args):
    """Show cache statistics."""
    cache = get_cache()
    if not cache:
        print(f"Cache not found at {CACHE_PATH}")
        return 1

    print(f"\n{'='*80}")
    print(f"Cache Statistics")
    print(f"{'='*80}\n")

    print(f"Location:    {CACHE_PATH}")

    # Get disk usage
    cache_dir = Path(CACHE_PATH)
    if cache_dir.exists():
        total_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
        print(f"Disk usage:  {format_size(total_size)}")

    # Count entries
    keys = list(cache)
    print(f"Entries:     {len(keys)}")

    # Categorize entries
    worker_counts = {}
    expired_count = 0
    total_value_size = 0

    for key in keys:
        info = get_cache_entry_info(cache, key)
        if info["exists"]:
            total_value_size += info.get("value_size", 0)

            # Check if expired
            if info.get("ttl_seconds", 1) <= 0:
                expired_count += 1

            # Count by worker
            worker = info.get("metadata", {}).get("worker", "Other")
            worker_counts[worker] = worker_counts.get(worker, 0) + 1

    print(f"Total size:  {format_size(total_value_size)} (serialized)")
    print(f"Expired:     {expired_count}")

    print(f"\nEntries by Worker:")
    print("-" * 40)
    for worker, count in sorted(worker_counts.items()):
        print(f"  {worker:<25} {count}")

    print()
    cache.close()
    return 0


def cmd_workers(args):
    """Show worker-specific cache information."""
    cache = get_cache()
    if not cache:
        print(f"Cache not found at {CACHE_PATH}")
        return 1

    print(f"\n{'='*80}")
    print(f"Worker Cache Status")
    print(f"{'='*80}\n")

    # Check each known worker's cache
    workers = [
        ("GamesWorker", "nhl_games_today"),
        ("StandingsWorker", "nhl_standings"),
        ("StatsLeadersWorker", "nhl_stats_leaders"),
        ("TeamScheduleWorker", "team_schedule_data"),
        ("WeatherAPI", "weather"),
        ("GeoLocation", "location"),
    ]

    for worker_name, cache_key in workers:
        info = get_cache_entry_info(cache, cache_key)
        meta = KNOWN_KEYS.get(cache_key, {})

        print(f"┌─ {worker_name}")
        print(f"│  Key: {cache_key}")
        print(f"│  Description: {meta.get('description', 'N/A')}")
        print(f"│  Refresh interval: {meta.get('refresh', 'N/A')}")

        if info["exists"]:
            print(f"│  Status: ✓ Cached")
            print(f"│  Size: {format_size(info.get('value_size', 0))}")
            print(f"│  TTL: {info.get('ttl_human', 'no expiry')}")

            if "expires_at" in info:
                print(f"│  Expires: {info['expires_at']}")

            # Show additional details for specific workers
            value = info["value"]

            # Unwrap CacheEntry if present
            actual_data = value
            fetched_at = None
            if hasattr(value, 'data') and hasattr(value, 'fetched_at'):
                # It's a CacheEntry
                actual_data = value.data
                fetched_at = value.fetched_at
                if fetched_at:
                    age = datetime.now() - fetched_at
                    print(f"│  Fetched: {format_timedelta(age)} ago")

            if cache_key == "nhl_games_today":
                # GamesData has raw and structured
                if hasattr(actual_data, 'raw'):
                    print(f"│  Games: {len(actual_data.raw)}")
                elif isinstance(actual_data, dict):
                    games = actual_data.get("raw", [])
                    print(f"│  Games: {len(games)}")

            elif cache_key == "nhl_standings":
                # Standings has eastern and western Conference objects
                if hasattr(actual_data, "eastern"):
                    east_teams = len(actual_data.eastern.teams) if hasattr(actual_data.eastern, 'teams') else 0
                    west_teams = len(actual_data.western.teams) if hasattr(actual_data.western, 'teams') else 0
                    print(f"│  Teams: {east_teams + west_teams} (East: {east_teams}, West: {west_teams})")

            elif cache_key == "nhl_stats_leaders" and isinstance(actual_data, dict):
                print(f"│  Categories: {list(actual_data.keys())}")

            elif cache_key == "team_schedule_data" and isinstance(actual_data, dict):
                print(f"│  Teams: {len(actual_data)}")
                for team_id, team_data in actual_data.items():
                    if hasattr(team_data, 'team_abbrev'):
                        print(f"│    └─ {team_data.team_abbrev}")
        else:
            print(f"│  Status: ✗ Not cached")

        print(f"└{'─'*40}\n")

    # Check for live game caches
    live_game_keys = [k for k in cache if k.startswith("live_game_overview_")]
    if live_game_keys:
        print(f"┌─ LiveGameWorker")
        print(f"│  Active game caches: {len(live_game_keys)}")
        for key in live_game_keys:
            game_id = key.replace("live_game_overview_", "")
            info = get_cache_entry_info(cache, key)
            if info["exists"]:
                ttl = info.get("ttl_human", "?")
                print(f"│    └─ Game {game_id} (TTL: {ttl})")
        print(f"└{'─'*40}\n")
    else:
        print(f"┌─ LiveGameWorker")
        print(f"│  No active game caches")
        print(f"└{'─'*40}\n")

    cache.close()
    return 0


def cmd_refresh_info(args):
    """Show information about when each cache was last refreshed."""
    cache = get_cache()
    if not cache:
        print(f"Cache not found at {CACHE_PATH}")
        return 1

    print(f"\n{'='*80}")
    print(f"Cache Freshness Report")
    print(f"{'='*80}\n")

    now = datetime.now()

    # Check each cache entry with fetched_at timestamp
    entries_with_time = []

    for key in cache:
        info = get_cache_entry_info(cache, key)
        if not info["exists"]:
            continue

        value = info["value"]
        fetched_at = None

        # Check for fetched_at in different structures
        if isinstance(value, dict):
            fetched_at = value.get("fetched_at")
            # Also check nested structures for StatsLeadersData
            if not fetched_at:
                # Try to get from first item if it's a dict of dataclasses
                for v in value.values():
                    if hasattr(v, 'fetched_at'):
                        fetched_at = v.fetched_at
                        break
        elif hasattr(value, 'fetched_at'):
            fetched_at = value.fetched_at

        if fetched_at:
            if isinstance(fetched_at, datetime):
                age = now - fetched_at
                entries_with_time.append((key, fetched_at, age, info))

    # Also report entries without timestamps but show TTL-based age estimate
    entries_without_time = []
    for key in cache:
        if any(key == e[0] for e in entries_with_time):
            continue
        info = get_cache_entry_info(cache, key)
        if info["exists"] and "expire_time" in info:
            # We can estimate when it was cached based on TTL
            entries_without_time.append((key, info))

    # Sort by most recent
    entries_with_time.sort(key=lambda x: x[1], reverse=True)

    if entries_with_time:
        print(f"{'Key':<35} {'Last Fetched':<20} {'Age':<15} {'TTL':<15}")
        print(f"{'-'*35} {'-'*20} {'-'*15} {'-'*15}")

        for key, fetched_at, age, info in entries_with_time:
            fetched_str = fetched_at.strftime("%H:%M:%S")
            age_str = format_timedelta(age)
            ttl_str = info.get("ttl_human", "no expiry")
            print(f"{key:<35} {fetched_str:<20} {age_str:<15} {ttl_str:<15}")
        print()

    if entries_without_time:
        print("Entries without fetch timestamp (TTL only):")
        print(f"{'-'*60}")
        for key, info in entries_without_time:
            ttl_str = info.get("ttl_human", "no expiry")
            expires = info.get("expires_at", "unknown")
            print(f"  {key:<33} TTL: {ttl_str:<15} Expires: {expires}")
        print()

    if not entries_with_time and not entries_without_time:
        print("No cache entries found.")
        print()

    cache.close()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="NHL LED Scoreboard Cache Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                     List all cache entries
  %(prog)s inspect nhl_standings    Inspect standings cache
  %(prog)s inspect nhl_standings -f Show full cache value
  %(prog)s delete nhl_games_today   Delete games cache
  %(prog)s clear --confirm          Clear entire cache
  %(prog)s workers                  Show worker status
  %(prog)s stats                    Show cache statistics
  %(prog)s freshness                Show when data was fetched
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list command
    list_parser = subparsers.add_parser("list", help="List all cache entries")
    list_parser.set_defaults(func=cmd_list)

    # inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect a cache entry")
    inspect_parser.add_argument("key", help="Cache key to inspect")
    inspect_parser.add_argument("-f", "--full", action="store_true",
                                help="Show full value (can be verbose)")
    inspect_parser.set_defaults(func=cmd_inspect)

    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a cache entry")
    delete_parser.add_argument("key", help="Cache key to delete")
    delete_parser.add_argument("-y", "--confirm", action="store_true",
                               help="Skip confirmation prompt")
    delete_parser.set_defaults(func=cmd_delete)

    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear all cache entries")
    clear_parser.add_argument("-y", "--confirm", action="store_true",
                              help="Skip confirmation prompt")
    clear_parser.set_defaults(func=cmd_clear)

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show cache statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # workers command
    workers_parser = subparsers.add_parser("workers", help="Show worker cache status")
    workers_parser.set_defaults(func=cmd_workers)

    # freshness command
    freshness_parser = subparsers.add_parser("freshness", help="Show cache freshness")
    freshness_parser.set_defaults(func=cmd_refresh_info)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
