#include "Arduino.h"
namespace Fake {
uint64_t now = 0, connectAt = 0;
bool pressed = false, led = false, wifi = true;
unsigned failPut = 0, failMarker = 0, failRemove = 0, failClear = 0;
std::vector<std::pair<uint64_t, bool> > edges;
std::map<String, Value> nvs;
std::vector<Reply> replies;
std::vector<Post> posts;
}
#include "WiFi.h"
FakeSerial Serial;
FakeWiFi WiFi;
#include "../../hardware/switch_hub.ino"

#define CHECK(expr) do { if (!(expr)) throw std::runtime_error(String(__FUNCTION__) + ": " + #expr); } while (0)

void sample(bool pressed, uint32_t wait = 0) { Fake::now += wait; Fake::pressed = pressed; loop(); }
void released() { sample(false); sample(false, 50); }
void tap() { sample(true); sample(true, 50); sample(false, 300); sample(false, 50); }
String selection(int64_t id) {
  return "{\"due\":true,\"id\":" + std::to_string(id) + ",\"fired_at\":\"2026-10-25T12:00:00.123456\"}";
}
void responses(int64_t id, int status = 200, uint32_t duration = 0) {
  Fake::replies.push_back({200, selection(id), 0});
  Fake::replies.push_back({status, status == 200 ? "{\"success\":true}" : "{}", duration});
}
JsonDocument decoded(const String &wire) { JsonDocument d; CHECK(!deserializeJson(d, wire)); return d; }
void initialize() { storageReady = retryStore.begin("doseclock", false); loadPending(); }
void setSaved(const String &body, bool marker = true) {
  Fake::nvs["pending"] = {PT_STR, body};
  if (marker) Fake::nvs["pending_set"] = {PT_U8, "1"};
}
String saved() { return "{\"id\":9223372036854775807,\"fired_at\":\"2026-10-25T12:00:00.123456\",\"action\":\"taken\",\"request_id\":\"stable-request-001\"}"; }
void retryDue() { lastRetryAt = millis() - RETRY_INTERVAL_MS; }

void thresholds() {
  for (uint32_t duration : {0U, 599U, 600U, 1499U, 1500U, 2000U}) {
    SwitchInput input;
    CHECK(input.update(true, 0) == SwitchInput::NONE); // Held at boot is ignored.
    input.update(false, 10); input.update(true, 59); // Release bounce cannot arm.
    input.update(false, 60); input.update(false, 110);
    input.update(true, 200); input.update(true, 249);
    input.update(true, 250);
    if (duration >= 1500) { input.update(true, 1750); CHECK(input.holdConfirmed()); }
    CHECK(input.update(false, 250 + duration) == SwitchInput::NONE);
    CHECK(input.update(false, 299 + duration) == SwitchInput::NONE);
    auto result = input.update(false, 300 + duration);
    CHECK(result == (duration < 600 ? SwitchInput::TAKEN : duration >= 1500 ? SwitchInput::SNOOZE : SwitchInput::NONE));
  }
  SwitchInput wrap;
  wrap.update(false, UINT32_MAX - 200); wrap.update(false, UINT32_MAX - 150);
  wrap.update(true, UINT32_MAX - 100); wrap.update(true, UINT32_MAX - 50);
  wrap.update(false, 100); CHECK(wrap.update(false, 150) == SwitchInput::TAKEN);
}

void retry_interlock() {
  initialize(); released(); responses(1, 503); tap(); CHECK(Fake::posts.size() == 2);
  const String first = Fake::posts.back().body;
  retryDue();
  const auto start = Fake::now;
  // A real press starts DURING the blocking retry and remains held after success.
  Fake::edges.push_back({start + 100, true});
  Fake::replies.push_back({200, "{\"success\":true}", 3000});
  loop(); CHECK(pendingBody.empty()); CHECK(Fake::posts.back().body == first);
  for (int i = 0; i < 200; ++i) loop();
  CHECK(Fake::posts.size() == 3); CHECK(!Fake::led);
  Fake::edges.clear();
  sample(false); sample(false, 39); sample(true); // Less than 50 ms high, then bounce.
  sample(true, 2000); CHECK(Fake::posts.size() == 3);
  released(); responses(2); tap();
  CHECK(Fake::posts.size() == 5);
  auto second = decoded(Fake::posts.back().body);
  CHECK(second["id"].as<int64_t>() == 2);
  CHECK(second["request_id"].as<String>() != decoded(first)["request_id"].as<String>());
}

