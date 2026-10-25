"""
app.py
------
DoseClock's Flask application.

    GET  /                render the add-medicine form            (login required)
    GET  /clock            render the full-screen clock/alarm view (login required)
    GET  /logs             render the dedicated dose-history screen (login required)
    GET  /dashboard        adherence stats and streak              (login required)
    GET  /medicine/<gid>   detail / edit page for a medicine group (login required)
    POST /medicine/<gid>/edit    replace a group's rows            (login required)
    POST /medicine/<gid>/delete  deactivate a group                (login required)
    GET  /export           download dose history as CSV            (login required)
    GET  /signup           create an account
    POST /signup
    GET  /login            sign in
    POST /login
    POST /logout
    POST /add_medicine     save a new medicine schedule            (login required)
    POST /delete_medicine  deactivate a medicine group             (login required)
    GET  /check_reminders  polled by the frontend every ~15-20s    (login required)
    POST /mark_taken       log a dose, decrement days if it was the last of the day
    POST /mark_snooze      re-fire the same reminder in 5 minutes
    POST /pair_device      mint a token for a piece of paired hardware
    POST /api/device/action   called by paired hardware instead of a browser

The frontend lives in ../frontend (templates/ and static/) so the two
halves of the project stay in separate, clearly-named folders.
"""

import csv
import io
import os
import re
import secrets
from datetime import date
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, make_response,
)

import database
import scheduler as reminder_scheduler
import tts

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
SECRET_KEY_PATH = os.path.join(os.path.dirname(__file__), ".secret_key")


def _load_or_create_secret_key():
    """
    Flask signs session cookies with this key. Generating a fresh random
    key on every process start would silently log every account out each
    time the dev server restarts or reloads, so it's persisted to a local
    file instead (gitignored - it must never be committed).
    """
    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, "r") as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(SECRET_KEY_PATH, "w") as f:
        f.write(key)
    return key


app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, "templates"),
    static_folder=os.path.join(FRONTEND_DIR, "static"),
)
app.secret_key = _load_or_create_secret_key()


def _json_object():
    data = request.get_json(silent=True)
    return {} if data is None else (data if isinstance(data, dict) else None)


def _valid_times(times):
    return (isinstance(times, list) and bool(times)
            and all(isinstance(t, str) and re.fullmatch(r'[0-9]{2}:[0-9]{2}', t)
                    and int(t[:2]) < 24 and int(t[3:]) < 60 for t in times)
            and len(times) == len(set(times)))


def login_required(view):
    """Redirect to /login instead of serving a page/API call with no session."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/check_reminders") or request.method == "POST":
                return jsonify({"error": "not logged in"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_current_user():
    """Every template can read `current_user` for the nav bar's greeting, with no per-route wiring."""
    if "user_id" in session:
        return {"current_user": database.get_user_by_id(session["user_id"])}
    return {"current_user": None}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("clock"))

    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        display_name = (request.form.get("display_name") or "").strip()
        password = request.form.get("password") or ""

        if not username or not display_name or len(password) < 4:
            error = "Fill in every field - password needs at least 4 characters."
        else:
            user = database.create_user(username, password, display_name)
            if user is None:
                error = "That username is already taken."
            else:
                session["user_id"] = user["id"]
                return redirect(url_for("index"))

    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("clock"))

    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        user = database.verify_user(username, password)
        if user is None:
            error = "Wrong username or password."
        else:
            session["user_id"] = user["id"]
            return redirect(url_for("clock"))

    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    """Add-medicine form, with today's schedule alongside it."""
    rows = database.get_active_medicines(session["user_id"])
    # Group rows by group_id so the aside can show one Remove button per course
    seen = {}
    for row in rows:
        gid = row["group_id"]
        if gid not in seen:
            seen[gid] = {
                "medicine_name": row["medicine_name"],
                "group_id": gid,
                "times": [],
            }
        seen[gid]["times"].append(row["time"])
    return render_template(
        "index.html",
        languages=tts.LANGUAGES,
        schedule=list(seen.values()),
    )


@app.route("/clock")
@login_required
def clock():
    """Full-screen clock + today's upcoming doses, grouped by medicine name."""
    rows = database.get_active_medicines(session["user_id"])
    grouped = {}
    for row in rows:
        gid = row["group_id"]
        if gid not in grouped:
            grouped[gid] = {
                "medicine_name": row["medicine_name"],
                "group_id": gid,
                "times": [],
            }
        grouped[gid]["times"].append(row["time"])
    return render_template("clock.html", grouped_schedule=list(grouped.values()))


