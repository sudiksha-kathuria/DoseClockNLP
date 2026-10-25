#pragma once

#include <stdint.h>

// Network/LED work runs only outside a measured gesture. Inhibit before AND
// after blocking work: a contact held across its completion cannot become a
// new press. Every re-arm requires an observed, continuous 50 ms release.
class SwitchInput {
 public:
  enum Action { NONE, TAKEN, SNOOZE };
  static constexpr uint32_t DEBOUNCE_MS = 50;
  static constexpr uint32_t SHORT_PRESS_MAX_MS = 600;
  static constexpr uint32_t HOLD_CONFIRM_MS = 1500;

  void inhibit() {
    known_ = armed_ = active_ = held_ = false;
  }

  Action update(bool pressed, uint32_t now) {
    if (!known_ || pressed != raw_) {
      known_ = true;
      raw_ = pressed;
      changedAt_ = now;
    }
    if (!armed_) {
      if (!pressed && elapsed(now, changedAt_) >= DEBOUNCE_MS) armed_ = true;
      return NONE;
    }
    if (!active_) {
      if (pressed && elapsed(now, changedAt_) >= DEBOUNCE_MS) {
        active_ = true;
        held_ = false;
        pressStart_ = now;  // Preserve the original post-debounce thresholds.
      }
      return NONE;
    }
    if (pressed) {
      held_ = elapsed(now, pressStart_) >= HOLD_CONFIRM_MS;
      return NONE;
    }
    if (elapsed(now, changedAt_) < DEBOUNCE_MS) return NONE;

    // Exclude release debounce from the measured hold, including at boundaries.
    const uint32_t duration = elapsed(changedAt_, pressStart_);
    active_ = held_ = false;
    if (duration < SHORT_PRESS_MAX_MS) return TAKEN;
    if (duration >= HOLD_CONFIRM_MS) return SNOOZE;
    return NONE;
  }

  bool holdConfirmed() const { return active_ && raw_ && held_; }

 private:
  static uint32_t elapsed(uint32_t now, uint32_t since) { return now - since; }
  bool known_ = false, raw_ = false, armed_ = false, active_ = false, held_ = false;
  uint32_t changedAt_ = 0, pressStart_ = 0;
};