void held_retry() {
  initialize(); released(); responses(1, 503); tap(); retryDue();
  const auto start = Fake::now;
  // Two seconds of physical hold overlap a three-second network wait. It must
  // not become a short Taken when the loop can observe it again.
  Fake::edges = {{start + 1000, true}, {start + 3100, false}};
  Fake::replies.push_back({200, "{\"success\":true}", 3000}); loop();
  for (int i = 0; i < 100; ++i) loop();
  CHECK(Fake::posts.size() == 3); CHECK(!Fake::led);
}

void hold_without_network() {
  initialize(); released(); responses(1, 200, 3000);
  sample(true); sample(true, 50);
  for (int i = 0; i < 160; ++i) { sample(true); CHECK(Fake::posts.empty()); }
  CHECK(Fake::led); sample(false); sample(false, 50);
  CHECK(Fake::posts.size() == 2);
  CHECK(decoded(Fake::posts.back().body)["action"].as<String>() == "snooze");
}

void replay() {
  initialize(); released(); responses(7, -11); tap();
  const String first = Fake::posts.back().body;
  // Simulated restart: only NVS remains; reload before retry.
  pendingBody = ""; queueMarked = queueCorrupt = false; switchInput.inhibit(); loadPending();
  for (const auto &reply : std::vector<Fake::Reply>{{503, "{}", 0}, {200, "bad JSON", 0}, {200, "{}", 0}, {200, "{\"success\":true}", 0}}) {
    retryDue(); Fake::replies.push_back(reply); loop(); CHECK(Fake::posts.back().body == first);
  }
  CHECK(pendingBody.empty()); CHECK(Fake::nvs.empty()); CHECK(Fake::posts.size() == 6);
  CHECK(Serial.output.find(DEVICE_TOKEN) == String::npos);
}

void ids() {
  initialize();
  for (int64_t id : {INT64_C(2147483648), INT64_MAX}) {
    responses(id); sendAction("taken");
    CHECK(decoded(Fake::posts.back().body)["id"].as<int64_t>() == id);
  }
  for (const String &id : {String("0"), String("-1"), String("true"), String("\"1\""), String("1.5"), String("9223372036854775808")}) {
    const auto before = Fake::posts.size();
    Fake::replies.push_back({200, "{\"due\":true,\"id\":" + id + ",\"fired_at\":\"stamp\"}", 0});
    sendAction("taken"); CHECK(Fake::posts.size() == before + 1);
  }
}

void corrupt_recovery() {
  setSaved("{broken"); initialize(); CHECK(queueCorrupt);
  Fake::pressed = true; Serial.input = "CLEAR CORRUPT RETRY\n"; loop();
  CHECK(!queueCorrupt); CHECK(Fake::nvs.empty()); CHECK(Fake::posts.empty());
  sample(true, 3000); CHECK(Fake::posts.empty());
  released(); responses(9); tap(); CHECK(Fake::posts.size() == 2);
}

void failed_recovery() {
  setSaved("[]"); initialize(); Fake::failClear = 1;
  Serial.input = "CLEAR CORRUPT RETRY\n"; loop();
  CHECK(queueCorrupt); CHECK(Fake::posts.empty()); CHECK(!Fake::nvs.empty());
  Serial.input = "CLEAR CORRUPT RETRY EXTRA\n"; loop(); CHECK(queueCorrupt);
  Serial.input = String(80, 'X') + "CLEAR CORRUPT RETRY\n"; loop(); loop(); CHECK(queueCorrupt);
  Serial.input = "CLEAR CORRUPT RETRY\n"; loop(); CHECK(!queueCorrupt); CHECK(Fake::posts.empty());
}

