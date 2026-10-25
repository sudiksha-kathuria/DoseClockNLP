#pragma once
#include "Arduino.h"
class HTTPClient {
  String url_, response_;
 public:
  void begin(const String &url) { url_ = url; }
  void setTimeout(int) {}
  void addHeader(const char *, const char *) {}
  int POST(const String &body) {
    if (Fake::replies.empty()) throw std::runtime_error("Unexpected HTTP POST: " + url_);
    Fake::posts.push_back({url_, body});
    const auto reply = Fake::replies.front(); Fake::replies.erase(Fake::replies.begin());
    delay(reply.delay); response_ = reply.body; return reply.status;
  }
  String getString() const { return response_; }
  void end() {}
};
