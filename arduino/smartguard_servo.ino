/*
 * SmartGuard Arduino Pan Servo Controller
 *
 * Receives fall event notifications from the SmartGuard Python backend over USB Serial.
 * Protocol:
 *   FALL:<angle>:<x>:<y>\n
 *     - angle: Body torso angle in degrees (90 = vertical, 0 = horizontal)
 *     - x: X coordinate of fallen person in camera frame (0 to 640)
 *     - y: Y coordinate of fallen person in camera frame (0 to 480)
 *
 * Actions:
 *   - Parses X position to determine pan direction:
 *       Left third (x < 213): Pan Left (45 degrees)
 *       Center third (213 <= x <= 426): Pan Center (90 degrees)
 *       Right third (x > 426): Pan Right (135 degrees)
 *   - Holds position for HOLD_TIME_MS (default 2000 ms)
 *   - Returns to HOME_ANGLE (90 degrees) automatically using non-blocking millis()
 *
 * Additional Commands:
 *   PAN:<angle>\n  - Manually pan to specified angle (10 - 170)
 *   HOME\n         - Immediately return to home position (90)
 *   PING\n         - Responds with PONG
 */

#include <Servo.h>

const int SERVO_PIN = 9;

// Servo Angles
const int HOME_ANGLE = 90;
const int LEFT_ANGLE = 45;
const int CENTER_ANGLE = 90;
const int RIGHT_ANGLE = 135;
const int MIN_ANGLE = 10;
const int MAX_ANGLE = 170;

// Camera Frame Dimensions
const int FRAME_WIDTH = 640;
const int LEFT_THRESHOLD = FRAME_WIDTH / 3;        // ~213
const int RIGHT_THRESHOLD = (FRAME_WIDTH * 2) / 3; // ~426

// Hold duration before returning home (ms)
const unsigned long HOLD_TIME_MS = 2000;

Servo panServo;
String inputString = "";
bool stringComplete = false;

unsigned long returnHomeTime = 0;
bool waitingToReturnHome = false;

void setup() {
  Serial.begin(9600);
  while (!Serial) {
    ; // Wait for serial port to connect
  }

  panServo.attach(SERVO_PIN);
  panServo.write(HOME_ANGLE);
  inputString.reserve(64);

  Serial.println("SMARTGUARD_SERVO_READY");
}

void loop() {
  // Check if hold time expired to return home
  if (waitingToReturnHome && millis() >= returnHomeTime) {
    panServo.write(HOME_ANGLE);
    waitingToReturnHome = false;
    Serial.println("STATUS:SERVO_RETURNED_HOME");
  }

  // Process incoming serial command
  if (stringComplete) {
    inputString.trim();
    handleCommand(inputString);
    inputString = "";
    stringComplete = false;
  }
}

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

void handleCommand(String cmd) {
  if (cmd.startsWith("FALL:")) {
    // Format: FALL:<angle>:<x>:<y>
    int firstColon = cmd.indexOf(':');
    int secondColon = cmd.indexOf(':', firstColon + 1);
    int thirdColon = cmd.indexOf(':', secondColon + 1);

    if (secondColon > 0 && thirdColon > 0) {
      int bodyAngle = cmd.substring(firstColon + 1, secondColon).toInt();
      int posX = cmd.substring(secondColon + 1, thirdColon).toInt();
      int posY = cmd.substring(thirdColon + 1).toInt();

      int targetAngle = CENTER_ANGLE;
      if (posX < LEFT_THRESHOLD) {
        targetAngle = LEFT_ANGLE;
      } else if (posX > RIGHT_THRESHOLD) {
        targetAngle = RIGHT_ANGLE;
      } else {
        targetAngle = CENTER_ANGLE;
      }

      panServo.write(targetAngle);
      returnHomeTime = millis() + HOLD_TIME_MS;
      waitingToReturnHome = true;

      Serial.print("ACK:FALL_PANNED:");
      Serial.print(targetAngle);
      Serial.print(" (x=");
      Serial.print(posX);
      Serial.println(")");
    } else {
      Serial.println("ERR:INVALID_FALL_FORMAT");
    }
  } else if (cmd.startsWith("PAN:")) {
    int target = cmd.substring(4).toInt();
    target = constrain(target, MIN_ANGLE, MAX_ANGLE);
    panServo.write(target);
    Serial.print("ACK:PAN:");
    Serial.println(target);
  } else if (cmd.equalsIgnoreCase("HOME")) {
    panServo.write(HOME_ANGLE);
    waitingToReturnHome = false;
    Serial.println("ACK:HOME");
  } else if (cmd.equalsIgnoreCase("PING")) {
    Serial.println("PONG");
  } else {
    Serial.print("ERR:UNKNOWN_CMD:");
    Serial.println(cmd);
  }
}
