from __future__ import annotations

import json
import logging
import random
import time
from collections import Counter, deque
from collections.abc import Iterable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, TextIO

import chess
import chess.pgn

from .candidate_reader import iter_candidates_from_paths
from .candidate_writer import CandidateWriter
from .eval_cache import EvalCache
from .evaluation import StockfishEvaluator, choose_eval, eval_passes, extract_eval_from_comment, project_eval
from .filters import (
    average_rating,
    dedupe_key,
    family_signature,
    infer_time_class,
    is_rated_game,
    material_matches,
    material_signature,
    normalized_fen,
    piece_counts,
    piece_placement_plus_turn,
    position_is_playable,
    side_to_move_matches,
)
from .header_filter import dry_run_record, header_matches, update_header_summary
from .models import CandidatePosition, ExtractConfig
from .phase_gate import PhaseGate
from .scoring import classify_training_label, compute_training_score, per_game_best, select_final_candidates
from .sources import GameChunk, iter_game_chunks_from_file, iter_input_files, parse_game

LOGGER = logging.getLogger(__name__)


class ProgressTracker:
    def __init__(self, config: ExtractConfig) -> None:
        self.config = config
        self.stats = Counter()
        self.started_at = time.monotonic()
        self._last_report_games = 0

    def maybe_report(self, *, force: bool = False) -> None:
        games_scanned = self.stats["games_scanned"]
        if not force and games_scanned - self._last_report_games < max(self.config.progress_every, 1):
            return
        elapsed_seconds = max(time.monotonic() - self.started_at, 0.001)
        minutes = elapsed_seconds / 60.0
        LOGGER.info(
            "files=%s games=%s header_pass=%s header_pgn=%s replayed=%s inspected=%s material_pass=%s candidates=%s evaluated=%s elapsed=%.1fs games/min=%.1f positions/min=%.1f",
            self.stats["files_scanned"],
            self.stats["games_scanned"],
            self.stats["games_passing_header_filters"],
            self.stats["header_pass_pgn_written"],
            self.stats["games_replayed"],
            self.stats["positions_inspected"],
            self.stats["positions_passing_material_filters"],
            self.stats["candidate_positions_written"] or self.stats["candidates_found"],
            self.stats["positions_evaluated"],
            elapsed_seconds,
            games_scanned / minutes,
            self.stats["positions_inspected"] / minutes,
        )
        self._last_report_games = games_scanned


class HeaderPassPgnWriter:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._handle: TextIO | None = None
        self.written = 0

    def __enter__(self) -> "HeaderPassPgnWriter":
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.path.open("w", encoding="utf-8", newline="")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def write_chunk(self, chunk: GameChunk) -> None:
        if self._handle is None:
            return
        self._handle.write(chunk.raw_pgn)
        self._handle.write("\n\n")
        self.written += 1


def next_move_metadata(node: chess.pgn.ChildNode, board: chess.Board) -> tuple[str | None, str | None]:
    if not node.variations:
        return None, None
    next_move = node.variations[0].move
    try:
        next_move_san = board.san(next_move)
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


def reservoir_sample(items: Iterable[Any], limit: int, rng: random.Random) -> list[Any]:
    sample: list[Any] = []
    for index, item in enumerate(items, start=1):
        if len(sample) < limit:
            sample.append(item)
            continue
        chosen = rng.randint(1, index)
        if chosen <= limit:
            sample[chosen - 1] = item
    return sample


def _candidate_input_paths(config: ExtractConfig) -> tuple[Path, ...]:
    return config.read_candidates + config.merge_candidates


def _output_record_key(record: dict[str, Any]) -> str:
    return str(record.get("dedupe_key") or record.get("normalized_fen") or record.get("fen") or json.dumps(record, sort_keys=True))


def merge_output_records(config: ExtractConfig) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in config.merge_outputs:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    continue
                key = _output_record_key(record)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(record)
    merged.sort(key=lambda record: float(record.get("training_score") or record.get("count") or 0.0), reverse=True)
    return merged[: config.max_positions]


def _iter_header_filtered_chunks(
    config: ExtractConfig,
    progress: ProgressTracker,
    header_pass_writer: HeaderPassPgnWriter | None = None,
) -> Iterator[GameChunk]:
    if config.input_path is None:
        return
    for file_path in iter_input_files(config.input_path):
        progress.stats["files_scanned"] += 1
        if file_path.name.lower().endswith(".torrent"):
            LOGGER.warning("Skipping torrent file %s. Provide the downloaded PGN archive instead.", file_path)
            continue
        try:
            for chunk in iter_game_chunks_from_file(file_path):
                progress.stats["games_scanned"] += 1
                if header_matches(chunk.headers, config):
                    progress.stats["games_passing_header_filters"] += 1
                    if header_pass_writer is not None:
                        header_pass_writer.write_chunk(chunk)
                        progress.stats["header_pass_pgn_written"] = header_pass_writer.written
                    yield chunk
                progress.maybe_report()
        except Exception as exc:
            LOGGER.warning("Skipping unreadable file %s: %s", file_path, exc)


