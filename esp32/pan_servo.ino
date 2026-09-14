#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

WebServer server(80);
Servo panServo;

const int servoPin = 18;
int currentAngle = 90;

void handleHealth() {
  StaticJsonDocument<200> doc;
  doc["status"] = "ok";
  doc["current_angle"] = currentAngle;
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handlePan() {
  if (server.hasArg("plain") == false) {
    server.send(400, "application/json", "{\"error\":\"Body not received\"}");
    return;
  }
  
  String body = server.arg("plain");
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, body);
  
  if (error) {
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }
  
  if (!doc.containsKey("angle")) {
    server.send(400, "application/json", "{\"error\":\"Missing angle parameter\"}");
    return;
  }
  
  int targetAngle = doc["angle"];
  
  // Clamp angle
  if (targetAngle < 10) targetAngle = 10;
  if (targetAngle > 170) targetAngle = 170;
  
  // Debounce (ignore < 3 degree changes)
  if (abs(targetAngle - currentAngle) >= 3) {
    panServo.write(targetAngle);
    currentAngle = targetAngle;
  }
  
  StaticJsonDocument<200> respDoc;
  respDoc["status"] = "ok";
  respDoc["current_angle"] = currentAngle;
  
  String response;
  serializeJson(respDoc, response);
  server.send(200, "application/json", response);
}

void setup() {
  Serial.begin(115200);
  
  // Configure Servo
  ESP32PWM::allocateTimer(0);
  panServo.setPeriodHertz(50);
  panServo.attach(servoPin, 500, 2400);
  panServo.write(currentAngle);
  
  // Connect WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.println("");
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("Connected to ");
  Serial.println(ssid);
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  
  // Setup routes
  server.on("/health", HTTP_GET, handleHealth);
  server.on("/pan", HTTP_POST, handlePan);
  
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  server.handleClient();
}
