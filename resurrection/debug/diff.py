from __future__ import annotations

from typing import Any

from resurrection.checkpoint.engine import CheckpointEngine
from resurrection.checkpoint.incremental import IncrementalTracker


class StateDiff:
    def __init__(self, checkpoint_engine: CheckpointEngine) -> None:
        self.checkpoint_engine = checkpoint_engine
        self.tracker = IncrementalTracker()

    def compare(self, from_checkpoint_id: str, to_checkpoint_id: str) -> dict[str, Any]:
        first = self.checkpoint_engine.get_checkpoint(from_checkpoint_id)
        second = self.checkpoint_engine.get_checkpoint(to_checkpoint_id)
        first_state = self.checkpoint_engine.restore_state(first.agent_id, first.id).model_dump(mode="json")
        second_state = self.checkpoint_engine.restore_state(second.agent_id, second.id).model_dump(mode="json")
        return {
            "from": from_checkpoint_id,
            "to": to_checkpoint_id,
            "agent_id": first.agent_id,
            "changes": self.tracker.diff(first_state, second_state),
        }
