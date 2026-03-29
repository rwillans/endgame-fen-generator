from __future__ import annotations

from collections import Counter
from typing import Any

from .filters import game_metadata_matches, infer_time_class, opening_matches
from .models import ExtractConfig


def _matches_csv_filter(value: str | None, filters: tuple[str, ...]) -> bool:
    if not filters:
        return True
    if not value:
        return False
    lowered = value.lower()
    return any(token.lower() == lowered for token in filters)


def header_matches(headers: dict[str, str], config: ExtractConfig) -> bool:
    if not opening_matches(headers, config):
        return False
    if not game_metadata_matches(headers, config):
        return False
    if config.result_filters and headers.get("Result") not in set(config.result_filters):
        return False
    if not _matches_csv_filter(headers.get("Variant") or "Standard", config.variant_filters):
        return False
    if config.event_contains and config.event_contains.lower() not in (headers.get("Event") or "").lower():
        return False
    return True


def update_header_summary(counters: dict[str, Counter[str]], headers: dict[str, str]) -> None:
    opening = headers.get("Opening") or headers.get("ECO") or "Unknown"
    eco = headers.get("ECO") or "Unknown"
    time_class = infer_time_class(headers) or "unknown"
    counters["opening"][opening] += 1
    counters["eco"][eco] += 1
    counters["time_control"][time_class] += 1


def dry_run_record(stats: dict[str, int], counters: dict[str, Counter[str]], limit: int) -> dict[str, Any]:
    def top(counter: Counter[str]) -> list[dict[str, Any]]:
        return [{"value": value, "count": count} for value, count in counter.most_common(limit)]

    return {
        "files_scanned": stats.get("files_scanned", 0),
        "games_scanned": stats.get("games_scanned", 0),
        "games_passing_header_filters": stats.get("games_passing_header_filters", 0),
        "openings": top(counters["opening"]),
        "eco": top(counters["eco"]),
        "time_controls": top(counters["time_control"]),
    }
