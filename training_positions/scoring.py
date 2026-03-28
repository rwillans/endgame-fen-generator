from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable

from .models import CandidatePosition, ExtractConfig


def classify_training_label(eval_pawns: float | None, side_to_move: str) -> str:
    if eval_pawns is None:
        return "balanced decision"
    if abs(eval_pawns) <= 0.75:
        return "balanced decision"

    side_is_better = (eval_pawns > 0 and side_to_move == "white") or (eval_pawns < 0 and side_to_move == "black")
    if abs(eval_pawns) <= 2.5:
        return "conversion" if side_is_better else "defence"
    return "technical win"


def eval_relevance(eval_pawns: float | None, bias: str) -> float:
    if eval_pawns is None:
        return 0.55
    absolute = abs(eval_pawns)
    if bias == "balanced":
        return max(0.0, 1.0 - absolute / 2.0)
    if bias == "conversion":
        return max(0.0, 1.0 - abs(absolute - 1.4) / 2.5)
    if bias == "defence":
        return max(0.0, 1.0 - abs(absolute - 1.8) / 2.5)
    return max(0.0, 1.0 - abs(absolute - 1.0) / 3.0)


def compute_training_score(candidate: CandidatePosition, config: ExtractConfig) -> float:
    rating_score = (candidate.average_rating or config.min_rating) / 2800.0
    playability_score = min(candidate.plies_remaining / 20.0, 1.0) * 0.7 + min(candidate.legal_moves / 12.0, 1.0) * 0.3
    commonness_score = min(math.log1p(candidate.position_frequency) / math.log(10), 1.0) * 0.45 + min(
        math.log1p(candidate.family_frequency) / math.log(20),
        1.0,
    ) * 0.55
    return (
        0.35 * eval_relevance(candidate.eval_pawns_projected, config.training_bias)
        + 0.25 * commonness_score
        + 0.20 * rating_score
        + 0.20 * playability_score
    )


def per_game_best(candidates: Iterable[CandidatePosition], limit: int) -> list[CandidatePosition]:
    buckets: dict[str, list[CandidatePosition]] = defaultdict(list)
    for candidate in candidates:
        buckets[candidate.game_key].append(candidate)
    selected: list[CandidatePosition] = []
    for values in buckets.values():
        values.sort(key=lambda item: item.training_score, reverse=True)
        selected.extend(values[:limit])
    return selected


def sort_key(candidate: CandidatePosition, mode: str) -> tuple[float, float]:
    if mode == "commonness":
        return float(candidate.family_frequency), float(candidate.position_frequency)
    if mode == "rating":
        return float(candidate.average_rating or 0.0), candidate.training_score
    if mode == "eval_abs":
        return -abs(candidate.eval_pawns_projected or 99.0), candidate.training_score
    return candidate.training_score, float(candidate.average_rating or 0.0)


def select_final_candidates(candidates: list[CandidatePosition], config: ExtractConfig) -> list[CandidatePosition]:
    dedupe_seen: set[str] = set()
    family_seen: Counter[str] = Counter()
    opening_seen: Counter[str] = Counter()
    selected: list[CandidatePosition] = []

    ranked = sorted(candidates, key=lambda item: sort_key(item, config.sort_by), reverse=True)
    while ranked and len(selected) < config.max_positions:
        best_index = 0
        best_value = -1e9
        for index, candidate in enumerate(ranked):
            if candidate.dedupe_key in dedupe_seen:
                continue
            if config.cluster_similar and family_seen[candidate.family_signature] >= config.max_similar_per_cluster:
                continue
            score = candidate.training_score
            if config.diversity:
                score -= 0.12 * family_seen[candidate.family_signature]
                score -= 0.04 * opening_seen[candidate.opening or candidate.eco or "unknown"]
            if score > best_value:
                best_value = score
                best_index = index

        chosen = ranked.pop(best_index)
        if chosen.dedupe_key in dedupe_seen:
            continue
        if config.cluster_similar and family_seen[chosen.family_signature] >= config.max_similar_per_cluster:
            continue
        dedupe_seen.add(chosen.dedupe_key)
        family_seen[chosen.family_signature] += 1
        opening_seen[chosen.opening or chosen.eco or "unknown"] += 1
        selected.append(chosen)
    return selected
