from __future__ import annotations

from resurrection.core.models import AgentCheckpoint, AgentHeartbeat, AgentState, CheckpointChain, CheckpointTrigger, StateBranch


def test_agent_state_defaults():
    state = AgentState(agent_id="a1")
    assert state.context_window == []
    assert state.variables == {}
    assert state.pending_actions == []


def test_checkpoint_model_requires_size_and_hash():
    checkpoint = AgentCheckpoint(
        agent_id="a1",
        checkpoint_number=1,
        trigger=CheckpointTrigger.MANUAL,
        state_blob=b"{}",
        state_hash="abc",
        size_bytes=2,
    )
    assert checkpoint.trigger == CheckpointTrigger.MANUAL
    assert checkpoint.id.startswith("chk_")


def test_db_saves_and_gets_checkpoint(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    loaded = engine.db.get_checkpoint(checkpoint.id)
    assert loaded is not None
    assert loaded.id == checkpoint.id
    assert loaded.state_hash == checkpoint.state_hash


def test_db_lists_checkpoints_in_number_order(engine, sample_state):
    c1 = engine.create_checkpoint(sample_state)
    sample_state.variables["attempt"] = 2
    c2 = engine.create_checkpoint(sample_state)
    assert [c.id for c in engine.list_checkpoints(sample_state.agent_id)] == [c1.id, c2.id]


def test_db_latest_checkpoint(engine, sample_state):
    engine.create_checkpoint(sample_state)
    sample_state.task_progress["percent"] = 80
    c2 = engine.create_checkpoint(sample_state)
    assert engine.db.get_latest_checkpoint(sample_state.agent_id).id == c2.id


def test_chain_round_trip(db):
    chain = CheckpointChain(agent_id="a1", checkpoints=["c1"], current_checkpoint_id="c1", branch_points={"c1": ["b1"]})
    db.save_chain(chain)
    assert db.get_chain("a1") == chain


def test_branch_round_trip(db):
    branch = StateBranch(agent_id="a1", branch_name="exp", forked_from_checkpoint_id="c1", checkpoints=["c1"])
    db.save_branch(branch)
    assert db.get_branch(branch.id) == branch


def test_heartbeat_round_trip(db):
    heartbeat = AgentHeartbeat(agent_id="a1", status="running", metadata={"pid": 123})
    db.save_heartbeat(heartbeat)
    assert db.get_heartbeat("a1").metadata["pid"] == 123
