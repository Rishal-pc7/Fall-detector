/*
 * SmartGuard Arduino Pan Servo Controller
 *
 * Idle Behaviour:
 *   Continuously sweeps the servo slowly back and forth (MIN_ANGLE <-> MAX_ANGLE)
 *   using non-blocking millis(). One degree per SWEEP_STEP_DELAY_MS.
 *
 * Tracking Behaviour (person in frame, no fall):
 *   TRACK:<x> command locks servo to the person's X position in real time.
 *   Servo follows the person smoothly until SWEEP command resumes patrol.
 *
 * Fall Behaviour:
 *   FALL command overrides tracking, locks to the fallen person's zone,
 *   holds for HOLD_TIME_MS, then resumes sweep.
 *
 * Serial Protocol:
 *   TRACK:<x>\n             – Person in frame at pixel X; follow them
 *   SWEEP\n                 – No person in frame; resume slow patrol sweep
 *   FALL:<angle>:<x>:<y>\n – Fall confirmed; lock and hold
 *   PAN:<angle>\n           – Manual angle override
 *   HOME\n                  – Jump to 90° and resume sweep
 *   PING\n                  – Responds PONG
 */

#include <Servo.h>

// ── Pin ──────────────────────────────────────────────────────────────────────
const int SERVO_PIN = 9;

// ── Sweep range & speed ───────────────────────────────────────────────────────
const int   SWEEP_MIN           = 10;    // leftmost sweep angle
const int   SWEEP_MAX           = 170;   // rightmost sweep angle
const unsigned long SWEEP_STEP_DELAY_MS = 30;  // ms between each 1° step → 30ms = very slow patrol

// ── Fall lock angles ──────────────────────────────────────────────────────────
const int LEFT_ANGLE   = 45;
const int CENTER_ANGLE = 90;
const int RIGHT_ANGLE  = 135;
const int HOME_ANGLE   = 90;
const int MIN_ANGLE    = 10;
const int MAX_ANGLE    = 170;

// ── Camera frame thresholds ───────────────────────────────────────────────────
const int FRAME_WIDTH      = 640;
const int LEFT_THRESHOLD   = FRAME_WIDTH / 3;         // ~213
const int RIGHT_THRESHOLD  = (FRAME_WIDTH * 2) / 3;   // ~426

// ── Fall hold duration ────────────────────────────────────────────────────────
const unsigned long HOLD_TIME_MS = 4000;   // how long to lock on fallen person (ms)

// ── State ─────────────────────────────────────────────────────────────────────
Servo panServo;
String inputString   = "";
bool   stringComplete = false;

bool          fallLocked       = false;   // true while holding on fall target
unsigned long fallUnlockTime   = 0;       // millis() when we resume sweep
bool          trackingPerson   = false;   // true while pipeline is tracking a live person

// Sweep state (non-blocking)
int           sweepAngle       = SWEEP_MIN;
int           sweepDirection   = 1;       // +1 = increasing, -1 = decreasing
unsigned long lastSweepStep    = 0;

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  while (!Serial) { ; }

  panServo.attach(SERVO_PIN);
  panServo.write(sweepAngle);
  inputString.reserve(64);

  Serial.println("SMARTGUARD_SERVO_READY");
}

// ── Main loop (non-blocking) ──────────────────────────────────────────────────
void loop() {
  // 1. Process any incoming serial command
  if (stringComplete) {
    inputString.trim();
    handleCommand(inputString);
    inputString    = "";
    stringComplete = false;
  }

  // 2. Release fall lock when hold time expires
  if (fallLocked && millis() >= fallUnlockTime) {
    fallLocked = false;
    Serial.println("STATUS:FALL_LOCK_RELEASED");
  }

  // 3. Sweep only when not locked on fall AND no person tracked
  if (!fallLocked && !trackingPerson) {
    unsigned long now = millis();
    if (now - lastSweepStep >= SWEEP_STEP_DELAY_MS) {
      lastSweepStep = now;

      panServo.write(sweepAngle);

      sweepAngle += sweepDirection;
      if (sweepAngle >= SWEEP_MAX) {
        sweepAngle    = SWEEP_MAX;
        sweepDirection = -1;
      } else if (sweepAngle <= SWEEP_MIN) {
        sweepAngle    = SWEEP_MIN;
        sweepDirection = 1;
      }
    }
  }
}

