# DoseClock

A talking, multilingual medicine reminder clock. Log in, add a medicine
and the times you take it, and DoseClock speaks a reminder out loud (in
English, Hindi, Tamil, Telugu, Kannada, or Bengali) when it's due.
Answer with a tap, a spoken word, or a single button press (see
[`HARDWARE.md`](HARDWARE.md) for why that matters).

DoseClock only ever says: **"It's time to take your [medicine name]."**
It does not diagnose, recommend dosages, or check drug interactions.
See [Out of scope](#out-of-scope).

## Accounts

Every reminder and dose log belongs to a signed-in account, so several
people can share one clock (or the same person can come back later on
another device) without seeing or completing each other's reminders. See
[Problems this ran into](#problems-this-ran-into-and-how-theyre-fixed)
for why this needed care.

## Screens

| Route | What it's for |
|---|---|
| `/signup`, `/login` | Create or open an account |
| `/` | Add a medicine reminder, with today's line-up alongside it |
| `/clock` | The full-screen kiosk clock and alarm, what runs all day |
| `/logs` | Dedicated dose-history screen, filterable by medicine, plus hardware pairing |

## Accessibility & hardware

The old two-tiny-buttons design didn't work for patients who can't
move. The fix is the **DoseClock Switch Hub**, a bedside ESP32 with a
standard accessibility-switch jack, so any switch matched to whatever
movement a patient still has (a paddle, a pillow switch, a sip-and-puff
breath switch) can confirm a dose. Documented in full, with parts list
and build steps, in **[`HARDWARE.md`](HARDWARE.md)** and
**[`hardware/README.md`](hardware/README.md)**, along with why infants
are a different (non-hardware) problem entirely.

## Project structure

```
DoseClock/
├── backend/                  # Flask app, scheduler, database, TTS
│   ├── app.py                 # routes: auth, pages, reminder API, hardware bridge API
│   ├── database.py            # all SQLite access (users, medicines, dose_log, devices)
│   ├── scheduler.py           # APScheduler: fires reminders, handles snooze
│   ├── tts.py                 # gTTS speech generation + mp3 caching
│   ├── requirements.txt
│   └── schedules.db           # SQLite database (auto-created on first run)
├── frontend/                  # plain HTML/CSS/JS, no build step
│   ├── templates/
│   │   ├── base.html           # shared nav shell
│   │   ├── login.html / signup.html
│   │   ├── index.html          # add-medicine form
│   │   ├── clock.html          # full-screen clock + alarm view
│   │   └── logs.html           # dose-history screen
│   └── static/
│       ├── css/style.css       # black/beige/white/pink "TV" theme, full-bleed layouts
│       ├── js/index.js         # add-medicine form behaviour
│       ├── js/clock.js         # clock, polling, alarm, voice + single-switch scanning
│       └── audio/              # cached gTTS mp3s (auto-created)
├── hardware/                  # DoseClock Switch Hub firmware + build guide (ESP32)
├── HARDWARE.md                 # the accessibility/hardware design write-up
└── README.md
```

## Running it

Requires Python 3.9+.

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5050** in your browser. You'll land on
`/login`. Create an account, and you're taken straight to the clock.

> Port **5050** is used instead of Flask's default 5000 because macOS's
> AirPlay Receiver occupies 5000 on most Macs.

The SQLite database (`backend/schedules.db`), the session-signing key
(`backend/.secret_key`), and the audio cache (`frontend/static/audio/`)
are all created automatically the first time you run the app, nothing
to set up by hand. None of the three are committed to git.

## Using it

1. Sign up or log in.
2. Add a medicine: its name, one or more times of day, how many days the
   course lasts, and a voice language.
3. You're redirected to `/clock`, a full-screen clock with today's
   doses alongside it. It quietly polls the server every ~17 seconds.
4. When a reminder is due, DoseClock speaks it aloud and shows two huge
   buttons: **Taken** and **Snooze**. Respond by tapping, by saying
   "taken"/"snooze" (or the equivalent word in the reminder's language,
   Chrome recommended), or by pressing Space/Enter, including from a
   paired single-switch accessibility device (see `HARDWARE.md`).
5. **Taken** logs the dose and, once the *last* scheduled time for that
   day has been taken, counts the day off the course. **Snooze**
   re-rings the same reminder five minutes later.
6. Visit `/logs` any time to see the full dose history for your
   account, filterable by medicine.

## How the reminder loop works

- **APScheduler** runs a job every minute inside the Flask process. It
  compares every active reminder's stored time-of-day (across all
  accounts) to the current clock time; on a match it generates (or
  reuses a cached) mp3 via **gTTS** and flips that reminder to "ringing"
  in the database.
- The `/check_reminders` endpoint, polled by the browser, returns
  whichever reminder is currently ringing **for the logged-in account
  only**.
- **Snooze** doesn't create a new database row. It schedules a one-off
  APScheduler job, keyed to that reminder's id, that re-rings it five
  minutes later.

## Problems this ran into (and how they're fixed)

Kept here because they're the kind of thing a small team hits doing
this without a second pair of eyes, and each one has a corresponding
fix commit in the git history:

- **Reminder audio was silently blocked by the browser.** Browsers
  refuse to autoplay sound with no user gesture behind it, and a
  background poll firing a reminder has no gesture at all. Fixed by
  unlocking the `<audio>` element on the very first tap/keypress
  anywhere on the page.
- **Adding accounts meant every existing query needed an owner check.**
  The original schema had no concept of a user, so any reminder id could
  be marked taken by anyone. Retrofitting `user_id` meant re-checking
  every route, not just adding a `users` table; it's easy to add login
  *pages* and forget to actually scope the *data* behind them.
- **The scheduler runs globally; the API must not.** APScheduler ticks
  once a minute across *every* account's reminders (it has no concept of
  "who's logged in"), but `/check_reminders` must only ever return the
  current session's own reminder, otherwise one user's screen could
  show another user's alarm. Two very similar-looking functions
  (`get_all_active_medicines` vs. `get_active_medicines(user_id)`) exist
  specifically so it's obvious at the call site which one is safe to use
  where.
