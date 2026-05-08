from __future__ import annotations

from typing import Any

from resurrection.checkpoint.engine import CheckpointEngine
from resurrection.core.models import AgentCheckpoint, AgentState
from resurrection.debug.diff import StateDiff
from resurrection.debug.replay import ReplayEngine


class TimeTravel:
    def __init__(self, checkpoint_engine: CheckpointEngine) -> None:
        self.checkpoint_engine = checkpoint_engine
        self.differ = StateDiff(checkpoint_engine)
        self.replayer = ReplayEngine(checkpoint_engine)

    def timeline(self, agent_id: str) -> list[AgentCheckpoint]:
        return self.checkpoint_engine.list_checkpoints(agent_id, branch_id="*")

    def view(self, agent_id: str, checkpoint_id: str) -> AgentState:
        return self.checkpoint_engine.restore_state(agent_id, checkpoint_id)

    def compare(self, from_checkpoint_id: str, to_checkpoint_id: str) -> dict[str, Any]:
        return self.differ.compare(from_checkpoint_id, to_checkpoint_id)

    def replay(self, agent_id: str, from_checkpoint_id: str | None = None, to_checkpoint_id: str | None = None) -> list[dict[str, Any]]:
        return self.replayer.replay(agent_id, from_checkpoint_id, to_checkpoint_id)
