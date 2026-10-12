/*
 * switch_hub.ino
 * ---------------
 * Firmware for the DoseClock Switch Hub - the physical hardware answer
 * to "a patient who can't move can't use a touchscreen." Full design
 * rationale, bill of materials, and build steps are in /HARDWARE.md and
 * hardware/README.md. Read those first - this file is just the code.
 *
 * What it is: a single ESP32, mains-powered, sitting at the bedside,
 * with one standard 3.5mm mono accessibility-switch jack wired to it.
 * ANY switch that uses that jack - a large low-force paddle, a pillow/
 * cheek switch, a grasp bulb, a sip-and-puff breath switch, a foot
 * pedal - works with this same board unmodified, because they're all
 * electrically just "the jack's tip touches its sleeve, or it doesn't."
 * The patient (or whoever sets this up) picks whichever switch matches
 * whatever movement the patient actually has left; the firmware doesn't
 * need to know or care which kind is plugged in.
 *
 * Behaviour, identical logic to a keyboard's "press" vs "press-and-hold":
 *   - Short press (<600ms)                -> POSTs action "taken"
 *   - Press-and-hold (~1.5s, onboard/wired LED goes solid to confirm
 *     the hold registered before it fires) -> POSTs action "snooze"
 *   - A release partway through the hold window (neither a clean short
 *     tap nor a confirmed hold) sends nothing - guessing wrong here
 *     (a false "taken") is worse than just not responding.
 *   - 50ms debounce so one physical actuation can't register as several.
 *
 * This device is mains/USB powered and stays in one place, so - unlike
 * a worn pendant - there's no battery life to manage and no deep sleep
 * needed; it just polls the switch pin in a plain loop.
 */

#include <WiFi.h>
#include <HTTPClient.h>

// ---- Configure before flashing --------------------------------------
constexpr char WIFI_SSID[] = "your-wifi-name";
constexpr char WIFI_PASSWORD[] = "your-wifi-password";
constexpr char DOSECLOCK_HOST[] = "http://192.168.1.50:5050"; // example only: replace with the laptop's current LAN IP
constexpr char DEVICE_TOKEN[] = "paste-token-from-the-logs-screen";
// -----------------------------------------------------------------------

// The 3.5mm jack's tip contact goes to this pin, its sleeve contact to
// GND. INPUT_PULLUP means "not pressed" reads HIGH and "pressed" (tip
// shorted to sleeve/GND by the switch) reads LOW - no external resistor
// needed.
constexpr int SWITCH_PIN = 4;
constexpr int LED_PIN = 2; // most ESP32 dev boards have one built in here

constexpr uint32_t DEBOUNCE_MS = 50;
constexpr uint32_t SHORT_PRESS_MAX_MS = 600;
constexpr uint32_t HOLD_CONFIRM_MS = 1500;

void blinkLed(int times, int onMs) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(onMs);
    digitalWrite(LED_PIN, LOW);
    delay(onMs);
  }
}

void sendAction(const char *action) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected; no action sent.");
    blinkLed(8, 60); // fast blink = no network, nothing was sent
    return;
  }

  HTTPClient http;
  http.begin(String(DOSECLOCK_HOST) + "/api/device/action");
  http.addHeader("Content-Type", "application/json");
  String body = String("{\"token\":\"") + DEVICE_TOKEN + "\",\"action\":\"" + action + "\"}";
  int status = http.POST(body);
  Serial.printf("Sent '%s', server responded %d\n", action, status);
  if (status < 0) {
    Serial.printf("HTTP error: %s\n", HTTPClient::errorToString(status).c_str());
  }
  http.end();

  // Confirmation feedback the patient (or a caregiver in the room) can
  // see even if they can't see the clock screen from the bed: two slow
  // blinks for success, five fast blinks if the server rejected it
  // (e.g. an unpaired token, or no reminder currently due).
  if (status == 200) {
    blinkLed(2, 150);
  } else {
    blinkLed(5, 60);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(SWITCH_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println(" connected.");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
  blinkLed(3, 200); // three blinks on boot = ready
}

void loop() {
  if (digitalRead(SWITCH_PIN) != LOW) {
    delay(20);
    return; // not pressed - keep polling
  }

  // Debounce: require the contact to stay closed past DEBOUNCE_MS
  // before treating it as a real actuation, not switch bounce/noise.
  delay(DEBOUNCE_MS);
  if (digitalRead(SWITCH_PIN) != LOW) return;

  uint32_t pressStart = millis();
  bool holdConfirmed = false;
  while (digitalRead(SWITCH_PIN) == LOW) {
    uint32_t held = millis() - pressStart;
    if (held >= HOLD_CONFIRM_MS && !holdConfirmed) {
      holdConfirmed = true;
      digitalWrite(LED_PIN, HIGH); // steady-on = "held long enough for Snooze"
    }
    delay(10);
  }
  digitalWrite(LED_PIN, LOW);

  uint32_t pressDuration = millis() - pressStart;
  if (pressDuration < SHORT_PRESS_MAX_MS) {
    sendAction("taken");
  } else if (holdConfirmed) {
    sendAction("snooze");
  }
}
