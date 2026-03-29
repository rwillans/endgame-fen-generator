from __future__ import annotations

import chess

from .filters import phase_matches, total_non_pawn_material
from .models import ExtractConfig


class PhaseGate:
    def __init__(self, config: ExtractConfig) -> None:
        self.config = config
        self._first_open_ply: int | None = None

    def gate_open(self, board: chess.Board, plies_remaining: int) -> bool:
        if board.fullmove_number < self.config.min_move_number:
            return False
        if self.config.only_after_queens_off and (
            board.pieces(chess.QUEEN, chess.WHITE) or board.pieces(chess.QUEEN, chess.BLACK)
        ):
            return False
        if self.config.max_non_pawn_material is not None:
            if total_non_pawn_material(board) > self.config.max_non_pawn_material:
                return False
        return phase_matches(board, self.config, plies_remaining)

    def should_inspect(self, board: chess.Board, ply_index: int, plies_remaining: int) -> bool:
        if not self.gate_open(board, plies_remaining):
            return False
        if self._first_open_ply is None:
            self._first_open_ply = ply_index
        interval = max(self.config.sample_every_n_plies, 1)
        return (ply_index - self._first_open_ply) % interval == 0
