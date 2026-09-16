# DoseClock: the accessibility and hardware problem

## The problem

DoseClock originally had exactly one way to answer a reminder: tap
"Taken" or "Snooze" on a touchscreen, or speak the word. That fails two
groups of real users:

- **Patients who can't move**, anywhere from tremor or arthritis making
  a precise tap unreliable, up to no voluntary movement at all except
  one small motion somewhere in the body. A small on-screen button
  assumes a level of reach and precision this population often doesn't
  have, and speech recognition isn't a substitute. It's inconsistent for
  frail speech and useless for someone who can't speak.
- **Infants**: an infant cannot and should not be expected to confirm
  their own medication under any circumstance.

These are two different problems with two different correct answers.
Treating them as one ("build a fancier button") would have gotten the
infant case wrong, so they're addressed separately below.

## Infants: this is not a hardware problem

An infant's medicine is always administered and confirmed by a parent or
caregiver. There is no scenario where the infant itself should be
pressing a button or speaking a keyword. The correct fix is the
**caregiver's own DoseClock account**: the parent signs in with their own
login (see the main README), adds the child's medicine under their
account, and taps Taken themselves right after administering it. That's
now supported end-to-end because every medicine and every dose log
belongs to a signed-in user. No new sensor makes sense here. Adding one
would be solving a problem that doesn't exist while ignoring the real
one (a caregiver needs an account, not a gadget).

## Patients who can't move: the DoseClock Switch Hub

### Requirement, restated precisely

Confirm "Taken" or "Snooze" from a person who may have **no reliable
voluntary movement at all**, except for one small motion somewhere in
the body (a finger, a head turn, a breath) that varies patient to
patient and can't be assumed in advance.

### The hardware: one box, a standard switch jack, and a matched switch

Full parts list, wiring, and flashing steps: **`hardware/README.md`**.
Firmware: **`hardware/switch_hub.ino`**. Summary of what it is and why
each piece was chosen:

- **One ESP32**, mains-powered, sitting at the bedside. Not worn and not
  battery-run, because this patient isn't roaming around; it lives next
  to the bed, plugged into the wall like a lamp.
- **One 3.5mm mono accessibility-switch jack** wired to it. This is a
  deliberate interface choice, not a shortcut: it's the actual
  industry-standard connector assistive technology already uses (powered
  wheelchairs, AAC devices, environmental controls), specifically so one
  piece of electronics can accept any of the many switch shapes that
  exist for different disabilities. The firmware doesn't need to know
  what's plugged in. A switch either closes the circuit or it doesn't.
- **A purpose-built accessibility switch, picked per patient**, plugged
  into that jack: a large low-force paddle for someone who can still
  press with a finger, a pillow/cheek switch for someone who can only
  turn their head, a sip-and-puff breath switch for someone with no
  limb or head movement at all, or a grasp bulb for a weak squeeze.
  Buying a purpose-built switch here instead of designing one from
  scratch is intentional: these are body-contact, safety-relevant parts
  (especially sip-and-puff, which touches the airway), and that's
  exactly the kind of component that should be a tested, already-proven
  product rather than a first DIY attempt.
- **A confirmation LED** on the box, because the patient may not be
  facing or able to see the clock screen from bed. Two slow blinks means
  the dose was logged, five fast blinks means it wasn't (no network, or
  the token wasn't recognized), so a caregiver checking on the room can
  tell at a glance whether it actually worked.

**Why this over a touch/capacitive or motion sensor:** a physical switch
gives a hard, unambiguous, tactile "yes, that registered" click.
Capacitive/proximity sensors and bed-pressure or PIR motion sensors
*cannot distinguish deliberate intent from incidental movement* (rolling
over in bed, bedding brushing the sensor). They'd either miss real
presses or fire on nothing, the wrong failure mode for a medical
reminder. A mechanical switch is the same principle nurse call buttons
use, for the same reason.

**Why not build a custom EMG/twitch or camera-based sensor**, which
would technically work for patients with literally zero mechanical
movement: those need real biomedical engineering, skin-safe electrodes,
and are exactly the kind of safety and privacy-sensitive device that
shouldn't be a first-time DIY build. The 3.5mm switch jack sidesteps
this entirely. If a patient's condition needs something that
specialized, the AT industry already sells switches down to breath and
even single-eyebrow-twitch level that plug into the exact same jack this
hub already supports, with no firmware or hardware changes needed here.

**Algorithm (`hardware/switch_hub.ino`):**
- Short press (< 600ms) → send `taken`.
- Press-and-hold (~1.5s, LED goes solid to confirm the hold registered
  before it fires) → send `snooze`.
- One switch, two deliberately different gestures, chosen over needing
  two separate switches, because locating "the correct one of two
  similar switches" is itself hard for someone with very limited motor
  control; one input with two distinguishable *gestures* is safer.
- 50ms debounce so one physical actuation can't register as several.
- A release partway through the hold window (neither a clean short tap
  nor a confirmed hold) sends nothing. A wrong guess (a false "taken")
  is worse than simply not responding.

**Escalation, not more sensors, for total non-response:** if a reminder
gets no response at all (no switch, no voice, no screen tap) for
several consecutive firings, that's a caregiver-notification problem (a
job for the `devices`/account layer already in `database.py`), not a
sensor problem. Deliberately not solved with a camera or continuous
motion sensor trying to infer whether the patient is still capable of
pressing anything. Disproportionate and privacy-invasive for a medicine
reminder.

**Server-side integration (already implemented, this *is* live code):**
`POST /api/device/action` in `backend/app.py` accepts
`{ "token": "<paired device token>", "action": "taken" | "snooze" }`.
The hub has no browser and no session cookie, so it authenticates with a
long-lived per-device token instead (minted from the Logs screen,
`database.create_device_token`) rather than the cookie-based login flow
built for humans. This is the same code path `/mark_taken` uses
internally (`_perform_mark_taken` in `app.py`), so a switch press and a
screen tap produce identical, indistinguishable log entries.

```bash
# what switch_hub.ino sends once the switch is released
curl -X POST http://<clock-host>:5050/api/device/action \
  -H "Content-Type: application/json" \
  -d '{"token": "<paired-device-token>", "action": "taken"}'
```

### Software fallback, for anyone who already owns a generic switch

Independent of the Switch Hub, `frontend/static/js/clock.js` also
auto-highlights Taken/Snooze on a scan cycle and confirms on Space/Enter,
the default output of any generic USB/Bluetooth single-switch interface.
If a patient already has one from unrelated AT equipment, it works with
DoseClock immediately with nothing to build. The Switch Hub above is the
recommended path when starting from nothing, since it's purpose-built
for this, gives physical confirmation via its own LED, and doesn't
depend on whichever device happens to be driving the browser.

## Summary

| User | Root cause | Fix | New hardware to buy/build? |
|---|---|---|---|
| Infant | Can't and shouldn't self-confirm | Caregiver's own login + account | No |
| Patient who can't move (any degree) | Can't operate a touchscreen or reach it | **DoseClock Switch Hub** (`hardware/`) + a switch matched to the patient's ability | Yes, see `hardware/README.md` for the full parts list and build steps |
| Someone who already owns a generic AT switch | Same as above, hardware already on hand | Plug it into whatever runs the browser; DoseClock's scan mode already listens for it | No |
