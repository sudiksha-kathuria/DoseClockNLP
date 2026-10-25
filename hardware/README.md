# hardware/: the DoseClock Switch Hub

A real, buildable piece of hardware that lets a patient who can't move,
not "has trouble tapping a screen," but has little or no reliable
voluntary movement anywhere, confirm a dose with whatever tiny motion
they can still make: a finger twitch, a head turn against a pillow, a
breath. Full rationale for every choice below is in `/HARDWARE.md`.

This is firmware and a wiring/parts guide, not a finished assembled
product. Build and bench-test it before it's relied on for anyone's
medicine schedule.

## What it is

One ESP32, permanently plugged into a wall outlet at the bedside, with a
single **3.5mm mono accessibility-switch jack** wired to it. That jack is
the actual industry-standard connector used across assistive technology.
It's how powered wheelchairs, AAC devices, and environmental controls
all accept switches, specifically so one electronic box can work with
any of the dozens of switch shapes that exist for different
disabilities. The Switch Hub doesn't need to know what's plugged in: a
switch closes the circuit, or it doesn't.

## Shopping list

| # | Part | Approx. cost | Notes |
|---|---|---|---|
| 1 | ESP32 DevKit V1 (WROOM-32) board | $6-10 | Any generic one; needs Wi-Fi + USB programming, nothing exotic |
| 2 | 3.5mm mono panel-mount jack socket | $1-2 | "Switch-compatible" / "TS 3.5mm panel mount jack", 2-contact, not the 3-contact stereo kind |
| 3 | **One** accessibility switch, picked to match the patient | $25-90 | See "Picking the switch" below, buy the one that matches what the patient can actually move, not a generic button |
| 4 | Small project enclosure box | $5-10 | Big enough for the ESP32 + jack; a plastic mint tin works for a prototype |
| 5 | 5V USB wall adapter + cable | $5-10 | Any phone charger; this stays plugged in permanently |
| 6 | Hookup wire + a few inches of solder, or a small screw-terminal block | $5 | For the jack-to-ESP32 connection |

Total: roughly **$45-120** depending on which switch you pick, almost
entirely the switch itself. No battery, no soldering iron required if
you use screw terminals instead of solder.

### Picking the switch (this is the part that matters)

The whole point of the jack is that you buy *one* switch that fits the
specific patient, not a one-size-fits-all button. Pick one:

| If the patient can still... | Buy | Why |
|---|---|---|
| Press a finger, knuckle, or hand down with even light force | A large low-force paddle/"jelly bean"-style switch | Big flat target, needs only a few grams of force, can be taped anywhere within reach |
| Turn or press their head to one side, even slightly | A flat pillow/cheek switch (velcro or pillow-mount) | Slides under or beside the pillow; triggered by the head pressing it, no hand needed at all |
| Do neither of the above, but breathe on their own | A sip-and-puff (pneumatic breath) switch | The most universal option for near-total paralysis (this is exactly what it's used for on powered wheelchairs): a puff or sip closes the circuit through a tube, no limb or head movement needed |
| Squeeze weakly | A grasp/squeeze-bulb switch | Closes on a light hand squeeze, doesn't require opening the hand again to reset |

All four are standard, purpose-built, already-manufactured medical/AT
switches sold with a 3.5mm mono plug. Search "3.5mm accessibility
switch" plus the type (e.g. "sip and puff switch," "pillow switch,"
"jelly bean switch"). Building your own low-force switch from scratch
was deliberately rejected: these are safety-relevant, skin/body-contact
parts, and switches this specialized (especially sip-and-puff, which
touches the airway) are exactly the kind of thing that should be a
tested, purpose-built product, not a first-time DIY part.

## Wiring

1. The jack has two contacts: **tip** and **sleeve**. Wire tip to
   `SWITCH_PIN` (GPIO4) on the ESP32, and sleeve to `GND`.
2. That's the entire circuit. `INPUT_PULLUP` in the firmware handles the
   rest, no external resistor needed.
3. (Optional but recommended) if your ESP32 board's built-in LED
   (usually GPIO2) isn't easily visible once boxed up, wire a separate
   LED + ~220Ω resistor from a free GPIO to GND and change `LED_PIN` in
   the firmware to match. This is what blinks to confirm a press was
   received, which matters if the patient can't see the clock screen
   from bed.
4. Mount the ESP32 and jack in the enclosure with the jack socket
   accessible from outside; run the USB cable out for power.

## Flashing and pairing

1. Open `switch_hub.ino` in the Arduino IDE (or PlatformIO). Install the
   ESP32 board package if you haven't before (Boards Manager → search
   "esp32"). Install ArduinoJson 7 through Library Manager as well.
2. Fill in your Wi-Fi name/password and `DOSECLOCK_HOST` (the IP address
   and port, `5050`, of the machine running DoseClock's Flask server;
   find the IP with `hostname -I` on Linux, `ipconfig` on Windows, or
   `ipconfig getifaddr en0` on macOS). The address in the sketch is an
   example, not a fixed DoseClock address. Recheck the laptop IP when
   changing Wi-Fi networks or hotspots.
