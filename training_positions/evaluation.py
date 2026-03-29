from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import chess

from .models import EvalInfo, ExtractConfig

if TYPE_CHECKING:
    import chess.engine

EVAL_PATTERNS = (
    re.compile(r"\[%eval\s+([^\]]+)\]"),
    re.compile(r"\beval\s*[:=]\s*([+#\-M\d\.]+)", re.IGNORECASE),
)


def parse_eval_token(token: str, source: str) -> EvalInfo | None:
    raw = token.strip()
    if not raw:
        return None

    normalized = raw.upper().replace("MATE", "M")
    if normalized.startswith("#"):
        sign = -1 if raw[1:2] == "-" else 1
        value = raw[2:] if raw[1:2] in {"+", "-"} else raw[1:]
        return EvalInfo(source=source, raw=raw, mate=sign * int(value))
    if normalized.startswith("M"):
        sign = -1 if raw[1:2] == "-" else 1
        value = raw[2:] if raw[1:2] in {"+", "-"} else raw[1:]
        return EvalInfo(source=source, raw=raw, mate=sign * int(value))

    try:
        pawns = float(raw)
    except ValueError:
        return None
    return EvalInfo(source=source, raw=raw, pawns=pawns, cp=int(round(pawns * 100)))


def extract_eval_from_comment(comment: str | None) -> EvalInfo | None:
    if not comment:
        return None
    for pattern in EVAL_PATTERNS:
        match = pattern.search(comment)
        if match:
            return parse_eval_token(match.group(1), source="pgn")
    return None


def project_eval(eval_info: EvalInfo, board: chess.Board, config: ExtractConfig, for_filter: bool) -> float | None:
    if eval_info.mate is not None:
        if config.mate_score_policy == "exclude":
            return None
        if config.mate_score_policy == "cap":
            if for_filter:
                return None
            base_value = 100.0 if eval_info.mate > 0 else -100.0
        else:
            base_value = 100.0 if eval_info.mate > 0 else -100.0
    else:
        base_value = eval_info.pawns

    if base_value is None:
        return None

    if config.eval_perspective == "white":
        return base_value
    if config.eval_perspective == "side_to_move":
        return base_value if board.turn == chess.WHITE else -base_value
    if config.eval_perspective == "side_requested":
        if config.side_to_move == "white":
            return base_value
        if config.side_to_move == "black":
            return -base_value
        return base_value if board.turn == chess.WHITE else -base_value
    raise ValueError(f"Unsupported eval perspective: {config.eval_perspective}")


class StockfishEvaluator:
    def __init__(self, config: ExtractConfig) -> None:
        self.config = config
        self._engine: Any | None = None
        self._cache: dict[str, EvalInfo | None] = {}

    def __enter__(self) -> "StockfishEvaluator":
        if self.config.eval_source in {"stockfish", "pgn_or_stockfish"} and self.config.stockfish_path:
            import chess.engine

            self._engine = chess.engine.SimpleEngine.popen_uci(str(self.config.stockfish_path))
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    def evaluate(self, board: chess.Board, cache_key: str) -> EvalInfo | None:
        if cache_key in self._cache:
            return self._cache[cache_key]
        if self._engine is None:
            self._cache[cache_key] = None
            return None
        import chess.engine

        limit_kwargs = {"depth": self.config.stockfish_depth}
        if self.config.stockfish_nodes:
            limit_kwargs["nodes"] = self.config.stockfish_nodes
        info = self._engine.analyse(board, chess.engine.Limit(**limit_kwargs))
        score = info["score"].white()
        if score.is_mate():
            result = EvalInfo(source="stockfish", raw=f"#{score.mate()}", mate=score.mate())
        else:
            cp = score.score()
            result = EvalInfo(source="stockfish", raw=f"{cp / 100:.2f}", cp=cp, pawns=cp / 100)
        self._cache[cache_key] = result
        return result


def choose_eval(
    board: chess.Board,
    config: ExtractConfig,
    pgn_eval: EvalInfo | None,
    evaluator: StockfishEvaluator,
    cache_key: str,
) -> EvalInfo | None:
    if config.eval_source == "none":
        return pgn_eval
    if config.eval_source == "pgn":
        return pgn_eval
    if config.eval_source == "stockfish":
        return evaluator.evaluate(board, cache_key)
    if config.eval_source == "pgn_or_stockfish":
        return pgn_eval or evaluator.evaluate(board, cache_key)
    raise ValueError(f"Unsupported eval source: {config.eval_source}")


def eval_passes(eval_value: float | None, config: ExtractConfig, eval_info: EvalInfo | None) -> bool:
    if config.eval_min is None and config.eval_max is None:
        return True
    if eval_info is None or eval_value is None:
        return False
    if config.eval_min is not None and eval_value < config.eval_min:
        return False
    if config.eval_max is not None and eval_value > config.eval_max:
        return False
    return True
