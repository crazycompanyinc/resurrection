from __future__ import annotations

from copy import deepcopy
from typing import Any


class IncrementalTracker:
    """Compute and apply small JSON-like patches between agent states."""

    def diff(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        return self._diff_value(before, after)

    def has_changes(self, before: dict[str, Any], after: dict[str, Any]) -> bool:
        return bool(self.diff(before, after))

    def apply(self, base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(base)
        self._apply_into(result, patch)
        return result

    def _diff_value(self, before: Any, after: Any) -> Any:
        if isinstance(before, dict) and isinstance(after, dict):
            changes: dict[str, Any] = {}
            for key in sorted(set(before) | set(after)):
                if key not in after:
                    changes[key] = {"__op__": "remove"}
                elif key not in before:
                    changes[key] = {"__op__": "add", "value": after[key]}
                else:
                    child = self._diff_value(before[key], after[key])
                    if child:
                        changes[key] = child
            return changes
        if before != after:
            return {"__op__": "replace", "value": after}
        return {}

    def _apply_into(self, target: dict[str, Any], patch: dict[str, Any]) -> None:
        for key, change in patch.items():
            if isinstance(change, dict) and "__op__" in change:
                op = change["__op__"]
                if op == "remove":
                    target.pop(key, None)
                elif op in {"add", "replace"}:
                    target[key] = deepcopy(change["value"])
                else:
                    raise ValueError(f"Unknown patch op: {op}")
            else:
                if key not in target or not isinstance(target[key], dict):
                    target[key] = {}
                self._apply_into(target[key], change)
