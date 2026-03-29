from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from .models import CandidatePosition


class CandidateWriter:
    def __init__(self, path: Path, *, append: bool = False, max_candidates: int | None = None) -> None:
        self.path = path
        self.append = append
        self.max_candidates = max_candidates
        self.written = 0
        self._handle: TextIO | None = None

    def __enter__(self) -> "CandidateWriter":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a" if self.append else "w", encoding="utf-8", newline="")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    @property
    def limit_reached(self) -> bool:
        return self.max_candidates is not None and self.written >= self.max_candidates

    def write(self, candidate: CandidatePosition) -> bool:
        if self._handle is None:
            raise RuntimeError("CandidateWriter must be used as a context manager.")
        if self.limit_reached:
            return False
        self._handle.write(json.dumps(candidate.to_record(), ensure_ascii=True) + "\n")
        self.written += 1
        return True
