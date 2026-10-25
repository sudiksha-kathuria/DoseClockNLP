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
#define ARDUINOJSON_USE_LONG_LONG 1
#include <ArduinoJson.h> // ArduinoJson 7
#include <Preferences.h>
#include <esp_system.h>
#include <string.h>

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

// Save the selected occurrence and request ID BEFORE sending. No token is
// stored in this queue. Exact retries survive reboot and never select a new
// reminder. Server receipts make a lost successful response safe to retry.
Preferences retryStore;
String pendingBody;
bool storageReady = false;
uint32_t lastRetryAt = 0;
constexpr uint32_t RETRY_INTERVAL_MS = 5000;

bool validPending(JsonDocument &doc) {
  const char *action = doc["action"] | "";
  return doc["id"].is<int64_t>() && doc["id"].as<int64_t>() > 0 &&
         doc["fired_at"].is<const char *>() && strlen(doc["fired_at"].as<const char *>()) > 0 &&
         doc["request_id"].is<const char *>() && strlen(doc["request_id"].as<const char *>()) >= 8 &&
         (strcmp(action, "taken") == 0 || strcmp(action, "snooze") == 0);
}

void attemptPending() {
  if (!storageReady || pendingBody.length() == 0) return;
  lastRetryAt = millis();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected; selected action retained for retry.");
    blinkLed(8, 60);
    return;
  }
  JsonDocument request;
  if (deserializeJson(request, pendingBody) || !validPending(request)) {
    Serial.println("Invalid stored action; no request sent. Caregiver reset required.");
    return;
  }
  request["token"] = DEVICE_TOKEN;
  String wireBody;
  serializeJson(request, wireBody);
  HTTPClient http;
  http.begin(String(DOSECLOCK_HOST) + "/api/device/action");
  http.setTimeout(3000);
  http.addHeader("Content-Type", "application/json");
  int status = http.POST(wireBody);
  String response = http.getString();
  http.end();
  Serial.printf("Bound action responded %d\n", status); // Never print credentials/body.
  JsonDocument result;
  bool confirmed = status == 200 && !deserializeJson(result, response) && result["success"] == true;
  bool rejected = status >= 400 && status < 500;
  if (confirmed || rejected) {
    if (!retryStore.remove("pending")) {
      Serial.println("Could not clear local queue; retaining identical request.");
      blinkLed(5, 60);
      return;
    }
    pendingBody = "";
    blinkLed(confirmed ? 2 : 5, confirmed ? 150 : 60);
  } else {
    Serial.println("Result uncertain; will retry the identical selected action.");
    blinkLed(5, 60);
  }
}

void sendAction(const char *action) {
  if (!storageReady) {
    Serial.println("Retry storage unavailable; no action sent.");
    blinkLed(5, 60);
    return;
  }
  if (pendingBody.length() > 0) {
    Serial.println("Resolving the original pending action before accepting another.");
    attemptPending();
    return;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected; no firing selected or action sent.");
    blinkLed(8, 60);
    return;
  }
  HTTPClient http;
  http.begin(String(DOSECLOCK_HOST) + "/api/device/reminder");
  http.setTimeout(3000);
  http.addHeader("Content-Type", "application/json");
  JsonDocument auth;
  auth["token"] = DEVICE_TOKEN;
  String authBody;
  serializeJson(auth, authBody);
  int status = http.POST(authBody);
  String response = http.getString();
  http.end();
  JsonDocument selected;
  if (status != 200 || deserializeJson(selected, response) || !selected["due"].as<bool>() ||
      !selected["id"].is<int64_t>() || !selected["fired_at"].is<const char *>()) {
    Serial.println("No current firing selected; no action sent.");
    blinkLed(5, 60);
    return;
  }
  char requestId[33];
  snprintf(requestId, sizeof(requestId), "%08lx%08lx%08lx%08lx",
           (unsigned long)esp_random(), (unsigned long)esp_random(),
           (unsigned long)esp_random(), (unsigned long)esp_random());
  JsonDocument pending;
  pending["id"] = selected["id"].as<int64_t>();
  pending["fired_at"] = selected["fired_at"].as<const char *>();
  pending["action"] = action;
  pending["request_id"] = requestId;
  String saved;
  serializeJson(pending, saved);
  if (!validPending(pending) || retryStore.putString("pending", saved) != saved.length()) {
    Serial.println("Could not persist selected action; no request sent.");
    blinkLed(5, 60);
    return;
  }
  pendingBody = saved;
  attemptPending();
}

void setup() {
  Serial.begin(115200);
  pinMode(SWITCH_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  storageReady = retryStore.begin("doseclock", false);
  if (storageReady) pendingBody = retryStore.getString("pending", "");
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
  if (pendingBody.length() > 0 && millis() - lastRetryAt >= RETRY_INTERVAL_MS) attemptPending();
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
