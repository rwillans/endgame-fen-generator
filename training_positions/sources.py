from __future__ import annotations

import contextlib
import gzip
import io
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import chess.pgn
import zstandard

LOGGER = logging.getLogger(__name__)
HEADER_PATTERN = re.compile(r'^\[([A-Za-z0-9_]+)\s+"(.*)"\]\s*$')


@dataclass
class GameChunk:
    game_index: int
    file_path: Path
    headers: dict[str, str]
    raw_pgn: str


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


def _parse_header_line(line: str, headers: dict[str, str]) -> bool:
    match = HEADER_PATTERN.match(line.strip())
    if not match:
        return False
    headers[match.group(1)] = match.group(2).replace(r'\\"', '"').replace(r'\\\\', '\\')
    return True


def _trim_trailing_blank_lines(lines: list[str]) -> list[str]:
    trimmed = list(lines)
    while trimmed and not trimmed[-1].strip():
        trimmed.pop()
    return trimmed


def iter_game_chunks_from_file(path: Path) -> Iterator[GameChunk]:
    with open_text_stream(path) as handle:
        buffer: list[str] = []
        headers: dict[str, str] = {}
        state = "idle"
        previous_blank = False
        game_index = 0

        for line in handle:
            if state == "idle":
                if not line.strip():
                    continue
                buffer = [line]
                headers = {}
                state = "headers" if _parse_header_line(line, headers) else "movetext"
                previous_blank = not line.strip()
                continue

            if state == "headers":
                if _parse_header_line(line, headers):
                    buffer.append(line)
                    previous_blank = False
                    continue
                buffer.append(line)
                if line.strip():
                    state = "movetext"
                    previous_blank = False
                else:
                    previous_blank = True
                continue

            if line.startswith("[") and previous_blank:
                raw_pgn = "".join(_trim_trailing_blank_lines(buffer))
                if raw_pgn.strip():
                    game_index += 1
                    yield GameChunk(game_index=game_index, file_path=path, headers=dict(headers), raw_pgn=raw_pgn)
                buffer = [line]
                headers = {}
                _parse_header_line(line, headers)
                state = "headers"
                previous_blank = False
                continue

            buffer.append(line)
            previous_blank = not line.strip()

        raw_pgn = "".join(_trim_trailing_blank_lines(buffer))
        if raw_pgn.strip():
            game_index += 1
            yield GameChunk(game_index=game_index, file_path=path, headers=dict(headers), raw_pgn=raw_pgn)


def parse_game(raw_pgn: str) -> chess.pgn.Game | None:
    handle = io.StringIO(raw_pgn)
    return chess.pgn.read_game(handle)
