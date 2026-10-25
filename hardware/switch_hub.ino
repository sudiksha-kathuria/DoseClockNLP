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
#include "switch_input.h"

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

SwitchInput switchInput;

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
bool queueCorrupt = false;
bool queueMarked = false;
uint32_t lastRetryAt = 0;
constexpr uint32_t RETRY_INTERVAL_MS = 5000;

bool validText(JsonVariantConst value, size_t minimum, size_t maximum) {
  if (!value.is<const char *>()) return false;
  const JsonString text = value.as<JsonString>();
  return text.size() >= minimum && text.size() <= maximum &&
         strlen(text.c_str()) == text.size(); // Never truncate embedded NULs.
}

bool validPending(JsonDocument &doc) {
  const char *action = doc["action"] | "";
  if (!doc.is<JsonObject>() || doc.size() != 4 || !doc["id"].is<int64_t>() ||
      doc["id"].is<bool>() || doc["id"].as<int64_t>() <= 0 ||
      !validText(doc["fired_at"], 1, 128) || !validText(doc["request_id"], 8, 128) ||
      !validText(doc["action"], 5, 6) ||
      (strcmp(action, "taken") != 0 && strcmp(action, "snooze") != 0)) return false;
  for (const char *p = doc["request_id"].as<const char *>(); *p; ++p) {
    if (!((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') ||
          (*p >= '0' && *p <= '9') || *p == '_' || *p == '-')) return false;
  }
  return true;
}

void corruptQueue() {
  queueCorrupt = true;
  switchInput.inhibit();
  Serial.println("Invalid saved retry; actions blocked. USB command: CLEAR CORRUPT RETRY");
}

void loadPending() {
  const bool hasBody = retryStore.isKey("pending");
  const bool hasMarker = retryStore.isKey("pending_set");
  queueMarked = hasMarker && retryStore.getType("pending_set") == PT_U8 &&
                retryStore.getUChar("pending_set", 0) == 1;
  if (!hasBody && !hasMarker) return;
  if ((hasMarker && !queueMarked) || !hasBody || retryStore.getType("pending") != PT_STR) {
    corruptQueue();
    return;
  }
  pendingBody = retryStore.getString("pending", "");
  JsonDocument saved;
  if (pendingBody.length() > 512 || deserializeJson(saved, pendingBody) || !validPending(saved)) corruptQueue();
  // A valid pre-marker queue from the October 23 firmware is retained unchanged.
}

// USB maintenance only, never a switch gesture or HTTP operation. A valid
// uncertain action cannot be discarded through this recovery command.
bool serviceRecoveryCommand() {
  static char line[40];
  static size_t length = 0;
  static bool overflow = false;
  for (unsigned int read = 0; read < 64 && Serial.available(); ++read) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') continue;
    if (c != '\n') {
      if (static_cast<unsigned char>(c) < 32 || static_cast<unsigned char>(c) > 126) { overflow = true; continue; }
      if (length + 1 < sizeof(line)) line[length++] = c;
      else overflow = true;
      continue;
    }
    line[length] = '\0';
    const bool recover = !overflow && strcmp(line, "CLEAR CORRUPT RETRY") == 0;
    length = 0;
    overflow = false;
    if (!recover) {
      Serial.println("Unknown maintenance command; no action sent.");
    } else if (!storageReady || !queueCorrupt) {
      Serial.println("Recovery refused: no corrupt queue or storage unavailable; no action sent.");
    } else if (!retryStore.clear()) {
      Serial.println("Recovery failed; actions remain blocked. No action sent.");
    } else {
      pendingBody = "";
      queueMarked = queueCorrupt = false;
      Serial.println("Corrupt retry cleared; no action sent. Release switch, then press anew.");
    }
    switchInput.inhibit();
    return true;
  }
  return false;
}

