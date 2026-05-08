from __future__ import annotations

from datetime import timedelta
from typing import Any

from resurrection.core.db import ResurrectionDB
from resurrection.core.models import AgentHeartbeat, utc_now


class CrashDetector:
    def __init__(self, db: ResurrectionDB | None = None, stale_after_seconds: int = 60) -> None:
        self.db = db or ResurrectionDB()
        self.stale_after_seconds = stale_after_seconds
        self.db.initialize()

    def heartbeat(self, agent_id: str, status: str = "running", metadata: dict[str, Any] | None = None) -> AgentHeartbeat:
        heartbeat = AgentHeartbeat(agent_id=agent_id, status=status, metadata=metadata or {})
        self.db.save_heartbeat(heartbeat)
        return heartbeat

    def mark_stopped(self, agent_id: str) -> AgentHeartbeat:
        return self.heartbeat(agent_id, "stopped")

    def mark_crashed(self, agent_id: str, error: str | None = None) -> AgentHeartbeat:
        return self.heartbeat(agent_id, "crashed", {"error": error} if error else {})

    def health(self, agent_id: str) -> dict[str, Any]:
        heartbeat = self.db.get_heartbeat(agent_id)
        latest = self.db.get_latest_checkpoint(agent_id)
        if not heartbeat:
            status = "unknown"
            stale = True
        else:
            age = utc_now() - heartbeat.updated_at
            stale = age > timedelta(seconds=self.stale_after_seconds)
            status = "crashed" if heartbeat.status == "crashed" or stale else heartbeat.status
        return {
            "agent_id": agent_id,
            "status": status,
            "stale": stale,
            "last_heartbeat": heartbeat.updated_at.isoformat() if heartbeat else None,
            "latest_checkpoint_id": latest.id if latest else None,
        }

    def crashed(self, agent_id: str) -> bool:
        return self.health(agent_id)["status"] == "crashed"
