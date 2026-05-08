from __future__ import annotations

import hashlib
import json
import zlib
from typing import Any

from resurrection.core.models import AgentState


class SnapshotManager:
    """Serialize, compress, hash, and restore agent state snapshots."""

    def serialize(self, state: AgentState | dict[str, Any]) -> bytes:
        payload = self.to_plain_dict(state)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return zlib.compress(encoded)

    def deserialize(self, blob: bytes) -> AgentState:
        decoded = zlib.decompress(blob).decode("utf-8")
        return AgentState.model_validate(json.loads(decoded))

    def hash_state(self, blob: bytes) -> str:
        return hashlib.sha256(blob).hexdigest()

    def verify(self, blob: bytes, expected_hash: str) -> bool:
        return self.hash_state(blob) == expected_hash

    def size(self, blob: bytes) -> int:
        return len(blob)

    def to_plain_dict(self, state: AgentState | dict[str, Any]) -> dict[str, Any]:
        if isinstance(state, AgentState):
            return state.model_dump(mode="json")
        return AgentState.model_validate(state).model_dump(mode="json")
