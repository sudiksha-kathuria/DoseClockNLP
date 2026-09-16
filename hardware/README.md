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
   "esp32").
2. Fill in your Wi-Fi name/password and `DOSECLOCK_HOST` (the IP address
   and port, `5050`, of the machine running DoseClock's Flask server;
   find the IP with `ipconfig getifaddr en0` on the Mac running it).
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

## Placement

Position the switch wherever the patient's usable movement actually is:
under a hand resting on the bed, against a cheek on the pillow, near the
mouth for sip-and-puff, or at the foot of the bed for a foot pedal. The
Switch Hub box itself just needs to sit somewhere near an outlet within
the jack's cable reach. It doesn't need to be visible or reachable by
the patient, only the switch does.
