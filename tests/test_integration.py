from __future__ import annotations

from click.testing import CliRunner

from resurrection.branch.branch import BranchManager
from resurrection.branch.merge import MergeEngine
from resurrection.checkpoint.engine import CheckpointEngine, CheckpointStrategy
from resurrection.cli import cli
from resurrection.core.models import AgentState
from resurrection.recovery.detector import CrashDetector
from resurrection.recovery.recovery import RecoveryManager
from resurrection.server.app import BranchRequest, CheckpointRequest, MergeRequest, create_app


def route_endpoint(app, name):
    for route in app.routes:
        if getattr(route, "name", None) == name:
            return route.endpoint
    raise AssertionError(f"Route not found: {name}")


def test_full_crash_recovery_branch_merge_flow(db):
    engine = CheckpointEngine(db, strategy=CheckpointStrategy(auto_every_actions=2))
    detector = CrashDetector(db)
    state = AgentState(agent_id="Felix-CTO", current_task="Complex task")
    for i in range(5):
        state.completed_actions.append({"index": i})
        state.task_progress["completed"] = i + 1
        engine.post_action(state, {"index": i})
        detector.heartbeat("Felix-CTO")
    detector.mark_crashed("Felix-CTO", "simulated")
    restored = RecoveryManager(engine, detector).recover("Felix-CTO")
    checkpoint_three = engine.list_checkpoints("Felix-CTO")[2]
    branch = BranchManager(engine).create_branch("Felix-CTO", "try-other", checkpoint_three.id)
    branch_state = engine.restore_state("Felix-CTO", checkpoint_three.id)
    branch_state.variables["approach"] = "other"
    engine.create_checkpoint(branch_state, branch_id=branch.id)
    merged_branch, merged_checkpoint_id = MergeEngine(engine).merge("Felix-CTO", branch.id)
    assert restored.task_progress["completed"] == 5
    assert detector.crashed("Felix-CTO")
    assert merged_branch.status == "merged"
    assert engine.restore_state("Felix-CTO", merged_checkpoint_id).variables["approach"] == "other"


def test_cli_init_and_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("RESURRECTION_DB", str(tmp_path / "cli.db"))
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    result = runner.invoke(cli, ["checkpoint", "Felix-CTO"])
    assert result.exit_code == 0
    assert "Felix-CTO" in result.output


def test_cli_restore(tmp_path, monkeypatch):
    monkeypatch.setenv("RESURRECTION_DB", str(tmp_path / "cli.db"))
    runner = CliRunner()
    runner.invoke(cli, ["checkpoint", "Felix-CTO"])
    result = runner.invoke(cli, ["restore", "Felix-CTO"])
    assert result.exit_code == 0
    assert '"agent_id": "Felix-CTO"' in result.output


def test_api_health(db_path):
    app = create_app(str(db_path))
    assert route_endpoint(app, "service_health")() == {"status": "ok"}


def test_api_checkpoint_and_restore(db_path):
    app = create_app(str(db_path))
    create_checkpoint = route_endpoint(app, "create_checkpoint")
    restore = route_endpoint(app, "restore")
    request = CheckpointRequest(state=AgentState(agent_id="Felix-CTO", variables={"x": 1}))
    checkpoint = create_checkpoint("Felix-CTO", request)
    assert checkpoint["agent_id"] == "Felix-CTO"
    assert restore("Felix-CTO")["variables"]["x"] == 1


def test_api_branch_and_merge(db_path):
    app = create_app(str(db_path))
    create_checkpoint = route_endpoint(app, "create_checkpoint")
    create_branch = route_endpoint(app, "create_branch")
    merge = route_endpoint(app, "merge")
    checkpoint = create_checkpoint("Felix-CTO", CheckpointRequest(state=AgentState(agent_id="Felix-CTO")))
    branch = create_branch("Felix-CTO", BranchRequest(name="exp", from_checkpoint_id=checkpoint["id"]))
    create_checkpoint(
        "Felix-CTO",
        CheckpointRequest(state=AgentState(agent_id="Felix-CTO", variables={"b": True}), branch_id=branch["id"]),
    )
    merged = merge("Felix-CTO", MergeRequest(branch_id=branch["id"]))
    assert merged["branch"]["status"] == "merged"
