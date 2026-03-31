"""FastAPI Backend — Digital Twin Hospital Monitor
Run: uvicorn main:app --host 0.0.0.0 --port 8000
Docs: http://localhost:8000/docs
"""
import json, numpy as np, joblib, os, asyncio
from datetime import datetime
from collections import deque
import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super().default(obj)

MODELS_DIR = "models"
for f in ["rf_model.pkl","gb_model.pkl","scaler.pkl","label_encoder.pkl","metadata.json"]:
    if not os.path.exists(f"{MODELS_DIR}/{f}"):
        raise FileNotFoundError(f"Missing {MODELS_DIR}/{f} — copy from phase1_ml/")

rf=joblib.load(f"{MODELS_DIR}/rf_model.pkl"); gb=joblib.load(f"{MODELS_DIR}/gb_model.pkl")
scaler=joblib.load(f"{MODELS_DIR}/scaler.pkl"); le=joblib.load(f"{MODELS_DIR}/label_encoder.pkl")
with open(f"{MODELS_DIR}/metadata.json") as f: meta=json.load(f)

app = FastAPI(title="Digital Twin — Hospital Monitor", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

latest_vitals={}; alert_log=[]; vitals_history=deque(maxlen=500); ws_clients=[]

def predict(hr,spo2,movement):
    feat=np.array([[movement,hr,spo2,hr/(spo2+1e-6),movement*hr,100-spo2]])
    fs=scaler.transform(feat)
    prob=(rf.predict_proba(fs)[0][1]+gb.predict_proba(fs)[0][1])/2
    pred=int(prob>0.5); label=int(le.inverse_transform([pred])[0])
    t=meta["thresholds"]
    if prob>=t["critical"]: risk,emoji="CRITICAL","🔴"
    elif prob>=t["warning"]: risk,emoji="WARNING","🟡"
    else: risk,emoji="NORMAL","🟢"
    return {"label":label,"risk_level":risk,"risk_emoji":emoji,"probability":round(prob,4)}

def on_mqtt_message(client,userdata,msg):
    global latest_vitals
    try:
        p=json.loads(msg.payload.decode()); topic=msg.topic
        if "heartrate" in topic: latest_vitals["HR"]=p["value"]
        elif "spo2" in topic: latest_vitals["SpO2"]=p["value"]
        elif "movement" in topic: latest_vitals["movement"]=p["value"]
        elif "temperature" in topic: latest_vitals["temperature"]=p["value"]
        elif "fall" in topic: latest_vitals["fall"]=p["value"]
        elif "vitals" in topic: latest_vitals.update(p)
        if all(k in latest_vitals for k in ["HR","SpO2","movement"]):
            r=predict(latest_vitals["HR"],latest_vitals["SpO2"],latest_vitals["movement"])
            latest_vitals.update(r); latest_vitals["timestamp"]=datetime.now().isoformat()
            vitals_history.append(dict(latest_vitals))
            if r["risk_level"]=="CRITICAL":
                alert_log.append({"timestamp":latest_vitals["timestamp"],"hr":latest_vitals.get("HR"),"spo2":latest_vitals.get("SpO2"),"probability":r["probability"]})
    except Exception as e: print(f"MQTT err: {e}")

def start_mqtt():
    c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="backend_bridge"); c.on_message=on_mqtt_message
    try:
        c.connect("localhost",1883,60); c.subscribe("hospital/patient_001/#")
        c.loop_start(); print("✅  MQTT bridge running")
    except Exception as e: print(f"⚠️  MQTT unavailable ({e})")

start_mqtt()

@app.get("/") 
def root(): return {"service":"Digital Twin Hospital Monitor","version":"1.0.0","docs":"/docs"}

@app.get("/health") 
def health(): return {"status":"ok","timestamp":datetime.now().isoformat()}

@app.get("/vitals/current")
def get_vitals():
    if not latest_vitals: raise HTTPException(503,"No data — is simulator running?")
    return latest_vitals

@app.get("/vitals/history")
def get_history(limit:int=100): return {"count":len(list(vitals_history)[-limit:]),"data":list(vitals_history)[-limit:]}

@app.get("/alerts")
def get_alerts(limit:int=50): return {"total":len(alert_log),"alerts":alert_log[-limit:]}

@app.get("/model/info")
def model_info(): return {"accuracy":f"{meta['metrics']['accuracy']*100:.2f}%","auc":meta['metrics']['roc_auc'],"features":meta['features']}

class VitalsReq(BaseModel):
    hr:float; spo2:float; movement:float

@app.post("/predict")
def predict_ep(data:VitalsReq):
    r=predict(data.hr,data.spo2,data.movement)
    return {"input":{"hr":data.hr,"spo2":data.spo2,"movement":data.movement},"output":r,"timestamp":datetime.now().isoformat()}

@app.websocket("/ws")
async def ws_endpoint(websocket:WebSocket):
    await websocket.accept(); ws_clients.append(websocket)
    print(f"🔌 WS connected. Total: {len(ws_clients)}")
    try:
        while True:
            if latest_vitals: await websocket.send_text(json.dumps(latest_vitals, cls=NumpyEncoder))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        ws_clients.remove(websocket); print(f"🔌 WS gone. Remaining: {len(ws_clients)}")
