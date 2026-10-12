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
`/login`. Signup opens the add-medicine page; an existing user's login opens
the clock.

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

- **APScheduler** runs `_check_due_reminders` every second inside the
  direct-script Flask process. It checks active rows across all accounts,
  recovers eligible overdue times from today, and re-fires expired snoozes.
  `fire_reminder` marks the row due immediately and uses an already cached
  audio path when available. `init_scheduler` warms audio for schedules
  present at startup; adding a new schedule does not itself enqueue speech
  generation in the current implementation. Verify audio readiness before
  demonstrating a spoken reminder.
- The `/check_reminders` endpoint, polled by the browser, returns
  whichever reminder is currently ringing **for the logged-in account
  only**.
- **Snooze** clears `is_due` and stores `snoozed_until` five minutes in the
  future on the same medicine row. The regular scheduler checks this
  persisted deadline; it is not a newly created one-off scheduler job.

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
- **The scheduler runs globally; the API must not.** APScheduler checks
  *every* account's reminders (it has no concept of
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

## ESP32 Hardware-Software Integration

The Switch Hub adds a physical acknowledgment input to the existing web
application. An ESP32 is used because it combines Wi-Fi, GPIO input and a
programmable controller in one board. The current sketch is a networked
switch client, not a medication dispenser or standalone talking clock:
the backend must be running, and the browser provides the reminder display
and audio. An acknowledgment records a user's response; it does not verify
that medication was swallowed.

### Input and network layers

The tip of the 3.5mm mono switch jack connects to GPIO4 and the sleeve to
GND. `INPUT_PULLUP` makes an open contact read HIGH and a closed contact
read LOW. Use a compatible dry-contact switch/interface; a matching plug
alone does not establish electrical or patient suitability.

`hardware/switch_hub.ino` uses these measured input thresholds:

| Parameter | Value | Firmware behavior |
|---|---:|---|
| `DEBOUNCE_MS` | 50 ms | Contact must remain LOW after the initial delay. |
| `SHORT_PRESS_MAX_MS` | 600 ms | A shorter measured press sends `taken` on release. |
| `HOLD_CONFIRM_MS` | 1,500 ms | LED becomes steady during the hold; release sends `snooze`. |
| Intermediate release | 600 ms to below confirmed hold | No action is guessed. |

Timing starts after the debounce delay, so physical closure duration is
slightly longer than the measured duration. A continuously held contact
does not submit an action until released. GPIO2 is the configured feedback
LED pin; confirm the actual board's LED wiring and polarity.

The hub joins the configured access point in station mode. The ESP32 and
Flask host need IP reachability, usually on the same local Wi-Fi network.
Wi-Fi carries the IP packets; TCP carries the HTTP exchange to port 5050.
HTTP was chosen to reuse Flask's existing request-response API without an
additional message broker. JSON is the application payload format, not an
authentication or encryption mechanism.

### Device request and backend state changes

The sketch sends `POST /api/device/action` with
`Content-Type: application/json` and one of these bodies:

```json
{"token":"<paired-device-token>","action":"taken"}
```

```json
{"token":"<paired-device-token>","action":"snooze"}
```

The device does not send a medicine ID or a browser session cookie.
`device_action` in `backend/app.py` calls
`database.get_user_id_for_token` to resolve the registered token's owner,
then `database.get_due_reminder` to select that user's oldest due row.
A valid token also updates `devices.last_seen_at`; this is an action-time
record, not a periodic device heartbeat.

For Taken, `_perform_mark_taken` calls `database.acknowledge_due`. Its
`BEGIN IMMEDIATE` transaction checks ownership/due state, clears `is_due`
and `snoozed_until`, and inserts a timestamp into `dose_log`. Acknowledging
the group's latest stored time also decrements its `days_remaining`.
This check is based on the time slot, not proof that every earlier dose
was acknowledged. Browser `/mark_taken` uses the same internal helper.

For Snooze, `scheduler.schedule_snooze` calls `database.snooze_due`, which
clears `is_due` and persists the five-minute deadline. It adds no Taken
log. The scheduler later marks the row due again. Both paths use SQLite;
there is no database connection opened by the ESP32.

### Response and browser visibility