def _iter_discovered_candidates(
    config: ExtractConfig,
    progress: ProgressTracker,
    header_pass_writer: HeaderPassPgnWriter | None = None,
) -> Iterator[CandidatePosition]:
    rng = random.Random(config.random_seed)
    chunk_iter: Iterable[GameChunk] = _iter_header_filtered_chunks(config, progress, header_pass_writer)
    if config.sample_games:
        chunk_iter = reservoir_sample(chunk_iter, config.sample_games, rng)
    for chunk in chunk_iter:
        yield from _extract_candidates_from_chunk(chunk, config, progress)


def _extract_candidates_from_chunk(chunk: GameChunk, config: ExtractConfig, progress: ProgressTracker) -> Iterator[CandidatePosition]:
    game = parse_game(chunk.raw_pgn)
    if game is None:
        return

    headers = dict(game.headers) if game.headers else dict(chunk.headers)
    end_node = game.end()
    total_plies = end_node.ply()
    if total_plies <= 0:
        return

    progress.stats["games_replayed"] += 1
    game_has_mate_finish = end_node.board().is_checkmate()
    game_key = headers.get("Site") or f"{Path(chunk.file_path).name}#{chunk.game_index}"
    board = game.board()
    node = game
    history: deque[str] = deque(maxlen=config.candidate_history_moves)
    phase_gate = PhaseGate(config)
    matches_in_game = 0

    for ply_index in range(1, total_plies + 1):
        if not node.variations:
            break
        child = node.variations[0]
        try:
            history.append(board.san(child.move))
        except ValueError:
            history.append(child.move.uci())
        board.push(child.move)
        node = child
        plies_remaining = total_plies - ply_index

        if not phase_gate.should_inspect(board, ply_index, plies_remaining):
            continue

        progress.stats["positions_inspected"] += 1
        if not side_to_move_matches(board, config):
            continue
        if not material_matches(board, config):
            continue
        progress.stats["positions_passing_material_filters"] += 1

        legal_moves = board.legal_moves.count()
        if not position_is_playable(board, config, legal_moves, plies_remaining, game_has_mate_finish):
            continue

        counts = piece_counts(board)
        embedded_eval = extract_eval_from_comment(node.comment)
        normalized = normalized_fen(board)
        next_move_uci, next_move_san = next_move_metadata(node, board)
        white_elo = headers.get("WhiteElo")
        black_elo = headers.get("BlackElo")
        candidate = CandidatePosition(
            game_key=game_key,
            file_path=str(chunk.file_path),
            game_index=chunk.game_index,
            event=headers.get("Event"),
            site=headers.get("Site"),
            white=headers.get("White"),
            black=headers.get("Black"),
            white_elo=int(white_elo) if white_elo and white_elo.isdigit() else None,
            black_elo=int(black_elo) if black_elo and black_elo.isdigit() else None,
            average_rating=average_rating(headers),
            rated=is_rated_game(headers),
            time_class=infer_time_class(headers),
            time_control=headers.get("TimeControl"),
            variant=headers.get("Variant"),
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
            last_san_moves=list(history),
            white_material=counts["white"],
            black_material=counts["black"],
            embedded_eval=embedded_eval,
            shard_label=config.shard_label,
        )
        progress.stats["candidates_found"] += 1
        yield candidate
        matches_in_game += 1
        if config.max_matches_per_game and matches_in_game >= config.max_matches_per_game:
            break
        if config.stop_after_first_match_per_game:
            break


def _write_candidates(candidates: list[CandidatePosition], config: ExtractConfig, progress: ProgressTracker) -> None:
    if config.write_candidates is None:
        return
    with CandidateWriter(
        config.write_candidates,
        append=config.append_candidates,
        max_candidates=config.max_candidates,
    ) as writer:
        for candidate in candidates:
            if not writer.write(candidate):
                break
            progress.stats["candidate_positions_written"] += 1


def _stream_candidates_to_file(
    config: ExtractConfig,
    progress: ProgressTracker,
    header_pass_writer: HeaderPassPgnWriter | None = None,
) -> None:
    if config.write_candidates is None:
        return
    with CandidateWriter(
        config.write_candidates,
        append=config.append_candidates,
        max_candidates=config.max_candidates,
    ) as writer:
        for candidate in _iter_discovered_candidates(config, progress, header_pass_writer):
            if not writer.write(candidate):
                break
            progress.stats["candidate_positions_written"] += 1


def _collect_candidates(
    config: ExtractConfig,
    progress: ProgressTracker,
    header_pass_writer: HeaderPassPgnWriter | None = None,
) -> list[CandidatePosition]:
    rng = random.Random(config.random_seed)
    if config.input_path is not None:
        iterator: Iterable[CandidatePosition] = _iter_discovered_candidates(config, progress, header_pass_writer)
    else:
        iterator = iter_candidates_from_paths(_candidate_input_paths(config))

    if config.sample_candidates:
        return reservoir_sample(iterator, config.sample_candidates, rng)

    candidates: list[CandidatePosition] = []
    for candidate in iterator:
        candidates.append(candidate)
        if config.max_candidates is not None and len(candidates) >= config.max_candidates:
            break
    return candidates


