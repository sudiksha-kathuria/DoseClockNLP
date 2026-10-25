# DoseClock

A talking, multilingual medicine reminder clock. Log in, add a medicine
and the times you take it, and DoseClock speaks a reminder out loud (in
English, Hindi, Tamil, Telugu, Kannada, or Bengali) when it's due.
Answer with a tap, a spoken word, or a single button press (see
[`HARDWARE.md`](HARDWARE.md) for why that matters).

DoseClock speaks a translated reminder meaning **"It's time to take your [medicine name]."**
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
  present at startup; adding or editing a schedule also enqueues speech
  generation off the request thread. Verify audio readiness before
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

The 23 October 2026 software-resolution update uses an occurrence-bound
protocol. Upgrade the firmware and backend together. Legacy token/action-only
requests receive HTTP 400 and cannot acknowledge a different pending medicine.

1. `POST /api/device/reminder` with `{"token":"<paired-device-token>"}`
   returns `due:false`, or the account's oldest pending `id`, `fired_at` and
   medicine label. Selection does not acknowledge or reserve it.
2. The device saves that identity, action and a unique `request_id` before
   transmission, then sends `POST /api/device/action`:

```json
{"token":"<paired-device-token>","action":"taken","id":42,"fired_at":"<exact value from selection>","request_id":"<unique ID for this intentional action>"}
```

Use `snooze` for Snooze. Every retry reuses all five fields. A new intentional
action gets a new request ID and selection. The firmware retains the selected
request in ESP32 Preferences across restart, with the credential supplied from
its private configuration. It never stores the token in the pending JSON.
While a result is uncertain, new switch gestures are ignored and automatic
retries keep the original pending action. After blocking work, the switch
requires a fresh debounced release and press; an overlapping gesture does not
choose another reminder. An HTTP 200 with `success:true` confirms
the result; a definite 4xx rejection clears that pending action. Transport/5xx
failures retain it and retry every five seconds.

`database.apply_device_action` checks the device's account, target and firing
inside `BEGIN IMMEDIATE`. It commits Taken/Snooze and a durable retry receipt
in the same transaction. Exact duplicate requests return the original success
without another log, course decrement or Snooze deadline extension. Reusing a
key for a different target/action, or sending a fresh key for a stale firing,
returns 409. Failed transactions roll back both the transition and receipt.

Taken and browser actions share the dose/course update helper. Snooze stores
one five-minute deadline and adds no Taken log. Browser action bodies require
`id` and `fired_at` from `/check_reminders`; the shipped frontend already sends
them. Firing identity prevents a delayed action from answering a later alarm.

| HTTP status | Device action meaning |
|---:|---|
| 200 | One selected action succeeded, or its exact success receipt was replayed. |
| 400 | Invalid action or missing/invalid occurrence identity or request ID. |
| 401 | Missing or unknown token. |
| 404 | Selected target does not belong to that account or does not exist. |
| 409 | Stale/resolved target, or request ID reused with another binding. |
| 503 | Database transaction unavailable; retry the identical request. |

The browser polls every 17 seconds and reconciles external changes. The
firmware uses the existing success/error LED patterns, but physical LED,
GPIO, NVS power-loss/reboot and ESP32 Wi-Fi behavior still require board tests.
See [the protocol contract](docs/DEVICE_PROTOCOL.md) and the dated testing
report for compatibility, retained evidence and verification limits.

Tokens are bearer credentials. The example still uses local-network HTTP;
TLS, token revocation and receipt-retention policy remain future work. The
hub has no local schedule or speaker. Server receipts are retained so exact
retries survive backend restart. Two deliberately new actions may address two
reminders; a retry of one action cannot silently become the other action.

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
selections to that account's pending reminders; every action is then bound to one firing.

### 4. Configure and upload a private sketch copy

Use the Arduino IDE with the Espressif ESP32 board package and select the
board/USB port matching the actual hardware (for a WROOM-32 DevKit, an
appropriate ESP32 Dev Module configuration). The package supplies
`WiFi.h`, `HTTPClient.h` and `Preferences.h`. Install **ArduinoJson 7** through Library Manager as well.

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
Startup and schedule creation/editing warm audio in the background. The
current TTS text uses a translated template for the selected language.
Medicine labels remain unchanged. Human pronunciation/intelligibility and
independent native-speaker review remain unverified; report the actual audio observed.

