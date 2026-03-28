from __future__ import annotations

from collections import Counter
from typing import Any

import chess

from .models import PIECE_TYPES, ExtractConfig, RangeConstraint

PIECE_NAME_TO_TYPE = {
    "queens": chess.QUEEN,
    "rooks": chess.ROOK,
    "bishops": chess.BISHOP,
    "knights": chess.KNIGHT,
    "pawns": chess.PAWN,
}

NON_PAWN_VALUES = {
    chess.QUEEN: 9,
    chess.ROOK: 5,
    chess.BISHOP: 3,
    chess.KNIGHT: 3,
}

TIME_CLASSES = ("ultrabullet", "bullet", "blitz", "rapid", "classical", "correspondence")


def parse_rating(headers: dict[str, str], key: str) -> int | None:
    raw = headers.get(key)
    if not raw or raw == "?":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def average_rating(headers: dict[str, str]) -> float | None:
    ratings = [value for value in (parse_rating(headers, "WhiteElo"), parse_rating(headers, "BlackElo")) if value is not None]
    if not ratings:
        return None
    return sum(ratings) / len(ratings)


def is_rated_game(headers: dict[str, str]) -> bool:
    event = (headers.get("Event") or "").lower()
    return "rated" in event


def is_standard_game(headers: dict[str, str]) -> bool:
    variant = (headers.get("Variant") or "Standard").lower()
    return variant in {"standard", "chess", "from position"}


def infer_time_class(headers: dict[str, str]) -> str | None:
    event = (headers.get("Event") or "").lower()
    for value in TIME_CLASSES:
        if value in event:
            return value

    time_control = headers.get("TimeControl")
    if not time_control or time_control in {"?", "-"}:
        return None

    if "+" in time_control:
        base_str, increment_str = time_control.split("+", 1)
    else:
        base_str, increment_str = time_control, "0"
    try:
        base = int(base_str)
        increment = int(increment_str)
    except ValueError:
        return None

    estimated_seconds = base + 40 * increment
    if estimated_seconds < 30:
        return "ultrabullet"
    if estimated_seconds < 180:
        return "bullet"
    if estimated_seconds < 480:
        return "blitz"
    if estimated_seconds < 1500:
        return "rapid"
    return "classical"


def eco_sort_key(code: str) -> tuple[int, int]:
    letters = "".join(char for char in code.upper() if char.isalpha()) or "A"
    digits = "".join(char for char in code if char.isdigit()) or "0"
    letter_value = 0
    for char in letters:
        letter_value = letter_value * 26 + (ord(char) - ord("A") + 1)
    return letter_value, int(digits)


def eco_matches(eco_value: str | None, filters: tuple[str, ...]) -> bool:
    if not filters:
        return True
    if not eco_value:
        return False
    eco_value = eco_value.upper()
    current = eco_sort_key(eco_value)
    for item in filters:
        token = item.upper()
        if ":" in token:
            start, end = token.split(":", 1)
            if eco_sort_key(start) <= current <= eco_sort_key(end):
                return True
        elif eco_value == token:
            return True
    return False


def opening_matches(headers: dict[str, str], config: ExtractConfig) -> bool:
    if not eco_matches(headers.get("ECO"), config.eco):
        return False
    if config.opening and config.opening.lower() not in (headers.get("Opening") or "").lower():
        return False
    if config.variation and config.variation.lower() not in (headers.get("Variation") or "").lower():
        return False
    return True


def game_metadata_matches(headers: dict[str, str], config: ExtractConfig) -> bool:
    if not config.allow_nonstandard and not is_standard_game(headers):
        return False
    if not config.allow_casual and not is_rated_game(headers):
        return False

    rating = average_rating(headers)
    if rating is None:
        if not config.allow_unrated:
            return False
    elif rating < config.min_rating:
        return False

    inferred_time = infer_time_class(headers)
    if config.time_controls:
        allowed = {item.lower() for item in config.time_controls}
        if inferred_time not in allowed:
            return False
    return True


def piece_counts(board: chess.Board) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {"white": {}, "black": {}}
    for color_name, color_value in (("white", chess.WHITE), ("black", chess.BLACK)):
        for piece_name, piece_type in PIECE_NAME_TO_TYPE.items():
            counts[color_name][piece_name] = len(board.pieces(piece_type, color_value))
    return counts


def _matches_constraints(values: dict[str, int], constraints: dict[str, RangeConstraint | None]) -> bool:
    for piece_name in PIECE_TYPES:
        constraint = constraints.get(piece_name)
        if constraint is not None and not constraint.matches(values[piece_name]):
            return False
    return True