@app.route("/medicine/<group_id>")
@login_required
def medicine_detail(group_id):
    """Detail / edit page for a medicine group."""
    summary = database.get_group_summary(group_id, session["user_id"])
    if summary is None:
        return redirect(url_for("index"))
    history = database.get_group_dose_history(group_id, limit=10)
    return render_template(
        "medicine_detail.html",
        summary=summary,
        history=history,
        languages=tts.LANGUAGES,
    )


@app.route("/medicine/<group_id>/edit", methods=["POST"])
@login_required
def medicine_edit(group_id):
    """Replace a medicine group's rows with new values from the edit form."""
    summary = database.get_group_summary(group_id, session["user_id"])
    if summary is None:
        return redirect(url_for("index"))

    medicine_name = (request.form.get("medicine_name") or "").strip()
    times = [t for t in request.form.getlist("times") if t]
    language = request.form.get("language") or ""
    valid_languages = {code for code, _ in tts.LANGUAGES}

    try:
        days_remaining = int(request.form.get("days_remaining") or 1)
        if days_remaining < 0:
            days_remaining = 0
    except (TypeError, ValueError):
        days_remaining = summary["days_remaining"]

    if not _valid_times(times):
        return jsonify({'error': 'times must be distinct HH:MM values'}), 400
    if medicine_name and times and language in valid_languages:
        database.update_group(group_id, medicine_name, times, language, days_remaining)
        reminder_scheduler.prepare_audio(medicine_name, language)

    return redirect(url_for("medicine_detail", group_id=group_id))


@app.route("/medicine/<group_id>/delete", methods=["POST"])
@login_required
def medicine_group_delete(group_id):
    """Deactivate a medicine group from its detail page."""
    summary = database.get_group_summary(group_id, session["user_id"])
    if summary is not None:
        database.deactivate_group(group_id)
    return redirect(url_for("index"))


