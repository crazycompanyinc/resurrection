from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from resurrection.branch.branch import BranchManager
from resurrection.branch.merge import MergeEngine
from resurrection.checkpoint.engine import CheckpointEngine
from resurrection.core.models import AgentState, CheckpointTrigger
from resurrection.debug.diff import StateDiff
from resurrection.debug.replay import ReplayEngine
from resurrection.recovery.detector import CrashDetector
from resurrection.recovery.recovery import RecoveryManager


class CheckpointRequest(BaseModel):
    state: AgentState | None = None
    trigger: CheckpointTrigger = CheckpointTrigger.MANUAL
    metadata: dict[str, Any] = Field(default_factory=dict)
    branch_id: str | None = None


class BranchRequest(BaseModel):
    name: str
    from_checkpoint_id: str


class MergeRequest(BaseModel):
    branch_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


def create_app(db_path: str | None = None) -> FastAPI:
    engine = CheckpointEngine.from_path(db_path or os.environ.get("RESURRECTION_DB", ".resurrection/resurrection.db"))
    recovery = RecoveryManager(engine)
    crash_detector = CrashDetector(engine.db)
    differ = StateDiff(engine)
    replayer = ReplayEngine(engine)
    branch_manager = BranchManager(engine)
    merge_engine = MergeEngine(engine)

    app = FastAPI(title="Resurrection", version="0.1.0")

    @app.get("/health")
    def service_health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/agents/{agent_id}/checkpoint")
    def create_checkpoint(agent_id: str, request: CheckpointRequest) -> dict[str, Any]:
        state = request.state or AgentState(agent_id=agent_id)
        if state.agent_id != agent_id:
            raise HTTPException(status_code=400, detail="State agent_id does not match path")
        checkpoint = engine.create_checkpoint(
            state,
            trigger=request.trigger,
            metadata=request.metadata,
            branch_id=request.branch_id,
        )
        return checkpoint.model_dump(mode="json", exclude={"state_blob"})

    @app.get("/agents/{agent_id}/checkpoints")
    def list_checkpoints(agent_id: str) -> list[dict[str, Any]]:
        return [c.model_dump(mode="json", exclude={"state_blob"}) for c in engine.list_checkpoints(agent_id)]

    @app.get("/agents/{agent_id}/restore")
    def restore(agent_id: str, checkpoint_id: str | None = None) -> dict[str, Any]:
        try:
            return engine.restore_state(agent_id, checkpoint_id).model_dump(mode="json")
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/agents/{agent_id}/recovery-options")
    def recovery_options(agent_id: str) -> dict[str, Any]:
        return recovery.options(agent_id)

    @app.get("/agents/{agent_id}/diff")
    def diff(agent_id: str, from_checkpoint_id: str, to_checkpoint_id: str) -> dict[str, Any]:
        result = differ.compare(from_checkpoint_id, to_checkpoint_id)
        if result["agent_id"] != agent_id:
            raise HTTPException(status_code=400, detail="Checkpoint agent_id does not match path")
        return result

    @app.get("/agents/{agent_id}/replay")
    def replay(agent_id: str, from_checkpoint_id: str | None = None, to_checkpoint_id: str | None = None) -> list[dict[str, Any]]:
        return replayer.replay(agent_id, from_checkpoint_id, to_checkpoint_id)

    @app.post("/agents/{agent_id}/branches")
    def create_branch(agent_id: str, request: BranchRequest) -> dict[str, Any]:
        branch = branch_manager.create_branch(agent_id, request.name, request.from_checkpoint_id)
        return branch.model_dump(mode="json")

    @app.get("/agents/{agent_id}/branches")
    def list_branches(agent_id: str) -> list[dict[str, Any]]:
        return [b.model_dump(mode="json") for b in branch_manager.list_branches(agent_id)]

    @app.post("/agents/{agent_id}/merge")
    def merge(agent_id: str, request: MergeRequest) -> dict[str, Any]:
        branch, checkpoint_id = merge_engine.merge(agent_id, request.branch_id, request.metadata)
        return {"branch": branch.model_dump(mode="json"), "merged_checkpoint_id": checkpoint_id}

    @app.post("/agents/{agent_id}/heartbeat")
    def heartbeat(agent_id: str, status: str = "running") -> dict[str, Any]:
        return crash_detector.heartbeat(agent_id, status=status).model_dump(mode="json")

    @app.get("/agents/{agent_id}/health")
    def agent_health(agent_id: str) -> dict[str, Any]:
        return crash_detector.health(agent_id)

    return app


app = create_app()