When the dummy reminder is due:

1. **Taken:** make a deliberate short closure longer than debounce but
   below the short-press threshold, then release. Expect Serial Monitor
   to show the bound action and HTTP 200, followed by two slow blinks. Refresh
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

## Communication testing and troubleshooting

Actual software validation, measured loopback benchmarks, failure evidence and
retests are recorded in [`docs/testing/TEST_REPORT.md`](docs/testing/TEST_REPORT.md).
Physical GPIO, switch, LED and ESP32 Wi-Fi checks remain separate from simulated HTTP.
The following checklist describes the validation criteria. Record the date, actual board/core version, host, network,
trial count, HTTP status, database before/after state and evidence filename
when performing them. Use disposable accounts and dummy medicines. Keep
one due medicine per account unless the test explicitly concerns multiple
pending reminders. Do not use real patient schedules for fault injection.

### Proposed benchmarks

These acceptance targets are chosen for a local review demonstration.
They have not been measured and are not product performance guarantees.

| Requirement | Planned sample | Proposed acceptance target | Measurement |
|---|---:|---|---|
| Valid Taken correctness | 10 independently due dummy reminders | 10/10 intended reminders logged exactly once, owned by the paired account | Compare HTTP JSON, Logs and SQLite row counts before/after. |
| Invalid-token isolation | 10 requests | 10/10 return 401; no medicine/dose-log changes | Use a deliberately invalid credential; compare state. |
| HTTP response time on healthy LAN | 30 requests, each with a fresh due reminder | Median <= 500 ms and 95th percentile <= 1,000 ms | Time from POST start to response received; report all samples and failures. |
| Snooze persistence/timing | 3 fresh reminders | No Taken log; stored deadline approximately 300 s after request; due re-fires within 2 s of deadline on an idle awake host | Record persisted timestamp and backend due state; include actual scheduler delay. |
| Browser initial reminder visibility | 5 fresh page/due cycles | Visible within 20 s under an active foreground page and healthy LAN | Scheduler interval is 1 s and browser polling is 17 s; overhead makes this a target, not a proven bound. |
| Press classification | 10 short, 10 confirmed hold, 10 intermediate-release trials | Correct action for each deliberate short/hold; no POST for intermediate releases | Observe switch waveform/timing where available, Serial action and database state. |
| Outage feedback | 3 Wi-Fi loss and 3 backend-loss trials | No success feedback for a failed send; no fabricated Taken record | Record LED/Serial behavior and state; a selected pending action is retained for retry, but physical recovery remains unverified. |

Use one consistent timer for HTTP duration. State whether the reported
time includes LED feedback (the response-time target above does not).
Sort the 30 durations and use a documented percentile method, such as the
nearest-rank 95th percentile. Count timeout/transport failures separately;
do not discard them to make the result look better. Proposed trial counts
are not executed-trial counts: until run, record `0 executed / Not Tested`.

### Functional test cases