// ── Serial character accumulator ──────────────────────────────────────────────
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n' || inChar == '\r') {
      if (inputString.length() > 0) {
        stringComplete = true;
      }
    } else {
      inputString += inChar;
    }
  }
}

// ── Command handler ───────────────────────────────────────────────────────────
void handleCommand(String cmd) {

  if (cmd.startsWith("TRACK:")) {
    // Format: TRACK:<x_pixel>  (camera X coordinate 0-640)
    // Only follow if not locked on a fall event
    if (!fallLocked) {
      int posX = cmd.substring(6).toInt();
      // Map camera X (0-640) linearly to servo angle (MIN_ANGLE-MAX_ANGLE)
      int targetAngle = map(posX, 0, FRAME_WIDTH, MAX_ANGLE, MIN_ANGLE);
      targetAngle = constrain(targetAngle, MIN_ANGLE, MAX_ANGLE);
      panServo.write(targetAngle);
      trackingPerson = true;
      // Keep sweepAngle in sync so sweep resumes smoothly from here
      sweepAngle = targetAngle;
    }

  } else if (cmd.equalsIgnoreCase("SWEEP")) {
    // Pipeline says frame is empty — resume sweep (unless fall-locked)
    if (!fallLocked) {
      trackingPerson = false;
      Serial.println("STATUS:SWEEP_RESUMED");
    }

  } else if (cmd.startsWith("FALL:")) {
    // Format: FALL:<bodyAngle>:<x>:<y>
    int firstColon  = cmd.indexOf(':');
    int secondColon = cmd.indexOf(':', firstColon  + 1);
    int thirdColon  = cmd.indexOf(':', secondColon + 1);

    if (secondColon > 0 && thirdColon > 0) {
      int posX = cmd.substring(secondColon + 1, thirdColon).toInt();

      int targetAngle = CENTER_ANGLE;
      if      (posX < LEFT_THRESHOLD)  targetAngle = LEFT_ANGLE;
      else if (posX > RIGHT_THRESHOLD) targetAngle = RIGHT_ANGLE;

      // Lock servo onto fallen person — overrides tracking
      trackingPerson = false;
      panServo.write(targetAngle);
      fallLocked     = true;
      fallUnlockTime = millis() + HOLD_TIME_MS;

      Serial.print("ACK:FALL_LOCKED:");
      Serial.print(targetAngle);
      Serial.print("° (x=");
      Serial.print(posX);
      Serial.println(")");
    } else {
      Serial.println("ERR:INVALID_FALL_FORMAT");
    }

  } else if (cmd.startsWith("PAN:")) {
    int target = constrain(cmd.substring(4).toInt(), MIN_ANGLE, MAX_ANGLE);
    // Pause sweep and hold this angle
    fallLocked     = true;
    fallUnlockTime = millis() + HOLD_TIME_MS;
    panServo.write(target);
    Serial.print("ACK:PAN:");
    Serial.println(target);

  } else if (cmd.equalsIgnoreCase("HOME")) {
    // Jump home and resume sweep from center
    fallLocked  = false;
    sweepAngle  = HOME_ANGLE;
    panServo.write(HOME_ANGLE);
    Serial.println("ACK:HOME");

  } else if (cmd.equalsIgnoreCase("PING")) {
    Serial.println("PONG");

  } else {
    Serial.print("ERR:UNKNOWN_CMD:");
    Serial.println(cmd);
  }
}
