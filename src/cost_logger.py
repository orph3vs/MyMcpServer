"""SQLite-based request cost logger."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional


@dataclass(frozen=True)
class CostLogEntry:
    request_id: str
    risk_level: str
    mode: str
    tokens_in: int
    tokens_out: int
    cost: float
    latency: float
    score: float


class CostLogger:
    """Persists cost logs for all requests into SQLite."""

    def __init__(self, db_path: str = "data/cost_logs.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Provide a connection that is always closed.

        Note: sqlite3 connection context manager commits/rolls back transactions,
        but does not guarantee connection close on all runtimes.
        """
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_cost_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    tokens_in INTEGER NOT NULL,
                    tokens_out INTEGER NOT NULL,
                    cost REAL NOT NULL,
                    latency REAL NOT NULL,
                    score REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def log_request(self, entry: CostLogEntry) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO request_cost_logs (
                    request_id, risk_level, mode, tokens_in, tokens_out, cost, latency, score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.request_id,
                    entry.risk_level,
                    entry.mode,
                    entry.tokens_in,
                    entry.tokens_out,
                    entry.cost,
                    entry.latency,
                    entry.score,
                ),
            )
            conn.commit()

    def list_recent(self, limit: int = 50) -> List[CostLogEntry]:
        if limit <= 0:
            raise ValueError("limit must be positive")

        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT request_id, risk_level, mode, tokens_in, tokens_out, cost, latency, score
                FROM request_cost_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            CostLogEntry(
                request_id=row[0],
                risk_level=row[1],
                mode=row[2],
                tokens_in=row[3],
                tokens_out=row[4],
                cost=row[5],
                latency=row[6],
                score=row[7],
            )
            for row in rows
        ]

    def get_by_request_id(self, request_id: str) -> Optional[CostLogEntry]:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT request_id, risk_level, mode, tokens_in, tokens_out, cost, latency, score
                FROM request_cost_logs
                WHERE request_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()

        if row is None:
            return None

        return CostLogEntry(
            request_id=row[0],
            risk_level=row[1],
            mode=row[2],
            tokens_in=row[3],
            tokens_out=row[4],
            cost=row[5],
            latency=row[6],
            score=row[7],
        )