def _evaluate_candidate(candidate: CandidatePosition, config: ExtractConfig, evaluator: StockfishEvaluator) -> CandidatePosition | None:
    board = chess.Board(candidate.fen)
    pgn_eval = candidate.embedded_eval
    selected_eval = choose_eval(board, config, pgn_eval, evaluator, candidate.normalized_fen)
    projected_filter = project_eval(selected_eval, board, config, for_filter=True) if selected_eval else None
    if not eval_passes(projected_filter, config, selected_eval):
        return None
    projected_score = project_eval(selected_eval, board, config, for_filter=False) if selected_eval else None
    return replace(
        candidate,
        eval_info=selected_eval,
        eval_pawns_projected=projected_score,
        training_label=classify_training_label(projected_score, candidate.side_to_move),
    )


def _finalize_candidates(candidates: list[CandidatePosition], config: ExtractConfig) -> list[CandidatePosition]:
    position_counts = Counter(candidate.normalized_fen for candidate in candidates)
    family_counts = Counter(candidate.family_signature for candidate in candidates)
    finalized: list[CandidatePosition] = []
    for candidate in candidates:
        enriched = replace(
            candidate,
            position_frequency=position_counts[candidate.normalized_fen],
            family_frequency=family_counts[candidate.family_signature],
        )
        enriched.training_score = compute_training_score(enriched, config)
        if frequency_passes(enriched, config):
            finalized.append(enriched)
    if config.selection_strategy == "best_training":
        finalized = per_game_best(finalized, config.positions_per_game)
    return select_final_candidates(finalized, config)


def _run_dry_run_summary(
    config: ExtractConfig,
    progress: ProgressTracker,
    header_pass_writer: HeaderPassPgnWriter | None = None,
) -> list[dict[str, Any]]:
    counters = {
        "opening": Counter(),
        "eco": Counter(),
        "time_control": Counter(),
    }
    if config.input_path is None:
        return []
    for _chunk in _iter_header_filtered_chunks(config, progress, header_pass_writer):
        update_header_summary(counters, _chunk.headers)
    progress.maybe_report(force=True)
    return [dry_run_record(progress.stats, counters, config.summary_limit)]


def _should_stream_candidate_discovery(config: ExtractConfig) -> bool:
    return (
        config.input_path is not None
        and config.write_candidates is not None
        and config.output_path is None
        and config.mode == "extract"
        and config.sample_candidates is None
        and config.eval_source in {"none", "pgn"}
        and config.eval_min is None
        and config.eval_max is None
    )


def _should_stream_header_pass_only(config: ExtractConfig) -> bool:
    return (
        config.input_path is not None
        and config.write_header_pass_pgn is not None
        and config.write_candidates is None
        and config.output_path is None
        and not config.dry_run_summary
    )


def extract_positions(config: ExtractConfig) -> list[dict[str, object]]:
    progress = ProgressTracker(config)

    if config.merge_outputs:
        merged = merge_output_records(config)
        progress.maybe_report(force=True)
        return merged

    with HeaderPassPgnWriter(config.write_header_pass_pgn) as header_pass_writer:
        if config.dry_run_summary:
            return _run_dry_run_summary(config, progress, header_pass_writer)

        if _should_stream_header_pass_only(config):
            for _chunk in _iter_header_filtered_chunks(config, progress, header_pass_writer):
                pass
            progress.maybe_report(force=True)
            return []

        if _should_stream_candidate_discovery(config):
            _stream_candidates_to_file(config, progress, header_pass_writer)
            progress.maybe_report(force=True)
            return []

        candidates = _collect_candidates(config, progress, header_pass_writer)

    if config.write_candidates is not None and config.input_path is not None:
        _write_candidates(candidates, config, progress)

    with EvalCache(config.eval_cache_path, reuse=config.reuse_eval_cache) as eval_cache:
        with StockfishEvaluator(config, eval_cache=eval_cache) as evaluator:
            evaluated: list[CandidatePosition] = []
            for candidate in candidates:
                enriched = _evaluate_candidate(candidate, config, evaluator)
                progress.stats["positions_evaluated"] = evaluator.analysis_calls
                if enriched is not None:
                    evaluated.append(enriched)

    if config.write_candidates is not None and config.input_path is None:
        _write_candidates(evaluated, config, progress)

    selected = _finalize_candidates(evaluated, config)
    progress.stats["positions_evaluated"] = max(progress.stats["positions_evaluated"], 0)
    progress.maybe_report(force=True)

    if config.mode == "summary":
        return build_summary(selected, config)
    return [candidate.to_record() for candidate in selected]