A successful device request returns HTTP 200 and JSON such as:

```json
{"success":true,"medicine_name":"Demo medicine"}
```

| HTTP status | Backend meaning |
|---:|---|
| 200 | Selected due reminder was acknowledged or snoozed. |
| 400 | `action` is neither `taken` nor `snooze`, after token validation. |
| 401 | Token is absent or unknown. |
| 404 | No reminder is currently due for the token's owner. |
| 409 | The selected firing changed or was resolved before its update. |

The firmware checks HTTP status and logs it at 115200 baud. It does not
parse `medicine_name` from the response. Two slow LED blinks indicate 200;
five fast blinks indicate a rejected request or HTTP transport failure;
eight fast blinks indicate Wi-Fi is disconnected and no request was sent.
Three boot blinks indicate that Wi-Fi connected.

The database changes immediately on success, but the browser does not
receive a pushed update. `clock.js` normally polls `/check_reminders` every
17 seconds and skips polling while its own alarm is visible. After an
external device action, refresh the clock/logs to verify the persisted
state; do not assume the displayed alarm was automatically reconciled.

```mermaid
sequenceDiagram
    actor Patient
    participant Hub as ESP32 Switch Hub
    participant API as Flask device_action
    participant DB as SQLite helpers
    participant Scheduler as One-second scheduler
    participant Browser as Clock / Logs
    Patient->>Hub: Close then release switch
    Hub->>Hub: Debounce and classify duration
    Hub->>API: Wi-Fi / TCP / HTTP POST {token, action}
    API->>DB: Resolve token owner and oldest due row
    alt Taken
        API->>DB: acknowledge_due (atomic claim and dose_log insert)
    else Snooze
        API->>DB: snooze_due (clear due, store now + 5 min)
        Scheduler->>DB: Re-fire after persisted deadline
    end
    API-->>Hub: HTTP status + JSON result
    Hub-->>Patient: Status-dependent LED pattern
    Note over DB,Browser: Database is authoritative; no pushed browser update
    Browser->>API: User refresh / next eligible reminder poll
    API->>DB: Read reminder or history for browser account
    API-->>Browser: Updated persisted state
```

### Integration boundaries

- Token pairing identifies an account-authorized device; it is not a
  cryptographic attestation of a particular physical board. Tokens are
  long-lived, stored in the database and configured in the sketch.
- The example uses plaintext HTTP on a local network. Treat the token as
  a bearer secret, use disposable review accounts, and redact it from
  recordings. Secure transport and token revocation are future work.
- The API always chooses the oldest due medicine. Repeating the same
  request when several medicines are due can acknowledge the next one;
  the request has no occurrence/request ID for replay-safe retries.
- Disconnected actions are not queued. The hub stores no local reminder
  schedule and has no speaker output in the current firmware.
- Firmware, endpoint and wiring inspection establish implemented paths.
  Actual assembly, timing, network recovery and patient usability require
  physical test evidence; documentation commits do not establish those tests.

## Hardware setup and device pairing

This is a setup procedure for a disposable local demonstration. Its steps
describe what an operator should do; they are not a record of an assembled
or tested board. The more detailed parts guide remains in
[`hardware/README.md`](hardware/README.md).

### 1. Prepare the controller and switch

Required parts are an ESP32 DevKit/WROOM-32 board, a compatible dry-contact
accessibility switch, a 3.5mm mono jack, connection wire, an enclosure and
a suitable USB power supply/cable. A separate visible LED is optional.

| Connection | Destination |
|---|---|
| Jack tip | GPIO4 (`SWITCH_PIN`) |
| Jack sleeve | GND |
| Optional LED anode | GPIO2 through an approximately 220-ohm resistor |
| Optional LED cathode | GND |
| Board power | USB supply appropriate for the actual board |

Disconnect power while wiring. Confirm the switch gives the expected
contact closure and that the board pin labels match the GPIO numbers.
The internal pull-up is configured by the sketch. Do not apply an external
voltage to the switch input just because a device has a 3.5mm connector.

### 2. Start the existing backend

From the repository root, using an environment that already has
`backend/requirements.txt` installed:

```bash
python3 backend/app.py
```