| ID | Setup and input | Expected current behavior | Observed result |
|---|---|---|---|
| C01 | Valid token; one due row; `taken` | 200, success JSON, one dose log, due/snooze cleared | PASS: simulated device HTTP and SQLite |
| C02 | Unknown or absent token | 401; no acknowledgment | PASS: simulated HTTP; unchanged database digest |
| C03 | Valid token; `action: "unknown"` | 400; no dose transition (token use may update last-seen) | PASS: API validation |
| C04 | Physical short closure then release | Firmware sends `taken`; outcome follows C01 | NOT TESTED: physical GPIO input |
| C05 | Physical hold until steady LED, then release | Firmware sends `snooze`; 200 if due, deadline persisted, no Taken log | HTTP Snooze verified; physical hold NOT TESTED |
| C06 | Backend stopped while Wi-Fi is connected | HTTP transport failure/non-200; five fast blinks; no successful log | HTTP outage/recovery verified; LEDs NOT TESTED |
| C07 | Wi-Fi disconnected before actuation | Eight fast blinks; no new selection; an existing pending action remains queued | NOT TESTED: physical ESP32 Wi-Fi |
| C08 | Repeat exact occurrence/request ID | First and exact retry return 200 with one effect; a new key for a resolved firing returns 409 | PASS: sequential and actual concurrent HTTP checks |
| C09 | Valid token but no currently due reminder | Selection returns 200 and due=false; no action submitted | PASS: API/HTTP no-due checks |
| C10 | Token for account A; only B has a due reminder | A selection reports due=false; an explicit B target returns 404; B unchanged | PASS: simulated HTTP account isolation |
| C11 | Two due medicines; repeat identical bound request | One effect, same receipt; second medicine remains due. Id-less actions fail with 400. | PASS: unit, concurrent and real HTTP checks; historical unsafe behavior retained separately |
| C12 | Snooze, then restart backend before deadline | Persisted deadline remains and regular checks re-fire when reached | PASS: real 300-second waits with process restarts |
| C13 | Hardware Taken while browser alarm is showing | Database/log changes; browser reconciles on next successful poll | PASS: simulated device HTTP + Chromium polling |

Keep failure diagnosis separate from application changes. A documentation
correction is not a firmware/backend fix, and a test plan is not a pass
record. If an acceptance target fails, report the actual sample and cause;
retest only after a separately authorized change or configuration repair.

### Software-only API demonstration

This sends the same application message as the hub, but does **not** test
GPIO, debounce, Wi-Fi association, uploaded firmware or LEDs. Run only on
a disposable local demo account with the intended due reminder:

```bash
# Set DOSECLOCK_DEVICE_TOKEN privately in the environment first.
python3 tests/esp32_simulator.py --host http://<host-lan-ip>:5050 --action taken --request-file /private/tmp/doseclock-demo-request.json
```

Repeat that command with the same file to demonstrate a safe retry. Use a new
file for a deliberately new action; use `--action snooze` with its own new
request file to demonstrate Snooze. Files contain firing identity, not the
token. Never record a terminal containing real credentials.

After a successful Taken, refresh `/logs` under the paired account. For
an optional read-only SQLite check, if the SQLite CLI is installed:

```bash
sqlite3 'file:backend/schedules.db?mode=ro' \
  "SELECT l.id, m.medicine_name, m.time, l.taken_at
   FROM dose_log l JOIN medicines m ON m.id = l.medicine_id
   JOIN users u ON u.id = m.user_id
   WHERE u.username = 'review_demo'
   ORDER BY l.id DESC LIMIT 10;"
```

Replace `review_demo` with the disposable account's username. For Snooze,
inspect that account's `medicines.is_due` and `snoozed_until`; a dose-log
row is not the expected Snooze outcome. Do not edit or delete the database
to manufacture test results.

The original suite contains two database tests and seven hardware-API tests.
The validation branch adds 23 database/API/scheduler regressions, plus live
HTTP, audio and Chromium checks. See `docs/testing/TEST_REPORT.md` for actual results. It requires the declared Python dependencies. Since
importing `app` can create a session-key file, run it in an exported
temporary checkout when preserving the original workspace:

```bash
DOSECLOCK_TEST_COPY="$(mktemp -d)"
git archive HEAD | tar -x -C "$DOSECLOCK_TEST_COPY"
(cd "$DOSECLOCK_TEST_COPY" && PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s tests -v)
```

The suite uses Flask's test client and disposable SQLite; it is not a
physical ESP32 test. A missing dependency is a blocked run, not a pass.
The retained older audio-failure check patches generation while firing reads
only cache. Stronger provider-failure, real concurrency and retry regressions
are in `tests/test_resolution.py`; use the full suite for those claims.

### Troubleshooting by layer

