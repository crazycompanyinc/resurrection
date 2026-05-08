from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class CheckpointTrigger(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"
    PRE_ACTION = "pre_action"
    POST_ACTION = "post_action"
    CRASH = "crash"


BranchStatus = Literal["active", "merged", "abandoned"]


class AgentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    context_window: list[dict[str, Any]] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    current_task: str | None = None
    task_progress: dict[str, Any] = Field(default_factory=dict)
    pending_actions: list[dict[str, Any]] = Field(default_factory=list)
    completed_actions: list[dict[str, Any]] = Field(default_factory=list)
    learned_facts: dict[str, Any] = Field(default_factory=dict)
    emotional_state: dict[str, Any] | None = None
    custom_state: dict[str, Any] = Field(default_factory=dict)


class AgentCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("chk"))
    agent_id: str
    checkpoint_number: int
    timestamp: datetime = Field(default_factory=utc_now)
    trigger: CheckpointTrigger
    state_blob: bytes
    state_hash: str
    parent_checkpoint_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    size_bytes: int
    branch_id: str | None = None
    is_delta: bool = False


class CheckpointChain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    checkpoints: list[str] = Field(default_factory=list)
    current_checkpoint_id: str | None = None
    branch_points: dict[str, list[str]] = Field(default_factory=dict)


class StateBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: new_id("br"))
    agent_id: str
    branch_name: str
    forked_from_checkpoint_id: str
    checkpoints: list[str] = Field(default_factory=list)
    status: BranchStatus = "active"
    created_at: datetime = Field(default_factory=utc_now)


class AgentHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    updated_at: datetime = Field(default_factory=utc_now)
    status: Literal["running", "stopped", "crashed"] = "running"
    metadata: dict[str, Any] = Field(default_factory=dict)
