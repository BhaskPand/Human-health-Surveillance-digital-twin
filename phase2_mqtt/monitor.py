"""
╔══════════════════════════════════════════════════════════════╗
║   PHASE 2B — Real-Time ML Monitor                            ║
║   Subscribes to MQTT, runs inference, fires alerts           ║
║                                                              ║
║   Prerequisites:                                             ║
║     1. models/ folder copied from phase1_ml/                 ║
║     2. mosquitto running  →  mosquitto -v                    ║
║     3. simulator.py running in another terminal              ║
║                                                              ║
║   Run: python monitor.py                                     ║
╚══════════════════════════════════════════════════════════════╝
"""

import paho.mqtt.client as mqtt
import joblib, json, numpy as np, os
from datetime import datetime
from collections import deque

MODELS_DIR = "models"
for f in ["rf_model.pkl","gb_model.pkl","scaler.pkl","label_encoder.pkl","metadata.json"]:
    if not os.path.exists(f"{MODELS_DIR}/{f}"):
        raise FileNotFoundError(f"\n❌  Missing: {MODELS_DIR}/{f}\n   Copy models/ from phase1_ml/\n")

rf     = joblib.load(f"{MODELS_DIR}/rf_model.pkl")
gb     = joblib.load(f"{MODELS_DIR}/gb_model.pkl")
scaler = joblib.load(f"{MODELS_DIR}/scaler.pkl")
le     = joblib.load(f"{MODELS_DIR}/label_encoder.pkl")
with open(f"{MODELS_DIR}/metadata.json") as f: meta = json.load(f)

THRESHOLDS = meta["thresholds"]
BROKER = "localhost"
PATIENT_ID = "patient_001"
latest = {"HR": None, "SpO2": None, "movement": None}
alerts = []
risk_history = deque(maxlen=60)

print("="*65)
print("  ML Models loaded")
print(f"  Accuracy: {meta['metrics']['accuracy']*100:.2f}%  AUC: {meta['metrics']['roc_auc']:.4f}")
print("="*65)

def run_inference():
    if any(v is None for v in latest.values()): return
    hr, spo2, mov = latest["HR"], latest["SpO2"], latest["movement"]
    feat = np.array([[mov, hr, spo2, hr/(spo2+1e-6), mov*hr, 100-spo2]])
    fs   = scaler.transform(feat)
    prob = (rf.predict_proba(fs)[0][1] + gb.predict_proba(fs)[0][1]) / 2
    pred = int(prob > 0.5)
    label = le.inverse_transform([pred])[0]
    ts = datetime.now().strftime("%H:%M:%S")
    risk_history.append(prob)
    trend = "↑" if len(risk_history)>1 and risk_history[-1]>risk_history[-2] else "↓"
    if prob >= THRESHOLDS["critical"]:
        risk = "🔴 CRITICAL"
        alerts.append({"patient":PATIENT_ID,"timestamp":ts,"hr":hr,"spo2":spo2,"prob":round(prob,3)})
        print(f"\n{'!'*60}")
        print(f"  ⚠️  CRITICAL ALERT — {ts}")
        print(f"  HR: {hr} bpm  SpO₂: {spo2}%  Move: {mov}")
        print(f"  Risk: {prob*100:.1f}%  |  Alerts this session: {len(alerts)}")
        print(f"{'!'*60}\n")
    elif prob >= THRESHOLDS["warning"]: risk = "🟡 WARNING "
    else: risk = "🟢 Normal  "
    print(f"[{ts}] {risk} | HR:{hr:5.1f} SpO₂:{spo2:5.1f}% Mov:{mov:6.3f} | {prob*100:5.1f}% {trend} | {label}")

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.value == 0:
        client.subscribe(f"hospital/{PATIENT_ID}/#")
        print(f"📡  Subscribed to hospital/{PATIENT_ID}/#\n")
        print(f"{'Time':^10} {'Status':^14} {'HR':^7} {'SpO₂':^7} {'Move':^7} {'Risk%':^7} {'Trend':^5} {'Label':^10}")
        print("─"*70)
    else: print(f"❌  MQTT failed (rc={reason_code})")

def on_message(client, userdata, msg):
    try:
        p = json.loads(msg.payload.decode())
        t = msg.topic
        if   "heartrate" in t: latest["HR"]       = p["value"]
        elif "spo2"      in t: latest["SpO2"]      = p["value"]
        elif "movement"  in t: latest["movement"]  = p["value"]
        elif "fall"      in t and p["value"] == 1:
            print(f"\n🚨  FALL DETECTED — {datetime.now().strftime('%H:%M:%S')}")
        run_inference()
    except: pass

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"monitor_{PATIENT_ID}")
client.on_connect = on_connect
client.on_message = on_message
try:
    client.connect(BROKER, 1883, 60)
    client.loop_forever()
except ConnectionRefusedError:
    print("❌  Run  mosquitto -v  in another terminal first.")
except KeyboardInterrupt:
    print(f"\n🛑  Stopped. Total alerts: {len(alerts)}")
