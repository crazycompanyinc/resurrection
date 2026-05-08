from __future__ import annotations

from datetime import timedelta

from resurrection.core.models import utc_now
from resurrection.recovery.detector import CrashDetector
from resurrection.recovery.recovery import RecoveryManager
from resurrection.recovery.restorer import StateRestorer


def test_crash_detector_unknown_health(db):
    health = CrashDetector(db).health("a1")
    assert health["status"] == "unknown"
    assert health["stale"] is True


def test_crash_detector_running_health(db):
    detector = CrashDetector(db)
    detector.heartbeat("a1")
    assert detector.health("a1")["status"] == "running"


def test_crash_detector_mark_crashed(db):
    detector = CrashDetector(db)
    detector.mark_crashed("a1", "boom")
    assert detector.crashed("a1") is True


def test_crash_detector_stale_is_crashed(db):
    detector = CrashDetector(db, stale_after_seconds=1)
    heartbeat = detector.heartbeat("a1")
    heartbeat.updated_at = utc_now() - timedelta(seconds=10)
    db.save_heartbeat(heartbeat)
    assert detector.health("a1")["status"] == "crashed"


def test_recovery_options_without_checkpoints(engine):
    options = RecoveryManager(engine).options("a1")
    assert options["modes"] == ["fresh"]


def test_recovery_full(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    recovered = RecoveryManager(engine).recover("Felix-CTO", "full", checkpoint.id)
    assert recovered.current_task == sample_state.current_task


def test_recovery_selective(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    recovered = RecoveryManager(engine).recover("Felix-CTO", "selective", checkpoint.id, ["variables"])
    assert recovered == {"variables": {"attempt": 1}}


def test_restorer_selective_ignores_unknown_fields(engine, sample_state):
    checkpoint = engine.create_checkpoint(sample_state)
    restored = StateRestorer(engine).restore_selective("Felix-CTO", checkpoint.id, ["variables", "missing"])
    assert list(restored) == ["variables"]
