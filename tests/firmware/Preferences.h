#pragma once
#include "Arduino.h"
class Preferences {
 public:
  bool begin(const char *, bool) { return true; }
  bool isKey(const char *key) const { return Fake::nvs.count(key) != 0; }
  PreferenceType getType(const char *key) const { return isKey(key) ? Fake::nvs.at(key).type : PT_INVALID; }
  unsigned char getUChar(const char *key, unsigned char fallback) const {
    return getType(key) == PT_U8 ? static_cast<unsigned char>(std::stoi(Fake::nvs.at(key).text)) : fallback;
  }
  String getString(const char *key, const char *fallback) const { return getType(key) == PT_STR ? Fake::nvs.at(key).text : fallback; }
  size_t putBool(const char *key, bool value) {
    if (Fake::failMarker) { --Fake::failMarker; return 0; }
    Fake::nvs[key] = {PT_U8, value ? "1" : "0"}; return 1;
  }
  size_t putString(const char *key, const String &value) {
    if (Fake::failPut) { --Fake::failPut; return 0; }
    Fake::nvs[key] = {PT_STR, value}; return value.length();
  }
  bool remove(const char *key) {
    if (Fake::failRemove) { --Fake::failRemove; return false; }
    return Fake::nvs.erase(key) != 0;
  }
  bool clear() {
    if (Fake::failClear) { --Fake::failClear; return false; }
    Fake::nvs.clear(); return true;
  }
};
