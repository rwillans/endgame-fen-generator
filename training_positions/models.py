from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PIECE_TYPES = ("queens", "rooks", "bishops", "knights", "pawns")
COLORS = ("white", "black")


def lichess_analysis_url(fen: str) -> str:
    return f"https://lichess.org/analysis/{fen.replace(' ', '_')}"


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

    def to_payload(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "raw": self.raw,
            "pawns": self.pawns,
            "cp": self.cp,
            "mate": self.mate,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "EvalInfo | None":
        if not payload:
            return None
        return cls(
            source=str(payload.get("source") or "unknown"),
            raw=str(payload.get("raw") or ""),
            pawns=payload.get("pawns"),
            cp=payload.get("cp"),
            mate=payload.get("mate"),
        )


@dataclass
class ExtractConfig:
    input_path: Path | None = None
    output_path: Path | None = None
    output_format: str = "jsonl"
    mode: str = "extract"
    workflow: str | None = None
    dry_run_summary: bool = False
    white_constraints: dict[str, RangeConstraint | None] = field(default_factory=dict)
    black_constraints: dict[str, RangeConstraint | None] = field(default_factory=dict)
    opening: str | None = None
    variation: str | None = None
    eco: tuple[str, ...] = ()
    result_filters: tuple[str, ...] = ()
    variant_filters: tuple[str, ...] = ()
    event_contains: str | None = None
    min_rating: int = 1600
    time_controls: tuple[str, ...] = ("rapid", "classical")
    phase: str = "endgame"
    side_to_move: str = "either"
    min_move_number: int = 20
    sample_every_n_plies: int = 1
    only_after_queens_off: bool = False
    max_non_pawn_material: int | None = None
    stop_after_first_match_per_game: bool = False
    max_matches_per_game: int | None = None
    eval_min: float | None = None
    eval_max: float | None = None
    eval_source: str = "none"
    stockfish_path: Path | None = None
    stockfish_depth: int = 12
    stockfish_nodes: int | None = None
    mate_score_policy: str = "exclude"
    eval_perspective: str = "white"
    skip_engine_if_pgn_eval_present: bool = False
    eval_cache_path: Path | None = None
    reuse_eval_cache: bool = False
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
    write_candidates: Path | None = None
    write_header_pass_pgn: Path | None = None
    read_candidates: tuple[Path, ...] = ()
    candidate_format: str = "jsonl"
    append_candidates: bool = False
    max_candidates: int | None = None
    sample_games: int | None = None
    sample_candidates: int | None = None
    random_seed: int | None = None
    merge_candidates: tuple[Path, ...] = ()
    merge_outputs: tuple[Path, ...] = ()
    shard_label: str | None = None
    candidate_history_moves: int = 8

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
    time_control: str | None
    variant: str | None
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
    last_san_moves: list[str] = field(default_factory=list)
    white_material: dict[str, int] = field(default_factory=dict)
    black_material: dict[str, int] = field(default_factory=dict)
    embedded_eval: EvalInfo | None = None
    eval_info: EvalInfo | None = None
    eval_pawns_projected: float | None = None
    training_label: str = "balanced decision"
    training_score: float = 0.0
    position_frequency: int = 1
    family_frequency: int = 1
    shard_label: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "lichess_analysis_url": lichess_analysis_url(self.fen),
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
            "time_control": self.time_control,
            "variant": self.variant,
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
            "last_san_moves": self.last_san_moves,
            "white_material": self.white_material,
            "black_material": self.black_material,
            "embedded_eval": self.embedded_eval.to_payload() if self.embedded_eval else None,
            "eval": self.eval_info.to_payload() if self.eval_info else None,
            "eval_pawns_projected": self.eval_pawns_projected,
            "training_label": self.training_label,
            "training_score": round(self.training_score, 6),
            "position_frequency": self.position_frequency,
            "family_frequency": self.family_frequency,
            "shard_label": self.shard_label,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "CandidatePosition":
        return cls(
            game_key=str(record.get("game_key") or ""),
            file_path=str(record.get("file_path") or ""),
            game_index=int(record.get("game_index") or 0),
            event=record.get("event"),
            site=record.get("site"),
            white=record.get("white"),
            black=record.get("black"),
            white_elo=record.get("white_elo"),
            black_elo=record.get("black_elo"),
            average_rating=record.get("average_rating"),
            rated=bool(record.get("rated")),
            time_class=record.get("time_class"),
            time_control=record.get("time_control"),
            variant=record.get("variant"),
            eco=record.get("eco"),
            opening=record.get("opening"),
            variation=record.get("variation"),
            result=record.get("result"),
            ply=int(record.get("ply") or 0),
            move_number=int(record.get("move_number") or 0),
            plies_remaining=int(record.get("plies_remaining") or 0),
            side_to_move=str(record.get("side_to_move") or "either"),
            legal_moves=int(record.get("legal_moves") or 0),
            fen=str(record.get("fen") or ""),
            normalized_fen=str(record.get("normalized_fen") or ""),
            piece_placement=str(record.get("piece_placement") or ""),
            piece_placement_plus_turn=str(record.get("piece_placement_plus_turn") or ""),
            material_signature=str(record.get("material_signature") or ""),
            family_signature=str(record.get("family_signature") or ""),
            dedupe_key=str(record.get("dedupe_key") or ""),
            next_move_uci=record.get("next_move_uci"),
            next_move_san=record.get("next_move_san"),
            last_san_moves=list(record.get("last_san_moves") or []),
            white_material=dict(record.get("white_material") or {}),
            black_material=dict(record.get("black_material") or {}),
            embedded_eval=EvalInfo.from_payload(record.get("embedded_eval")),
            eval_info=EvalInfo.from_payload(record.get("eval")),
            eval_pawns_projected=record.get("eval_pawns_projected"),
            training_label=str(record.get("training_label") or "balanced decision"),
            training_score=float(record.get("training_score") or 0.0),
            position_frequency=int(record.get("position_frequency") or 1),
            family_frequency=int(record.get("family_frequency") or 1),
            shard_label=record.get("shard_label"),
        )


