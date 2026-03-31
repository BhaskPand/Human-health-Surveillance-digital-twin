/*
 * Phase 5 — ESP32 Patient Sensor Node
 * Sensors: MAX30102 (HR + SpO2) + MPU6050 (fall detection)
 *
 * Libraries to install via Arduino Library Manager:
 *   - PubSubClient          (MQTT)
 *   - ArduinoJson           (JSON payloads)
 *   - SparkFun MAX3010x     (MAX30102 HR/SpO2)
 *   - Adafruit MPU6050      (accelerometer)
 *   - WiFi (built-in ESP32)
 *
 * Wiring:
 *   MAX30102  → SDA=GPIO21, SCL=GPIO22, VCC=3.3V, GND=GND
 *   MPU6050   → SDA=GPIO21, SCL=GPIO22, VCC=3.3V, GND=GND (same I2C bus)
 *   Status LED → GPIO2 (built-in LED on most ESP32 boards)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include "MAX30105.h"
#include "spo2_algorithm.h"
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <math.h>

// ── WiFi & MQTT Config ────────────────────────────────────────────────────────
const char* WIFI_SSID     = "YOUR_HOSPITAL_WIFI";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_BROKER   = "192.168.1.100";    // IP of your PC running Mosquitto
const int   MQTT_PORT     = 1883;
const char* PATIENT_ID    = "patient_001";
const char* DEVICE_ID     = "esp32_bed1";

// MQTT Topics
char TOPIC_HR[64], TOPIC_SPO2[64], TOPIC_TEMP[64],
     TOPIC_MOV[64], TOPIC_FALL[64], TOPIC_VITALS[64];

// ── Hardware ──────────────────────────────────────────────────────────────────
#define LED_PIN         2
#define SAMPLE_INTERVAL 1000    // ms between readings
#define BUFFER_SIZE     100     // SpO2 algorithm buffer

MAX30105       particleSensor;
Adafruit_MPU6050 mpu;
WiFiClient     wifiClient;
PubSubClient   mqttClient(wifiClient);

// SpO2 algorithm buffers
uint32_t irBuffer[BUFFER_SIZE], redBuffer[BUFFER_SIZE];
int32_t  spo2Value;
int8_t   spo2Valid;
int32_t  heartRate;
int8_t   hrValid;

// Fall detection
float    accelMag          = 0.0;
bool     fallDetected      = false;
float    FALL_THRESHOLD    = 2.5;  // g — tune for your patient population
unsigned long lastSample   = 0;
int      readingCount      = 0;

// ── WiFi ──────────────────────────────────────────────────────────────────────
void connectWiFi() {
  Serial.print("[WiFi] Connecting to "); Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500); Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected: " + WiFi.localIP().toString());
    digitalWrite(LED_PIN, HIGH);
  } else {
    Serial.println("\n[WiFi] FAILED — restarting in 5s");
    delay(5000); ESP.restart();
  }
}

// ── MQTT ──────────────────────────────────────────────────────────────────────
void connectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("[MQTT] Connecting...");
    String clientId = String(DEVICE_ID) + "_" + String(millis());
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(" Connected.");
    } else {
      Serial.print(" Failed (rc="); Serial.print(mqttClient.state());
      Serial.println(") — retry in 5s");
      delay(5000);
    }
  }
}

void publishVital(const char* topic, float value, const char* unit) {
  StaticJsonDocument<128> doc;
  doc["value"]      = value;
  doc["unit"]       = unit;
  doc["patient_id"] = PATIENT_ID;
  doc["device_id"]  = DEVICE_ID;
  doc["reading_no"] = readingCount;

  char buf[128];
  serializeJson(doc, buf);
  mqttClient.publish(topic, buf, true);   // retained message
}

void publishFullVitals(float hr, float spo2, float temp, float mov, int fall) {
  StaticJsonDocument<256> doc;
  doc["patient_id"]   = PATIENT_ID;
  doc["device_id"]    = DEVICE_ID;
  doc["reading_no"]   = readingCount;
  doc["heartrate"]    = hr;
  doc["spo2"]         = spo2;
  doc["temperature"]  = temp;
  doc["movement"]     = mov;
  doc["fall"]         = fall;

  char buf[256];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_VITALS, buf);
}

// ── Sensors ───────────────────────────────────────────────────────────────────
float readTemperature() {
  // MAX30102 has a built-in die temperature sensor
  // Correlates with skin/body temperature ±0.5°C
  float raw = particleSensor.readTemperature();
  return raw + 2.0;  // calibration offset — measure and tune
}

void computeSpO2andHR() {
  // Load buffer
  for (int i = 0; i < BUFFER_SIZE; i++) {
    while (!particleSensor.available())
      particleSensor.check();
    redBuffer[i] = particleSensor.getRed();
    irBuffer[i]  = particleSensor.getIR();
    particleSensor.nextSample();
  }
  maxim_heart_rate_and_oxygen_saturation(
    irBuffer, BUFFER_SIZE, redBuffer,
    &spo2Value, &spo2Valid, &heartRate, &hrValid
  );
}

float readMovementMag() {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);
  float ax = a.acceleration.x;
  float ay = a.acceleration.y;
  float az = a.acceleration.z;
  // Subtract gravity (1g = 9.81 m/s²) for movement-only magnitude
  float mag = sqrt(ax*ax + ay*ay + az*az) / 9.81;
  return mag;
}

bool detectFall() {
  accelMag = readMovementMag();
  // Simple threshold — high-G event (impact)
  if (accelMag > FALL_THRESHOLD) {
    Serial.println("[SENSOR] High-G event — possible fall!");
    return true;
  }
  return false;
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  // Build MQTT topic strings
  snprintf(TOPIC_HR,     64, "hospital/%s/heartrate",   PATIENT_ID);
  snprintf(TOPIC_SPO2,   64, "hospital/%s/spo2",        PATIENT_ID);
  snprintf(TOPIC_TEMP,   64, "hospital/%s/temperature", PATIENT_ID);
  snprintf(TOPIC_MOV,    64, "hospital/%s/movement",    PATIENT_ID);
  snprintf(TOPIC_FALL,   64, "hospital/%s/fall",        PATIENT_ID);
  snprintf(TOPIC_VITALS, 64, "hospital/%s/vitals",      PATIENT_ID);

  // WiFi
  connectWiFi();

  // MQTT
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setKeepAlive(60);
  connectMQTT();

  // MAX30102
  Wire.begin(21, 22);
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("[SENSOR] MAX30102 not found — check wiring!");
    while (1) { digitalWrite(LED_PIN, !digitalRead(LED_PIN)); delay(200); }
  }
  particleSensor.setup();
  particleSensor.setPulseAmplitudeRed(0x0A);
  particleSensor.setPulseAmplitudeIR(0x1F);
  particleSensor.enableDIETEMPRDY();

  // MPU6050
  if (!mpu.begin()) {
    Serial.println("[SENSOR] MPU6050 not found — check wiring!");
    // Don't halt — continue without fall detection
  } else {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    Serial.println("[SENSOR] MPU6050 OK");
  }

  Serial.println("[SETUP] All systems ready. Starting monitoring...");
  Serial.println("════════════════════════════════════════");
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  // Maintain connections
  if (WiFi.status() != WL_CONNECTED) { connectWiFi(); }
  if (!mqttClient.connected())        { connectMQTT(); }
  mqttClient.loop();

  unsigned long now = millis();
  if (now - lastSample < SAMPLE_INTERVAL) return;
  lastSample = now;
  readingCount++;

  // ── Read Sensors ──────────────────────────────────────────
  computeSpO2andHR();

  float hr   = hrValid   ? (float)heartRate : 0;
  float spo2 = spo2Valid ? (float)spo2Value : 0;
  float temp = readTemperature();
  float mov  = readMovementMag();
  bool  fall = detectFall();

  // Validate readings (reject clearly bad values)
  if (hr   < 20  || hr   > 250) { Serial.println("[WARN] HR out of range"); hr = 0; }
  if (spo2 < 50  || spo2 > 100) { Serial.println("[WARN] SpO2 out of range"); spo2 = 0; }
  if (temp < 30  || temp > 43)  { Serial.println("[WARN] Temp out of range"); temp = 0; }

  // ── Publish ───────────────────────────────────────────────
  if (hr   > 0) publishVital(TOPIC_HR,   hr,   "bpm");
  if (spo2 > 0) publishVital(TOPIC_SPO2, spo2, "%");
  if (temp > 0) publishVital(TOPIC_TEMP, temp, "C");
  publishVital(TOPIC_MOV, mov, "g");

  if (fall) {
    publishVital(TOPIC_FALL, 1.0, "bool");
    // Flash LED 3 times on fall
    for (int i = 0; i < 3; i++) {
      digitalWrite(LED_PIN, LOW); delay(100);
      digitalWrite(LED_PIN, HIGH); delay(100);
    }
  }

  publishFullVitals(hr, spo2, temp, mov, fall ? 1 : 0);

  // Serial log
  Serial.printf(
    "[#%d] HR:%.0f SpO2:%.0f%% Temp:%.1fC Mov:%.2fg Fall:%d\n",
    readingCount, hr, spo2, temp, mov, fall ? 1 : 0
  );

  // Heartbeat LED blink
  digitalWrite(LED_PIN, LOW); delay(50);
  digitalWrite(LED_PIN, HIGH);
}
