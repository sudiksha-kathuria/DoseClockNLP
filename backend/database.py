"""
database.py
------------
All SQLite access lives here. Nothing else in the app should open a
connection directly - routes and the scheduler call these helper
functions instead. Keeping the SQL in one place makes the schema easy
to find and change later.

Schema:
    medicines  - one row per reminder TIME. A medicine taken twice a day
                 (e.g. 8am and 8pm) creates two rows that share a
                 `group_id`, so we know they belong to the same course.
    dose_log   - a simple history of every "Taken" action, for the
                 "log the dose" requirement.
"""

import sqlite3
import os
import uuid
from datetime import datetime

# schedules.db lives next to this file, inside backend/, and is created
# automatically the first time the app runs.
DB_PATH = os.path.join(os.path.dirname(__file__), "schedules.db")


def get_db_connection():
    """Open a new connection with rows accessible by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the tables if they don't exist yet. Safe to call every startup."""
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS medicines (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id        TEXT NOT NULL,      -- ties together multiple times of one course
            medicine_name   TEXT NOT NULL,      -- free-text label, never parsed
            time            TEXT NOT NULL,      -- 'HH:MM', 24-hour, one row per time
            days_remaining  INTEGER NOT NULL,
            language        TEXT NOT NULL,      -- gTTS language code, e.g. 'en', 'hi'
            created_at      TEXT NOT NULL,
            last_fired_at   TEXT,                -- last time this reminder rang
            is_due          INTEGER NOT NULL DEFAULT 0,  -- 1 while an alarm is actively ringing
            audio_path      TEXT                 -- cached mp3, relative to static/
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dose_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id  INTEGER NOT NULL REFERENCES medicines(id),
            taken_at     TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def add_medicine(medicine_name, times, days, language):
    """
    Create one row per time-of-day, all sharing a new group_id.
    `times` is a list of 'HH:MM' strings, e.g. ['08:00', '20:00'].
    """
    group_id = uuid.uuid4().hex
    created_at = datetime.now().isoformat()
    conn = get_db_connection()
    for t in times:
        conn.execute(
            """
            INSERT INTO medicines
                (group_id, medicine_name, time, days_remaining, language, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (group_id, medicine_name, t, days, language, created_at),
        )
    conn.commit()
    conn.close()
    return group_id


def get_active_medicines():
    """All reminder rows that still have doses left, soonest time first."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM medicines WHERE days_remaining > 0 ORDER BY time ASC"
    ).fetchall()
    conn.close()
    return rows


def get_medicine(medicine_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM medicines WHERE id = ?", (medicine_id,)
    ).fetchone()
    conn.close()
    return row


def get_group(group_id):
    """All time-slots that belong to the same medicine course."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM medicines WHERE group_id = ?", (group_id,)
    ).fetchall()
    conn.close()
    return rows


def mark_fired(medicine_id, audio_path):
    """Flip a reminder into the 'ringing' state and remember when + what audio."""
    conn = get_db_connection()
    conn.execute(
        "UPDATE medicines SET is_due = 1, last_fired_at = ?, audio_path = ? WHERE id = ?",
        (datetime.now().isoformat(), audio_path, medicine_id),
    )
    conn.commit()
    conn.close()


def clear_due(medicine_id):
    """Silence a ringing reminder (used by both Taken and Snooze)."""
    conn = get_db_connection()
    conn.execute("UPDATE medicines SET is_due = 0 WHERE id = ?", (medicine_id,))
    conn.commit()
    conn.close()


def get_due_reminder():
    """The single oldest reminder that is currently ringing, if any."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM medicines WHERE is_due = 1 ORDER BY last_fired_at ASC LIMIT 1"
    ).fetchone()
    conn.close()
    return row


def log_dose(medicine_id):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO dose_log (medicine_id, taken_at) VALUES (?, ?)",
        (medicine_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def decrement_group_days(group_id):
    """Once the last dose of the day for a course is taken, count the day off."""
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE medicines
        SET days_remaining = MAX(days_remaining - 1, 0)
        WHERE group_id = ?
        """,
        (group_id,),
    )
    conn.commit()
    conn.close()
