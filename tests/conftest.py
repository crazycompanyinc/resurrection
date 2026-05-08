from __future__ import annotations

import pytest

from resurrection.checkpoint.engine import CheckpointEngine
from resurrection.core.db import ResurrectionDB
from resurrection.core.models import AgentState


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "resurrection.db"


@pytest.fixture
def db(db_path):
    database = ResurrectionDB(db_path)
    database.initialize()
    return database


@pytest.fixture
def engine(db):
    return CheckpointEngine(db)


@pytest.fixture
def sample_state():
    return AgentState(
        agent_id="Felix-CTO",
        context_window=[{"role": "user", "content": "Build persistence"}],
        variables={"attempt": 1},
        current_task="Build checkpoint engine",
        task_progress={"percent": 25},
        pending_actions=[{"name": "write tests"}],
        completed_actions=[{"name": "design schema"}],
        learned_facts={"gap": "agent persistence"},
        emotional_state={"mood": "focused"},
        custom_state={"framework": "generic"},
    )
