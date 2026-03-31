"""
╔══════════════════════════════════════════════════════════════╗
║   PHASE 2A — Patient Vital Signs Simulator                   ║
║   Publishes realistic vitals to MQTT broker                  ║
║                                                              ║
║   Prerequisites:                                             ║
║     1. mosquitto running  →  mosquitto -v                    ║
║     2. pip install paho-mqtt numpy                           ║
║                                                              ║
║   Run: python simulator.py                                   ║
╚══════════════════════════════════════════════════════════════╝
"""

import paho.mqtt.client as mqtt
import numpy as np
import time
import json
import random
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────
BROKER     = "localhost"
PORT       = 1883
PATIENT_ID = "patient_001"
INTERVAL   = 1.0  # seconds between readings

TOPICS = {
    "heartrate"  : f"hospital/{PATIENT_ID}/heartrate",
    "spo2"       : f"hospital/{PATIENT_ID}/spo2",
    "temperature": f"hospital/{PATIENT_ID}/temperature",
    "movement"   : f"hospital/{PATIENT_ID}/movement",
    "fall"       : f"hospital/{PATIENT_ID}/fall",
    "all"        : f"hospital/{PATIENT_ID}/vitals",  # combined payload for dashboard
}

# ── Realistic Vital Signs Generator ──────────────────────────────────────────
class PatientSimulator:
    def __init__(self):
        self.hr          = 75.0
        self.spo2        = 98.0
        self.temp        = 36.8
        self.movement    = 1.0
        self.crisis_mode = False
        self.crisis_timer = 0
        self.reading_count = 0

    def generate(self):
        self.reading_count += 1

        # Trigger a crisis randomly (~every 3 min at 1 reading/sec)
        if random.random() < 0.006 and not self.crisis_mode:
            self.crisis_mode  = True
            self.crisis_timer = 40
            print("\n⚠️  [CRISIS TRIGGERED] Patient deteriorating...")

        if self.crisis_mode:
            self.hr       += random.uniform(1.5, 4.0)
            self.spo2     -= random.uniform(0.2, 0.7)
            self.temp     += random.uniform(0.05, 0.12)
            self.movement  = random.uniform(0.5, 2.5)
            self.crisis_timer -= 1
            if self.crisis_timer <= 0:
                self.crisis_mode = False
                # Gradual recovery
                self.hr   = 85.0
                self.spo2 = 94.0
                print("✅  [RECOVERING] Vitals stabilising...\n")
        else:
            # Physiological random walk — realistic drift
            self.hr       += random.gauss(0, 0.5)
            self.spo2     += random.gauss(0, 0.08)
            self.temp     += random.gauss(0, 0.015)
            self.movement  = max(0, random.gauss(0.9, 0.4))

        # Physiological bounds
        self.hr       = float(np.clip(self.hr,   35,  200))
        self.spo2     = float(np.clip(self.spo2, 70,  100))
        self.temp     = float(np.clip(self.temp, 34.5, 42.0))
        self.movement = float(np.clip(self.movement, 0, 15))

        # Fall event (rare, ~0.15% chance)
        fall = 1 if random.random() < 0.0015 else 0
        if fall:
            self.movement = random.uniform(6.0, 12.0)  # high acceleration = fall
            print("🚨  [FALL DETECTED]")

        return {
            "patient_id" : PATIENT_ID,
            "timestamp"  : datetime.now().isoformat(),
            "heartrate"  : round(self.hr, 1),
            "spo2"       : round(self.spo2, 1),
            "temperature": round(self.temp, 2),
            "movement"   : round(self.movement, 3),
            "fall"       : fall,
            "crisis"     : self.crisis_mode,
            "reading_no" : self.reading_count,
        }


# ── MQTT Publisher ────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties):
    codes = {0: "Connected ✅", 1: "Wrong protocol", 2: "Client ID rejected",
             3: "Server unavailable", 4: "Bad credentials", 5: "Not authorised"}
    rc_int = reason_code.value
    print(f"MQTT: {codes.get(rc_int, f'Unknown code {reason_code}')}")

def run_simulator():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"simulator_{PATIENT_ID}")
    client.on_connect = on_connect
    try:
        client.connect(BROKER, PORT, keepalive=60)
    except ConnectionRefusedError:
        print("\n❌  Cannot connect to MQTT broker.")
        print("   → Is Mosquitto running? Open another terminal and run: mosquitto -v\n")
        return

    client.loop_start()
    patient = PatientSimulator()

    print("=" * 65)
    print(f"  🏥  Digital Twin Simulator — Patient: {PATIENT_ID}")
    print(f"  📡  MQTT Broker: {BROKER}:{PORT}")
    print(f"  ⏱   Interval: {INTERVAL}s  |  Ctrl+C to stop")
    print("=" * 65)
    print(f"{'Time':^10} {'Status':^14} {'HR':^8} {'SpO₂':^8} {'Temp':^8} {'Move':^8} {'Fall':^6}")
    print("─" * 65)

    try:
        while True:
            vitals = patient.generate()
            ts     = vitals["timestamp"][11:19]

            # Publish individual topics (for ML subscriber)
            for key in ["heartrate", "spo2", "temperature", "movement", "fall"]:
                payload = json.dumps({
                    "value"      : vitals[key],
                    "timestamp"  : vitals["timestamp"],
                    "patient_id" : PATIENT_ID,
                })
                client.publish(TOPICS[key], payload, qos=1)

            # Publish combined payload (for dashboard / Unity)
            client.publish(TOPICS["all"], json.dumps(vitals), qos=1)

            status = "🔴 CRISIS " if vitals["crisis"] else ("🚨 FALL   " if vitals["fall"] else "🟢 Normal ")
            print(f"{ts:^10} {status:^14} "
                  f"{vitals['heartrate']:^8.1f} "
                  f"{vitals['spo2']:^8.1f} "
                  f"{vitals['temperature']:^8.2f} "
                  f"{vitals['movement']:^8.3f} "
                  f"{'YES' if vitals['fall'] else 'no':^6}")

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print("\n\n🛑  Simulator stopped.")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    run_simulator()
