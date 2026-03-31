# Hospital Deployment Guide

## Prerequisites on Hospital Server
- Ubuntu 20.04+ or Windows Server 2019+
- Docker + Docker Compose installed
- Port 80, 1883, 8000 open on firewall

## Quick Deploy (5 minutes)

```bash
# 1. Copy entire digital_twin/ folder to server

# 2. Copy models/ from phase1_ml/ into phase3_backend/
cp -r phase1_ml/models phase3_backend/models

# 3. Start everything
cd phase6_deployment
docker compose up -d

# 4. Verify all containers are running
docker compose ps

# 5. Check logs
docker compose logs -f
```

## Access Points
| Service | URL |
|---------|-----|
| Dashboard | http://SERVER_IP:80 |
| API Docs | http://SERVER_IP:8000/docs |
| Live Vitals | http://SERVER_IP:8000/vitals/current |
| Alert Log | http://SERVER_IP:8000/alerts |
| MQTT Broker | SERVER_IP:1883 |

## Production Security Checklist
- [ ] Set MQTT password in mosquitto.conf (`allow_anonymous false`)
- [ ] Enable HTTPS (SSL certificate via Let's Encrypt)
- [ ] Restrict CORS in FastAPI main.py to hospital domain only
- [ ] Change default WiFi credentials in Arduino .ino file
- [ ] Set up log rotation for MQTT and application logs
- [ ] Configure hospital firewall to allow only known device IPs on port 1883

## Updating Models
```bash
# Retrain on phase1_ml/
cd phase1_ml && python train_model.py

# Copy new models to backend
cp -r models/ ../phase3_backend/models/

# Restart backend container
cd ../phase6_deployment
docker compose restart backend
```