This direct-script entry point initializes SQLite and the scheduler and
listens on `0.0.0.0:5050`. Importing the Flask object through a different
launcher does not execute that initialization block. Keep the machine
awake and the process running. Open `http://localhost:5050` on that machine
to log in or create a disposable demonstration account.

Find the host's LAN address, not `127.0.0.1` or `0.0.0.0`:

| Host OS | Example address-discovery command |
|---|---|
| macOS, Wi-Fi commonly on en0 | `ipconfig getifaddr en0` (confirm the active interface) |
| Linux | `hostname -I` (select the interface reachable by the ESP32) |
| Windows | `ipconfig` (use the active adapter's IPv4 address) |

Check `http://<host-lan-ip>:5050/login` from another device on the intended
network. Local access alone does not prove the ESP32 can reach the host.
Avoid guest networks that isolate clients and review the host firewall's
port-5050 access. The IP can change after moving networks or renewing DHCP.

### 3. Pair with the intended account

1. Log in as the account whose reminders the switch should acknowledge.
2. Open **Logs -> Pair a hardware button**, enter a descriptive name and
   submit the Pair form.
3. Copy the one-time token into a private local upload copy of the sketch.
   `create_device_token` generates 16 random bytes represented by 32 hex
   characters and saves their account association in `devices`.
4. Redact the token in screenshots/video and do not put it in a commit.
   The response is `Cache-Control: no-store`; a later Logs visit does not
   display that token again.

Pairing here means issuing a credential, not Bluetooth discovery or an
automatic Wi-Fi provisioning handshake. A paired device has no browser
login cookie. Choosing the wrong account at pairing time directs all its
actions to that account's oldest due reminder.

### 4. Configure and upload a private sketch copy

Use the Arduino IDE with the Espressif ESP32 board package and select the
board/USB port matching the actual hardware (for a WROOM-32 DevKit, an
appropriate ESP32 Dev Module configuration). The package supplies
`WiFi.h` and `HTTPClient.h`; this sketch does not require ArduinoJson.

Keep the upload copy outside the repository in a sketch folder named
`switch_hub`. Configure these existing constants in that copy only:

| Constant | Local configuration |
|---|---|
| `WIFI_SSID` | Access-point name reachable by the board |
| `WIFI_PASSWORD` | Access-point password; keep private |
| `DOSECLOCK_HOST` | `http://<host-lan-ip>:5050` without an endpoint suffix |
| `DEVICE_TOKEN` | Token copied from the intended account |

Upload using a data-capable USB cable. Open Serial Monitor at **115200**
baud. Successful Wi-Fi startup prints the ESP32's IP and gives three
200-ms LED blinks. If it continually prints dots, Wi-Fi connection has not
completed; the current setup loop has no timeout. USB can supply power
after configuration, but a working network/backend remains necessary.

### 5. Exercise the integration with dummy reminders

Create a clearly labeled dummy medicine with a time a few minutes ahead
of the backend clock. Use one due medicine per account for an unambiguous
first test. Open `/clock`; enable audio through a real user gesture and
verify that cached speech exists if spoken output is part of the demo.
Startup warms existing schedule audio, but a newly added label is not
automatically warmed, and the current TTS text remains a fixed English
sentence even when a regional voice code is selected. Report the actual
audio observed rather than assuming translation or offline fallback.

When the dummy reminder is due:

1. **Taken:** make a deliberate short closure longer than debounce but
   below the short-press threshold, then release. Expect Serial Monitor
   to show action `taken` and HTTP 200, followed by two slow blinks. Refresh
   Logs and verify one new acknowledgment for the intended account.
2. **Snooze:** use a separate due reminder, hold until the LED becomes
   steady, then release. Expect `snooze` and HTTP 200. No Taken log should
   be added; the persisted deadline is approximately five minutes ahead.
   Wait for re-firing and the next eligible browser poll or refresh.
3. Confirm the database/log change, not only the browser's success flash
   or the LED. Keep the returned status and the timestamped log evidence.

If no reminder is due, a valid press returns HTTP 404. That is a valid API
response, not proof that wiring or Wi-Fi failed. See the communication
test plan below before testing repeated presses or network failures.
