# Resurrection

Resurrection is an agent persistence and checkpointing engine. It gives long-running agents a durable "save game" layer: automatic checkpoints, crash recovery, time-travel debugging, state diffs, branchable execution, and branch merge.

## Features

- Checkpoint agent state manually, around actions, on timers, or after errors.
- Restore an agent from the latest or selected checkpoint.
- Compare checkpoints with structured diffs.
- Replay checkpoint history over a selected range.
- Fork state into named branches and merge branch state back into main.
- Store state durably in SQLite with integrity hashes.
- Expose the engine through Python APIs, a Click CLI, and a FastAPI server.

## Install

```bash
pip install -e ".[test]"
```

## CLI

```bash
resurrection init
resurrection checkpoint Felix-CTO
resurrection checkpoints Felix-CTO
resurrection restore Felix-CTO --checkpoint <id>
resurrection diff Felix-CTO --from <id> --to <id>
resurrection replay Felix-CTO --from <id> --to <id>
resurrection branch Felix-CTO --name experiment --from <id>
resurrection branches Felix-CTO
resurrection merge Felix-CTO --branch <branch_id>
resurrection health Felix-CTO
resurrection serve --port 8000
resurrection demo
```

By default the CLI stores data in `.resurrection/resurrection.db`. Set `RESURRECTION_DB` to choose another path.

## Python API

```python
from resurrection import AgentState, CheckpointEngine

engine = CheckpointEngine.from_path(".resurrection/resurrection.db")
state = AgentState(agent_id="Felix-CTO", current_task="Design recovery plan")

checkpoint = engine.create_checkpoint(state, trigger="manual")
restored = engine.restore_state("Felix-CTO", checkpoint.id)
```

## Server

```bash
resurrection serve --port 8000
```

The API exposes checkpoint, restore, diff, replay, branch, merge, and health endpoints under `/agents/{agent_id}`.

## Development

```bash
pytest
```
