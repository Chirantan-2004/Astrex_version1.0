import csv
import io
import json
import os
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone

if os.getenv("ASTRO_DB_PATH"):
    DB_PATH = Path(os.environ["ASTRO_DB_PATH"])
elif os.getenv("VERCEL"):
    DB_PATH = Path("/tmp/astrax/astrax.db")
else:
    DB_PATH = Path(__file__).resolve().parent.parent / "data" / "astrax.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def new_experiment_id() -> str:
    return f"BAS-001-{uuid4().hex}"


def init_db():
    with get_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            started_at TEXT,
            ended_at TEXT,
            status TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            step INTEGER,
            expected_activity TEXT,
            detected_activity TEXT NOT NULL,
            confidence REAL NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            source TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS communications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('UPLINK','DOWNLINK')),
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            delivery_status TEXT NOT NULL
        )""")


def start_experiment(experiment_id: str, name: str, started_at: str):
    with get_conn() as conn:
        conn.execute("INSERT INTO experiments(id,name,started_at,ended_at,status) VALUES(?,?,?,?,?)",
                     (experiment_id, name, started_at, None, "RUNNING"))


def finish_experiment(experiment_id: str, ended_at: str, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE experiments SET ended_at=?, status=? WHERE id=?", (ended_at, status, experiment_id))


def add_event(experiment_id: str, event: dict[str, Any], expected: str | None):
    with get_conn() as conn:
        conn.execute("""INSERT INTO events(experiment_id,timestamp,step,expected_activity,detected_activity,confidence,status,message,source)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                     (experiment_id, event["timestamp"], event.get("step"), expected, event["detected_activity"],
                      event["confidence"], event["status"], event["message"], event.get("source")))


def events(experiment_id: str):
    with get_conn() as conn:
        rows = conn.execute("SELECT timestamp,step,expected_activity,detected_activity,confidence,status,message,source FROM events WHERE experiment_id=? ORDER BY id",
                            (experiment_id,)).fetchall()
        return [dict(r) for r in rows]


def list_experiments():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,name,started_at,ended_at,status FROM experiments ORDER BY started_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def add_communication(direction: str, sender: str, message: str):
    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO communications(created_at,direction,sender,message,delivery_status) VALUES(?,?,?,?,?)",
            (created_at, direction, sender, message, "QUEUED_LOCAL"),
        )
        row = conn.execute(
            "SELECT id,created_at,direction,sender,message,delivery_status FROM communications WHERE id=?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(row)


def communications(limit: int = 30):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,created_at,direction,sender,message,delivery_status FROM communications ORDER BY id DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]


def export_json(experiment_id: str):
    return json.dumps({"experiment_id": experiment_id, "events": events(experiment_id)}, indent=2)


def export_csv(experiment_id: str):
    rows = events(experiment_id)
    out = io.StringIO()
    fields = ["timestamp","step","expected_activity","detected_activity","confidence","status","message","source"]
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()
