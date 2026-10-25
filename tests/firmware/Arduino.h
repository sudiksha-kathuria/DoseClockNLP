#pragma once
// Host-only fake hardware. The harness includes the production .ino and real
// ArduinoJson; it does not establish GPIO, flash/NVS, Wi-Fi or LED behavior.
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string>
#include <vector>
#include <map>
#include <stdexcept>
using String = std::string;
enum { LOW = 0, HIGH = 1, INPUT_PULLUP = 2, OUTPUT = 3, WL_CONNECTED = 3 };
enum PreferenceType { PT_INVALID, PT_U8, PT_STR };
namespace Fake {
struct Value { PreferenceType type; String text; };
struct Reply { int status; String body; uint32_t delay; };
struct Post { String url, body; };
extern uint64_t now, connectAt;
extern bool pressed, led, wifi;
extern unsigned failPut, failMarker, failRemove, failClear;
extern std::vector<std::pair<uint64_t, bool> > edges;
extern std::map<String, Value> nvs;
extern std::vector<Reply> replies;
extern std::vector<Post> posts;
}
inline uint32_t millis() { return static_cast<uint32_t>(Fake::now); }
inline void delay(uint32_t ms) { Fake::now += ms; }
inline void pinMode(int, int) {}
inline int digitalRead(int) {
  bool pressed = Fake::pressed;
  for (const auto &edge : Fake::edges) if (edge.first <= Fake::now) pressed = edge.second;
  return pressed ? LOW : HIGH;
}
inline void digitalWrite(int, int value) { Fake::led = value == HIGH; }
class FakeSerial {
 public:
  String input, output;
  void begin(int) {}
  int available() const { return static_cast<int>(input.size()); }
  int read() { int c = static_cast<unsigned char>(input[0]); input.erase(0, 1); return c; }
  void print(const String &s) { output += s; }
  void println(const String &s) { output += s + "\n"; }
  void printf(const char *format, ...) {
    char buffer[1024]; va_list args; va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args); va_end(args); output += buffer;
  }
};
extern FakeSerial Serial;
