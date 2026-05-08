from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import click

from resurrection.branch.branch import BranchManager
from resurrection.branch.merge import MergeEngine
from resurrection.checkpoint.engine import CheckpointEngine, CheckpointStrategy
from resurrection.core.models import AgentState, CheckpointTrigger
from resurrection.debug.diff import StateDiff
from resurrection.debug.replay import ReplayEngine
from resurrection.debug.timetravel import TimeTravel
from resurrection.recovery.detector import CrashDetector
from resurrection.recovery.recovery import RecoveryManager


def db_path() -> str:
    return os.environ.get("RESURRECTION_DB", ".resurrection/resurrection.db")


def engine() -> CheckpointEngine:
    return CheckpointEngine.from_path(db_path())


def echo_json(payload: Any) -> None:
    click.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def load_state(agent_id: str, state_file: str | None = None) -> AgentState:
    if not state_file:
        return AgentState(agent_id=agent_id)
    with open(state_file, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload.setdefault("agent_id", agent_id)
    return AgentState.model_validate(payload)


@click.group()
def cli() -> None:
    """Durable checkpointing, crash recovery, and time-travel debugging for agents."""


@cli.command("init")
def init_cmd() -> None:
    eng = engine()
    eng.db.initialize()
    click.echo(f"Initialized Resurrection at {db_path()}")


@cli.command("checkpoint")
@click.argument("agent_id")
@click.option("--state-file", type=click.Path(exists=True, dir_okay=False), help="JSON file containing AgentState fields.")
@click.option("--trigger", type=click.Choice([t.value for t in CheckpointTrigger]), default="manual")
@click.option("--metadata", default="{}", help="JSON metadata for this checkpoint.")
@click.option("--branch-id", default=None)
def checkpoint_cmd(agent_id: str, state_file: str | None, trigger: str, metadata: str, branch_id: str | None) -> None:
    checkpoint = engine().create_checkpoint(
        load_state(agent_id, state_file),
        trigger=trigger,
        metadata=json.loads(metadata),
        branch_id=branch_id,
    )
    echo_json(checkpoint.model_dump(mode="json", exclude={"state_blob"}))


@cli.command("checkpoints")
@click.argument("agent_id")
def checkpoints_cmd(agent_id: str) -> None:
    echo_json([c.model_dump(mode="json", exclude={"state_blob"}) for c in engine().list_checkpoints(agent_id)])


@cli.command("restore")
@click.argument("agent_id")
@click.option("--checkpoint", "checkpoint_id", default=None)
def restore_cmd(agent_id: str, checkpoint_id: str | None) -> None:
    echo_json(engine().restore_state(agent_id, checkpoint_id).model_dump(mode="json"))


@cli.command("diff")
@click.argument("agent_id")
@click.option("--from", "from_checkpoint", required=True)
@click.option("--to", "to_checkpoint", required=True)
def diff_cmd(agent_id: str, from_checkpoint: str, to_checkpoint: str) -> None:
    result = StateDiff(engine()).compare(from_checkpoint, to_checkpoint)
    if result["agent_id"] != agent_id:
        raise click.ClickException("Checkpoint agent_id does not match argument")
    echo_json(result)


@cli.command("replay")
@click.argument("agent_id")
@click.option("--from", "from_checkpoint", default=None)
@click.option("--to", "to_checkpoint", default=None)
def replay_cmd(agent_id: str, from_checkpoint: str | None, to_checkpoint: str | None) -> None:
    echo_json(ReplayEngine(engine()).replay(agent_id, from_checkpoint, to_checkpoint))


@cli.command("branch")
@click.argument("agent_id")
@click.option("--name", required=True)
@click.option("--from", "from_checkpoint", required=True)
def branch_cmd(agent_id: str, name: str, from_checkpoint: str) -> None:
    echo_json(BranchManager(engine()).create_branch(agent_id, name, from_checkpoint).model_dump(mode="json"))


@cli.command("branches")
@click.argument("agent_id")
def branches_cmd(agent_id: str) -> None:
    echo_json([b.model_dump(mode="json") for b in BranchManager(engine()).list_branches(agent_id)])


@cli.command("merge")
@click.argument("agent_id")
@click.option("--branch", "branch_id", required=True)
def merge_cmd(agent_id: str, branch_id: str) -> None:
    branch, checkpoint_id = MergeEngine(engine()).merge(agent_id, branch_id)
    echo_json({"branch": branch.model_dump(mode="json"), "merged_checkpoint_id": checkpoint_id})


@cli.command("health")
@click.argument("agent_id")
def health_cmd(agent_id: str) -> None:
    echo_json(CrashDetector(engine().db).health(agent_id))


@cli.command("serve")
@click.option("--port", default=8000, show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
def serve_cmd(port: int, host: str) -> None:
    import uvicorn

    uvicorn.run("resurrection.server.app:create_app", factory=True, host=host, port=port)


@cli.command("demo")
def demo_cmd() -> None:
    demo_db = Path(db_path())
    eng = CheckpointEngine(CheckpointEngine.from_path(demo_db).db, strategy=CheckpointStrategy(auto_every_actions=2))
    crash_detector = CrashDetector(eng.db)
    branch_manager = BranchManager(eng)
    merge_engine = MergeEngine(eng)
    time_travel = TimeTravel(eng)
    agent_id = "Felix-CTO"
    state = AgentState(agent_id=agent_id, current_task="Design resilient agent platform")

    created = []
    for index in range(1, 6):
        action = {"name": f"architecture-step-{index}"}
        eng.pre_action(state, action)
        state.completed_actions.append(action)
        state.task_progress["completed"] = index
        state.context_window.append({"role": "assistant", "content": f"Completed action {index}"})
        created.append(eng.post_action(state, action))
        crash_detector.heartbeat(agent_id, metadata={"action": index})

    crash_detector.mark_crashed(agent_id, "simulated crash after action 5")
    recovery = RecoveryManager(eng, crash_detector)
    restored = recovery.recover(agent_id, "full")
    checkpoints = eng.list_checkpoints(agent_id)
    fork_from = checkpoints[2].id
    branch = branch_manager.create_branch(agent_id, "experimental-approach", fork_from)
    branched_state = eng.restore_state(agent_id, fork_from)
    branched_state.variables["approach"] = "parallel recovery workers"
    branch_checkpoint = eng.create_checkpoint(
        branched_state,
        CheckpointTrigger.MANUAL,
        {"demo": "experimental branch"},
        branch_id=branch.id,
    )
    merged_branch, merged_checkpoint_id = merge_engine.merge(agent_id, branch.id)

    echo_json(
        {
            "agent_id": agent_id,
            "simulated_crash": crash_detector.health(agent_id),
            "recovery_options": recovery.options(agent_id),
            "restored_progress": restored.task_progress,
            "timeline": [
                c.model_dump(mode="json", exclude={"state_blob"}) for c in time_travel.timeline(agent_id)
            ],
            "branch": merged_branch.model_dump(mode="json"),
            "branch_checkpoint_id": branch_checkpoint.id,
            "merged_checkpoint_id": merged_checkpoint_id,
        }
    )


if __name__ == "__main__":
    cli()
