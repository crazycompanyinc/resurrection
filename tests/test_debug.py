from __future__ import annotations

from resurrection.debug.diff import StateDiff
from resurrection.debug.replay import ReplayEngine
from resurrection.debug.timetravel import TimeTravel


def test_state_diff_reports_changes(engine, sample_state):
    c1 = engine.create_checkpoint(sample_state)
    sample_state.variables["attempt"] = 2
    c2 = engine.create_checkpoint(sample_state)
    diff = StateDiff(engine).compare(c1.id, c2.id)
    assert diff["changes"]["variables"]["attempt"]["value"] == 2


def test_replay_returns_events(engine, sample_state):
    c1 = engine.create_checkpoint(sample_state)
    sample_state.variables["attempt"] = 2
    c2 = engine.create_checkpoint(sample_state)
    replay = ReplayEngine(engine).replay("Felix-CTO", c1.id, c2.id)
    assert [event["checkpoint_id"] for event in replay] == [c1.id, c2.id]


def test_replay_from_middle(engine, sample_state):
    engine.create_checkpoint(sample_state)
    sample_state.variables["attempt"] = 2
    c2 = engine.create_checkpoint(sample_state)
    replay = ReplayEngine(engine).replay("Felix-CTO", c2.id)
    assert len(replay) == 1


def test_time_travel_timeline(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    assert TimeTravel(engine).timeline("Felix-CTO")[0].id == checkpoint.id


def test_time_travel_view(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    assert TimeTravel(engine).view("Felix-CTO", checkpoint.id).agent_id == "Felix-CTO"


def test_time_travel_compare(engine, sample_state):
    c1 = engine.create_checkpoint(sample_state)
    sample_state.current_task = "Changed"
    c2 = engine.create_checkpoint(sample_state)
    assert TimeTravel(engine).compare(c1.id, c2.id)["changes"]["current_task"]["value"] == "Changed"