@app.route("/export")
@login_required
def export_csv():
    """Download the logged-in user's full dose history as a CSV file."""
    user = database.get_user_by_id(session["user_id"])
    history = database.get_dose_history(session["user_id"])

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["medicine_name", "scheduled_time", "taken_at", "language"])
    for row in history:
        writer.writerow([
            row["medicine_name"],
            row["scheduled_time"],
            row["taken_at"],
            row["language"],
        ])

    filename = "doseclock_history_{}_{}.csv".format(
        user["username"],
        date.today().isoformat(),
    )
    response = make_response(buf.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

@app.route("/dashboard")
@login_required
def dashboard():
    from datetime import datetime, timedelta

    user_id = session["user_id"]
    history = database.get_dose_history(user_id)
    medicines = database.get_active_medicines(user_id)

    today = datetime.now().date()
    week_start = today - timedelta(days=6)

    # Dates on which at least one dose was taken
    taken_dates = set()
    for row in history:
        try:
            taken_dates.add(datetime.fromisoformat(row["taken_at"]).date())
        except Exception:
            pass

    # Doses taken this week (count of log rows, not just days)
    doses_this_week = sum(
        1 for row in history
        if datetime.fromisoformat(row["taken_at"]).date() >= week_start
    )

    # Overall adherence: doses taken this week vs doses scheduled this week
    active_groups = {}
    for m in medicines:
        gid = m["group_id"]
        if gid not in active_groups:
            active_groups[gid] = 0
        active_groups[gid] += 1  # count time slots per group
    expected_this_week = sum(slots * 7 for slots in active_groups.values())
    adherence_pct = (
        min(round(doses_this_week / expected_this_week * 100), 100)
        if expected_this_week > 0 else 0
    )

    # Current streak: consecutive days going back from today
    streak = 0
    check = today
    while check in taken_dates:
        streak += 1
        check -= timedelta(days=1)
    if streak == 0:  # if nothing today, check from yesterday
        check = today - timedelta(days=1)
        while check in taken_dates:
            streak += 1
            check -= timedelta(days=1)

    # Per-medicine: group by group_id, collect all times, compute adherence
    groups = {}
    for m in medicines:
        gid = m["group_id"]
        if gid not in groups:
            groups[gid] = {
                "name": m["medicine_name"],
                "group_id": gid,
                "days_remaining": m["days_remaining"],
                "times": [],
            }
        groups[gid]["times"].append(m["time"])

    # Count doses taken per group from the full history
    group_taken = {}
    for row in history:
        gid = row["group_id"]
        if gid:
            group_taken[gid] = group_taken.get(gid, 0) + 1

    per_med = []
    for gid, g in groups.items():
        slots = len(g["times"])
        # scheduled = days already elapsed × slots (approximated as total - remaining)
        # Use a simple measure: taken vs (taken + remaining doses)
        taken = group_taken.get(gid, 0)
        remaining_doses = g["days_remaining"] * slots
        total = taken + remaining_doses
        pct = min(round(taken / total * 100), 100) if total > 0 else 0
        per_med.append({
            "name": g["name"],
            "group_id": gid,
            "times": sorted(g["times"]),
            "days_remaining": g["days_remaining"],
            "pct": pct,
        })

    # Count distinct active medicine courses
    active_count = len(groups)

    return render_template(
        "dashboard.html",
        adherence_pct=adherence_pct,
        streak=streak,
        doses_this_week=doses_this_week,
        active_count=active_count,
        per_med=per_med,
        today=today.strftime("%A, %d %B %Y"),
    )
    
@app.route("/logs")
@login_required
def logs(paired_token=None):
    """Dedicated dose-history screen, optionally filtered to one medicine."""
    medicine_filter = request.args.get("medicine") or None
    history = database.get_dose_history(session["user_id"], medicine_filter)
    medicine_names = database.get_distinct_medicine_names(session["user_id"])
    devices = database.get_devices(session["user_id"])
    return render_template(
        "logs.html",
        history=history,
        medicine_names=medicine_names,
        selected_medicine=medicine_filter,
        devices=devices,
        paired_token=paired_token,
    )


@app.route("/pair_device", methods=["POST"])
@login_required
def pair_device():
    """Mint a new hardware pairing token (see HARDWARE.md) and show it once on the Logs screen."""
    name = (request.form.get("name") or "Bedside button").strip()[:60]
    token = database.create_device_token(session["user_id"], name)
    response = app.make_response(logs(paired_token=token))
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# API - browser
# ---------------------------------------------------------------------------

@app.route("/add_medicine", methods=["POST"])
@login_required
def add_medicine():
    """
    Accepts JSON: { medicine_name, times: ['08:00', '20:00'], days, language }
    `medicine_name` is stored as-is - a plain label, never parsed or validated
    against any external medicine database.
    """
    data = _json_object()
    if data is None:
        return jsonify({'error': 'JSON body must be an object'}), 400
    if not isinstance(data.get('medicine_name'), str):
        return jsonify({'error': 'medicine name must be text'}), 400
    medicine_name = data['medicine_name'].strip()
    times = data.get("times")
    days = data.get("days")
    language = data.get("language")

    valid_languages = {code for code, _ in tts.LANGUAGES}
    if not medicine_name or not _valid_times(times) or not isinstance(language, str) or language not in valid_languages:
        return jsonify({"error": "medicine name, at least one time, and a language are required"}), 400
    try:
        if isinstance(days, bool) or not isinstance(days, (str, int)):
            raise ValueError
        days = int(days)
        if days < 1:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "days must be a positive number"}), 400

    database.add_medicine(session["user_id"], medicine_name, times, days, language)
    reminder_scheduler.prepare_audio(medicine_name, language)
    return jsonify({"success": True})


@app.route("/delete_medicine", methods=["POST"])
@login_required
def delete_medicine():
    """
    Accepts JSON: { "id": "<group_id>" }
    Sets days_remaining = 0 for every row in that group, after verifying
    it belongs to the logged-in user.
    """
    data = _json_object()
    if data is None or not isinstance(data.get('id', ''), str):
        return jsonify({'error': 'JSON object with a text group id required'}), 400
    group_id = data.get("id") or ""
    # Verify ownership before deactivating
    summary = database.get_group_summary(group_id, session["user_id"])
    if summary is None:
        return jsonify({"error": "medicine not found"}), 404
    database.deactivate_group(group_id)
    return jsonify({"success": True})


