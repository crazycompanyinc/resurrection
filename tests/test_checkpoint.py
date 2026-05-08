from __future__ import annotations

import pytest

from resurrection.checkpoint.engine import CheckpointEngine, CheckpointStrategy
from resurrection.checkpoint.incremental import IncrementalTracker
from resurrection.checkpoint.snapshot import SnapshotManager
from resurrection.core.models import CheckpointTrigger


def test_snapshot_round_trip(sample_state):
    manager = SnapshotManager()
    restored = manager.deserialize(manager.serialize(sample_state))
    assert restored == sample_state


def test_snapshot_hash_verification(sample_state):
    manager = SnapshotManager()
    blob = manager.serialize(sample_state)
    assert manager.verify(blob, manager.hash_state(blob))


def test_create_checkpoint_sets_parent(engine, sample_state):
    first = engine.create_checkpoint(sample_state)
    second = engine.create_checkpoint(sample_state)
    assert second.parent_checkpoint_id == first.id


def test_restore_latest_state(engine, sample_state):
    engine.create_checkpoint(sample_state)
    sample_state.variables["attempt"] = 9
    engine.create_checkpoint(sample_state)
    assert engine.restore_state("Felix-CTO").variables["attempt"] == 9


def test_restore_specific_state(engine, sample_state):
    first = engine.create_checkpoint(sample_state)
    sample_state.variables["attempt"] = 2
    engine.create_checkpoint(sample_state)
    assert engine.restore_state("Felix-CTO", first.id).variables["attempt"] == 1


def test_restore_missing_agent_raises(engine):
    with pytest.raises(LookupError):
        engine.restore_state("missing")


def test_pre_action_checkpoint(sample_state, db):
    eng = CheckpointEngine(db, strategy=CheckpointStrategy(pre_action=True, post_action=False))
    checkpoint = eng.pre_action(sample_state, {"name": "think"})
    assert checkpoint.trigger == CheckpointTrigger.PRE_ACTION


def test_post_action_auto_checkpoint_every_two(sample_state, db):
    eng = CheckpointEngine(db, strategy=CheckpointStrategy(post_action=False, auto_every_actions=2))
    assert eng.post_action(sample_state) is None
    checkpoint = eng.post_action(sample_state)
    assert checkpoint.trigger == CheckpointTrigger.AUTO


def test_error_checkpoint(sample_state, engine):
    checkpoint = engine.on_error(sample_state, RuntimeError("boom"))
    assert checkpoint.trigger == CheckpointTrigger.CRASH
    assert checkpoint.metadata["error"] == "boom"


def test_incremental_diff_and_apply():
    tracker = IncrementalTracker()
    before = {"a": 1, "b": {"x": 1}, "c": 3}
    after = {"a": 2, "b": {"x": 1, "y": 2}}
    patch = tracker.diff(before, after)
    assert tracker.apply(before, patch) == after
