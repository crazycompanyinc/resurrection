from __future__ import annotations

import pytest

from resurrection.branch.branch import BranchManager
from resurrection.branch.merge import MergeEngine


def test_create_branch_records_branch_point(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    branch = BranchManager(engine).create_branch("Felix-CTO", "experiment", checkpoint.id)
    chain = engine.db.get_chain("Felix-CTO")
    assert chain.branch_points[checkpoint.id] == [branch.id]


def test_list_branches(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    branch = BranchManager(engine).create_branch("Felix-CTO", "experiment", checkpoint.id)
    assert BranchManager(engine).list_branches("Felix-CTO")[0].id == branch.id


def test_branch_checkpoint_appends_to_branch(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    branch = BranchManager(engine).create_branch("Felix-CTO", "experiment", checkpoint.id)
    sample_state.variables["branch"] = True
    branch_checkpoint = engine.create_checkpoint(sample_state, branch_id=branch.id)
    assert engine.db.get_branch(branch.id).checkpoints[-1] == branch_checkpoint.id


def test_merge_branch_creates_main_checkpoint(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    branch = BranchManager(engine).create_branch("Felix-CTO", "experiment", checkpoint.id)
    sample_state.variables["branch"] = True
    engine.create_checkpoint(sample_state, branch_id=branch.id)
    merged_branch, merged_checkpoint_id = MergeEngine(engine).merge("Felix-CTO", branch.id)
    assert merged_branch.status == "merged"
    assert engine.get_checkpoint(merged_checkpoint_id).branch_id is None


def test_merge_nonexistent_branch_raises(engine):
    with pytest.raises(LookupError):
        MergeEngine(engine).merge("Felix-CTO", "missing")


def test_abandon_branch(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    branch = BranchManager(engine).create_branch("Felix-CTO", "experiment", checkpoint.id)
    abandoned = BranchManager(engine).abandon(branch.id)
    assert abandoned.status == "abandoned"
