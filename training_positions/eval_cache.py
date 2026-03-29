from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import EvalInfo


class EvalCache:
    MISS = object()

    def __init__(self, path: Path | None, *, reuse: bool = False) -> None:
        self.path = path
        self.reuse = reuse
        self._conn: sqlite3.Connection | None = None
        self._pending_writes = 0

    def __enter__(self) -> "EvalCache":
        if self.path is None:
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS eval_cache (
                fen_key TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                raw TEXT NOT NULL,
                pawns REAL,
                cp INTEGER,
                mate INTEGER
            )
            """
        )
        self._conn.commit()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def get(self, fen_key: str) -> EvalInfo | object:
        if self._conn is None or not self.reuse:
            return self.MISS
        row = self._conn.execute(
            "SELECT source, raw, pawns, cp, mate FROM eval_cache WHERE fen_key = ?",
            (fen_key,),
        ).fetchone()
        if row is None:
            return self.MISS
        return EvalInfo(source=row[0], raw=row[1], pawns=row[2], cp=row[3], mate=row[4])

    def put(self, fen_key: str, eval_info: EvalInfo | None) -> None:
        if self._conn is None or eval_info is None:
            return
        self._conn.execute(
            """
            INSERT INTO eval_cache (fen_key, source, raw, pawns, cp, mate)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(fen_key) DO UPDATE SET
                source = excluded.source,
                raw = excluded.raw,
                pawns = excluded.pawns,
                cp = excluded.cp,
                mate = excluded.mate
            """,
            (fen_key, eval_info.source, eval_info.raw, eval_info.pawns, eval_info.cp, eval_info.mate),
        )
        self._pending_writes += 1
        if self._pending_writes >= 100:
            self._conn.commit()
            self._pending_writes = 0
