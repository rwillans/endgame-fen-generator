from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from .models import CandidatePosition


def iter_candidates_from_file(path: Path) -> Iterator[CandidatePosition]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                yield CandidatePosition.from_record(payload)


def iter_candidates_from_paths(paths: tuple[Path, ...]) -> Iterator[CandidatePosition]:
    for path in paths:
        yield from iter_candidates_from_file(path)
