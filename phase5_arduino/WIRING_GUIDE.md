# ESP32 Wiring Guide — Digital Twin Sensor Node

## Parts List
| Component | Purpose | Cost (approx) |
|-----------|---------|--------------|
| ESP32 Dev Board (30-pin) | WiFi + MQTT controller | ₹350 |
| MAX30102 Module | Heart Rate + SpO₂ | ₹180 |
| MPU6050 Module | Accelerometer (fall detection) | ₹120 |
| DS18B20 Module | Body temperature | ₹90 |
| 4.7kΩ resistor | DS18B20 pullup | ₹2 |
| Breadboard + wires | Connections | ₹80 |
| **Total** | | **≈ ₹820** |

## Wiring Diagram

### MAX30102 → ESP32
```
MAX30102 Pin   →   ESP32 Pin
VIN/VCC        →   3.3V
GND            →   GND
SDA            →   GPIO 21
SCL            →   GPIO 22
INT            →   (not needed)
```

### MPU6050 → ESP32
```
MPU6050 Pin    →   ESP32 Pin
VCC            →   3.3V
GND            →   GND
SDA            →   GPIO 21  (same I2C bus — shares with MAX30102)
SCL            →   GPIO 22  (same I2C bus)
AD0            →   GND      (sets I2C address to 0x68)
INT            →   (optional, not used)
```

### DS18B20 → ESP32
```
DS18B20 Pin    →   ESP32 Pin
VCC (Red)      →   3.3V
GND (Black)    →   GND
DATA (Yellow)  →   GPIO 4
                   Also connect a 4.7kΩ resistor between DATA and VCC
```

## I2C Addresses (must not conflict)
- MAX30102: 0x57
- MPU6050:  0x68 (AD0=GND) or 0x69 (AD0=3.3V)

## Arduino IDE Setup
1. Install ESP32 board: File → Preferences → Board Manager URL:
   `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
2. Tools → Board → esp32 → "ESP32 Dev Module"
3. Tools → Upload Speed → 115200
4. Install libraries via Sketch → Include Library → Manage Libraries:
   - `PubSubClient` by Nick O'Leary
   - `SparkFun MAX3010x Pulse and Proximity Sensor Library`
   - `MPU6050_light` by rfetick
   - `DallasTemperature` by Miles Burton
   - `OneWire` by Paul Stoffregen
   - `ArduinoJson` by Benoit Blanchon

## Before Upload — Edit patient_sensor.ino
```cpp
const char* WIFI_SSID     = "YOUR_HOSPITAL_WIFI";   // ← your WiFi name
const char* WIFI_PASSWORD = "YOUR_PASSWORD";          // ← your WiFi password
const char* MQTT_SERVER   = "192.168.1.100";          // ← your server's IP
const char* PATIENT_ID    = "patient_001";            // ← unique per patient
```

## Testing
Open Serial Monitor (115200 baud) — you should see:
```
✅  WiFi connected: 192.168.1.105
✅  MAX30102 initialized
✅  MPU6050 initialized — calibrating...
✅  MPU6050 calibrated
✅  DS18B20 initialized (1 sensor(s))
📡  All sensors ready — publishing vitals...
[PUBLISH] HR:75  SpO₂:98%  Temp:36.80°C  Mov:0.982  Fall:0
```
