"""
scheduler.py
------------
Owns the single APScheduler instance and the two jobs that use it:

1. A recurring job that ticks every minute and fires any reminder whose
   time-of-day matches right now.
2. One-off "snooze" jobs, added on demand, that re-fire a specific
   reminder five minutes after the user taps Snooze.

Firing a reminder never creates new database rows - it just flips the
existing row's `is_due` flag on, which is what /check_reminders polls.
"""

from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

import database
import tts

scheduler = BackgroundScheduler()


def fire_reminder(medicine_id):
    """Generate/reuse the audio for this reminder and mark it as ringing."""
    medicine = database.get_medicine(medicine_id)
    if medicine is None or medicine["days_remaining"] <= 0:
        return  # course finished or deleted between scheduling and firing

    audio_path = tts.get_or_create_audio(medicine["medicine_name"], medicine["language"])
    database.mark_fired(medicine_id, audio_path)


def _check_due_reminders():
    """
    Runs once a minute. Compares each active reminder's stored 'HH:MM'
    to the current clock time and fires the ones that match.

    The `last_fired_at` guard stops a reminder firing twice inside the
    same 60-second window if the job happens to run slightly early/late.
    """
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_minute_key = now.strftime("%Y-%m-%d %H:%M")

    for row in database.get_all_active_medicines():
        if row["time"] != current_time:
            continue
        already_fired_this_minute = (
            row["last_fired_at"] and row["last_fired_at"][:16].replace("T", " ") == current_minute_key
        )
        if not already_fired_this_minute:
            fire_reminder(row["id"])


def schedule_snooze(medicine_id):
    """Re-fire this exact reminder in 5 minutes, replacing any earlier snooze for it."""
    run_at = datetime.now() + timedelta(minutes=5)
    scheduler.add_job(
        fire_reminder,
        trigger="date",
        run_date=run_at,
        args=[medicine_id],
        id=f"snooze_{medicine_id}",
        replace_existing=True,
    )


def cancel_snooze(medicine_id):
    """If 'Taken' is pressed before a pending snooze fires, drop the pending job."""
    job_id = f"snooze_{medicine_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def init_scheduler():
    """Start the background scheduler and register the once-a-minute check."""
    if not scheduler.running:
        scheduler.add_job(
            _check_due_reminders,
            trigger="interval",
            minutes=1,
            id="check_due_reminders",
            replace_existing=True,
        )
        scheduler.start()
