from __future__ import annotations

import contextlib
import gzip
import io
import logging
from collections.abc import Iterator
from pathlib import Path

import chess.pgn
import zstandard

LOGGER = logging.getLogger(__name__)


def is_supported_input(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".pgn") or name.endswith(".pgn.gz") or name.endswith(".pgn.zst") or name.endswith(".torrent")


def iter_input_files(root: Path) -> Iterator[Path]:
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and is_supported_input(path):
            yield path


@contextlib.contextmanager
def open_text_stream(path: Path) -> Iterator[io.TextIOBase]:
    name = path.name.lower()
    if name.endswith(".torrent"):
        raise ValueError(f"{path} is a torrent descriptor, not a PGN archive.")
    if name.endswith(".pgn"):
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            yield handle
        return
    if name.endswith(".pgn.gz"):
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            yield handle
        return
    if name.endswith(".pgn.zst"):
        with path.open("rb") as raw_handle:
            with zstandard.ZstdDecompressor().stream_reader(raw_handle) as reader:
                with io.TextIOWrapper(reader, encoding="utf-8", errors="replace") as text_handle:
                    yield text_handle
        return
    raise ValueError(f"Unsupported input file: {path}")


def iter_games_from_file(path: Path) -> Iterator[tuple[int, chess.pgn.Game]]:
    with open_text_stream(path) as handle:
        game_index = 0
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            game_index += 1
            if getattr(game, "errors", None):
                LOGGER.warning("Skipping malformed fragments in %s game %s: %s", path, game_index, game.errors)
            yield game_index, game
