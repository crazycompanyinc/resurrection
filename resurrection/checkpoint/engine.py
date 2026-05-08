from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from resurrection.checkpoint.snapshot import SnapshotManager
from resurrection.core.db import ResurrectionDB
from resurrection.core.models import AgentCheckpoint, AgentState, CheckpointTrigger


@dataclass(frozen=True)
class CheckpointStrategy:
    pre_action: bool = True
    post_action: bool = True
    auto_every_actions: int | None = None
    on_error: bool = True


class CheckpointEngine:
    def __init__(
        self,
        db: ResurrectionDB | None = None,
        snapshot_manager: SnapshotManager | None = None,
        strategy: CheckpointStrategy | None = None,
    ) -> None:
        self.db = db or ResurrectionDB()
        self.snapshot_manager = snapshot_manager or SnapshotManager()
        self.strategy = strategy or CheckpointStrategy()
        self._action_counts: dict[str, int] = {}
        self.db.initialize()

    @classmethod
    def from_path(cls, path: str | Path) -> "CheckpointEngine":
        return cls(ResurrectionDB(path))

    def create_checkpoint(
        self,
        state: AgentState | dict[str, Any],
        trigger: CheckpointTrigger | str = CheckpointTrigger.MANUAL,
        metadata: dict[str, Any] | None = None,
        branch_id: str | None = None,
        parent_checkpoint_id: str | None = None,
    ) -> AgentCheckpoint:
        agent_state = AgentState.model_validate(state)
        blob = self.snapshot_manager.serialize(agent_state)
        latest = self.db.get_latest_checkpoint(agent_state.agent_id, branch_id=branch_id)
        checkpoint = AgentCheckpoint(
            agent_id=agent_state.agent_id,
            checkpoint_number=self.db.next_checkpoint_number(agent_state.agent_id, branch_id=branch_id),
            trigger=CheckpointTrigger(trigger),
            state_blob=blob,
            state_hash=self.snapshot_manager.hash_state(blob),
            parent_checkpoint_id=parent_checkpoint_id or (latest.id if latest else None),
            metadata=metadata or {},
            size_bytes=self.snapshot_manager.size(blob),
            branch_id=branch_id,
            is_delta=False,
        )
        self.db.save_checkpoint(checkpoint)
        self._append_to_chain(checkpoint)
        self._append_to_branch(checkpoint)
        return checkpoint

    def pre_action(self, state: AgentState | dict[str, Any], action: dict[str, Any] | None = None) -> AgentCheckpoint | None:
        if not self.strategy.pre_action:
            return None
        return self.create_checkpoint(state, CheckpointTrigger.PRE_ACTION, {"action": action or {}})

    def post_action(self, state: AgentState | dict[str, Any], action: dict[str, Any] | None = None) -> AgentCheckpoint | None:
        agent_state = AgentState.model_validate(state)
        self._action_counts[agent_state.agent_id] = self._action_counts.get(agent_state.agent_id, 0) + 1
        checkpoint: AgentCheckpoint | None = None
        if self.strategy.post_action:
            checkpoint = self.create_checkpoint(agent_state, CheckpointTrigger.POST_ACTION, {"action": action or {}})
        every = self.strategy.auto_every_actions
        if every and self._action_counts[agent_state.agent_id] % every == 0:
            checkpoint = self.create_checkpoint(
                agent_state,
                CheckpointTrigger.AUTO,
                {"action_count": self._action_counts[agent_state.agent_id]},
            )
        return checkpoint

    def on_error(
        self,
        state: AgentState | dict[str, Any],
        error: BaseException | str,
        branch_id: str | None = None,
    ) -> AgentCheckpoint | None:
        if not self.strategy.on_error:
            return None
        return self.create_checkpoint(
            state,
            CheckpointTrigger.CRASH,
            {"error": str(error), "error_type": type(error).__name__},
            branch_id=branch_id,
        )

    def list_checkpoints(self, agent_id: str, branch_id: str | None = None) -> list[AgentCheckpoint]:
        return self.db.list_checkpoints(agent_id, branch_id=branch_id)

    def get_checkpoint(self, checkpoint_id: str) -> AgentCheckpoint:
        checkpoint = self.db.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise LookupError(f"Checkpoint not found: {checkpoint_id}")
        return checkpoint

    def restore_state(self, agent_id: str, checkpoint_id: str | None = None) -> AgentState:
        checkpoint = self.get_checkpoint(checkpoint_id) if checkpoint_id else self.db.get_latest_checkpoint(agent_id)
        if not checkpoint:
            raise LookupError(f"No checkpoints found for agent: {agent_id}")
        if checkpoint.agent_id != agent_id:
            raise ValueError(f"Checkpoint {checkpoint.id} belongs to {checkpoint.agent_id}, not {agent_id}")
        if not self.snapshot_manager.verify(checkpoint.state_blob, checkpoint.state_hash):
            raise ValueError(f"Checkpoint integrity check failed: {checkpoint.id}")
        return self.snapshot_manager.deserialize(checkpoint.state_blob)

    def _append_to_chain(self, checkpoint: AgentCheckpoint) -> None:
        if checkpoint.branch_id:
            return
        chain = self.db.get_chain(checkpoint.agent_id)
        if checkpoint.id not in chain.checkpoints:
            chain.checkpoints.append(checkpoint.id)
        chain.current_checkpoint_id = checkpoint.id
        self.db.save_chain(chain)

    def _append_to_branch(self, checkpoint: AgentCheckpoint) -> None:
        if not checkpoint.branch_id:
            return
        branch = self.db.get_branch(checkpoint.branch_id)
        if branch and checkpoint.id not in branch.checkpoints:
            branch.checkpoints.append(checkpoint.id)
            self.db.save_branch(branch)