- **Session cookies invalidated on every restart.** Flask signs session
  cookies with `app.secret_key`; generating a fresh random one on every
  process start (the initial approach) logs everyone out on every dev
  reload. Fixed by persisting the key to a local, gitignored file.
- **The palette constraint (black/beige/white/pink only, no other
  colours) had to double as the error/success/accent system**, not just
  decoration. Worth flagging because a strict palette can quietly fail
  contrast for exactly the elderly users this app is for if accent
  colours are chosen for looks before checking contrast against both the
  black and the beige backgrounds they sit on.

### General pitfalls a small team should expect on a project like this

- **Working solo/small on auth:** it's easy to protect *pages* with a
  login redirect and forget to protect the *JSON API routes* the pages
  call. An unauthenticated `POST /add_medicine` is just as much a hole
  as an unauthenticated `/`. Every state-changing route needs its own
  check, not just the page that links to it.
- **Secrets and generated files reaching GitHub:** `schedules.db`
  (real dose history), `.secret_key` (session signing key), and the
  generated `audio/*.mp3` cache are all easy to `git add -A` by accident
  the first time; they're gitignored here specifically so a rushed
  commit doesn't publish someone's medicine schedule or session secret.
- **Force-pushing over teammates' work:** with more than one person
  committing, `git pull --rebase` before pushing (rather than reaching
  for `--force` when a push is rejected) avoids quietly discarding a
  teammate's commit.
- **Commit messages that just describe the diff** ("update files",
  "fix bug") instead of the problem being fixed make it hard to find
  *why* a change happened later, especially relevant here since several
  of the fixes above (audio autoplay, session key persistence, per-user
  scoping) are exactly the kind of thing you want to grep commit history
  for in six months.
- **Testing only the happy path:** most of the bugs worth writing down
  above (cross-user data leakage, audio blocked by autoplay policy) only
  show up when you deliberately try to misuse the app - two browser
  tabs logged in as different users, a fresh browser profile with no
  prior click on the page, a slow/dropped network request - not when
  you just click through it once yourself.

## Out of scope

By design, DoseClock does **not**:
- Diagnose symptoms or give medical advice.
- Recommend, validate, or check dosages.
- Check drug interactions.
- Look up medicine names against any external database or API. The
  name you type is stored and spoken back exactly as-is, as a label.

## Tech stack

- **Backend:** Python, Flask (sessions + werkzeug password hashing),
  APScheduler, gTTS, SQLite
- **Frontend:** plain HTML/CSS/JS, no build tooling, no frameworks
- **Hardware:** ESP32 firmware for the DoseClock Switch Hub (a bedside
  unit with a standard accessibility-switch jack), see `hardware/` and
  `HARDWARE.md`