@app.route("/check_reminders")
@login_required
def check_reminders():
    """Polled by the frontend. Returns the oldest reminder ringing for *this* user, if any."""
    due = database.get_due_reminder(session["user_id"])
    if due is None:
        return jsonify({"due": False})

    return jsonify(
        {
            "due": True,
            "id": due["id"],
            "medicine_name": due["medicine_name"],
            # Resolve against current translated content, not a legacy cached
            # English-only path persisted before the template upgrade.
            "audio_url": url_for("static", filename=audio_path) if (audio_path := tts.get_cached_audio(due['medicine_name'], due['language'])) else None,
            "language": due["language"],
            "fired_at": due["last_fired_at"],
        }
    )


def _perform_mark_taken(medicine_id, user_id, expected_fired_at=None):
    """
    Shared by /mark_taken and the hardware bridge: log the dose, silence
    the alarm, and count the day off if this was the last dose of the day.
    """
    updated = database.acknowledge_due(medicine_id, user_id, expected_fired_at)
    if updated is not None:
        reminder_scheduler.cancel_snooze(medicine_id)
    return updated


@app.route("/mark_taken", methods=["POST"])
@login_required
def mark_taken():
    """Log the dose, silence the alarm, and count the day off if it was the last dose today."""
    data = _json_object()
    if data is None or isinstance(data.get('id'), (dict, list, bool)):
        return jsonify({'error': 'JSON object with a reminder id required'}), 400
    medicine_id = data.get("id")
    row = database.get_medicine(medicine_id, user_id=session["user_id"])
    if row is None:
        return jsonify({"error": "reminder not found"}), 404

    updated = _perform_mark_taken(medicine_id, session['user_id'], data.get('fired_at'))
    if updated is None:
        return jsonify({'error': 'reminder is no longer due'}), 409
    return jsonify({"success": True, "days_remaining": updated["days_remaining"] if updated else 0})


@app.route("/mark_snooze", methods=["POST"])
@login_required
def mark_snooze():
    """Silence the alarm now, re-ring the exact same reminder in 5 minutes."""
    data = _json_object()
    if data is None or isinstance(data.get('id'), (dict, list, bool)):
        return jsonify({'error': 'JSON object with a reminder id required'}), 400
    medicine_id = data.get("id")
    row = database.get_medicine(medicine_id, user_id=session["user_id"])
    if row is None:
        return jsonify({"error": "reminder not found"}), 404

    if not reminder_scheduler.schedule_snooze(medicine_id, session['user_id'], data.get('fired_at')):
        return jsonify({'error': 'reminder is no longer due'}), 409
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# API - paired hardware (see HARDWARE.md)
# A wireless bedside button, adaptive switch receiver, or other paired
# device has no browser and no session cookie, so it authenticates with a
# long-lived per-device token instead and acts on whichever reminder is
# currently due for the user that token is paired with.
# ---------------------------------------------------------------------------

@app.route("/api/device/action", methods=["POST"])
def device_action():
    data = _json_object()
    if data is None or not isinstance(data.get('token', ''), str) or not isinstance(data.get('action', ''), str):
        return jsonify({'error': 'JSON object with text token and action required'}), 400
    token = data.get("token")
    action = data.get("action")

    user_id = database.get_user_id_for_token(token) if token else None
    if user_id is None:
        return jsonify({"error": "unknown or missing device token"}), 401
    if action not in ("taken", "snooze"):
        return jsonify({"error": "action must be 'taken' or 'snooze'"}), 400

    due = database.get_due_reminder(user_id)
    if due is None:
        return jsonify({"error": "no reminder is currently due"}), 404

    if action == "taken":
        if _perform_mark_taken(due['id'], user_id, due['last_fired_at']) is None:
            return jsonify({'error': 'reminder is no longer due'}), 409
    else:
        if not reminder_scheduler.schedule_snooze(due['id'], user_id, due['last_fired_at']):
            return jsonify({'error': 'reminder is no longer due'}), 409

    return jsonify({"success": True, "medicine_name": due["medicine_name"]})


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    database.init_db()

    DEBUG = False

    # Flask's debug reloader re-imports this module in a child process;
    # only start the scheduler in the process that's actually serving
    # requests so reminders don't fire twice.
    if not DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        reminder_scheduler.init_scheduler()

    # Port 5050, not 5000: macOS's AirPlay Receiver squats on 5000.
    app.run(host="0.0.0.0", debug=DEBUG, port=5050)