3. In DoseClock, log in as the patient's account and go to
   **Logs → Pair a hardware button**. Name it (e.g. "Bedside switch"),
   submit, and copy the token it displays.
4. Paste that token into `DEVICE_TOKEN` in the sketch.
5. Flash it to the ESP32, open Serial Monitor at 115200 baud, and
   confirm it connects to Wi-Fi (three slow LED blinks on boot means
   ready).
6. Plug the chosen switch into the jack, force a reminder to fire (or
   just wait for a real one), and press the switch. Serial Monitor
   should log the forwarded request and the DoseClock Logs screen should
   show the dose.

Keep both devices on the same Wi-Fi network. Start Flask with
`backend/.venv/bin/python backend/app.py` from the repository root; it
listens on `0.0.0.0:5050`. Check `http://<laptop-lan-ip>:5050/` from the
laptop before testing the switch. The laptop must stay awake and Flask
must remain running. The ESP32 can use Wi-Fi without the laptop's USB
data cable, but it still needs power from a USB wall adapter or another
suitable supply. EN resets the ESP32; it does not erase the uploaded sketch.

For the GPIO2 status LED, wire GPIO2/D2 through a roughly 220Ω resistor
to the LED anode (long leg), then connect the cathode to GND. Connecting
the LED to 3.3V instead makes it stay on without firmware control.

The firmware first selects an account-owned firing with
`POST /api/device/reminder`, then sends `token`, `action`, `id`, `fired_at`
and `request_id` to `POST /api/device/action`. It persists the selected request
in Preferences before sending; transport/5xx failures retry the same request,
including after reboot. While a request is unresolved, new switch gestures are
ignored and automatic retries keep the original binding. Only confirmed success
or a definite 4xx rejection clears it. After every blocking request/LED sequence,
the input must observe a continuous 50 ms release before accepting a fresh,
debounced press. Network work never runs during a measured gesture. The original
post-press-debounce thresholds remain: <600 ms Taken, >=1500 ms Snooze, and no
action in the intermediate window. Release debounce does not extend the hold.

### Reproducible build and USB recovery (25 October 2026)

The pinned [PlatformIO project](platformio.ini) uses `esp32dev`, Espressif32 6.9.0
(Arduino ESP32 2.0.17) and ArduinoJson 7.4.3. PlatformIO Core 6.2.0 produced a
complete `firmware.bin` on 25 October 2026; this is a cross-compilation result,
not a physical test. From the repository root, with PlatformIO installed:

```sh
pio run --project-dir hardware --environment esp32dev
```

The ArduinoJson proxy comparison now explicitly extracts a Boolean. Reminder
IDs use signed 64-bit parsing, validation, storage and serialization, matching
Flask/SQLite's positive signed 64-bit range. The request fields and IDs used for
retries have not changed. Valid older saved requests remain retryable unchanged.

A durable `pending_set` marker is written before the pending JSON. Incomplete
writes, invalid JSON/schema/identity or a wrong stored value type block all
actions and automatic transmission. No token is stored in this retry data.

For a **reported corrupt queue only**, a caregiver can use USB Serial Monitor
at **115200 baud**, with **Newline** enabled, and send exactly:

```text
CLEAR CORRUPT RETRY
```

Recovery clears only the sketch's `doseclock` Preferences namespace. It sends
no HTTP request, cannot be invoked by the switch, and requires a new debounced
release/press before any new action. A failed clear remains blocked. A valid
uncertain request cannot be cleared using this command. Recovery also works
while setup is waiting for Wi-Fi. EN/reboot alone does not clear saved data.
The previous outcome may be unknown after corruption: check Flask receipts and
dose history before making any new intentional acknowledgment. A caregiver's
recovery command cancels any input gesture in progress.

Three boot blinks indicate Wi-Fi connection; check Serial for queue/storage
errors before treating the switch as ready. Serial action logs include action,
64-bit ID, firing timestamp, request ID and HTTP status, excluding the token.

See [Ayush's flashing and physical checklist](../docs/testing/AYUSH_FIRMWARE_CHECKLIST_20261025.md).
No hardware has been flashed or independently tested in this validation.

Install this firmware and the updated backend together. Old token/action-only
requests are rejected with 400. See [protocol details](../docs/DEVICE_PROTOCOL.md).
Firmware build and physical GPIO/LED/Wi-Fi/NVS behavior require the separate
verification described in the testing report; backend simulation does not
establish those results.

Keep real Wi-Fi credentials and paired tokens in your local upload
copy. Do not commit them to this repository.

## Placement

Position the switch wherever the patient's usable movement actually is:
under a hand resting on the bed, against a cheek on the pillow, near the
mouth for sip-and-puff, or at the foot of the bed for a foot pedal. The
Switch Hub box itself just needs to sit somewhere near an outlet within
the jack's cable reach. It doesn't need to be visible or reachable by
the patient, only the switch does.
