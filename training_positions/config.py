from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .models import COLORS, PIECE_TYPES, ExtractConfig, RangeConstraint

DEFAULTS: dict[str, Any] = {
    "output_format": None,
    "mode": "extract",
    "workflow": None,
    "dry_run_summary": False,
    "opening": None,
    "variation": None,
    "eco": None,
    "result": None,
    "variant": None,
    "event_contains": None,
    "min_rating": 1600,
    "time_controls": "rapid,classical",
    "phase": "endgame",
    "side_to_move": "either",
    "min_move_number": 20,
    "sample_every_n_plies": 1,
    "only_after_queens_off": False,
    "max_non_pawn_material": None,
    "stop_after_first_match_per_game": False,
    "max_matches_per_game": None,
    "eval_min": None,
    "eval_max": None,
    "eval_source": "none",
    "stockfish_path": None,
    "stockfish_depth": 12,
    "stockfish_nodes": None,
    "mate_score_policy": "exclude",
    "eval_perspective": "white",
    "skip_engine_if_pgn_eval_present": False,
    "eval_cache_path": None,
    "reuse_eval_cache": False,
    "max_positions": 100,
    "positions_per_game": 1,
    "dedupe": "normalized_fen",
    "sort_by": "training_value",
    "min_legal_moves": 2,
    "min_plies_remaining": 4,
    "exclude_checkmate_nearby": True,
    "checkmate_nearby_plies": 2,
    "training_bias": "balanced",
    "min_position_frequency": 1,
    "min_family_frequency": 1,
    "commonness_mode": "either",
    "cluster_similar": False,
    "max_similar_per_cluster": 2,
    "simplified_non_pawn_threshold": 18,
    "endgame_non_pawn_threshold": 12,
    "final_phase_plies": 12,
    "diversity": True,
    "selection_strategy": "best_training",
    "progress_every": 1000,
    "allow_unrated": False,
    "allow_casual": False,
    "allow_nonstandard": False,
    "summary_limit": 50,
    "log_level": "INFO",
    "write_candidates": None,
    "write_header_pass_pgn": None,
    "read_candidates": None,
    "candidate_format": "jsonl",
    "append_candidates": False,
    "max_candidates": None,
    "sample_games": None,
    "sample_candidates": None,
    "random_seed": None,
    "merge_candidates": None,
    "merge_outputs": None,
    "shard_label": None,
    "candidate_history_moves": 8,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract study-worthy chess positions from PGN, PGN.GZ, and PGN.ZST archives."
    )
    parser.add_argument("--config", help="Optional JSON or YAML config file.")
    parser.add_argument("--input", dest="input_path")
    parser.add_argument("--output", dest="output_path")
    parser.add_argument("--output-format", choices=("jsonl", "csv", "fen", "pgn", "html"))
    parser.add_argument("--mode", choices=("extract", "summary", "trainer_export"))
    parser.add_argument("--workflow", choices=("fast_training_pack",))
    parser.add_argument("--dry-run-summary", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--opening")
    parser.add_argument("--variation")
    parser.add_argument("--eco", help="ECO exact code, comma-separated list, or range like D30:D69.")
    parser.add_argument("--result", help="Comma-separated results to keep, for example 1-0,0-1,1/2-1/2.")
    parser.add_argument("--variant", help="Comma-separated Variant header filters.")
    parser.add_argument("--event-contains", help="Keep only games whose Event header contains this text.")
    parser.add_argument("--min-rating", type=int)
    parser.add_argument("--time-controls", help="Comma-separated time classes such as rapid,classical.")
    parser.add_argument("--phase", choices=("exact_material_only", "simplified", "endgame", "final_phase"))
    parser.add_argument("--side-to-move", choices=("either", "white", "black"))
    parser.add_argument("--min-move-number", type=int)
    parser.add_argument("--start-at-move", dest="start_at_move", type=int)
    parser.add_argument("--sample-every-n-plies", type=int)
    parser.add_argument("--only-after-queens-off", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--max-non-pawn-material", type=int)
    parser.add_argument("--stop-after-first-match-per-game", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--max-matches-per-game", type=int)
    parser.add_argument("--eval-min", type=float)
    parser.add_argument("--eval-max", type=float)
    parser.add_argument("--eval-source", choices=("none", "pgn", "stockfish", "pgn_or_stockfish"))
    parser.add_argument("--stockfish-path")
    parser.add_argument("--stockfish-depth", type=int)
    parser.add_argument("--stockfish-nodes", type=int)
    parser.add_argument("--mate-score-policy", choices=("exclude", "cap", "include"))
    parser.add_argument("--eval-perspective", choices=("white", "side_to_move", "side_requested"))
    parser.add_argument("--skip-engine-if-pgn-eval-present", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--eval-cache-path")
    parser.add_argument("--reuse-eval-cache", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--max-positions", type=int)
    parser.add_argument("--positions-per-game", type=int)
    parser.add_argument(
        "--dedupe",
        choices=(
            "none",
            "full_fen",
            "normalized_fen",
            "piece_placement",
            "piece_placement_plus_turn",
            "material_signature",
            "family_signature",
        ),
    )
    parser.add_argument("--sort-by", choices=("training_value", "commonness", "rating", "eval_abs"))
    parser.add_argument("--min-legal-moves", type=int)
    parser.add_argument("--min-plies-remaining", type=int)
    parser.add_argument("--checkmate-nearby-plies", type=int)
    parser.add_argument("--training-bias", choices=("balanced", "conversion", "defence", "mixed"))
    parser.add_argument("--min-position-frequency", type=int)
    parser.add_argument("--min-family-frequency", type=int)
    parser.add_argument("--commonness-mode", choices=("exact_position", "family", "either"))
    parser.add_argument("--max-similar-per-cluster", type=int)
    parser.add_argument("--simplified-non-pawn-threshold", type=int)
    parser.add_argument("--endgame-non-pawn-threshold", type=int)
    parser.add_argument("--final-phase-plies", type=int)
    parser.add_argument("--selection-strategy", choices=("best_training",))
    parser.add_argument("--progress-every", type=int)
    parser.add_argument("--summary-limit", type=int)
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    parser.add_argument("--write-candidates")
    parser.add_argument("--write-header-pass-pgn")
    parser.add_argument("--read-candidates")
    parser.add_argument("--candidate-format", choices=("jsonl",))
    parser.add_argument("--append-candidates", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--max-candidates", type=int)
    parser.add_argument("--sample-games", type=int)
    parser.add_argument("--sample-candidates", type=int)
    parser.add_argument("--random-seed", type=int)
    parser.add_argument("--merge-candidates", nargs="+")
    parser.add_argument("--merge-outputs", nargs="+")
    parser.add_argument("--shard-label")

    for name, help_text in (
        ("exclude-checkmate-nearby", "Reject positions that are only a few plies before a mating finish."),
        ("cluster-similar", "Limit repeated family signatures in the final output."),
        ("diversity", "Greedily diversify the final selection."),
        ("allow-unrated", "Keep games that do not expose rating headers."),
        ("allow-casual", "Keep casual games instead of rated-only."),
        ("allow-nonstandard", "Keep non-standard variants."),
    ):
        parser.add_argument(f"--{name}", action=argparse.BooleanOptionalAction, default=None, help=help_text)

    for color in COLORS:
        for piece in PIECE_TYPES:
            parser.add_argument(f"--{color}-{piece}", dest=f"{color}_{piece}")
    return parser


def parse_config_file(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
    elif path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ModuleNotFoundError as exc:
            raise RuntimeError("YAML config requested but PyYAML is not installed.") from exc
        payload = yaml.safe_load(text) or {}
    else:
        raise ValueError(f"Unsupported config format: {path.suffix}")
    if not isinstance(payload, dict):
        raise ValueError("Config file must define an object at the top level.")
    return payload


def parse_range_constraint(value: Any) -> RangeConstraint | None:
    if value is None or value == "":
        return None
    if isinstance(value, RangeConstraint):
        return value
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid material constraints.")
    if isinstance(value, int):
        return RangeConstraint(value, value)
    if isinstance(value, dict):
        minimum = int(value["min"])
        maximum = int(value.get("max", minimum))
        return RangeConstraint(minimum, maximum)
    if isinstance(value, str):
        raw = value.strip()
        if ":" in raw:
            left, right = raw.split(":", 1)
            return RangeConstraint(int(left), int(right))
        return RangeConstraint(int(raw), int(raw))
    raise ValueError(f"Unsupported material constraint: {value!r}")


def split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def normalize_piece_settings(settings: dict[str, Any], color: str) -> dict[str, RangeConstraint | None]:
    constraints: dict[str, RangeConstraint | None] = {}
    for piece in PIECE_TYPES:
        constraints[piece] = parse_range_constraint(settings.get(f"{color}_{piece}"))
    return constraints


def infer_output_format(output_path: Path | None, explicit: str | None) -> str:
    if explicit:
        return explicit
    if output_path is None:
        return "jsonl"
    suffix = output_path.suffix.lower()
    return {
        ".jsonl": "jsonl",
        ".csv": "csv",
        ".fen": "fen",
        ".pgn": "pgn",
        ".html": "html",
    }.get(suffix, "jsonl")


def apply_workflow_defaults(settings: dict[str, Any], explicit_keys: set[str]) -> None:
    if settings.get("workflow") != "fast_training_pack":
        return
    workflow_defaults = {
        "time_controls": "rapid,classical",
        "eval_source": "none",
        "positions_per_game": 1,
        "stop_after_first_match_per_game": True,
        "max_matches_per_game": 1,
        "sample_every_n_plies": 2,
        "only_after_queens_off": True,
    }
    for key, value in workflow_defaults.items():
        if key not in explicit_keys:
            settings[key] = value


def _as_path_tuple(value: Any) -> tuple[Path, ...]:
    if not value:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(Path(item) for item in value)
    return (Path(str(value)),)


def build_config(args: argparse.Namespace) -> ExtractConfig:
    settings = dict(DEFAULTS)
    if args.config:
        settings.update(parse_config_file(args.config))

    explicit_keys = {key for key, value in vars(args).items() if value is not None}
    for key, value in vars(args).items():
        if value is not None:
            settings[key] = value

    if settings.get("start_at_move") is not None:
        settings["min_move_number"] = settings["start_at_move"]

    apply_workflow_defaults(settings, explicit_keys)

    input_path = settings.get("input_path")
    read_candidates = _as_path_tuple(settings.get("read_candidates"))
    merge_candidates = _as_path_tuple(settings.get("merge_candidates"))
    merge_outputs = _as_path_tuple(settings.get("merge_outputs"))
    write_candidates = settings.get("write_candidates")
    write_header_pass_pgn = settings.get("write_header_pass_pgn")
    output_path = settings.get("output_path")

    if not input_path and not read_candidates and not merge_candidates and not merge_outputs:
        raise ValueError("--input, --read-candidates, --merge-candidates, or --merge-outputs is required.")
    if input_path and read_candidates:
        raise ValueError("Use either --input or --read-candidates, not both in the same run.")
    if merge_outputs and (input_path or read_candidates or merge_candidates):
        raise ValueError("--merge-outputs is a standalone mode and cannot be combined with raw or candidate inputs.")
    if settings.get("append_candidates") and not write_candidates:
        raise ValueError("--append-candidates requires --write-candidates.")
    if write_header_pass_pgn and not input_path:
        raise ValueError("--write-header-pass-pgn requires --input.")

    for numeric_key in ("sample_every_n_plies", "max_positions", "positions_per_game", "progress_every", "summary_limit"):
        if settings.get(numeric_key) is not None and int(settings[numeric_key]) < 1:
            raise ValueError(f"{numeric_key} must be at least 1.")
    for optional_positive in ("max_matches_per_game", "max_candidates", "sample_games", "sample_candidates"):
        if settings.get(optional_positive) is not None and int(settings[optional_positive]) < 1:
            raise ValueError(f"{optional_positive} must be at least 1 when provided.")

    if settings.get("stop_after_first_match_per_game") and settings.get("max_matches_per_game") is None:
        settings["max_matches_per_game"] = 1

    output_path_obj = Path(output_path) if output_path else None
    return ExtractConfig(
        input_path=Path(input_path) if input_path else None,
        output_path=output_path_obj,
        output_format=infer_output_format(output_path_obj, settings.get("output_format")),
        mode=str(settings["mode"]),
        workflow=settings.get("workflow"),
        dry_run_summary=bool(settings["dry_run_summary"]),
        white_constraints=normalize_piece_settings(settings, "white"),
        black_constraints=normalize_piece_settings(settings, "black"),
        opening=settings.get("opening"),
        variation=settings.get("variation"),
        eco=split_csv(settings.get("eco")),
        result_filters=split_csv(settings.get("result")),
        variant_filters=split_csv(settings.get("variant")),
        event_contains=settings.get("event_contains"),
        min_rating=int(settings["min_rating"]),
        time_controls=split_csv(settings.get("time_controls")),
        phase=str(settings["phase"]),
        side_to_move=str(settings["side_to_move"]),
        min_move_number=int(settings["min_move_number"]),
        sample_every_n_plies=int(settings["sample_every_n_plies"]),
        only_after_queens_off=bool(settings["only_after_queens_off"]),
        max_non_pawn_material=settings.get("max_non_pawn_material"),
        stop_after_first_match_per_game=bool(settings["stop_after_first_match_per_game"]),
        max_matches_per_game=settings.get("max_matches_per_game"),
        eval_min=settings.get("eval_min"),
        eval_max=settings.get("eval_max"),
        eval_source=str(settings["eval_source"]),
        stockfish_path=Path(settings["stockfish_path"]) if settings.get("stockfish_path") else None,
        stockfish_depth=int(settings["stockfish_depth"]),
        stockfish_nodes=settings.get("stockfish_nodes"),
        mate_score_policy=str(settings["mate_score_policy"]),
        eval_perspective=str(settings["eval_perspective"]),
        skip_engine_if_pgn_eval_present=bool(settings["skip_engine_if_pgn_eval_present"]),
        eval_cache_path=Path(settings["eval_cache_path"]) if settings.get("eval_cache_path") else None,
        reuse_eval_cache=bool(settings["reuse_eval_cache"]),
        max_positions=int(settings["max_positions"]),
        positions_per_game=int(settings["positions_per_game"]),
        dedupe=str(settings["dedupe"]),
        sort_by=str(settings["sort_by"]),
        min_legal_moves=int(settings["min_legal_moves"]),
        min_plies_remaining=int(settings["min_plies_remaining"]),
        exclude_checkmate_nearby=bool(settings["exclude_checkmate_nearby"]),
        checkmate_nearby_plies=int(settings["checkmate_nearby_plies"]),
        training_bias=str(settings["training_bias"]),
        min_position_frequency=int(settings["min_position_frequency"]),
        min_family_frequency=int(settings["min_family_frequency"]),
        commonness_mode=str(settings["commonness_mode"]),
        cluster_similar=bool(settings["cluster_similar"]),
        max_similar_per_cluster=int(settings["max_similar_per_cluster"]),
        simplified_non_pawn_threshold=int(settings["simplified_non_pawn_threshold"]),
        endgame_non_pawn_threshold=int(settings["endgame_non_pawn_threshold"]),
        final_phase_plies=int(settings["final_phase_plies"]),
        diversity=bool(settings["diversity"]),
        selection_strategy=str(settings["selection_strategy"]),
        progress_every=int(settings["progress_every"]),
        allow_unrated=bool(settings["allow_unrated"]),
        allow_casual=bool(settings["allow_casual"]),
        allow_nonstandard=bool(settings["allow_nonstandard"]),
        summary_limit=int(settings["summary_limit"]),
        log_level=str(settings["log_level"]),
        write_candidates=Path(write_candidates) if write_candidates else None,
        write_header_pass_pgn=Path(write_header_pass_pgn) if write_header_pass_pgn else None,
        read_candidates=read_candidates,
        candidate_format=str(settings["candidate_format"]),
        append_candidates=bool(settings["append_candidates"]),
        max_candidates=settings.get("max_candidates"),
        sample_games=settings.get("sample_games"),
        sample_candidates=settings.get("sample_candidates"),
        random_seed=settings.get("random_seed"),
        merge_candidates=merge_candidates,
        merge_outputs=merge_outputs,
        shard_label=settings.get("shard_label"),
        candidate_history_moves=int(settings["candidate_history_moves"]),
    )
