"""
app.py
------
DoseClock's Flask application. Six routes, matching the brief exactly:

    GET  /                render the add-medicine form
    GET  /clock            render the full-screen clock / alarm view
    POST /add_medicine     save a new medicine schedule
    GET  /check_reminders  polled by the frontend every ~15-20s
    POST /mark_taken       log a dose, decrement days if it was the last of the day
    POST /mark_snooze      re-fire the same reminder in 5 minutes

The frontend lives in ../frontend (templates/ and static/) so the two
halves of the project stay in separate, clearly-named folders.
"""

import os
from datetime import datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for

import database
import scheduler as reminder_scheduler
import tts

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, "templates"),
    static_folder=os.path.join(FRONTEND_DIR, "static"),
)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Add-medicine form."""
    return render_template("index.html", languages=tts.LANGUAGES)


@app.route("/clock")
def clock():
    """Full-screen clock + today's upcoming doses."""
    today_schedule = database.get_active_medicines()
    return render_template("clock.html", schedule=today_schedule)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.route("/add_medicine", methods=["POST"])
def add_medicine():
    """
    Accepts JSON: { medicine_name, times: ['08:00', '20:00'], days, language }
    `medicine_name` is stored as-is - a plain label, never parsed or validated
    against any external medicine database.
    """
    data = request.get_json(silent=True) or {}

    medicine_name = (data.get("medicine_name") or "").strip()
    times = [t for t in (data.get("times") or []) if t]
    days = data.get("days")
    language = data.get("language")

    valid_languages = {code for code, _ in tts.LANGUAGES}
    if not medicine_name or not times or language not in valid_languages:
        return jsonify({"error": "medicine name, at least one time, and a language are required"}), 400
    try:
        days = int(days)
        if days < 1:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "days must be a positive number"}), 400

    database.add_medicine(medicine_name, times, days, language)
    return jsonify({"success": True})


@app.route("/check_reminders")
def check_reminders():
    """Polled by the frontend. Returns the oldest currently-ringing reminder, if any."""
    due = database.get_due_reminder()
    if due is None:
        return jsonify({"due": False})

    return jsonify(
        {
            "due": True,
            "id": due["id"],
            "medicine_name": due["medicine_name"],
            "audio_url": url_for("static", filename=due["audio_path"]),
            "language": due["language"],
        }
    )


@app.route("/mark_taken", methods=["POST"])
def mark_taken():
    """Log the dose, silence the alarm, and count the day off if it was the last dose today."""
    data = request.get_json(silent=True) or {}
    medicine_id = data.get("id")
    row = database.get_medicine(medicine_id)
    if row is None:
        return jsonify({"error": "reminder not found"}), 404

    database.log_dose(medicine_id)
    database.clear_due(medicine_id)
    reminder_scheduler.cancel_snooze(medicine_id)  # in case Taken beat a pending snooze

    # "Final dose of the day" = this row's time is the latest among the
    # still-active times in its course.
    group_rows = [r for r in database.get_group(row["group_id"]) if r["days_remaining"] > 0]
    is_final_dose = bool(group_rows) and row["time"] == max(r["time"] for r in group_rows)
    if is_final_dose:
        database.decrement_group_days(row["group_id"])

    updated = database.get_medicine(medicine_id)
    return jsonify({"success": True, "days_remaining": updated["days_remaining"] if updated else 0})


@app.route("/mark_snooze", methods=["POST"])
def mark_snooze():
    """Silence the alarm now, re-ring the exact same reminder in 5 minutes."""
    data = request.get_json(silent=True) or {}
    medicine_id = data.get("id")
    row = database.get_medicine(medicine_id)
    if row is None:
        return jsonify({"error": "reminder not found"}), 404

    database.clear_due(medicine_id)
    reminder_scheduler.schedule_snooze(medicine_id)
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    database.init_db()

    DEBUG = True

    # Flask's debug reloader re-imports this module in a child process;
    # only start the scheduler in the process that's actually serving
    # requests so reminders don't fire twice.
    if not DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        reminder_scheduler.init_scheduler()

    # Port 5050, not 5000: macOS's AirPlay Receiver squats on 5000.
    app.run(debug=DEBUG, port=5050)