def material_matches(board: chess.Board, config: ExtractConfig) -> bool:
    counts = piece_counts(board)
    return _matches_constraints(counts["white"], config.white_constraints) and _matches_constraints(
        counts["black"], config.black_constraints
    )


def total_non_pawn_material(board: chess.Board) -> int:
    total = 0
    for piece_type, value in NON_PAWN_VALUES.items():
        total += value * (len(board.pieces(piece_type, chess.WHITE)) + len(board.pieces(piece_type, chess.BLACK)))
    return total


def is_endgame(board: chess.Board, config: ExtractConfig) -> bool:
    queens_off = not board.pieces(chess.QUEEN, chess.WHITE) and not board.pieces(chess.QUEEN, chess.BLACK)
    return queens_off or total_non_pawn_material(board) <= config.endgame_non_pawn_threshold


def is_simplified(board: chess.Board, config: ExtractConfig) -> bool:
    return total_non_pawn_material(board) <= config.simplified_non_pawn_threshold


def phase_matches(board: chess.Board, config: ExtractConfig, plies_remaining: int) -> bool:
    if config.phase == "exact_material_only":
        return True
    if config.phase == "simplified":
        return is_simplified(board, config)
    if config.phase == "endgame":
        return is_endgame(board, config)
    if config.phase == "final_phase":
        return plies_remaining <= config.final_phase_plies
    return True


def move_number_matches(board: chess.Board, config: ExtractConfig) -> bool:
    return board.fullmove_number >= config.min_move_number


def side_to_move_matches(board: chess.Board, config: ExtractConfig) -> bool:
    if config.side_to_move == "either":
        return True
    return board.turn == (chess.WHITE if config.side_to_move == "white" else chess.BLACK)


def normalized_fen(board: chess.Board) -> str:
    ep_square = chess.square_name(board.ep_square) if board.ep_square is not None and board.has_legal_en_passant() else "-"
    return f"{board.board_fen()} {'w' if board.turn else 'b'} {board.castling_xfen()} {ep_square}"


def piece_placement_plus_turn(board: chess.Board) -> str:
    return f"{board.board_fen()} {'w' if board.turn else 'b'}"


def material_signature(board: chess.Board) -> str:
    counts = piece_counts(board)
    white_bits = "".join(f"{piece[0]}{counts['white'][piece]}" for piece in PIECE_TYPES)
    black_bits = "".join(f"{piece[0]}{counts['black'][piece]}" for piece in PIECE_TYPES)
    return f"W:{white_bits}|B:{black_bits}"


def pawn_structure_signature(board: chess.Board) -> str:
    def file_counts(color: chess.Color) -> str:
        counts = Counter(chess.square_file(square) for square in board.pieces(chess.PAWN, color))
        return ",".join(str(counts.get(index, 0)) for index in range(8))

    return f"W:{file_counts(chess.WHITE)}|B:{file_counts(chess.BLACK)}"


def family_signature(board: chess.Board) -> str:
    return f"{material_signature(board)}|P:{pawn_structure_signature(board)}"


def dedupe_key(board: chess.Board, mode: str) -> str:
    if mode == "none":
        return normalized_fen(board) + f"|{board.fullmove_number}|{board.halfmove_clock}"
    if mode == "full_fen":
        return board.fen()
    if mode == "normalized_fen":
        return normalized_fen(board)
    if mode == "piece_placement":
        return board.board_fen()
    if mode == "piece_placement_plus_turn":
        return piece_placement_plus_turn(board)
    if mode == "material_signature":
        return material_signature(board)
    if mode == "family_signature":
        return family_signature(board)
    raise ValueError(f"Unsupported dedupe mode: {mode}")


def position_is_playable(
    board: chess.Board,
    config: ExtractConfig,
    legal_moves: int,
    plies_remaining: int,
    game_has_mate_finish: bool,
) -> bool:
    if board.is_game_over(claim_draw=False):
        return False
    if legal_moves < config.min_legal_moves:
        return False
    if plies_remaining < config.min_plies_remaining:
        return False
    if config.exclude_checkmate_nearby and game_has_mate_finish and plies_remaining <= config.checkmate_nearby_plies:
        return False
    return True


def flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    eval_info = record.pop("eval", None)
    if eval_info:
        for key, value in eval_info.items():
            record[f"eval_{key}"] = value
    return record
