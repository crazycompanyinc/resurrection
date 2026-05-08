from __future__ import annotations

from typing import Any

from resurrection.checkpoint.engine import CheckpointEngine
from resurrection.core.models import AgentState, CheckpointTrigger, StateBranch


class MergeEngine:
    def __init__(self, checkpoint_engine: CheckpointEngine) -> None:
        self.checkpoint_engine = checkpoint_engine
        self.db = checkpoint_engine.db

    def merge(self, agent_id: str, branch_id: str, metadata: dict[str, Any] | None = None) -> tuple[StateBranch, str]:
        branch = self.db.get_branch(branch_id)
        if not branch:
            raise LookupError(f"Branch not found: {branch_id}")
        if branch.agent_id != agent_id:
            raise ValueError(f"Branch {branch_id} belongs to {branch.agent_id}, not {agent_id}")
        if branch.status != "active":
            raise ValueError(f"Branch {branch_id} is {branch.status}, not active")
        if not branch.checkpoints:
            raise ValueError(f"Branch {branch_id} has no checkpoints to merge")

        latest_id = branch.checkpoints[-1]
        state = self.checkpoint_engine.restore_state(agent_id, latest_id)
        merged_state = AgentState.model_validate(state.model_dump())
        checkpoint = self.checkpoint_engine.create_checkpoint(
            merged_state,
            CheckpointTrigger.MANUAL,
            {
                "merge": True,
                "merged_branch_id": branch_id,
                "source_checkpoint_id": latest_id,
                **(metadata or {}),
            },
        )
        branch.status = "merged"
        self.db.save_branch(branch)
        return branch, checkpoint.id