void write_failure() {
  initialize(); Fake::failPut = 1; responses(5); sendAction("taken");
  CHECK(queueCorrupt); CHECK(Fake::posts.size() == 1); CHECK(Fake::nvs.count("pending_set") == 1);
  pendingBody = ""; queueCorrupt = queueMarked = false; loadPending();
  CHECK(queueCorrupt); CHECK(Fake::posts.size() == 1); // Orphan marker survives boot.
}

void marker_failure() {
  initialize(); Fake::failMarker = 1; responses(5); sendAction("taken");
  CHECK(queueCorrupt); CHECK(Fake::posts.size() == 1);
}

void valid_recovery_refused() {
  setSaved(saved()); initialize(); CHECK(!queueCorrupt);
  const auto before = Fake::nvs;
  Serial.input = "CLEAR CORRUPT RETRY\n"; loop();
  CHECK(!pendingBody.empty()); CHECK(Fake::posts.empty()); CHECK(Fake::nvs.size() == before.size());
  CHECK(Fake::nvs.at("pending").text == before.at("pending").text);
}

void legacy_queue() {
  setSaved(saved(), false); initialize(); CHECK(!queueCorrupt); CHECK(!queueMarked);
  Fake::replies.push_back({200, "{\"success\":true}", 0}); retryDue(); loop();
  CHECK(Fake::posts.size() == 1); CHECK(Fake::posts[0].url.find("/api/device/action") != String::npos);
  auto wire = decoded(Fake::posts[0].body);
  CHECK(wire["request_id"].as<String>() == "stable-request-001");
  CHECK(wire["id"].as<int64_t>() == INT64_MAX); CHECK(Fake::nvs.empty());
}

void malformed_queues() {
  for (const String &body : {String(""), String("{}"), String("[]"), String("{broken"),
       String("{\"id\":1,\"fired_at\":\"x\",\"action\":\"taken\",\"request_id\":\"bad key!\"}"),
       String("{\"id\":true,\"fired_at\":\"x\",\"action\":\"taken\",\"request_id\":\"good-key\"}")}) {
    Fake::nvs.clear(); pendingBody = ""; queueCorrupt = queueMarked = false;
    setSaved(body); loadPending(); CHECK(queueCorrupt); attemptPending(); CHECK(Fake::posts.empty());
  }
  Fake::nvs["pending"] = {PT_U8, "1"}; queueCorrupt = false; loadPending(); CHECK(queueCorrupt);
}

void offline_recovery() {
  setSaved("bad JSON"); Fake::wifi = false; Fake::connectAt = 900;
  Serial.input = "CLEAR CORRUPT RETRY\n"; Fake::pressed = true; setup();
  CHECK(!queueCorrupt); CHECK(Fake::nvs.empty()); CHECK(Fake::posts.empty());
  sample(true, 2000); CHECK(Fake::posts.empty());
}

void remove_failure() {
  initialize(); released(); responses(5); Fake::failRemove = 1; tap();
  CHECK(!pendingBody.empty()); CHECK(!queueCorrupt);
  const auto first = Fake::posts.back().body;
  retryDue(); Fake::replies.push_back({200, "{\"success\":true}", 0}); loop();
  CHECK(Fake::posts.back().body == first); CHECK(pendingBody.empty()); CHECK(Fake::nvs.empty());
}

int main(int argc, char **argv) {
  try {
    CHECK(argc == 2);
    const std::map<String, void(*)()> cases = {
      {"thresholds", thresholds}, {"retry_interlock", retry_interlock}, {"held_retry", held_retry},
      {"hold_without_network", hold_without_network}, {"replay", replay}, {"ids", ids},
      {"corrupt_recovery", corrupt_recovery}, {"failed_recovery", failed_recovery},
      {"write_failure", write_failure}, {"marker_failure", marker_failure},
      {"valid_recovery_refused", valid_recovery_refused}, {"legacy_queue", legacy_queue},
      {"malformed_queues", malformed_queues}, {"offline_recovery", offline_recovery},
      {"remove_failure", remove_failure}};
    cases.at(argv[1])(); printf("PASS %s (host simulation; no physical hardware)\n", argv[1]);
    return 0;
  } catch (const std::exception &e) { fprintf(stderr, "%s\n", e.what()); return 1; }
}
