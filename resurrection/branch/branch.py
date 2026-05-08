from __future__ import annotations

from resurrection.checkpoint.engine import CheckpointEngine
from resurrection.core.models import StateBranch


class BranchManager:
    def __init__(self, checkpoint_engine: CheckpointEngine) -> None:
        self.checkpoint_engine = checkpoint_engine
        self.db = checkpoint_engine.db

    def create_branch(self, agent_id: str, name: str, from_checkpoint_id: str) -> StateBranch:
        checkpoint = self.checkpoint_engine.get_checkpoint(from_checkpoint_id)
        if checkpoint.agent_id != agent_id:
            raise ValueError(f"Checkpoint {from_checkpoint_id} belongs to {checkpoint.agent_id}, not {agent_id}")
        branch = StateBranch(
            agent_id=agent_id,
            branch_name=name,
            forked_from_checkpoint_id=from_checkpoint_id,
            checkpoints=[from_checkpoint_id],
        )
        self.db.save_branch(branch)
        chain = self.db.get_chain(agent_id)
        chain.branch_points.setdefault(from_checkpoint_id, []).append(branch.id)
        self.db.save_chain(chain)
        return branch

    def list_branches(self, agent_id: str) -> list[StateBranch]:
        return self.db.list_branches(agent_id)

    def abandon(self, branch_id: str) -> StateBranch:
        branch = self._get(branch_id)
        branch.status = "abandoned"
        self.db.save_branch(branch)
        return branch

    def _get(self, branch_id: str) -> StateBranch:
        branch = self.db.get_branch(branch_id)
        if not branch:
            raise LookupError(f"Branch not found: {branch_id}")
        return branch
