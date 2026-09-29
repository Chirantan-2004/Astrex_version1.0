import sqlite3

import pytest

from app.database import add_communication, add_event, communications, events, init_db, list_experiments, new_experiment_id, start_experiment


def test_experiment_runs_keep_immutable_event_history(monkeypatch, tmp_path):
    from app import database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "astrax.db")
    init_db()

    first_id, second_id = new_experiment_id(), new_experiment_id()
    assert first_id != second_id

    start_experiment(first_id, "BAS Sample Experiment", "2026-09-28T00:00:00+00:00")
    add_event(first_id, {
        "timestamp": "2026-09-28T00:00:01+00:00",
        "detected_activity": "OPEN",
        "confidence": 0.95,
        "status": "VALID",
        "message": "Step verified.",
    }, "OPEN")

    start_experiment(second_id, "BAS Sample Experiment", "2026-09-28T00:01:00+00:00")

    assert len(events(first_id)) == 1
    assert events(second_id) == []
    assert {run["id"] for run in list_experiments()} == {first_id, second_id}
    with pytest.raises(sqlite3.IntegrityError):
        start_experiment(first_id, "BAS Sample Experiment", "2026-09-28T00:02:00+00:00")
    assert len(events(first_id)) == 1

    queued = add_communication("UPLINK", "crew@example.test", "Need guidance on the next step.")
    assert queued["delivery_status"] == "QUEUED_LOCAL"
    assert communications()[-1]["message"] == "Need guidance on the next step."