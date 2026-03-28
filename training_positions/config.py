from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .models import COLORS, PIECE_TYPES, ExtractConfig, RangeConstraint

DEFAULTS: dict[str, Any] = {
    "output_format": None,
    "mode": "extract",
    "opening": None,
    "variation": None,
    "eco": None,
    "min_rating": 1600,
    "time_controls": "blitz,rapid,classical",
    "phase": "endgame",
    "side_to_move": "either",
    "min_move_number": 20,
    "eval_min": None,
    "eval_max": None,
    "eval_source": "none",
    "stockfish_path": None,
    "stockfish_depth": 12,
    "stockfish_nodes": None,
    "mate_score_policy": "exclude",
    "eval_perspective": "white",
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
    parser.add_argument("--opening")
    parser.add_argument("--variation")
    parser.add_argument("--eco", help="ECO exact code, comma-separated list, or range like D30:D69.")
    parser.add_argument("--min-rating", type=int)
    parser.add_argument("--time-controls", help="Comma-separated time classes such as blitz,rapid,classical.")
    parser.add_argument("--phase", choices=("exact_material_only", "simplified", "endgame", "final_phase"))
    parser.add_argument("--side-to-move", choices=("either", "white", "black"))
    parser.add_argument("--min-move-number", type=int)
    parser.add_argument("--eval-min", type=float)
    parser.add_argument("--eval-max", type=float)
    parser.add_argument("--eval-source", choices=("none", "pgn", "stockfish", "pgn_or_stockfish"))
    parser.add_argument("--stockfish-path")
    parser.add_argument("--stockfish-depth", type=int)
    parser.add_argument("--stockfish-nodes", type=int)
    parser.add_argument("--mate-score-policy", choices=("exclude", "cap", "include"))
    parser.add_argument("--eval-perspective", choices=("white", "side_to_move", "side_requested"))
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


def infer_output_format(output_path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    suffix = output_path.suffix.lower()
    return {
        ".jsonl": "jsonl",
        ".csv": "csv",
        ".fen": "fen",
        ".pgn": "pgn",
        ".html": "html",
    }.get(suffix, "jsonl")


def build_config(args: argparse.Namespace) -> ExtractConfig:
    settings = dict(DEFAULTS)
    if args.config:
        settings.update(parse_config_file(args.config))
    for key, value in vars(args).items():
        if value is not None:
            settings[key] = value

    input_path = settings.get("input_path")
    output_path = settings.get("output_path")
    if not input_path:
        raise ValueError("--input is required unless supplied via config.")
    if not output_path:
        raise ValueError("--output is required unless supplied via config.")

    output_path_obj = Path(output_path)
    return ExtractConfig(
        input_path=Path(input_path),
        output_path=output_path_obj,
        output_format=infer_output_format(output_path_obj, settings.get("output_format")),
        mode=str(settings["mode"]),
        white_constraints=normalize_piece_settings(settings, "white"),
        black_constraints=normalize_piece_settings(settings, "black"),
        opening=settings.get("opening"),
        variation=settings.get("variation"),
        eco=split_csv(settings.get("eco")),
        min_rating=int(settings["min_rating"]),
        time_controls=split_csv(settings.get("time_controls")),
        phase=str(settings["phase"]),
        side_to_move=str(settings["side_to_move"]),
        min_move_number=int(settings["min_move_number"]),
        eval_min=settings.get("eval_min"),
        eval_max=settings.get("eval_max"),
        eval_source=str(settings["eval_source"]),
        stockfish_path=Path(settings["stockfish_path"]) if settings.get("stockfish_path") else None,
        stockfish_depth=int(settings["stockfish_depth"]),
        stockfish_nodes=settings.get("stockfish_nodes"),
        mate_score_policy=str(settings["mate_score_policy"]),
        eval_perspective=str(settings["eval_perspective"]),
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
    )
