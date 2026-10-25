#pragma once
#include "Arduino.h"
inline uint32_t esp_random() { static uint32_t value = 12345; return ++value; }
