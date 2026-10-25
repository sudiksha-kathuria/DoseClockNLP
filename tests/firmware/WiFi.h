#pragma once
#include "Arduino.h"
enum { WIFI_STA = 1 };
class FakeWiFi {
 public:
  int status() const { return Fake::wifi || (Fake::connectAt && Fake::now >= Fake::connectAt) ? WL_CONNECTED : 0; }
  void mode(int) {}
  void begin(const char *, const char *) {}
  String localIP() const { return "192.0.2.1"; }
};
extern FakeWiFi WiFi;
