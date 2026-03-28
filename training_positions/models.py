from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PIECE_TYPES = ("queens", "rooks", "bishops", "knights", "pawns")
COLORS = ("white", "black")


@dataclass(frozen=True)
class RangeConstraint:
    minimum: int
    maximum: int

    def matches(self, value: int) -> bool:
        return self.minimum <= value <= self.maximum


@dataclass
class EvalInfo:
    source: str
    raw: str
    pawns: float | None = None
    cp: int | None = None
    mate: int | None = None


@dataclass
class ExtractConfig:
    input_path: Path
    output_path: Path
    output_format: str = "jsonl"
    mode: str = "extract"
    white_constraints: dict[str, RangeConstraint | None] = field(default_factory=dict)
    black_constraints: dict[str, RangeConstraint | None] = field(default_factory=dict)
    opening: str | None = None
    variation: str | None = None
    eco: tuple[str, ...] = ()
    min_rating: int = 1600
    time_controls: tuple[str, ...] = ("blitz", "rapid", "classical")
    phase: str = "endgame"
    side_to_move: str = "either"
    min_move_number: int = 20
    eval_min: float | None = None
    eval_max: float | None = None
    eval_source: str = "none"
    stockfish_path: Path | None = None
    stockfish_depth: int = 12
    stockfish_nodes: int | None = None
    mate_score_policy: str = "exclude"
    eval_perspective: str = "white"
    max_positions: int = 100
    positions_per_game: int = 1
    dedupe: str = "normalized_fen"
    sort_by: str = "training_value"
    min_legal_moves: int = 2
    min_plies_remaining: int = 4
    exclude_checkmate_nearby: bool = True
    checkmate_nearby_plies: int = 2
    training_bias: str = "balanced"
    min_position_frequency: int = 1
    min_family_frequency: int = 1
    commonness_mode: str = "either"
    cluster_similar: bool = False
    max_similar_per_cluster: int = 2
    simplified_non_pawn_threshold: int = 18
    endgame_non_pawn_threshold: int = 12
    final_phase_plies: int = 12
    diversity: bool = True
    selection_strategy: str = "best_training"
    progress_every: int = 1000
    allow_unrated: bool = False
    allow_casual: bool = False
    allow_nonstandard: bool = False
    summary_limit: int = 50
    log_level: str = "INFO"

    def constraints_for(self, color: str) -> dict[str, RangeConstraint | None]:
        return self.white_constraints if color == "white" else self.black_constraints


@dataclass
class CandidatePosition:
    game_key: str
    file_path: str
    game_index: int
    event: str | None
    site: str | None
    white: str | None
    black: str | None
    white_elo: int | None
    black_elo: int | None
    average_rating: float | None
    rated: bool
    time_class: str | None
    eco: str | None
    opening: str | None
    variation: str | None
    result: str | None
    ply: int
    move_number: int
    plies_remaining: int
    side_to_move: str
    legal_moves: int
    fen: str
    normalized_fen: str
    piece_placement: str
    piece_placement_plus_turn: str
    material_signature: str
    family_signature: str
    dedupe_key: str
    next_move_uci: str | None
    next_move_san: str | None
    eval_info: EvalInfo | None
    eval_pawns_projected: float | None
    training_label: str
    training_score: float = 0.0
    position_frequency: int = 1
    family_frequency: int = 1

    def to_record(self) -> dict[str, Any]:
        eval_payload = None
        if self.eval_info is not None:
            eval_payload = {
                "source": self.eval_info.source,
                "raw": self.eval_info.raw,
                "pawns": self.eval_info.pawns,
                "cp": self.eval_info.cp,
                "mate": self.eval_info.mate,
            }
        return {
            "game_key": self.game_key,
            "file_path": self.file_path,
            "game_index": self.game_index,
            "event": self.event,
            "site": self.site,
            "white": self.white,
            "black": self.black,
            "white_elo": self.white_elo,
            "black_elo": self.black_elo,
            "average_rating": self.average_rating,
            "rated": self.rated,
            "time_class": self.time_class,
            "eco": self.eco,
            "opening": self.opening,
            "variation": self.variation,
            "result": self.result,
            "ply": self.ply,
            "move_number": self.move_number,
            "plies_remaining": self.plies_remaining,
            "side_to_move": self.side_to_move,
            "legal_moves": self.legal_moves,
            "fen": self.fen,
            "normalized_fen": self.normalized_fen,
            "piece_placement": self.piece_placement,
            "piece_placement_plus_turn": self.piece_placement_plus_turn,
            "material_signature": self.material_signature,
            "family_signature": self.family_signature,
            "dedupe_key": self.dedupe_key,
            "next_move_uci": self.next_move_uci,
            "next_move_san": self.next_move_san,
            "eval": eval_payload,
            "eval_pawns_projected": self.eval_pawns_projected,
            "training_label": self.training_label,
            "training_score": round(self.training_score, 6),
            "position_frequency": self.position_frequency,
            "family_frequency": self.family_frequency,
        }
