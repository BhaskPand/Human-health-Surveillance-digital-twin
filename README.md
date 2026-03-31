# Digital Twin — Hospital Patient Monitoring System
**ML-powered real-time patient health surveillance with 3D visualization**

---

## Project Architecture
```
Sensors (ESP32) → MQTT Broker → ML Monitor → FastAPI Backend → Dashboard / Unity
```

## Folder Structure
```
digital_twin/
├── README.md                          ← This file
│
├── phase1_ml/                         ← STEP 1: Train ML models
│   ├── train_model.py                 ← Run this FIRST
│   ├── Synthetic_Health_Data.csv      ← Place your dataset here
│   ├── requirements.txt
│   └── models/                        ← Auto-created after training
│       ├── rf_model.pkl
│       ├── gb_model.pkl
│       ├── scaler.pkl
│       ├── label_encoder.pkl
│       └── metadata.json
│
├── phase2_mqtt/                       ← STEP 2: Real-time data pipeline
│   ├── simulator.py                   ← Simulates patient vitals (use until hardware ready)
│   ├── monitor.py                     ← ML inference on live MQTT data
│   └── requirements.txt
│
├── phase3_backend/                    ← STEP 3: FastAPI REST + WebSocket server
│   ├── main.py                        ← API server (REST + WebSocket)
│   ├── Dockerfile
│   └── requirements.txt
│
├── phase4_dashboard/                  ← STEP 4: Open in browser immediately
│   └── dashboard.html                 ← Live charts, alerts, risk scores
│
├── phase4_unity/                      ← STEP 4 (alt): Unity 3D Digital Twin
│   └── Assets/Scripts/
│       ├── PatientDataManager.cs      ← WebSocket client
│       ├── VitalsUIController.cs      ← Updates all UI elements
│       └── HeartbeatAnimator.cs       ← Pulses at real heart rate
│
├── phase5_arduino/                    ← STEP 5: Real hardware
│   ├── patient_sensor.ino             ← Upload to ESP32
│   └── WIRING_GUIDE.md               ← Pin diagrams + parts list (~₹820 total)
│
└── phase6_deployment/                 ← STEP 6: Hospital deployment
    ├── docker-compose.yml             ← One-command deploy
    ├── HOSPITAL_DEPLOY.md            ← Full deployment guide
    ├── mosquitto/config/mosquitto.conf
    └── nginx/nginx.conf
```

---

## Execution Order (follow exactly)

### Step 1 — Train ML Model
```bash
cd phase1_ml
pip install -r requirements.txt
# Place Synthetic_Health_Data.csv in this folder
python train_model.py
# Expected: 95%+ accuracy
```

### Step 2 — Copy Models
```bash
# Copy models/ into both phase2 and phase3
cp -r phase1_ml/models phase2_mqtt/models
cp -r phase1_ml/models phase3_backend/models
```

### Step 3 — Start MQTT Pipeline
```bash
# Terminal 1: Start MQTT broker
mosquitto -v

# Terminal 2: Start patient simulator
cd phase2_mqtt
pip install -r requirements.txt
python simulator.py

# Terminal 3: Start real-time ML monitor
cd phase2_mqtt
python monitor.py
```

### Step 4 — Start API Backend
```bash
# Terminal 4:
cd phase3_backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# API Docs: http://localhost:8000/docs
# Live Vitals: http://localhost:8000/vitals/current
```

### Step 5 — Open Dashboard
```
Open phase4_dashboard/dashboard.html in any browser
→ See live vitals, charts, risk scores, and alerts
```

### Step 6 — Real Hardware (when ready)
```
Edit phase5_arduino/patient_sensor.ino:
  - Set WIFI_SSID, WIFI_PASSWORD, MQTT_SERVER
  - Set PATIENT_ID (unique per patient)
Upload to ESP32 via Arduino IDE
Remove simulator.py — real data now flows
```

### Step 7 — Hospital Deployment
```bash
cd phase6_deployment
docker compose up -d
# Access dashboard at http://SERVER_IP:80
```

---

## Tech Stack
| Component | Technology |
|-----------|-----------|
| ML Models | Random Forest + Gradient Boosting Ensemble |
| Data Transport | MQTT (Mosquitto broker) |
| Backend API | FastAPI + WebSocket |
| Dashboard | HTML5 + Chart.js |
| 3D Twin | Unity 3D (C#) |
| Hardware | ESP32 + MAX30102 + MPU6050 + DS18B20 |
| Deployment | Docker Compose + Nginx |

## Model Performance (expected on Synthetic_Health_Data.csv)
- Accuracy: ~98%
- ROC-AUC: ~0.99
- Features: HR, SpO₂, Movement + 3 derived clinical features
