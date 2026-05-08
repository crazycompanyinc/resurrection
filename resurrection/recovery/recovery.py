from __future__ import annotations

from typing import Any, Literal

from resurrection.checkpoint.engine import CheckpointEngine
from resurrection.core.models import AgentState
from resurrection.recovery.detector import CrashDetector
from resurrection.recovery.restorer import StateRestorer


RecoveryMode = Literal["full", "selective", "fresh"]


class RecoveryManager:
    def __init__(
        self,
        checkpoint_engine: CheckpointEngine,
        crash_detector: CrashDetector | None = None,
        restorer: StateRestorer | None = None,
    ) -> None:
        self.checkpoint_engine = checkpoint_engine
        self.crash_detector = crash_detector or CrashDetector(checkpoint_engine.db)
        self.restorer = restorer or StateRestorer(checkpoint_engine)

    def options(self, agent_id: str) -> dict[str, Any]:
        checkpoints = self.checkpoint_engine.list_checkpoints(agent_id)
        return {
            "agent_id": agent_id,
            "has_checkpoints": bool(checkpoints),
            "latest_checkpoint_id": checkpoints[-1].id if checkpoints else None,
            "checkpoint_count": len(checkpoints),
            "modes": ["full", "selective", "fresh"] if checkpoints else ["fresh"],
            "health": self.crash_detector.health(agent_id),
        }

    def recover(
        self,
        agent_id: str,
        mode: RecoveryMode = "full",
        checkpoint_id: str | None = None,
        fields: list[str] | None = None,
    ) -> AgentState | dict[str, object]:
        if mode == "fresh":
            return AgentState(agent_id=agent_id)
        if mode == "selective":
            if not checkpoint_id:
                raise ValueError("Selective recovery requires checkpoint_id")
            return self.restorer.restore_selective(agent_id, checkpoint_id, fields or [])
        return self.restorer.restore_full(agent_id, checkpoint_id)
