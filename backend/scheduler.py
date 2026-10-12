"""One-second checks with speech off the critical path and persistent snooze."""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Lock
from time import monotonic
from apscheduler.schedulers.background import BackgroundScheduler
import database
import tts

scheduler = BackgroundScheduler()
_audio_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="doseclock-audio")
_audio_pending = set()
_audio_retry_after = {}
_audio_lock = Lock()
logger = logging.getLogger(__name__)


def prepare_audio(medicine_name, language):
    """Warm speech off request/scheduler threads, deduplicating work."""
    key = (medicine_name, language)
    with _audio_lock:
        if key in _audio_pending or tts.get_cached_audio(*key) or monotonic() < _audio_retry_after.get(key, 0):
            return
        _audio_pending.add(key)

    def generate():
        try:
            tts.get_or_create_audio(*key)
            with _audio_lock:
                _audio_retry_after.pop(key, None)
        except Exception as error:
            with _audio_lock:
                _audio_retry_after[key] = monotonic() + 30
            logger.warning("Speech unavailable for %s; retrying later (%s)", language, type(error).__name__)
        finally:
            with _audio_lock:
                _audio_pending.discard(key)
    _audio_pool.submit(generate)


def fire_reminder(medicine_id):
    """Set due immediately; use cached speech or the browser fallback."""
    medicine = database.get_medicine(medicine_id)
    if medicine is None or medicine["days_remaining"] <= 0:
        return
    database.mark_fired(medicine_id, tts.get_cached_audio(medicine["medicine_name"], medicine["language"]))


def _check_due_reminders():
    now = datetime.now()
    today = now.date().isoformat()
    for row in database.get_all_active_medicines():
        if row["is_due"]:
            continue
        if row["snoozed_until"]:
            if datetime.fromisoformat(row["snoozed_until"]) <= now:
                fire_reminder(row["id"])
            continue
        if row["last_fired_at"] and row["last_fired_at"][:10] == today:
            continue
        try:
            scheduled = datetime.combine(now.date(), datetime.strptime(row["time"], "%H:%M").time())
            created = datetime.fromisoformat(row["created_at"])
        except (ValueError, TypeError):
            continue
        # Past times on a newly created schedule start tomorrow. Existing
        # overdue doses from today are recovered after sleep or restart.
        if scheduled <= now and created < scheduled + timedelta(minutes=1):
            fire_reminder(row["id"])


def schedule_snooze(medicine_id, user_id=None, expected_fired_at=None):
    return database.snooze_due(medicine_id, (datetime.now() + timedelta(minutes=5)).isoformat(),
                               user_id, expected_fired_at)


def cancel_snooze(medicine_id):
    # Acknowledgement clears the persisted deadline in its transaction.
    job_id = f"snooze_{medicine_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def init_scheduler():
    if not scheduler.running:
        scheduler.add_job(_check_due_reminders, trigger="interval", seconds=1,
                          next_run_time=datetime.now(), id="check_due_reminders",
                          replace_existing=True, coalesce=True, max_instances=1)
        scheduler.start()
        for row in database.get_all_active_medicines():
            prepare_audio(row["medicine_name"], row["language"])
