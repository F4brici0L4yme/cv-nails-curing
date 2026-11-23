#pragma once
#include <Arduino.h>
namespace cfg {
constexpr uint32_t BAUD = 115200;
constexpr int SERVO1_PIN = 18;
constexpr int SERVO2_PIN = 19;
constexpr int SERVO_MIN_US = 500;
constexpr int SERVO_MAX_US = 2500;
constexpr int SERVO_FREQ_HZ = 50;
// Calibrate these against the assembled mechanism before operation.
constexpr float SERVO1_MIN_DEG = 0.0f;
constexpr float SERVO1_MAX_DEG = 180.0f;
constexpr float SERVO2_MIN_DEG = 0.0f;
constexpr float SERVO2_MAX_DEG = 180.0f;
constexpr float SERVO1_ZERO_OFFSET_DEG = 0.0f;
constexpr float SERVO2_ZERO_OFFSET_DEG = 0.0f;
constexpr uint32_t MOVE_STEP_MS = 20;
constexpr float MOVE_STEP_DEG = 1.0f;
constexpr size_t SERIAL_LINE_MAX = 256;
}
