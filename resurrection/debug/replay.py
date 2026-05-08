from __future__ import annotations

from typing import Any

from resurrection.checkpoint.engine import CheckpointEngine


class ReplayEngine:
    def __init__(self, checkpoint_engine: CheckpointEngine) -> None:
        self.checkpoint_engine = checkpoint_engine

    def replay(self, agent_id: str, from_checkpoint_id: str | None = None, to_checkpoint_id: str | None = None) -> list[dict[str, Any]]:
        checkpoints = self.checkpoint_engine.list_checkpoints(agent_id, branch_id="*")
        started = from_checkpoint_id is None
        events: list[dict[str, Any]] = []
        for checkpoint in checkpoints:
            if checkpoint.id == from_checkpoint_id:
                started = True
            if not started:
                continue
            state = self.checkpoint_engine.restore_state(agent_id, checkpoint.id)
            events.append(
                {
                    "checkpoint_id": checkpoint.id,
                    "checkpoint_number": checkpoint.checkpoint_number,
                    "trigger": checkpoint.trigger.value,
                    "timestamp": checkpoint.timestamp.isoformat(),
                    "metadata": checkpoint.metadata,
                    "state": state.model_dump(mode="json"),
                }
            )
            if checkpoint.id == to_checkpoint_id:
                break
        return events
