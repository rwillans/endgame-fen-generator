from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

import chess
import chess.pgn

from .evaluation import StockfishEvaluator, choose_eval, eval_passes, extract_eval_from_comment, project_eval
from .filters import (
    average_rating,
    dedupe_key,
    family_signature,
    game_metadata_matches,
    infer_time_class,
    material_matches,
    material_signature,
    move_number_matches,
    normalized_fen,
    opening_matches,
    phase_matches,
    piece_placement_plus_turn,
    position_is_playable,
    side_to_move_matches,
)
from .models import CandidatePosition, ExtractConfig
from .scoring import classify_training_label, compute_training_score, per_game_best, select_final_candidates
from .sources import iter_games_from_file, iter_input_files

LOGGER = logging.getLogger(__name__)


def next_move_metadata(node: chess.pgn.ChildNode) -> tuple[str | None, str | None]:
    if not node.variations:
        return None, None
    next_move = node.variations[0].move
    try:
        next_move_san = node.board().san(next_move)
    except ValueError:
        next_move_san = None
    return next_move.uci(), next_move_san


def frequency_passes(candidate: CandidatePosition, config: ExtractConfig) -> bool:
    position_ok = candidate.position_frequency >= config.min_position_frequency
    family_ok = candidate.family_frequency >= config.min_family_frequency
    if config.commonness_mode == "exact_position":
        return position_ok
    if config.commonness_mode == "family":
        return family_ok
    return position_ok or family_ok


def build_summary(selected: list[CandidatePosition], config: ExtractConfig) -> list[dict[str, object]]:
    buckets: dict[tuple[str, str], dict[str, object]] = {}
    for candidate in selected:
        key = (candidate.opening or candidate.eco or "Unknown", candidate.family_signature)
        current = buckets.setdefault(
            key,
            {
                "opening": key[0],
                "family_signature": key[1],
                "count": 0,
                "average_rating_total": 0.0,
                "sample_fen": candidate.fen,
                "sample_label": candidate.training_label,
                "sample_eval": candidate.eval_pawns_projected,
            },
        )
        current["count"] = int(current["count"]) + 1
        current["average_rating_total"] = float(current["average_rating_total"]) + float(candidate.average_rating or 0.0)
    rows = []
    for value in buckets.values():
        count = int(value["count"])
        average_rating = round(float(value["average_rating_total"]) / count, 2) if count else None
        rows.append(
            {
                "opening": value["opening"],
                "family_signature": value["family_signature"],
                "count": count,
                "average_rating": average_rating,
                "sample_fen": value["sample_fen"],
                "sample_label": value["sample_label"],
                "sample_eval": value["sample_eval"],
            }
        )
    rows.sort(key=lambda item: (item["count"], item.get("average_rating") or 0), reverse=True)
    return rows[: config.summary_limit]


def extract_positions(config: ExtractConfig) -> list[dict[str, object]]:
    files = list(iter_input_files(config.input_path))
    candidates: list[CandidatePosition] = []
    stats = Counter()

    with StockfishEvaluator(config) as evaluator:
        for file_path in files:
            if file_path.name.lower().endswith(".torrent"):
                LOGGER.warning("Skipping torrent file %s. Provide the downloaded PGN archive instead.", file_path)
                continue
            try:
                game_iter = iter_games_from_file(file_path)
                for game_index, game in game_iter:
                    stats["games_seen"] += 1
                    if stats["games_seen"] % max(config.progress_every, 1) == 0:
                        LOGGER.info(
                            "Scanned %s games, collected %s candidate positions.",
                            stats["games_seen"],
                            stats["candidates_seen"],
                        )

                    headers = dict(game.headers)
                    if not opening_matches(headers, config):
                        continue
                    if not game_metadata_matches(headers, config):
                        continue

                    mainline = list(game.mainline())
                    if not mainline:
                        continue

                    total_plies = len(mainline)
                    game_has_mate_finish = mainline[-1].board().is_checkmate()
                    game_key = headers.get("Site") or f"{Path(file_path).name}#{game_index}"

                    for ply_index, node in enumerate(mainline, start=1):
                        board = node.board()
                        plies_remaining = total_plies - ply_index

                        if not phase_matches(board, config, plies_remaining):
                            continue
                        if not move_number_matches(board, config):
                            continue
                        if not side_to_move_matches(board, config):
                            continue
                        if not material_matches(board, config):
                            continue

                        legal_moves = board.legal_moves.count()
                        if not position_is_playable(board, config, legal_moves, plies_remaining, game_has_mate_finish):
                            continue

                        pgn_eval = extract_eval_from_comment(node.comment)
                        normalized = normalized_fen(board)
                        selected_eval = choose_eval(board, config, pgn_eval, evaluator, normalized)
                        projected_filter = project_eval(selected_eval, board, config, for_filter=True) if selected_eval else None
                        if not eval_passes(projected_filter, config, selected_eval):
                            continue

                        projected_score = project_eval(selected_eval, board, config, for_filter=False) if selected_eval else None
                        next_move_uci, next_move_san = next_move_metadata(node)
                        white_elo = headers.get("WhiteElo")
                        black_elo = headers.get("BlackElo")
                        candidate = CandidatePosition(
                            game_key=game_key,
                            file_path=str(file_path),
                            game_index=game_index,
                            event=headers.get("Event"),
                            site=headers.get("Site"),
                            white=headers.get("White"),
                            black=headers.get("Black"),
                            white_elo=int(white_elo) if white_elo and white_elo.isdigit() else None,
                            black_elo=int(black_elo) if black_elo and black_elo.isdigit() else None,
                            average_rating=average_rating(headers),
                            rated="rated" in (headers.get("Event") or "").lower(),
                            time_class=infer_time_class(headers),
                            eco=headers.get("ECO"),
                            opening=headers.get("Opening"),
                            variation=headers.get("Variation"),
                            result=headers.get("Result"),
                            ply=ply_index,
                            move_number=board.fullmove_number,
                            plies_remaining=plies_remaining,
                            side_to_move="white" if board.turn == chess.WHITE else "black",
                            legal_moves=legal_moves,
                            fen=board.fen(),
                            normalized_fen=normalized,
                            piece_placement=board.board_fen(),
                            piece_placement_plus_turn=piece_placement_plus_turn(board),
                            material_signature=material_signature(board),
                            family_signature=family_signature(board),
                            dedupe_key=dedupe_key(board, config.dedupe),
                            next_move_uci=next_move_uci,
                            next_move_san=next_move_san,
                            eval_info=selected_eval,
                            eval_pawns_projected=projected_score,
                            training_label=classify_training_label(
                                projected_score,
                                "white" if board.turn == chess.WHITE else "black",
                            ),
                        )
                        candidates.append(candidate)
                        stats["candidates_seen"] += 1
            except Exception as exc:
                LOGGER.warning("Skipping unreadable file %s: %s", file_path, exc)
                continue

    position_counts = Counter(candidate.normalized_fen for candidate in candidates)
    family_counts = Counter(candidate.family_signature for candidate in candidates)
    for candidate in candidates:
        candidate.position_frequency = position_counts[candidate.normalized_fen]
        candidate.family_frequency = family_counts[candidate.family_signature]
        candidate.training_score = compute_training_score(candidate, config)

    candidates = [candidate for candidate in candidates if frequency_passes(candidate, config)]
    if config.selection_strategy == "best_training":
        candidates = per_game_best(candidates, config.positions_per_game)
    candidates = select_final_candidates(candidates, config)

    if config.mode == "summary":
        return build_summary(candidates, config)
    return [candidate.to_record() for candidate in candidates]
