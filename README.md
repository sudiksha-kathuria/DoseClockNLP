# DoseClock

A talking, multilingual medicine reminder alarm clock. Add a medicine and
the times you take it, and DoseClock speaks a reminder out loud (in
English, Hindi, Tamil, Telugu, Kannada, or Bengali) when it's due —
answer with a tap, or by voice.

DoseClock only ever says: **"It's time to take your [medicine name]."**
It does not diagnose, recommend dosages, or check drug interactions —
see [Out of scope](#out-of-scope).

## Project structure

```
DoseClock/
├── backend/                 # Flask app, scheduler, database, TTS
│   ├── app.py                # routes: /, /clock, /add_medicine, /check_reminders, /mark_taken, /mark_snooze
│   ├── database.py           # all SQLite access
│   ├── scheduler.py          # APScheduler: fires reminders, handles snooze
│   ├── tts.py                # gTTS speech generation + mp3 caching
│   ├── requirements.txt
│   └── schedules.db          # SQLite database (auto-created on first run)
├── frontend/                 # plain HTML/CSS/JS, no build step
│   ├── templates/
│   │   ├── index.html         # add-medicine form
│   │   └── clock.html         # full-screen clock + alarm view
│   └── static/
│       ├── css/style.css
│       ├── js/index.js        # form page behaviour
│       ├── js/clock.js        # clock, polling, alarm, voice input
│       └── audio/             # cached gTTS mp3s (auto-created)
└── README.md
```

## Running it

Requires Python 3.9+.

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5050** in your browser.

> Port **5050** is used instead of Flask's default 5000 because macOS's
> AirPlay Receiver occupies 5000 on most Macs.

The SQLite database (`backend/schedules.db`) and the audio cache
(`frontend/static/audio/`) are created automatically the first time you
run the app — nothing to set up by hand.

## Using it

1. Visit `/` and add a medicine: its name, one or more times of day,
   how many days the course lasts, and a voice language.
2. You're redirected to `/clock` — a full-screen clock. It quietly polls
   the server every ~17 seconds.
3. When a reminder is due, DoseClock speaks it aloud and shows two large
   buttons: **Taken** and **Snooze**. You can also just say "taken" or
   "snooze" (or the equivalent word in the reminder's language) if your
   browser supports the Web Speech API (Chrome recommended) — the
   buttons work regardless, so speech is a convenience, not a
   requirement.
4. **Taken** logs the dose and, once the *last* scheduled time for that
   day has been taken, counts the day off the course. **Snooze**
   re-rings the same reminder five minutes later.

## How the reminder loop works

- **APScheduler** runs a job every minute inside the Flask process. It
  compares each active reminder's stored time-of-day to the current
  clock time; on a match it generates (or reuses a cached) mp3 via
  **gTTS** and flips that reminder to "ringing" in the database.
- The `/check_reminders` endpoint, polled by the browser, simply returns
  whichever reminder is currently ringing.
- **Snooze** doesn't create a new database row — it schedules a one-off
  APScheduler job, keyed to that reminder's id, that re-rings it five
  minutes later.

## Out of scope

By design, DoseClock does **not**:
- Diagnose symptoms or give medical advice.
- Recommend, validate, or check dosages.
- Check drug interactions.
- Look up medicine names against any external database or API — the
  name you type is stored and spoken back exactly as-is, as a label.

## Tech stack

- **Backend:** Python, Flask, APScheduler, gTTS, SQLite
- **Frontend:** plain HTML/CSS/JS — no build tooling, no frameworks