void attemptPending() {
  if (!storageReady || queueCorrupt || pendingBody.length() == 0) return;
  lastRetryAt = millis();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected; selected action retained for retry.");
    blinkLed(8, 60);
    return;
  }
  JsonDocument request;
  if (deserializeJson(request, pendingBody) || !validPending(request)) {
    corruptQueue();
    return;
  }
  if (!queueMarked) {
    if (retryStore.putBool("pending_set", true) != 1) {
      Serial.println("Could not mark saved retry; no request sent.");
      return;
    }
    queueMarked = true;
  }
  if (retryStore.getType("pending") != PT_STR) {
    corruptQueue();
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
  Serial.printf("Bound action %s id=%lld fired_at=%s request_id=%s responded %d\n",
                request["action"].as<const char *>(), (long long)request["id"].as<int64_t>(),
                request["fired_at"].as<const char *>(), request["request_id"].as<const char *>(), status);
  // Identity is observable; credentials and the full request body are never logged.
  JsonDocument result;
  bool confirmed = status == 200 && !deserializeJson(result, response) && result["success"] == true;
  bool rejected = status >= 400 && status < 500;
  if (confirmed || rejected) {
    if (!retryStore.remove("pending")) {
      Serial.println("Could not clear local queue; retaining identical request.");
      blinkLed(5, 60);
      return;
    }
    // A separate marker makes an interrupted/failed queue write detectable on
    // reboot. Orphaned markers fail closed; recovery never acknowledges a dose.
    if (!retryStore.remove("pending_set")) {
      corruptQueue();
      return;
    }
    pendingBody = "";
    queueMarked = false;
    blinkLed(confirmed ? 2 : 5, confirmed ? 150 : 60);
  } else {
    Serial.println("Result uncertain; will retry the identical selected action.");
    blinkLed(5, 60);
  }
}

void sendAction(const char *action) {
  if (!storageReady || queueCorrupt) {
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
  if (status != 200 || deserializeJson(selected, response) ||
      !selected["due"].is<bool>() || !selected["due"].as<bool>() ||
      !selected["id"].is<int64_t>() || selected["id"].is<bool>() || selected["id"].as<int64_t>() <= 0 ||
      !validText(selected["fired_at"], 1, 128)) {
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
  if (!validPending(pending)) return;
  if (retryStore.putBool("pending_set", true) != 1) {
    corruptQueue();
    return;
  }
  queueMarked = true;
  if (retryStore.putString("pending", saved) != saved.length()) {
    Serial.println("Could not persist selected action; no request sent.");
    corruptQueue();
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
  if (storageReady) loadPending();
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    serviceRecoveryCommand(); // USB recovery also works without Wi-Fi.
    delay(300);
    Serial.print(".");
  }
  Serial.println(" connected.");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
  blinkLed(3, 200); // three blinks on boot = ready
  switchInput.inhibit();
}

void loop() {
  if (!storageReady || queueCorrupt || pendingBody.length() > 0) {
    // No new gesture can start while a retry/recovery is pending. In particular,
    // a held Snooze is never reinterpreted as Taken after a blocking HTTP call.
    switchInput.inhibit();
    digitalWrite(LED_PIN, LOW);
    const bool commandHandled = serviceRecoveryCommand();
    if (!commandHandled && !queueCorrupt && pendingBody.length() > 0 &&
        millis() - lastRetryAt >= RETRY_INTERVAL_MS) attemptPending();
    switchInput.inhibit(); // Begin release debounce AFTER all HTTP/LED delays.
    delay(10);
    return;
  }
  const SwitchInput::Action action = switchInput.update(digitalRead(SWITCH_PIN) == LOW, millis());
  digitalWrite(LED_PIN, switchInput.holdConfirmed() ? HIGH : LOW);
  // Parsing serial input is nonblocking. Any completed maintenance command
  // cancels the gesture, including commands refused against a healthy queue.
  if (serviceRecoveryCommand()) { digitalWrite(LED_PIN, LOW); delay(10); return; }
  if (action != SwitchInput::NONE) {
    switchInput.inhibit();
    digitalWrite(LED_PIN, LOW);
    sendAction(action == SwitchInput::TAKEN ? "taken" : "snooze");
    switchInput.inhibit();
  }
  delay(10);
}
