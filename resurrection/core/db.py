from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from resurrection.core.models import AgentCheckpoint, AgentHeartbeat, CheckpointChain, StateBranch


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _loads_dict(value: str | None) -> dict[str, Any]:
    return json.loads(value) if value else {}


def _loads_list(value: str | None) -> list[str]:
    return json.loads(value) if value else []


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class ResurrectionDB:
    """Small SQLite repository for durable agent checkpoint data."""

    def __init__(self, path: str | Path = ".resurrection/resurrection.db") -> None:
        self.path = Path(path)

    @classmethod
    def in_memory(cls) -> "ResurrectionDB":
        return cls(":memory:")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    checkpoint_number INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    state_blob BLOB NOT NULL,
                    state_hash TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    metadata TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    branch_id TEXT,
                    is_delta INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_checkpoints_agent_number
                    ON checkpoints(agent_id, checkpoint_number);
                CREATE INDEX IF NOT EXISTS idx_checkpoints_branch
                    ON checkpoints(branch_id);

                CREATE TABLE IF NOT EXISTS chains (
                    agent_id TEXT PRIMARY KEY,
                    checkpoints TEXT NOT NULL,
                    current_checkpoint_id TEXT,
                    branch_points TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS branches (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    branch_name TEXT NOT NULL,
                    forked_from_checkpoint_id TEXT NOT NULL,
                    checkpoints TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_branches_agent ON branches(agent_id);

                CREATE TABLE IF NOT EXISTS heartbeats (
                    agent_id TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT NOT NULL
                );
                """
            )

    def save_checkpoint(self, checkpoint: AgentCheckpoint) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO checkpoints (
                    id, agent_id, checkpoint_number, timestamp, trigger, state_blob,
                    state_hash, parent_checkpoint_id, metadata, size_bytes, branch_id, is_delta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.id,
                    checkpoint.agent_id,
                    checkpoint.checkpoint_number,
                    checkpoint.timestamp.isoformat(),
                    checkpoint.trigger.value,
                    checkpoint.state_blob,
                    checkpoint.state_hash,
                    checkpoint.parent_checkpoint_id,
                    json.dumps(checkpoint.metadata, default=_json_default, sort_keys=True),
                    checkpoint.size_bytes,
                    checkpoint.branch_id,
                    int(checkpoint.is_delta),
                ),
            )

    def get_checkpoint(self, checkpoint_id: str) -> AgentCheckpoint | None:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM checkpoints WHERE id = ?", (checkpoint_id,)).fetchone()
        return self._checkpoint_from_row(row) if row else None

    def get_latest_checkpoint(self, agent_id: str, branch_id: str | None = None) -> AgentCheckpoint | None:
        self.initialize()
        sql = "SELECT * FROM checkpoints WHERE agent_id = ?"
        params: list[Any] = [agent_id]
        if branch_id is None:
            sql += " AND branch_id IS NULL"
        else:
            sql += " AND branch_id = ?"
            params.append(branch_id)
        sql += " ORDER BY checkpoint_number DESC LIMIT 1"
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return self._checkpoint_from_row(row) if row else None

    def list_checkpoints(self, agent_id: str, branch_id: str | None = None) -> list[AgentCheckpoint]:
        self.initialize()
        sql = "SELECT * FROM checkpoints WHERE agent_id = ?"
        params: list[Any] = [agent_id]
        if branch_id is None:
            sql += " AND branch_id IS NULL"
        elif branch_id != "*":
            sql += " AND branch_id = ?"
            params.append(branch_id)
        sql += " ORDER BY checkpoint_number ASC"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._checkpoint_from_row(row) for row in rows]

    def next_checkpoint_number(self, agent_id: str, branch_id: str | None = None) -> int:
        self.initialize()
        sql = "SELECT COALESCE(MAX(checkpoint_number), 0) + 1 AS n FROM checkpoints WHERE agent_id = ?"
        params: list[Any] = [agent_id]
        if branch_id is None:
            sql += " AND branch_id IS NULL"
        else:
            sql += " AND branch_id = ?"
            params.append(branch_id)
        with self.connect() as conn:
            return int(conn.execute(sql, params).fetchone()["n"])

    def save_chain(self, chain: CheckpointChain) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO chains (agent_id, checkpoints, current_checkpoint_id, branch_points)
                VALUES (?, ?, ?, ?)
                """,
                (
                    chain.agent_id,
                    json.dumps(chain.checkpoints),
                    chain.current_checkpoint_id,
                    json.dumps(chain.branch_points, sort_keys=True),
                ),
            )

    def get_chain(self, agent_id: str) -> CheckpointChain:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM chains WHERE agent_id = ?", (agent_id,)).fetchone()
        if not row:
            return CheckpointChain(agent_id=agent_id)
        return CheckpointChain(
            agent_id=row["agent_id"],
            checkpoints=_loads_list(row["checkpoints"]),
            current_checkpoint_id=row["current_checkpoint_id"],
            branch_points=_loads_dict(row["branch_points"]),
        )

    def save_branch(self, branch: StateBranch) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO branches (
                    id, agent_id, branch_name, forked_from_checkpoint_id, checkpoints, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    branch.id,
                    branch.agent_id,
                    branch.branch_name,
                    branch.forked_from_checkpoint_id,
                    json.dumps(branch.checkpoints),
                    branch.status,
                    branch.created_at.isoformat(),
                ),
            )

    def get_branch(self, branch_id: str) -> StateBranch | None:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM branches WHERE id = ?", (branch_id,)).fetchone()
        return self._branch_from_row(row) if row else None

    def list_branches(self, agent_id: str) -> list[StateBranch]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM branches WHERE agent_id = ? ORDER BY created_at ASC", (agent_id,)
            ).fetchall()
        return [self._branch_from_row(row) for row in rows]

    def save_heartbeat(self, heartbeat: AgentHeartbeat) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO heartbeats (agent_id, updated_at, status, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    heartbeat.agent_id,
                    heartbeat.updated_at.isoformat(),
                    heartbeat.status,
                    json.dumps(heartbeat.metadata, default=_json_default, sort_keys=True),
                ),
            )

    def get_heartbeat(self, agent_id: str) -> AgentHeartbeat | None:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM heartbeats WHERE agent_id = ?", (agent_id,)).fetchone()
        if not row:
            return None
        return AgentHeartbeat(
            agent_id=row["agent_id"],
            updated_at=_dt(row["updated_at"]),
            status=row["status"],
            metadata=_loads_dict(row["metadata"]),
        )

    @staticmethod
    def _checkpoint_from_row(row: sqlite3.Row) -> AgentCheckpoint:
        return AgentCheckpoint(
            id=row["id"],
            agent_id=row["agent_id"],
            checkpoint_number=row["checkpoint_number"],
            timestamp=_dt(row["timestamp"]),
            trigger=row["trigger"],
            state_blob=row["state_blob"],
            state_hash=row["state_hash"],
            parent_checkpoint_id=row["parent_checkpoint_id"],
            metadata=_loads_dict(row["metadata"]),
            size_bytes=row["size_bytes"],
            branch_id=row["branch_id"],
            is_delta=bool(row["is_delta"]),
        )

    @staticmethod
    def _branch_from_row(row: sqlite3.Row) -> StateBranch:
        return StateBranch(
            id=row["id"],
            agent_id=row["agent_id"],
            branch_name=row["branch_name"],
            forked_from_checkpoint_id=row["forked_from_checkpoint_id"],
            checkpoints=_loads_list(row["checkpoints"]),
            status=row["status"],
            created_at=_dt(row["created_at"]),
        )