| Symptom | Check first | Interpretation / next step |
|---|---|---|
| Dots continue at boot | SSID/password, board-compatible Wi-Fi, AP availability | The setup loop is still waiting for association. No API exchange occurred. |
| Local browser works; hub cannot connect | LAN IP, port 5050, guest/client isolation, firewall, host awake | `localhost` on the ESP32 is not the laptop. Confirm access from another LAN client. |
| Negative HTTP result in Serial | Host process/address and network route | Transport failed before a normal HTTP response. Record the library error text. |
| HTTP 401 | Token copied from the intended pairing response | Authentication failed; do not diagnose it as a GPIO fault. |
| HTTP 400 | Action, JSON, id/fired_at and request_id | Legacy id-less bodies are rejected; update the client and use the selected firing. |
| HTTP 404 | Selected target and paired account | Target absent or outside the paired account; selection with no due row instead returns due=false. |
| HTTP 409 | Another client/device resolving the selected firing | Keep the old binding on retries. A new intentional action may select current state; never retarget an uncertain request. |
| LED does not match Serial success | Actual GPIO2 LED wiring/polarity, resistor, visible placement | Serial/HTTP and database state can distinguish feedback wiring from an API problem. |
| Hold never sends | Switch still closed or no confirmed hold | Actions are sent on release; an intermediate duration intentionally sends nothing. |
| One press changes a different medicine | Multiple pending rows or wrong token owner | Inspect the selected id/fired_at and pairing owner; an exact retry cannot select another medicine. |
| Successful hardware action leaves browser alarm | Polling interval or failed network request | Allow the next successful 17-second poll; inspect HTTP and database state if the display remains stale. |
| No spoken audio | User gesture, cached path, actual file, TTS/network readiness | Do not treat missing audio as an HTTP/device fault. No generic offline speech fallback is included. |

Evidence for a completed integration test should combine the HTTP/Serial
result with an account-scoped state change. A photo establishes assembly;
a screen showing a curl request establishes a simulated API exchange.
Neither alone proves physical switch timing or independent medication use.

## Executed Review 3 software validation

Run the complete unit suite in a disposable exported source tree:

```bash
python3 -m pip install -r tests/requirements-review3.txt
python3 -m playwright install chromium
python3 -B tests/run_review3_suite.py --source . --output /private/tmp/doseclock-unit-new-run
```

See [TEST_REPORT](docs/testing/TEST_REPORT.md), [review results](docs/testing/REVIEW3_RESULTS.md)
and [bug/retest evidence](docs/testing/BUG_REPORT.md). Live test helpers bind only
to loopback and use temporary databases. The Python simulator exercises the real
device endpoint; it does not validate physical switch classification or LEDs.
The new device protocol requires occurrence identity and a durable request ID;
exact retries preserve their target. Six translated TTS templates are verified
as provider inputs and MP3/cache handling; human intelligibility is unverified.
The ESP32 target build and physical retry behavior still require validation.

## Multilingual reminder content (23 October 2026 update)

English, Hindi, Tamil, Telugu, Kannada and Bengali each have a translated
reminder template. The medicine label is inserted unchanged; time slots,
course counters and dose instructions are not translated or inferred. Audio
cache names include the actual sentence and language, preventing reuse of the
old English-only non-English files. Existing cache files are preserved; new
speech requires connectivity. Empty/failed generation is not published, and
visual reminders remain usable when speech is unavailable. Provider inputs,
MP3 handling and cache reuse are tested; human pronunciation/intelligibility
and independent native-speaker review remain unverified.

October 23 testing is a later validation, distinct from the original October 9
Review 3. See [current results](docs/testing/REVIEW3_RESULTS.md) and
[software-resolution evidence](docs/testing/SOFTWARE_RESOLUTION_20261023.md).


## Firmware validation (25 October 2026)

The complete software suite has 115 passing checks, no failures and five
unexecuted physical/human/LAN cases. A separate clean ESP32 target compilation
passed and generated firmware.bin, bringing the combined count to 116 passes.
Compilation and host simulations do not establish physical hardware acceptance.
See [the dated firmware report](docs/testing/FIRMWARE_RESOLUTION_20261025.md) and
[Ayush's private-build and physical checklist](docs/testing/AYUSH_FIRMWARE_CHECKLIST_20261025.md).
