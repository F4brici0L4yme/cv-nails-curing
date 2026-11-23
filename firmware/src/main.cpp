#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <cmath>
#include "config.h"

Servo servo1, servo2;
enum class State { Idle, Moving, Error };
State state = State::Idle;
float current1 = 90.0f, current2 = 90.0f;
float target1 = 90.0f, target2 = 90.0f;
int activeNail = 0;
uint32_t moveStarted = 0, lastStep = 0;
String input;

void reply(const char* status, int nailId, uint32_t elapsedMs = 0, const char* reason = nullptr) {
  JsonDocument doc;
  doc["status"] = status;
  if (nailId > 0) doc["nail_id"] = nailId;
  if (strcmp(status, "READY") == 0) doc["move_ms"] = elapsedMs;
  if (reason) doc["reason"] = reason;
  serializeJson(doc, Serial);
  Serial.println();
}
bool within(float v, float lo, float hi) { return isfinite(v) && v >= lo && v <= hi; }
void beginMove(JsonDocument& doc) {
  const char* cmd = doc["cmd"] | "";
  if (strcmp(cmd, "ABORT") == 0) {
    if (state == State::Moving) { state = State::Idle; reply("ABORTED", activeNail); activeNail = 0; }
    else reply("IDLE", 0);
    return;
  }
  // CURE is retained as the host's target-command name. duration_ms is intentionally
  // ignored: this controller only positions the autonomous lamp; the operator cures manually.
  if (strcmp(cmd, "CURE") != 0) { reply("ERROR", 0, 0, "unsupported_cmd"); return; }
  if (state == State::Moving) { reply("ERROR", 0, 0, "busy"); return; }
  int nail = doc["nail_id"] | 0;
  float a1 = doc["theta1"] | NAN, a2 = doc["theta2"] | NAN;
  if (nail < 1 || !within(a1, cfg::SERVO1_MIN_DEG, cfg::SERVO1_MAX_DEG) ||
      !within(a2, cfg::SERVO2_MIN_DEG, cfg::SERVO2_MAX_DEG)) {
    reply("ERROR", nail, 0, "invalid_target"); return;
  }
  activeNail = nail;
  target1 = a1 + cfg::SERVO1_ZERO_OFFSET_DEG;
  target2 = a2 + cfg::SERVO2_ZERO_OFFSET_DEG;
  if (!within(target1, cfg::SERVO1_MIN_DEG, cfg::SERVO1_MAX_DEG) ||
      !within(target2, cfg::SERVO2_MIN_DEG, cfg::SERVO2_MAX_DEG)) {
    activeNail = 0; reply("ERROR", nail, 0, "offset_target_out_of_range"); return;
  }
  state = State::Moving; moveStarted = millis(); lastStep = 0;
}
void handleLine(const String& line) {
  JsonDocument doc;
  if (deserializeJson(doc, line)) { reply("ERROR", 0, 0, "invalid_json"); return; }
  beginMove(doc);
}
void pollSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') { input.trim(); if (input.length()) handleLine(input); input = ""; }
    else if (c != '\r') {
      if (input.length() >= cfg::SERIAL_LINE_MAX) { input = ""; reply("ERROR", 0, 0, "line_too_long"); }
      else input += c;
    }
  }
}
void updateMotion() {
  if (state != State::Moving || millis() - lastStep < cfg::MOVE_STEP_MS) return;
  lastStep = millis();
  auto step = [](float now, float target) { float d = target - now; if (fabsf(d) <= cfg::MOVE_STEP_DEG) return target; return now + copysignf(cfg::MOVE_STEP_DEG, d); };
  current1 = step(current1, target1); current2 = step(current2, target2);
  servo1.write((int)lroundf(current1)); servo2.write((int)lroundf(current2));
  if (current1 == target1 && current2 == target2) {
    uint32_t elapsed = millis() - moveStarted;
    state = State::Idle;
    reply("READY", activeNail, elapsed);
    activeNail = 0;
  }
}
void setup() {
  Serial.begin(cfg::BAUD);
  servo1.setPeriodHertz(cfg::SERVO_FREQ_HZ); servo2.setPeriodHertz(cfg::SERVO_FREQ_HZ);
  servo1.attach(cfg::SERVO1_PIN, cfg::SERVO_MIN_US, cfg::SERVO_MAX_US);
  servo2.attach(cfg::SERVO2_PIN, cfg::SERVO_MIN_US, cfg::SERVO_MAX_US);
  servo1.write((int)current1); servo2.write((int)current2);
  input.reserve(cfg::SERIAL_LINE_MAX);
  reply("BOOT", 0);
}
void loop() { pollSerial(); updateMotion(); }
