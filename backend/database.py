"""
database.py
------------
All SQLite access lives here. Nothing else in the app should open a
connection directly - routes and the scheduler call these helper
functions instead. Keeping the SQL in one place makes the schema easy
to find and change later.

Schema:
    users      - one row per DoseClock account. Every medicine, dose log
                 entry, and paired hardware device belongs to a user, so
                 two people sharing the same clock never see or complete
                 each other's reminders.
    medicines  - one row per reminder TIME, owned by a user. A medicine
                 taken twice a day (e.g. 8am and 8pm) creates two rows
                 that share a `group_id`, so we know they belong to the
                 same course.
    dose_log   - a history of every "Taken" action, joined back to
                 medicines (and so to a user) for the Logs screen.
    devices    - long-lived tokens issued to paired hardware (e.g. a
                 wireless bedside button) so firmware can act on a
                 user's due reminder without a browser session/cookie.
"""

import sqlite3
import os
import uuid
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT NOT NULL UNIQUE,
            display_name    TEXT NOT NULL,
            password_hash   TEXT NOT NULL,
            created_at      TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS medicines (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS devices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            token           TEXT NOT NULL UNIQUE,
            name            TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            last_seen_at    TEXT
        )
        """
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Users / accounts
# ---------------------------------------------------------------------------

def create_user(username, password, display_name):
    """Create an account and return its row, or None if the username is taken."""
    conn = get_db_connection()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return None
    conn.execute(
        "INSERT INTO users (username, display_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (username, display_name, generate_password_hash(password), datetime.now().isoformat()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row


def get_user_by_username(username):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def verify_user(username, password):
    """Return the user row if the password matches, else None."""
    row = get_user_by_username(username)
    if row and check_password_hash(row["password_hash"], password):
        return row
    return None


# ---------------------------------------------------------------------------
# Medicines
# ---------------------------------------------------------------------------

def add_medicine(user_id, medicine_name, times, days, language):
    """
    Create one row per time-of-day, all sharing a new group_id, owned by user_id.
    `times` is a list of 'HH:MM' strings, e.g. ['08:00', '20:00'].
    """
    group_id = uuid.uuid4().hex
    created_at = datetime.now().isoformat()
    conn = get_db_connection()
    for t in times:
        conn.execute(
            """
            INSERT INTO medicines
                (user_id, group_id, medicine_name, time, days_remaining, language, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, group_id, medicine_name, t, days, language, created_at),
        )
    conn.commit()
    conn.close()
    return group_id


def get_active_medicines(user_id):
    """One user's reminder rows that still have doses left, soonest time first."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM medicines WHERE user_id = ? AND days_remaining > 0 ORDER BY time ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_all_active_medicines():
    """
    Every active reminder row, across every user. Only the background
    scheduler should call this - it has no logged-in user of its own and
    has to check all of them once a minute; routes must always use the
    user-scoped get_active_medicines() instead.
    """
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM medicines WHERE days_remaining > 0 ORDER BY time ASC"
    ).fetchall()
    conn.close()
    return rows


def get_medicine(medicine_id, user_id=None):
    """
    Look up one reminder row by id. Pass user_id from a route to make sure
    the row actually belongs to the logged-in user before acting on it -
    without that check, one account could guess another account's numeric
    medicine id and mark its dose taken. Internal callers (the scheduler)
    that don't have a user in hand can omit it.
    """
    conn = get_db_connection()
    if user_id is None:
        row = conn.execute("SELECT * FROM medicines WHERE id = ?", (medicine_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM medicines WHERE id = ? AND user_id = ?", (medicine_id, user_id)
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


def get_due_reminder(user_id):
    """The oldest currently-ringing reminder that belongs to this user, if any."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM medicines WHERE user_id = ? AND is_due = 1 ORDER BY last_fired_at ASC LIMIT 1",
        (user_id,),
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


def get_dose_history(user_id, medicine_name=None):
    """
    Every dose this user has ever logged as taken, newest first, joined
    back to the medicine it belongs to. Powers the dedicated Logs screen.
    """
    conn = get_db_connection()
    query = """
        SELECT dose_log.id AS id, dose_log.taken_at AS taken_at,
               medicines.medicine_name AS medicine_name,
               medicines.time AS scheduled_time,
               medicines.language AS language
        FROM dose_log
        JOIN medicines ON medicines.id = dose_log.medicine_id
        WHERE medicines.user_id = ?
    """
    params = [user_id]
    if medicine_name:
        query += " AND medicines.medicine_name = ?"
        params.append(medicine_name)
    query += " ORDER BY dose_log.taken_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_distinct_medicine_names(user_id):
    """Every medicine name this user has ever added, for the Logs filter dropdown."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT DISTINCT medicine_name FROM medicines WHERE user_id = ? ORDER BY medicine_name COLLATE NOCASE",
        (user_id,),
    ).fetchall()
    conn.close()
    return [r["medicine_name"] for r in rows]


# ---------------------------------------------------------------------------
# Paired hardware devices (see /HARDWARE.md)
# ---------------------------------------------------------------------------

def create_device_token(user_id, name):
    """Mint a new long-lived token a piece of hardware uses to act as this user."""
    conn = get_db_connection()
    token = secrets.token_hex(16)
    conn.execute(
        "INSERT INTO devices (user_id, token, name, created_at) VALUES (?, ?, ?, ?)",
        (user_id, token, name, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def get_devices(user_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM devices WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return rows


def get_user_id_for_token(token):
    """Resolve a device token to the user it's paired with, touching last_seen_at."""
    conn = get_db_connection()
    row = conn.execute("SELECT user_id FROM devices WHERE token = ?", (token,)).fetchone()
    if row:
        conn.execute(
            "UPDATE devices SET last_seen_at = ? WHERE token = ?",
            (datetime.now().isoformat(), token),
        )
        conn.commit()
    conn.close()
    return row["user_id"] if row else None
