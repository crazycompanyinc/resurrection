from __future__ import annotations

from resurrection.checkpoint.engine import CheckpointEngine
from resurrection.core.models import AgentState


class StateRestorer:
    def __init__(self, checkpoint_engine: CheckpointEngine) -> None:
        self.checkpoint_engine = checkpoint_engine

    def restore_full(self, agent_id: str, checkpoint_id: str | None = None) -> AgentState:
        return self.checkpoint_engine.restore_state(agent_id, checkpoint_id)

    def restore_selective(self, agent_id: str, checkpoint_id: str, fields: list[str]) -> dict[str, object]:
        state = self.restore_full(agent_id, checkpoint_id)
        payload = state.model_dump()
        return {field: payload[field] for field in fields if field in payload}
